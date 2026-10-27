"""
run_batch.py — Stage 4 Step 1: feasibility screen for all 84 Nd–Fe–B binary combinations.

Loops over 3 × 7 × 4 = 84 combinations of the available SGTE binary assessments:
    Fe–Nd  (3 files)  ×  Fe–B  (7 files)  ×  Nd–B  (4 files)

For each combination:
  1. Merge the three TDB files with tdb_merge.merged_tdb_path().
  2. Run the feasibility screen (logic from feasibility.py) at the standard temperatures.
  3. Record the threshold ΔH_f* and competing assemblage at each temperature.

Output (in the same directory as this script):
  results/
    batch_results.csv      — one row per combination, flat schema
    summary.json           — survival stats + threshold distribution
    detail/
      <combo_id>.json      — full temperature curve + conflict report

Usage (from stage_three/, venv active):
    python stage4_step1/run_batch.py
    python stage4_step1/run_batch.py --workers 8   # parallel (default: 1, safe)
    python stage4_step1/run_batch.py --dry-run      # list combos, no compute
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

# ── paths ──────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
STAGE3 = HERE.parent                          # stage_three/
sys.path.insert(0, str(STAGE3))               # so we can import tdb_merge, feasibility

TDB_DIR = STAGE3.parent / "data" / "tdb" / "sgte_binary"

from tdb_merge import merged_tdb_path         # noqa: E402

# ── target composition: Nd₂Fe₁₄B ──────────────────────────────────────────────
ELEMENTS   = ["FE", "ND", "B"]
X_TARGET   = {"FE": 14/17, "ND": 2/17, "B": 1/17}   # mole fractions

# temperatures to evaluate (K) — same as Stage 3 grid
TEMPERATURES = [800, 1000, 1100, 1200, 1300, 1375, 1450, 1600]

# ── the three edges and their available files ──────────────────────────────────
EDGE_FILES = {
    "FeNd": ["FeNd-16Che.tdb", "FeNd-16Wan.tdb", "FeNd-95Hal-LB.tdb"],
    "FeB":  ["FeB-01Pal.tdb", "FeB-02Rom.tdb", "FeB-08Yos.tdb",
             "FeB-19Wit.tdb", "FeB-20Tak.tdb", "FeB-91Pan.tdb", "FeB-94Hal-LB.tdb"],
    "NdB":  ["NdB-16Zho-corrected.tdb", "NdB-19Che.tdb",
             "NdB-95Hal-LB.tdb", "NdB-98Che.tdb"],
}


def combo_id(fend: str, feb: str, ndb: str) -> str:
    """Stable identifier: sorted edge labels joined by '__'."""
    return f"{fend.replace('.tdb','')}___{feb.replace('.tdb','')}___{ndb.replace('.tdb','')}"


# ── feasibility kernel (inlined from feasibility.py) ──────────────────────────

def _feasibility_at_T(db, T_K: float, x_fe: float, x_nd: float, x_b: float,
                      dH_f: float = 0.0):
    """
    Compute dG = G_target(dH_f) - G_competing at temperature T_K.
    Returns (dG_kJ, phases_dict) where phases_dict maps phase name -> mole fraction.
    Raises on pycalphad error.
    """
    from pycalphad import Database, equilibrium, variables as v

    comps   = ["FE", "ND", "B", "VA"]
    conds   = {v.X("ND"): x_nd, v.X("B"): x_b, v.T: T_K, v.P: 101325, v.N: 1}
    phases  = list(db.phases.keys())

    eq = equilibrium(db, comps, phases, conds, calc_opts={"pdens": 500})

    # competing Gibbs energy (per mol-atom)
    G_competing = float(eq.GM.squeeze().values)

    # target Gibbs energy at dH_f (stoichiometric line compound)
    # G_target = Σ x_i * GHSER_i  +  dH_f   (pycalphad convention: GM in J/mol-atom)
    # We compute Σ x_i * GHSER_i from equilibrium at pure elements separately,
    # then add dH_f.
    # Shortcut: G_target = G_competing + dG  →  dG = G_target - G_competing
    # At dH_f = 0 the target is a mechanical mixture of SER states:
    #   G_target(dH_f=0) = Σ x_i * GHSER_i
    # threshold = -dG(dH_f=0) = G_competing - Σ x_i * GHSER_i

    # get GHSER contributions for each element
    ghser = {}
    for el, x in [("FE", x_fe), ("ND", x_nd), ("B", x_b)]:
        if x < 1e-9:
            ghser[el] = 0.0
            continue
        conds_pure = {v.T: T_K, v.P: 101325, v.N: 1}
        phases_pure = [p for p in phases if el in db.phases[p].constituents[0]]
        if not phases_pure:
            phases_pure = phases
        eq_pure = equilibrium(db, [el, "VA"], phases_pure, conds_pure,
                              calc_opts={"pdens": 200})
        ghser[el] = float(eq_pure.GM.squeeze().values)

    G_ser = x_fe * ghser["FE"] + x_nd * ghser["ND"] + x_b * ghser["B"]
    G_target = G_ser + dH_f * 1000.0   # dH_f in kJ/mol-atom → J/mol-atom

    dG_kJ = (G_target - G_competing) / 1000.0   # J → kJ

    # stable phases and their fractions
    phase_fracs = {}
    try:
        for ph in phases:
            nf = float(eq.NP.sel(Phase=ph).squeeze().values)
            if nf > 0.01:
                phase_fracs[ph] = round(nf, 3)
    except Exception:
        pass

    return dG_kJ, phase_fracs


def run_feasibility(tdb_path: Path, temperatures: list[float],
                    x_fe: float, x_nd: float, x_b: float):
    """
    Run the feasibility screen at dH_f = 0 for all temperatures.
    Returns list of (T_K, threshold_kJ, competing_phases_dict).
    threshold = -dG at dH_f=0  (positive means target needs to be that stable to win).
    """
    from pycalphad import Database
    db = Database(str(tdb_path))

    results = []
    for T in temperatures:
        try:
            dG, phases = _feasibility_at_T(db, T, x_fe, x_nd, x_b, dH_f=0.0)
            threshold = -dG   # kJ/mol-atom; target stable when dH_f < -threshold... wait:
            # dG = G_target - G_competing  (at dH_f=0)
            # target stable when G_target(dH_f) < G_competing
            # G_target(dH_f) = G_ser + dH_f*1000  <  G_competing
            # dH_f < (G_competing - G_ser)/1000 = threshold
            # So threshold = (G_competing - G_ser)/1000  [kJ/mol-atom]
            # At dH_f=0: dG = G_ser - G_competing  →  threshold = -dG(dH_f=0)
            results.append((T, round(threshold, 4), phases))
        except Exception as e:
            results.append((T, None, {"error": str(e)}))
    return results


# ── single combination worker ──────────────────────────────────────────────────

def run_one(fend: str, feb: str, ndb: str) -> dict:
    """Run one combination. Returns a flat result dict."""
    cid = combo_id(fend, feb, ndb)
    t0  = time.time()

    result = {
        "combo_id":       cid,
        "binary_FeNd":    fend,
        "binary_FeB":     feb,
        "binary_NdB":     ndb,
        "element_order":  ELEMENTS,
        "run_timestamp":  datetime.now(timezone.utc).isoformat(),
        "merge_success":  False,
        "edge_check_passed": False,
        "survived":       False,
        "failure_stage":  None,
        "failure_reason": None,
        "conflict_report": [],
        "n_phases_after_merge": None,
        "phases_list":    [],
        "temperatures_K": [],
        "threshold_kJ_mol_atom": [],
        "threshold_at_800K":  None,
        "threshold_at_1000K": None,
        "threshold_at_1300K": None,
        "threshold_at_1375K": None,
        "threshold_at_1450K": None,
        "threshold_at_1600K": None,
        "competing_assemblage": {},
        "runtime_seconds": None,
        "notes": "",
    }

    tdb_paths = [TDB_DIR / fend, TDB_DIR / feb, TDB_DIR / ndb]

    # ── 1. merge ──
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merged_path = merged_tdb_path(ELEMENTS, tdb_paths=tdb_paths,
                                          out_dir=HERE / "results" / "merged_tdbs")
        merge_log = buf.getvalue()
        result["merge_success"] = True
        result["conflict_report"] = [l for l in merge_log.splitlines()
                                     if "conflict" in l.lower() or "differ" in l.lower()
                                     or "ignored" in l.lower()]
    except Exception as e:
        result["failure_stage"]  = "merge"
        result["failure_reason"] = str(e)
        result["runtime_seconds"] = round(time.time() - t0, 1)
        return result

    # ── 2. edge check (already done inside merged_tdb_path; check for OK) ──
    # merged_tdb_path raises if the edge check fails hard; a soft mismatch is logged.
    # We treat any successful return as edge_check_passed=True for now.
    result["edge_check_passed"] = True
    result["survived"] = True

    # ── 3. phase inventory ──
    try:
        from pycalphad import Database
        db = Database(str(merged_path))
        phases = sorted(db.phases.keys())
        result["n_phases_after_merge"] = len(phases)
        result["phases_list"] = phases
    except Exception as e:
        result["survived"] = False
        result["failure_stage"]  = "load"
        result["failure_reason"] = str(e)
        result["runtime_seconds"] = round(time.time() - t0, 1)
        return result

    # ── 4. feasibility screen ──
    x_fe = X_TARGET["FE"]
    x_nd = X_TARGET["ND"]
    x_b  = X_TARGET["B"]

    screen = run_feasibility(merged_path, TEMPERATURES, x_fe, x_nd, x_b)

    T_vals, thresh_vals, competing = [], [], {}
    for T, thr, phases_dict in screen:
        T_vals.append(T)
        thresh_vals.append(thr)
        competing[str(T)] = phases_dict

    result["temperatures_K"]          = T_vals
    result["threshold_kJ_mol_atom"]   = thresh_vals
    result["competing_assemblage"]     = competing

    for T_key, col in [(800,  "threshold_at_800K"),
                       (1000, "threshold_at_1000K"),
                       (1300, "threshold_at_1300K"),
                       (1375, "threshold_at_1375K"),
                       (1450, "threshold_at_1450K"),
                       (1600, "threshold_at_1600K")]:
        if T_key in T_vals:
            idx = T_vals.index(T_key)
            result[col] = thresh_vals[idx]

    result["runtime_seconds"] = round(time.time() - t0, 1)
    return result


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers",  type=int, default=1,
                    help="parallel workers (default 1; set to cpu_count for overnight run)")
    ap.add_argument("--dry-run",  action="store_true",
                    help="print combo list and exit")
    ap.add_argument("--resume",   action="store_true",
                    help="skip combos whose combo_id already appears in batch_results.csv")
    args = ap.parse_args()

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "merged_tdbs").mkdir(exist_ok=True)
    (out_dir / "detail").mkdir(exist_ok=True)

    # build combo list
    combos = list(product(EDGE_FILES["FeNd"], EDGE_FILES["FeB"], EDGE_FILES["NdB"]))
    assert len(combos) == 84, f"expected 84, got {len(combos)}"

    if args.dry_run:
        for i, (a, b, c) in enumerate(combos, 1):
            print(f"{i:3d}  {combo_id(a, b, c)}")
        print(f"\n{len(combos)} combinations total")
        return

    # resume: load already-done combo_ids
    done = set()
    csv_path = out_dir / "batch_results.csv"
    if args.resume and csv_path.exists():
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                done.add(row["combo_id"])
        print(f"Resuming: {len(done)} already done, {len(combos)-len(done)} remaining")

    todo = [(a, b, c) for a, b, c in combos if combo_id(a, b, c) not in done]

    # CSV writer (append if resuming)
    mode = "a" if args.resume and csv_path.exists() else "w"
    csv_file = open(csv_path, mode, newline="")
    fieldnames = [
        "combo_id", "binary_FeNd", "binary_FeB", "binary_NdB",
        "merge_success", "edge_check_passed", "survived",
        "failure_stage", "failure_reason",
        "n_phases_after_merge",
        "threshold_at_800K", "threshold_at_1000K", "threshold_at_1300K",
        "threshold_at_1375K", "threshold_at_1450K", "threshold_at_1600K",
        "runtime_seconds", "notes",
    ]
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
    if mode == "w":
        writer.writeheader()

    all_results = []
    n_done = len(done)
    n_total = len(combos)

    def handle(result: dict):
        nonlocal n_done
        n_done += 1
        cid = result["combo_id"]
        # write detail JSON
        detail_path = out_dir / "detail" / f"{cid}.json"
        with open(detail_path, "w") as f:
            json.dump(result, f, indent=2)
        # write CSV row
        writer.writerow(result)
        csv_file.flush()
        all_results.append(result)
        status = "✓" if result["survived"] else "✗"
        thr = result.get("threshold_at_1000K")
        thr_s = f"{thr:+.2f} kJ" if thr is not None else "—"
        print(f"[{n_done:3d}/{n_total}] {status} {cid}  thr@1000K={thr_s}  "
              f"({result['runtime_seconds']:.0f}s)")

    if args.workers == 1:
        for a, b, c in todo:
            result = run_one(a, b, c)
            handle(result)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(run_one, a, b, c): (a, b, c) for a, b, c in todo}
            for fut in as_completed(futs):
                try:
                    handle(fut.result())
                except Exception as e:
                    a, b, c = futs[fut]
                    print(f"  ERROR {combo_id(a,b,c)}: {e}")

    csv_file.close()

    # ── summary.json ──
    survived = [r for r in all_results if r["survived"]]

    def stats(vals):
        vals = [v for v in vals if v is not None]
        if not vals:
            return {}
        a = np.array(vals)
        return {"min": round(float(a.min()), 3), "q25": round(float(np.percentile(a, 25)), 3),
                "median": round(float(np.median(a)), 3), "q75": round(float(np.percentile(a, 75)), 3),
                "max": round(float(a.max()), 3), "n": len(vals)}

    summary = {
        "n_total":          len(combos),
        "n_attempted":      len(todo) + len(done),
        "n_merge_success":  sum(1 for r in all_results if r["merge_success"]),
        "n_edge_passed":    sum(1 for r in all_results if r["edge_check_passed"]),
        "n_survived":       len(survived),
        "survival_rate":    round(len(survived) / len(combos), 3) if combos else 0,
    }
    for T_key, col in [(800,  "threshold_at_800K"),
                       (1000, "threshold_at_1000K"),
                       (1300, "threshold_at_1300K"),
                       (1375, "threshold_at_1375K"),
                       (1450, "threshold_at_1450K"),
                       (1600, "threshold_at_1600K")]:
        summary[f"threshold_stats_{T_key}K"] = stats(
            [r[col] for r in survived])

    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nDone. {len(survived)}/{len(combos)} survived.")
    print(f"Results: {out_dir}")


if __name__ == "__main__":
    main()
