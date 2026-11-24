#!/usr/bin/env python3
"""
stage_five/screen_ternary.py

Unified Stage 5 Screening Orchestrator:
  1. Parses any ternary formula (e.g. 'Nd2Fe14B', 'Al16Fe5Mn5', 'Ni2MnSn')
  2. Runs the system-agnostic CALPHAD binary-ensemble threshold engine
  3. Runs Materials Project + pymatgen Bartel SISSO finite-T Gibbs predictor
  4. Aligns both onto kJ/mol-atom, prints the stability-margin table, and
     optionally persists results to PostgreSQL (`alloy_lab`).
"""
from __future__ import annotations

import argparse
import logging
import json
import os
import sys
from pathlib import Path

from pymatgen.core import Composition

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "stage_five"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dft_sisso_predictor import (
    add_prototype_arguments,
    compare_with_calphad_ensemble,
    format_comparison_table,
    predict_sisso_formation_gibbs,
    prototype_filter_from_args,
)
from prototype_match import SISSO_UNAVAILABLE, PrototypeFilter, provenance_label
from stability_window import format_windows, windows_from_rows

log = logging.getLogger(__name__)
from general_ensemble import DEFAULT_TEMPS, rethreshold_at_composition, run_binary_ensemble


def _connect_db():
    """Connect to alloy_lab PostgreSQL using repo db_config.py or environment variables."""
    import psycopg2

    try:
        import db_config
        if hasattr(db_config, "get_db_params"):
            return psycopg2.connect(**db_config.get_db_params())
        if hasattr(db_config, "DB_CONFIG"):
            cfg = {k: v for k, v in db_config.DB_CONFIG.items() if k != "schema"}
            return psycopg2.connect(**cfg)
    except ImportError:
        pass

    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "192.168.178.10"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "alloy_lab"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


def _has_column(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'alloy_lab' "
        "AND table_name = %s AND column_name = %s;",
        (table, column),
    )
    return cur.fetchone() is not None


def _has_prototype_columns(cur) -> bool:
    """True when migration 010 (match_type etc.) has been applied to alloy_lab.calphad_dft_comparison."""
    return _has_column(cur, "calphad_dft_comparison", "match_type")


def _has_run_filter_column(cur) -> bool:
    """True when migration 010 added calphad_ensemble_runs.prototype_filter (part of the cache key)."""
    return _has_column(cur, "calphad_ensemble_runs", "prototype_filter")


def parse_ternary_formula(formula: str) -> tuple[list[str], list[float], Composition]:
    comp = Composition(formula)
    frac_dict = comp.fractional_composition.get_el_amt_dict()
    if len(frac_dict) != 3:
        raise ValueError(f"Expected a ternary composition (3 elements), got {len(frac_dict)}: {list(frac_dict.keys())}")
    # Merge-priority order: the element with the largest amount first (ties alphabetical). The
    # engine merges the edges (e1-e2), (e1-e3), (e2-e3) and the first file wins on conflicting
    # parameters. For Nd2Fe14B this gives FE, ND, B, the order of the Stage 4 reference run
    # (78 of 84 survivors); alphabetical order (B, FE, ND) gives 52 of 84 on the same data.
    items = sorted(((str(el).upper(), float(amt)) for el, amt in frac_dict.items()), key=lambda kv: (-kv[1], kv[0]))
    elements = [k for k, _ in items]
    fractions = [v for _, v in items]
    return elements, fractions, comp


_JSONB_COLUMNS = {"target_composition", "gate_summary", "audit_summary", "prototype_filter",
                  "eta2_by_edge", "threshold_composition"}
# columns added by migration 010 / 011: written only when the table has them
_PROTOTYPE_COLUMNS = {"match_type", "prototype_formula", "delta_x", "comparable"}          # 010 (needed for prototype rows)


def _table_columns(cur, table: str) -> set[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'alloy_lab' AND table_name = %s;",
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def _insert(cur, table: str, row: dict, available: set[str], returning: str | None = None):
    """INSERT the entries of `row` whose column exists in the table (older schemas simply lack the newer ones)."""
    cols = [c for c in row if c in available]
    marks = ["%s::jsonb" if c in _JSONB_COLUMNS else "%s" for c in cols]
    vals = [json.dumps(row[c]) if (c in _JSONB_COLUMNS and row[c] is not None) else row[c] for c in cols]
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(marks)})" + (f" RETURNING {returning}" if returning else "") + ";"
    cur.execute(sql, vals)
    return cur.fetchone()[0] if returning else None


def save_screening_to_db(
    formula: str,
    ensemble_report: dict,
    sisso_report: dict,
    comparison_rows: list[dict],
    sample_code: str | None = None,
    prototype_filter: dict | None = None,
) -> int:
    """Insert ensemble run + temperature-by-candidate comparison rows into PostgreSQL.

    Columns that a migration has not added yet are skipped (the secondary fields of 011, the prototype
    provenance of 010); nearest-prototype rows are refused without migration 010."""
    conn = _connect_db()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SET search_path TO alloy_lab;")
            sample_id = None
            if sample_code:
                cur.execute("SELECT id FROM samples WHERE sample_id = %s;", (sample_code,))
                row = cur.fetchone()
                if row is not None:
                    sample_id = row[0]

            g = ensemble_report["gates"]
            excluded = [x for x in ensemble_report.get("audit_log", []) if x["status"] == "excluded"]
            run_cols = _table_columns(cur, "calphad_ensemble_runs")
            run_id = _insert(cur, "calphad_ensemble_runs", {
                "sample_id": sample_id, "formula": formula, "system_name": ensemble_report["system"],
                "target_composition": ensemble_report["target_composition"],
                "n_total_combos": g["G1_survival"]["total"], "n_survivors": g["G1_survival"]["survived"],
                "gate_passed": g["gate_passed"], "gate_summary": g, "audit_summary": excluded,
                "spec_sha256": ensemble_report["spec_sha256"],
                "pycalphad_version": ensemble_report.get("pycalphad_version"),
                # the prototype options decide which SISSO rows are stored, so they are part of the cache key
                "prototype_filter": prototype_filter,
            }, run_cols, returning="id")

            cmp_cols = _table_columns(cur, "calphad_dft_comparison")
            if not _PROTOTYPE_COLUMNS <= cmp_cols and any(
                    r.get("match_type", "exact_match") != "exact_match" for r in comparison_rows):
                raise RuntimeError(
                    "Nearest-prototype rows need migration 010_prototype_provenance.sql "
                    "(columns match_type, prototype_formula, delta_x, comparable); apply it first."
                )
            ehull_by_mp = {c["material_id"]: c.get("e_above_hull_0K_eV_atom") for c in sisso_report.get("candidates", [])}
            dist = ensemble_report.get("threshold_distribution", {})

            for r in comparison_rows:
                t_stats = dist.get(str(r["T_K"])) or {}
                _insert(cur, "calphad_dft_comparison", {
                    "run_id": run_id, "temperature_k": r["T_K"],
                    "threshold_median_kj": r["threshold_median_kJ"], "threshold_q25_kj": t_stats.get("q25_kJ"),
                    "threshold_q75_kj": t_stats.get("q75_kJ"), "threshold_p05_kj": r["threshold_p05_kJ"],
                    "threshold_p95_kj": r["threshold_p95_kJ"], "eta2_by_edge": t_stats.get("eta2_by_edge"),
                    "competing_assemblage": r["competing_assemblage"],
                    "mp_id": r["material_id"], "candidate_formula": r["formula"],
                    "e_above_hull_0k_ev": ehull_by_mp.get(r["material_id"]),
                    "dgf_sisso_kj": r["dGf_sisso_kJ"], "stability_margin_kj": r["stability_margin_kJ"],
                    "verdict": r["verdict"],
                    "match_type": r.get("match_type", "exact_match"),
                    "prototype_formula": r.get("prototype_formula", r["formula"]),
                    "delta_x": r.get("delta_x"), "comparable": r.get("comparable", True),
                    # secondary, approximate fields (migration 011)
                    "ref_correction_kj": r.get("ref_correction_kJ"), "dgf_sisso_ser_kj": r.get("dGf_sisso_ser_kJ"),
                    "margin_ser_kj": r.get("margin_ser_kJ"),
                    "threshold_composition": r.get("threshold_composition"),
                    "verdict_at_prototype": r.get("verdict_at_prototype"), "notes": r.get("notes"),
                }, cmp_cols)
            if not comparison_rows and g["gate_passed"]:
                kind = SISSO_UNAVAILABLE if sisso_report.get("match_type") == SISSO_UNAVAILABLE else "no_dft_entry"
                for t_str, t_stats in dist.items():
                    if not t_stats:
                        continue
                    _insert(cur, "calphad_dft_comparison", {
                        "run_id": run_id, "temperature_k": float(t_str),
                        "threshold_median_kj": t_stats["median_kJ"], "threshold_q25_kj": t_stats["q25_kJ"],
                        "threshold_q75_kj": t_stats["q75_kJ"], "threshold_p05_kj": t_stats["p05_kJ"],
                        "threshold_p95_kj": t_stats["p95_kJ"], "eta2_by_edge": t_stats["eta2_by_edge"],
                        "competing_assemblage": t_stats["dominant_competing_assemblage"],
                        "mp_id": "NO_MP_ENTRY", "verdict": kind, "match_type": kind, "comparable": False,
                    }, cmp_cols)
        return run_id
    finally:
        conn.close()


def screen_ternary(
    formula: str,
    temperatures: list[float] | None = None,
    tdb_dir: Path | None = None,
    suppress_phases: list[str] | None = None,
    workers: int = 4,
    include_subsystems: bool = False,
    progress_callback=None,
    prototype_filter: PrototypeFilter | None = PrototypeFilter(),
    matched_threshold: bool = True,
) -> dict:
    """prototype_filter=None disables the nearest-prototype fallback (exact matches only).
    matched_threshold: for every nearest prototype the threshold band is also evaluated at the prototype's own
    composition (surviving combinations only, no new edge check); a failure there never loses the result."""
    elements, fractions, comp = parse_ternary_formula(formula)
    temps = [float(t) for t in (temperatures or DEFAULT_TEMPS)]

    ensemble_report = run_binary_ensemble(
        elements=elements,
        fractions=fractions,
        temperatures=temps,
        tdb_dir=tdb_dir,
        suppress_phases=suppress_phases,
        workers=workers,
        progress_callback=progress_callback,
    )

    try:
        sisso_report = predict_sisso_formation_gibbs(
            formula=formula,           # as given: a reduced formula would mangle decimal compositions
            temperatures=temps,
            include_subsystems=include_subsystems,
            nearest_prototype=prototype_filter is not None,
            prototype_filter=prototype_filter,
        )
    except Exception as exc:   # missing key / package / network: keep the CALPHAD result, never lose it
        sisso_report = {
            "formula": formula, "candidates": [], "match_type": SISSO_UNAVAILABLE,
            "error": f"{type(exc).__name__}: {exc}",
        }

    matched = {}
    if matched_threshold and ensemble_report["gates"]["gate_passed"]:
        for cand in sisso_report.get("candidates", []):
            if cand.get("match_type") != "nearest_prototype" or not cand.get("composition_fractions"):
                continue
            try:
                matched[cand["material_id"]] = rethreshold_at_composition(
                    ensemble_report, {str(k).upper(): v for k, v in cand["composition_fractions"].items()},
                    tdb_dir=tdb_dir, suppress_phases=suppress_phases, workers=workers)
            except Exception as exc:    # keep the target-composition result
                log.warning("composition-matched threshold failed for %s: %s", cand["material_id"], exc)

    comparison_rows = compare_with_calphad_ensemble(sisso_report, ensemble_report, matched=matched)

    return {
        "input_formula": formula,
        "reduced_formula": comp.reduced_formula,
        "ensemble": ensemble_report,
        "sisso": sisso_report,
        "comparison": comparison_rows,
        "windows": windows_from_rows(comparison_rows),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formula", required=True, help="Ternary formula, e.g. Nd2Fe14B or Al16Fe5Mn5")
    ap.add_argument("--temps", nargs="+", type=float, default=DEFAULT_TEMPS)
    ap.add_argument("--suppress", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tdb-dir", type=Path, default=None)
    ap.add_argument("--include-subsystems", action="store_true",
                    help="also list other ternary phases of the system (not compared)")
    add_prototype_arguments(ap)
    ap.add_argument("--no-matched-threshold", action="store_true",
                    help="skip the threshold re-evaluation at the composition of nearest prototypes")
    ap.add_argument("--save-db", action="store_true", help="Persist results to alloy_lab PostgreSQL")
    ap.add_argument("--sample-code", default=None, help="Optional sample_id string in alloy_lab.samples")
    ap.add_argument("--out", type=Path, default=None, help="Optional combined JSON output path")
    args = ap.parse_args()

    flt = prototype_filter_from_args(args)
    bundle = screen_ternary(
        formula=args.formula,
        temperatures=args.temps,
        tdb_dir=args.tdb_dir,
        suppress_phases=args.suppress,
        workers=args.workers,
        include_subsystems=args.include_subsystems,
        prototype_filter=flt,
        matched_threshold=not args.no_matched_threshold,
    )

    ens = bundle["ensemble"]
    g = ens["gates"]
    print(f"\n==================== STAGE 5 SCREENING: {bundle['reduced_formula']} ({ens['system']}) ====================")
    print(f"CALPHAD Gate: {'PASS' if g['gate_passed'] else 'FAIL'} "
          f"(Survivors: {g['G1_survival']['survived']}/{g['G1_survival']['total']}, "
          f"Lineages: {g['G2_lineage_coverage']['surviving_lineages_per_edge']})")

    if not g["gate_passed"]:
        print("Ensemble failed its gates (ensemble_unreliable): the margin is not interpreted.")
    if bundle["comparison"]:
        print()
        print("\n".join(format_comparison_table(bundle["comparison"])))
        if bundle.get("windows"):
            print()
            print("\n".join(format_windows(bundle["windows"])))
    else:
        if bundle["sisso"].get("match_type") == SISSO_UNAVAILABLE:
            print(f"\n[{SISSO_UNAVAILABLE}] Materials Project / SISSO step failed: {bundle['sisso'].get('error')}")
            print("Competing binary threshold band (CALPHAD part is complete):")
        else:
            print("\n[no_dft_entry] No Materials Project entry at the target composition or within the prototype filter. Competing binary threshold band:")
        print(f"{'T (K)':>7} | {'Median':>8} | {'[5%, 95%] Band':>17} | Competing Assemblage")
        print("-" * 70)
        for t_str, s in ens["threshold_distribution"].items():
            if s:
                print(f"{float(t_str):>7.0f} | {s['median_kJ']:>+8.3f} | [{s['p05_kJ']:>+6.2f}, {s['p95_kJ']:>+6.2f}] | {s['dominant_competing_assemblage']}")
    if args.save_db:
        run_id = save_screening_to_db(
            formula=args.formula,
            ensemble_report=ens,
            sisso_report=bundle["sisso"],
            comparison_rows=bundle["comparison"],
            sample_code=args.sample_code,
            prototype_filter=flt.as_dict() if flt else None,
        )
        print(f"\nSaved to PostgreSQL (alloy_lab.calphad_ensemble_runs.id = {run_id})")
    if args.out:
        args.out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print(f"Saved combined JSON -> {args.out}")
if __name__ == "__main__":
    main()