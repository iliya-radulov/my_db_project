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
import json
import os
import sys
from pathlib import Path

from pymatgen.core import Composition

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "stage_five"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dft_sisso_predictor import compare_with_calphad_ensemble, predict_sisso_formation_gibbs
from general_ensemble import DEFAULT_TEMPS, run_binary_ensemble


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


def parse_ternary_formula(formula: str) -> tuple[list[str], list[float], Composition]:
    comp = Composition(formula)
    frac_dict = comp.fractional_composition.get_el_amt_dict()
    if len(frac_dict) != 3:
        raise ValueError(f"Expected a ternary composition (3 elements), got {len(frac_dict)}: {list(frac_dict.keys())}")
    items = sorted((str(el).upper(), float(amt)) for el, amt in frac_dict.items())
    elements = [k for k, _ in items]
    fractions = [v for _, v in items]
    return elements, fractions, comp


def save_screening_to_db(
    formula: str,
    ensemble_report: dict,
    sisso_report: dict,
    comparison_rows: list[dict],
    sample_code: str | None = None,
) -> int:
    """Insert ensemble run + temperature-by-candidate comparison rows into PostgreSQL."""
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

            cur.execute(
                """
                INSERT INTO calphad_ensemble_runs (
                    sample_id, formula, system_name, target_composition,
                    n_total_combos, n_survivors, gate_passed, gate_summary,
                    audit_summary, spec_sha256, pycalphad_version
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING id;
                """,
                (
                    sample_id,
                    formula,
                    ensemble_report["system"],
                    json.dumps(ensemble_report["target_composition"]),
                    g["G1_survival"]["total"],
                    g["G1_survival"]["survived"],
                    g["gate_passed"],
                    json.dumps(g),
                    json.dumps(excluded),
                    ensemble_report["spec_sha256"],
                    ensemble_report.get("pycalphad_version"),
                ),
            )
            run_id = cur.fetchone()[0]

            ehull_by_mp = {
                c["material_id"]: c.get("e_above_hull_0K_eV_atom")
                for c in sisso_report.get("candidates", [])
            }

            if comparison_rows:
                for r in comparison_rows:
                    t_stats = ensemble_report["threshold_distribution"][str(r["T_K"])]
                    cur.execute(
                        """
                        INSERT INTO calphad_dft_comparison (
                            run_id, temperature_k,
                            threshold_median_kj, threshold_q25_kj, threshold_q75_kj,
                            threshold_p05_kj, threshold_p95_kj, eta2_by_edge, competing_assemblage,
                            mp_id, candidate_formula, e_above_hull_0k_ev,
                            dgf_sisso_kj, stability_margin_kj, verdict
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            run_id,
                            r["T_K"],
                            r["threshold_median_kJ"],
                            t_stats["q25_kJ"],
                            t_stats["q75_kJ"],
                            r["threshold_p05_kJ"],
                            r["threshold_p95_kJ"],
                            json.dumps(t_stats["eta2_by_edge"]),
                            r["competing_assemblage"],
                            r["material_id"],
                            r["formula"],
                            ehull_by_mp.get(r["material_id"]),
                            r["dGf_sisso_kJ"],
                            r["stability_margin_kJ"],
                            r["verdict"],
                        ),
                    )
            elif g["gate_passed"]:
                for t_str, t_stats in ensemble_report["threshold_distribution"].items():
                    if not t_stats:
                        continue
                    cur.execute(
                        """
                        INSERT INTO calphad_dft_comparison (
                            run_id, temperature_k,
                            threshold_median_kj, threshold_q25_kj, threshold_q75_kj,
                            threshold_p05_kj, threshold_p95_kj, eta2_by_edge, competing_assemblage,
                            mp_id, verdict
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'NO_MP_ENTRY', 'no_dft_entry');
                        """,
                        (
                            run_id,
                            float(t_str),
                            t_stats["median_kJ"],
                            t_stats["q25_kJ"],
                            t_stats["q75_kJ"],
                            t_stats["p05_kJ"],
                            t_stats["p95_kJ"],
                            json.dumps(t_stats["eta2_by_edge"]),
                            t_stats["dominant_competing_assemblage"],
                        ),
                    )
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
) -> dict:
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

    sisso_report = predict_sisso_formation_gibbs(
        formula=comp.reduced_formula,
        temperatures=temps,
        include_subsystems=include_subsystems,
    )

    comparison_rows = compare_with_calphad_ensemble(sisso_report, ensemble_report)

    return {
        "input_formula": formula,
        "reduced_formula": comp.reduced_formula,
        "ensemble": ensemble_report,
        "sisso": sisso_report,
        "comparison": comparison_rows,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formula", required=True, help="Ternary formula, e.g. Nd2Fe14B or Al16Fe5Mn5")
    ap.add_argument("--temps", nargs="+", type=float, default=DEFAULT_TEMPS)
    ap.add_argument("--suppress", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tdb-dir", type=Path, default=None)
    ap.add_argument("--include-subsystems", action="store_true")
    ap.add_argument("--save-db", action="store_true", help="Persist results to alloy_lab PostgreSQL")
    ap.add_argument("--sample-code", default=None, help="Optional sample_id string in alloy_lab.samples")
    ap.add_argument("--out", type=Path, default=None, help="Optional combined JSON output path")
    args = ap.parse_args()

    bundle = screen_ternary(
        formula=args.formula,
        temperatures=args.temps,
        tdb_dir=args.tdb_dir,
        suppress_phases=args.suppress,
        workers=args.workers,
        include_subsystems=args.include_subsystems,
    )

    ens = bundle["ensemble"]
    g = ens["gates"]
    print(f"\n==================== STAGE 5 SCREENING: {bundle['reduced_formula']} ({ens['system']}) ====================")
    print(f"CALPHAD Gate: {'PASS' if g['gate_passed'] else 'FAIL'} "
          f"(Survivors: {g['G1_survival']['survived']}/{g['G1_survival']['total']}, "
          f"Lineages: {g['G2_lineage_coverage']['surviving_lineages_per_edge']})")

    if not g["gate_passed"]:
        print("Stop rule triggered: competing binary ensemble failed pre-registered gates.")
    elif bundle["comparison"]:
        print(f"\n{'MP ID':<15} | {'T (K)':>6} | {'ΔG_SISSO':>9} | {'ΔG* Med':>8} | {'[5%, 95%] Band':>17} | {'Margin':>8} | Verdict")
        print("-" * 102)
        for r in bundle["comparison"]:
            print(
                f"{r['material_id']:<15} | {r['T_K']:>6.0f} | {r['dGf_sisso_kJ']:>+9.3f} | "
                f"{r['threshold_median_kJ']:>+8.3f} | [{r['threshold_p05_kJ']:>+6.2f}, {r['threshold_p95_kJ']:>+6.2f}] | "
                f"{r['stability_margin_kJ']:>+8.3f} | {r['verdict']}"
            )
    else:
        print("\nNo exact MP polymorph found (novel stoichiometry). Competing binary threshold band:")
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
        )
        print(f"\nSaved to PostgreSQL (alloy_lab.calphad_ensemble_runs.id = {run_id})")
    if args.out:
        args.out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print(f"Saved combined JSON -> {args.out}")
if __name__ == "__main__":
    main()