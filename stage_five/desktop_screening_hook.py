#!/usr/bin/env python3
"""
stage_five/desktop_screening_hook.py

Cached database lookup + non-blocking UI helper for integrating Stage 5
CALPHAD Binary-Ensemble + Bartel SISSO screening into alloy_desktop_v2.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "stage_five"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from general_ensemble import DEFAULT_TEMPS
from screen_ternary import _connect_db, parse_ternary_formula, save_screening_to_db, screen_ternary


def compute_spec_sha256(formula: str, temperatures: list[float] | None = None, suppress: list[str] | None = None) -> str:
    elements, fractions, _ = parse_ternary_formula(formula)
    x_map = dict(zip(elements, fractions))
    temps = [float(t) for t in (temperatures or DEFAULT_TEMPS)]
    payload = json.dumps(
        {"elements": elements, "x_map": x_map, "temps": temps, "suppress": list(suppress or [])},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def fetch_cached_screening(formula: str, temperatures: list[float] | None = None) -> dict | None:
    """
    Check alloy_lab.calphad_ensemble_runs for an existing run matching `formula`
    (by spec_sha256). Returns formatted dict if cached, else None.
    """
    sha = compute_spec_sha256(formula, temperatures)
    conn = _connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO alloy_lab;")
            cur.execute(
                """
                SELECT id, formula, system_name, n_total_combos, n_survivors,
                       gate_passed, gate_summary, created_at
                FROM calphad_ensemble_runs
                WHERE spec_sha256 = %s
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (sha,),
            )
            run = cur.fetchone()
            if not run:
                return None

            run_id, db_formula, sys_name, n_tot, n_surv, gate_passed, gate_summary, created_at = run
            cur.execute(
                """
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
                rows.append({
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
                })

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
        "",
    ]
    if not result["gate_passed"]:
        lines.append("STOP RULE TRIGGERED: Competing binary ensemble failed pre-registered gates (G1/G2).")
        return "\n".join(lines)

    rows = result.get("rows", [])
    if not rows:
        lines.append("No comparison rows recorded.")
        return "\n".join(lines)

    if rows[0]["material_id"] == "NO_MP_ENTRY":
        lines.append("Novel stoichiometry (no exact MP entry). Competing binary threshold band:")
        lines.append(f"{'T (K)':>7} | {'Median':>8} | {'[5%, 95%] Band':>17} | Competing Assemblage")
        lines.append("-" * 68)
        for r in rows:
            lines.append(
                f"{r['T_K']:>7.0f} | {r['threshold_median_kJ']:>+8.3f} | "
                f"[{r['threshold_p05_kJ']:>+6.2f}, {r['threshold_p95_kJ']:>+6.2f}] | {r['competing_assemblage']}"
            )
    else:
        lines.append(f"{'MP ID':<15} | {'T (K)':>6} | {'ΔG_SISSO':>9} | {'ΔG* Med':>8} | {'[5%, 95%] Band':>17} | {'Margin':>8} | Verdict")
        lines.append("-" * 98)
        for r in rows:
            lines.append(
                f"{r['material_id']:<15} | {r['T_K']:>6.0f} | {r['dGf_sisso_kJ']:>+9.3f} | "
                f"{r['threshold_median_kJ']:>+8.3f} | [{r['threshold_p05_kJ']:>+6.2f}, {r['threshold_p95_kJ']:>+6.2f}] | "
                f"{r['stability_margin_kJ']:>+8.3f} | {r['verdict']}"
            )
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
) -> None:
    """
    Background worker for alloy_desktop_v2.py:
      1. Returns cached PostgreSQL result immediately if available (unless force_recompute=True).
      2. Otherwise runs screen_ternary() + save_screening_to_db() in a daemon thread.
    """
    def _worker():
        try:
            if not force_recompute:
                cached = fetch_cached_screening(formula)
                if cached is not None:
                    on_complete(format_screening_summary(cached))
                    return

            tdb_path = tdb_dir or Path(os.environ.get("SGTE_BINARY_DIR", REPO_ROOT / "data" / "tdb" / "sgte_binary"))
            n_workers = workers or min(20, max(4, (os.cpu_count() or 4) - 4))
            bundle = screen_ternary(formula=formula, tdb_dir=tdb_path, workers=n_workers, progress_callback=on_progress)
            ens = bundle["ensemble"]
            g = ens["gates"]
            run_id = save_screening_to_db(
                formula=formula,
                ensemble_report=ens,
                sisso_report=bundle["sisso"],
                comparison_rows=bundle["comparison"],
                sample_code=sample_code,
            )
            fresh = {
                "cached": False,
                "run_id": run_id,
                "formula": bundle["reduced_formula"],
                "system": ens["system"],
                "n_total": g["G1_survival"]["total"],
                "n_survivors": g["G1_survival"]["survived"],
                "gate_passed": g["gate_passed"],
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
            on_complete(format_screening_summary(fresh))
        except Exception as exc:
            if on_error:
                on_error(f"Stage 5 screening error: {type(exc).__name__}: {exc}")

    threading.Thread(target=_worker, daemon=True).start()
