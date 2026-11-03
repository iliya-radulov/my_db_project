"""
run_batch_v2.py — Stage 4 Step 1: feasibility screen for all 84 Nd–Fe–B binary combinations.

Version 2 of run_batch.py. The only change is the pure-element reference inside the
feasibility kernel:

  v1 (run_batch.py):   runs equilibrium() on each pure element and takes GM as the
                       "GHSER" value. At 800 K this returns the equilibrium pure-element
                       phase's Gibbs energy including magnetic contributions (BCC_A2
                       ferromagnetic for Fe, DHCP_A3 for Nd, …). This is NOT GHSER<EL>,
                       and the threshold is off by the magnetic / phase contribution
                       (0.7–1 kJ/mol-atom at 800–1000 K for Fe-rich compositions).

  v2 (this file):      evaluates the SER function symbolically from the merged database,
                       the way feasibility.py's check_reference does:
                           G_SER = Σ xi · db.symbols[ser[el]].subs({v.T: T_K})
                       where ser[el] is the actual SER symbol name in the database
                       (GHSERFE / GHSERND / GHSERBB — boron is GHSERBB, not GHSERB;
                       undefined functions silently return 0, Stage 3 lesson §7.1).

  Threshold definition is unchanged:
      threshold [kJ/mol-atom] = (G_competing − G_SER) / 1000
      target stable when ΔH_f < threshold (threshold is typically negative).

  Everything else — merge, edge check, survival logic, failure classification,
  CSV / JSON schema, CLI flags — is byte-for-byte compatible with v1 so the two runs
  can be diffed row by row.

Sanity check target (manual, before trusting the full run):
    FeNd-16Che___FeB-20Tak___NdB-19Che must reproduce Stage 3 feasibility.py:
        threshold ≈ −9.2 kJ/mol-atom at 800 K
        least-negative near 1370 K
        ≈ −10.8 kJ/mol-atom at 1800 K   (not tested here; grid stops at 1600 K)

Usage (from stage_three/, venv active):
    python stage4_step1/run_batch_v2.py --dry-run
    python stage4_step1/run_batch_v2.py --workers 1
    python stage4_step1/run_batch_v2.py --workers 8   # overnight / fast on 24-core
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
    """Stable identifier: edge labels joined by '___' (three underscores, as in v1)."""
    return f"{fend.replace('.tdb','')}___{feb.replace('.tdb','')}___{ndb.replace('.tdb','')}"


# ── SER lookup (same logic as feasibility.py) ─────────────────────────────────

def ser_function(db, el: str) -> str:
    """Name of the SER Gibbs-energy function of `el` in `db`.
    Tries GHSER<EL> then GHSER<EL><EL>; raises KeyError if neither exists.
    Boron in SGTE is GHSERBB, not GHSERB. An UNDEFINED function is silently
    treated as zero by pycalphad, which is the Stage 3 §7.1 bug this fixes."""
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return name
    raise KeyError(f"no SER function for {el} (tried GHSER{el}, GHSER{el}{el})")


def g_ser_at(db, ser_names: dict, T_K: float, xs: dict) -> float:
    """Σ xi · GHSER_i(T), J/mol-atom. Evaluated as symbolic substitution, no
    equilibrium call → no magnetic / phase-selection contamination."""
    from pycalphad import variables as v
    total = 0.0
    for el, xi in xs.items():
        if xi < 1e-12:
            continue
        g_i = float(db.symbols[ser_names[el]].subs({v.T: float(T_K)}))
        total += xi * g_i
    return total


# ── feasibility kernel (v2: GHSER-based reference) ────────────────────────────

def _feasibility_at_T(db, ser_names: dict, T_K: float,
                      x_fe: float, x_nd: float, x_b: float):
    """
    At ΔH_f = 0 the target phase is a mechanical mixture of SER states, so
        G_target(ΔH_f=0) = Σ x_i · GHSER_i(T)
    The threshold is the ΔH_f at which G_target meets G_competing:
        G_target(ΔH_f) = G_SER + ΔH_f · 1000   [J/mol-atom]
        G_target  <  G_competing   →   target wins
        ⇒ threshold [kJ/mol-atom] = (G_competing − G_SER) / 1000

    Returns (threshold_kJ_mol_atom, competing_phase_fractions_dict).
    """
    from pycalphad import equilibrium, variables as v

    comps  = ["FE", "ND", "B", "VA"]
    conds  = {v.X("ND"): x_nd, v.X("B"): x_b, v.T: T_K, v.P: 101325, v.N: 1}
    phases = list(db.phases.keys())

    eq = equilibrium(db, comps, phases, conds, calc_opts={"pdens": 500})
    G_competing = float(eq.GM.squeeze().values)                         # J/mol-atom

    G_SER = g_ser_at(db, ser_names, T_K,
                     {"FE": x_fe, "ND": x_nd, "B": x_b})                # J/mol-atom

    threshold_kJ = (G_competing - G_SER) / 1000.0                       # kJ/mol-atom

    # stable phases and their fractions
    phase_fracs = {}
    try:
        for ph in phases:
            nf = float(eq.NP.sel(Phase=ph).squeeze().values)
            if nf > 0.01:
                phase_fracs[ph] = round(nf, 3)
    except Exception:
        pass

    return threshold_kJ, phase_fracs


def run_feasibility(tdb_path: Path, temperatures: list[float],
                    x_fe: float, x_nd: float, x_b: float):
    """Run the feasibility screen at ΔH_f = 0 for all temperatures.
    Returns list of (T_K, threshold_kJ, competing_phases_dict | {"error": str})."""
    from pycalphad import Database
    db = Database(str(tdb_path))

    # look up the SER function name for each element in THIS merged database
    ser_names = {}
    try:
        for el in ("FE", "ND", "B"):
            ser_names[el] = ser_function(db, el)
    except KeyError as e:
        return [(T, None, {"error": f"SER lookup failed: {e}"}) for T in temperatures]

    results = []
    for T in temperatures:
        try:
            thr, phases = _feasibility_at_T(db, ser_names, T, x_fe, x_nd, x_b)
            results.append((T, round(thr, 4), phases))
        except Exception as e:
            results.append((T, None, {"error": str(e)}))
    return results, ser_names


# ── single combination worker ──────────────────────────────────────────────────

def run_one(fend: str, feb: str, ndb: str) -> dict:
    """Run one combination. Returns a flat result dict (same schema as v1)."""
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
        "ser_names":      {},
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
        "notes": "kernel=v2 (GHSER-based reference)",
    }

    tdb_paths = [TDB_DIR / fend, TDB_DIR / feb, TDB_DIR / ndb]

    # ── 1. merge ──
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            merged_path = merged_tdb_path(ELEMENTS, tdb_paths=tdb_paths,
                                          out_dir=HERE / "results_v2" / "merged_tdbs",
                                          tag=cid)
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

    # ── 2. edge check (merged_tdb_path raises on hard failure) ──
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

    try:
        screen_out = run_feasibility(merged_path, TEMPERATURES, x_fe, x_nd, x_b)
    except Exception as e:
        result["survived"] = False
        result["failure_stage"] = "feasibility"
        result["failure_reason"] = str(e)
        result["runtime_seconds"] = round(time.time() - t0, 1)
        return result

    # run_feasibility returns either (results, ser_names) or results-only on early fail
    if isinstance(screen_out, tuple):
        screen, ser_names = screen_out
        result["ser_names"] = ser_names
    else:
        screen = screen_out

    T_vals, thresh_vals, competing = [], [], {}
    for T, thr, phases_dict in screen:
        T_vals.append(T)
        thresh_vals.append(thr)
        competing[str(T)] = phases_dict

    result["temperatures_K"]          = T_vals
    result["threshold_kJ_mol_atom"]   = thresh_vals
    result["competing_assemblage"]    = competing

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
    ap.add_argument("--only",     type=str, default=None,
                    help="run only this combo_id (sanity check against Stage 3; "
                         "e.g. FeNd-16Che___FeB-20Tak___NdB-19Che)")
    args = ap.parse_args()

    out_dir = HERE / "results_v2"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "merged_tdbs").mkdir(exist_ok=True)
    (out_dir / "detail").mkdir(exist_ok=True)

    # build combo list
    combos = list(product(EDGE_FILES["FeNd"], EDGE_FILES["FeB"], EDGE_FILES["NdB"]))
    assert len(combos) == 84, f"expected 84, got {len(combos)}"

    if args.only:
        combos = [c for c in combos if combo_id(*c) == args.only]
        if not combos:
            print(f"combo_id not found: {args.only}")
            print("Available example: FeNd-16Che___FeB-20Tak___NdB-19Che")
            return
        print(f"Running only: {args.only}")

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
        thr800  = result.get("threshold_at_800K")
        thr1000 = result.get("threshold_at_1000K")
        s800  = f"{thr800:+.2f}"  if thr800  is not None else "  —  "
        s1000 = f"{thr1000:+.2f}" if thr1000 is not None else "  —  "
        print(f"[{n_done:3d}/{n_total}] {status} {cid}  "
              f"thr@800K={s800} thr@1000K={s1000} kJ  "
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
        "kernel_version":   "v2 (GHSER-based reference)",
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
