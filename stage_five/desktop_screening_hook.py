#!/usr/bin/env python3
"""
stage_five/desktop_screening_hook.py

Cached database lookup + non-blocking UI helper for integrating Stage 5
CALPHAD Binary-Ensemble + Bartel SISSO screening into alloy_desktop_v2.py.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "stage_five"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from general_ensemble import (
    DEFAULT_MIN_LINEAGES_PER_EDGE,
    DEFAULT_MIN_SURVIVAL_FRAC,
    compute_spec_sha256 as _engine_spec_sha256,
)
from dft_sisso_predictor import format_comparison_table
from prototype_match import PrototypeFilter
from screen_ternary import (
    _connect_db,
    _has_prototype_columns,
    _has_run_filter_column,
    parse_ternary_formula,
    save_screening_to_db,
    screen_ternary,
)

log = logging.getLogger(__name__)

_DEFAULT_FILTER = object()     # "use the default PrototypeFilter" (None means: fallback off)


def parse_site_groups(text: str | None) -> tuple[tuple[str, ...], ...]:
    """'FE,SI' -> (('FE','SI'),); several groups separated by ';' or a new line: 'FE,SI; AL,GA'.

    A site group is a set of elements that substitute on one crystallographic site (e.g. Fe and Si
    in the La(Fe,Si)13 phase); the nearest-prototype distance then compares the group totals.
    Opt-in only: leave the field empty for the plain composition distance.
    """
    groups = []
    for chunk in re.split(r"[;\n]+", text or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        els = [e.strip().upper() for e in re.split(r"[,\s]+", chunk) if e.strip()]
        bad = [e for e in els if not re.fullmatch(r"[A-Z][A-Z]?", e)]
        if bad or len(els) < 2 or len(set(els)) != len(els):
            raise ValueError(
                f"Invalid site group {chunk!r}: use two or more different element symbols, e.g. FE,SI"
            )
        groups.append(tuple(els))
    flat = [e for g in groups for e in g]
    if len(flat) != len(set(flat)):
        raise ValueError("An element may belong to one site group only")
    return tuple(groups)


def prototype_options(fallback: bool = True, site_groups_text: str | None = "") -> PrototypeFilter | None:
    """Options of the GUI -> filter. fallback=False: exact Materials Project matches only (None)."""
    if not fallback:
        return None
    return PrototypeFilter(site_groups=parse_site_groups(site_groups_text))


def describe_prototype_filter(flt: dict | PrototypeFilter | None) -> str:
    if flt is None:
        return "off (exact Materials Project matches only)"
    d = flt.as_dict() if isinstance(flt, PrototypeFilter) else flt
    groups = "; ".join("+".join(g) for g in d.get("site_groups") or []) or "none"
    anchors = ",".join(d.get("anchors") or []) or "minority element"
    return (f"on (max Δx {d['max_dx']}, anchor {anchors} within {d['anchor_tol']}, "
            f"site groups: {groups}, up to {d['max_prototypes']} prototypes)")


def compute_spec_sha256(
    formula: str,
    temperatures: list[float] | None = None,
    suppress: list[str] | None = None,
    min_survival_frac: float = DEFAULT_MIN_SURVIVAL_FRAC,
    min_lineages_per_edge: int = DEFAULT_MIN_LINEAGES_PER_EDGE,
) -> str:
    """Cache key. Uses the engine's own function (same normalisation, rounding, rules version and
    gate parameters), so the key cannot drift from the hash the engine stores with a run. The TDB
    collection is not part of the key: after the binary files change, force a recompute."""
    elements, fractions, _ = parse_ternary_formula(formula)
    return _engine_spec_sha256(elements, fractions, temperatures, suppress, min_survival_frac, min_lineages_per_edge)


def fetch_cached_screening(
    formula: str,
    temperatures: list[float] | None = None,
    suppress: list[str] | None = None,
    prototype_filter=_DEFAULT_FILTER,
) -> dict | None:
    """
    Check alloy_lab.calphad_ensemble_runs for an existing run matching `formula`
    (by spec_sha256) AND the same prototype options (the options decide which SISSO rows were
    stored). Returns formatted dict if cached, else None.

    Before migration 010 the table has no prototype_filter column: only runs made without the
    fallback could exist, so the cache is served only when the fallback is off; otherwise the
    screening is recomputed.
    """
    flt = PrototypeFilter() if prototype_filter is _DEFAULT_FILTER else prototype_filter
    flt_json = json.dumps(flt.as_dict()) if flt is not None else None
    sha = compute_spec_sha256(formula, temperatures, suppress)
    conn = _connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO alloy_lab;")
            has_filter_col = _has_run_filter_column(cur)
            if not has_filter_col and flt is not None:
                return None
            where = "spec_sha256 = %s"
            params = [sha]
            if has_filter_col:
                where += " AND prototype_filter IS NOT DISTINCT FROM %s::jsonb"
                params.append(flt_json)
            cur.execute(
                f"""
                SELECT id, formula, system_name, n_total_combos, n_survivors,
                       gate_passed, gate_summary, created_at
                FROM calphad_ensemble_runs
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                tuple(params),
            )
            run = cur.fetchone()
            if not run:
                return None

            run_id, db_formula, sys_name, n_tot, n_surv, gate_passed, gate_summary, created_at = run
            has_proto = _has_prototype_columns(cur)
            extra = ", match_type, prototype_formula, delta_x, comparable" if has_proto else ""
            cur.execute(
                f"""
                SELECT temperature_k, threshold_median_kj, threshold_p05_kj, threshold_p95_kj,
                       competing_assemblage, mp_id, candidate_formula, dgf_sisso_kj,
                       stability_margin_kj, verdict{extra}
                FROM calphad_dft_comparison
                WHERE run_id = %s
                ORDER BY comparable DESC NULLS LAST, delta_x NULLS FIRST, mp_id, temperature_k;
                """ if has_proto else """
                SELECT temperature_k, threshold_median_kj, threshold_p05_kj, threshold_p95_kj,
                       competing_assemblage, mp_id, candidate_formula, dgf_sisso_kj,
                       stability_margin_kj, verdict
                FROM calphad_dft_comparison
                WHERE run_id = %s
                ORDER BY mp_id, temperature_k;
                """,
                (run_id,),
            )
            rows = []
            for r in cur.fetchall():
                row = {
                    "T_K": r[0],
                    "threshold_median_kJ": r[1],
                    "threshold_p05_kJ": r[2],
                    "threshold_p95_kJ": r[3],
                    "competing_assemblage": r[4],
                    "material_id": r[5],
                    "formula": r[6],
                    "dGf_sisso_kJ": r[7],
                    "stability_margin_kJ": r[8],
                    "verdict": r[9],
                }
                if has_proto:
                    row.update({"match_type": r[10], "prototype_formula": r[11], "delta_x": r[12],
                                "comparable": r[13]})
                rows.append(row)

            return {
                "cached": True,
                "run_id": run_id,
                "formula": db_formula,
                "system": sys_name,
                "n_total": n_tot,
                "n_survivors": n_surv,
                "gate_passed": gate_passed,
                "gate_summary": gate_summary,
                "created_at": str(created_at),
                "prototype_filter": json.loads(flt_json) if flt_json else None,
                "prototype_filter_known": has_filter_col,
                "rows": rows,
            }
    finally:
        conn.close()


def format_screening_summary(result: dict) -> str:
    """Format cached or fresh Stage 5 result into clean monospace text for Tkinter ScrolledText."""
    tag = f"[CACHED DB run_id={result['run_id']}]" if result.get("cached") else f"[NEW RUN saved run_id={result.get('run_id')}]"
    lines = [
        f"=== Stage 5 CALPHAD Ensemble + Bartel SISSO Screening {tag} ===",
        f"Formula: {result['formula']}   System: {result['system']}",
        f"Gate: {'PASS' if result['gate_passed'] else 'FAIL'}  "
        f"(Survivors: {result['n_survivors']}/{result['n_total']})",
    ]
    if result.get("prototype_filter_known", True):
        lines.append(f"Nearest-prototype fallback: {describe_prototype_filter(result.get('prototype_filter'))}")
    lines.append("")
    if not result["gate_passed"]:
        lines.append("STOP RULE TRIGGERED: Competing binary ensemble failed pre-registered gates (G1/G2).")
        return "\n".join(lines)

    rows = result.get("rows", [])
    if not rows:
        lines.append("No comparison rows recorded.")
        return "\n".join(lines)

    if rows[0]["material_id"] == "NO_MP_ENTRY":
        lines.append("[no_dft_entry] No MP entry at the target composition or within the prototype filter. Competing binary threshold band:")
        lines.append(f"{'T (K)':>7} | {'Median':>8} | {'[5%, 95%] Band':>17} | Competing Assemblage")
        lines.append("-" * 68)
        for r in rows:
            lines.append(
                f"{r['T_K']:>7.0f} | {r['threshold_median_kJ']:>+8.3f} | "
                f"[{r['threshold_p05_kJ']:>+6.2f}, {r['threshold_p95_kJ']:>+6.2f}] | {r['competing_assemblage']}"
            )
    else:
        lines.extend(format_comparison_table(rows))
    return "\n".join(lines)


def run_screening_async(
    formula: str,
    on_complete: Callable[[str], None],
    on_error: Callable[[str], None] | None = None,
    sample_code: str | None = None,
    tdb_dir: Path | None = None,
    workers: int | None = None,
    force_recompute: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
    schedule: Callable[[Callable[[], None]], None] | None = None,
    prototype_filter=_DEFAULT_FILTER,
) -> None:
    """
    Background worker for alloy_desktop_v2.py:
      1. Returns cached PostgreSQL result immediately if available (unless force_recompute=True).
      2. Otherwise runs screen_ternary() + save_screening_to_db() in a daemon thread.

    The callbacks are called from the worker thread. Tkinter widgets must only be touched from the
    main thread, so pass `schedule=lambda fn: root.after(0, fn)` and every callback is delivered
    through it. With schedule=None the callbacks run directly in the worker thread (only safe for
    thread-agnostic callbacks, e.g. a queue.put).

    `prototype_filter`: PrototypeFilter (default: the standard filter), or None to use exact
    Materials Project matches only. Build it from the GUI fields with prototype_options().
    """
    flt = PrototypeFilter() if prototype_filter is _DEFAULT_FILTER else prototype_filter
    def _post(fn, *args) -> None:
        if fn is None:
            return
        if schedule is None:
            fn(*args)
        else:
            schedule(lambda: fn(*args))

    def _worker():
        try:
            if not force_recompute:
                cached = fetch_cached_screening(formula, prototype_filter=flt)
                if cached is not None:
                    _post(on_complete, format_screening_summary(cached))
                    return

            tdb_path = tdb_dir or Path(os.environ.get("SGTE_BINARY_DIR", REPO_ROOT / "data" / "tdb" / "sgte_binary"))
            n_workers = workers or min(20, max(4, (os.cpu_count() or 4) - 4))
            progress = (lambda done, total: _post(on_progress, done, total)) if on_progress else None
            bundle = screen_ternary(formula=formula, tdb_dir=tdb_path, workers=n_workers, progress_callback=progress,
                                    prototype_filter=flt)
            ens = bundle["ensemble"]
            g = ens["gates"]
            run_id = save_screening_to_db(
                formula=formula,
                ensemble_report=ens,
                sisso_report=bundle["sisso"],
                comparison_rows=bundle["comparison"],
                sample_code=sample_code,
                prototype_filter=flt.as_dict() if flt else None,
            )
            fresh = {
                "cached": False,
                "run_id": run_id,
                "formula": bundle["reduced_formula"],
                "system": ens["system"],
                "n_total": g["G1_survival"]["total"],
                "n_survivors": g["G1_survival"]["survived"],
                "gate_passed": g["gate_passed"],
                "prototype_filter": flt.as_dict() if flt else None,
                "rows": bundle["comparison"] or [
                    {
                        "T_K": float(t_str),
                        "threshold_median_kJ": s["median_kJ"],
                        "threshold_p05_kJ": s["p05_kJ"],
                        "threshold_p95_kJ": s["p95_kJ"],
                        "competing_assemblage": s["dominant_competing_assemblage"],
                        "material_id": "NO_MP_ENTRY",
                    }
                    for t_str, s in ens["threshold_distribution"].items()
                    if s
                ],
            }
            _post(on_complete, format_screening_summary(fresh))
        except Exception as exc:
            log.exception("Stage 5 screening failed for %s", formula)   # never swallow silently
            _post(on_error, f"Stage 5 screening error: {type(exc).__name__}: {exc}")

    threading.Thread(target=_worker, daemon=True).start()
