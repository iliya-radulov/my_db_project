#!/usr/bin/env python3
"""
nimnsn_thresholds.py (18 Nov 2026) - threshold stage of Ni-Mn-Sn Pilot-v1.

    dG_f*(T) = ( G_competing(T) - sum_i x_i * GHSER_i(T) ) / 1000     [kJ per mol of atoms]

for every surviving combination of the edge check (rule v2 = column `pass` of
edge_check.csv), every distinct composition of the 25 pure-ternary S6 rows, and the
temperatures 1000 K (primary) and 800, 1200 K (sensitivity). G_competing is the
equilibrium Gibbs energy of the merged binary description with all phases; nothing is
suspended (the merged binaries contain no ternary Heusler phase).

Solver rule: the same fallback as edge-check rule v2 (leave out one phase at a time and
take the lowest converged energy if the equilibrium with all phases does not converge);
a point that still fails is written with status=failed and an empty value, never skipped.

Guards: (1) the output must hold exactly n_combinations x n_compositions x n_temperatures
rows, otherwise the exit code is non-zero (partial output = failed run); (2) any failed
point is counted in run_info.json and printed; (3) no hard-coded paths.

Systems: nimnsn (compositions from --rows) and alfemn (validation: the Al-Fe-Mn point
16/26, 5/26, 5/26 of threshold_alfemn.py; must give the same numbers).

Usage:
  python nimnsn_thresholds.py --system nimnsn --run-dir edge_check_nimnsn --rows nimnsn_rows.csv --workers 6
  python nimnsn_thresholds.py --system alfemn --run-dir val_alfemn --limit 3   (validation)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import warnings
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import pycalphad
from pycalphad import Database, equilibrium, variables as v

SYSTEMS = {
    "nimnsn": {"prefix": "NIMNSN", "elements": ["NI", "MN", "SN"],
               "ghser": {"NI": "GHSERNI", "MN": "GHSERMN", "SN": "GHSERSN"}},
    "alfemn": {"prefix": "ALFEMN", "elements": ["AL", "FE", "MN"],
               "ghser": {"AL": "GHSERAL", "FE": "GHSERFE", "MN": "GHSERMN"}},
}
TEMPS_DEFAULT = (1000.0, 800.0, 1200.0)       # 1000 K primary


# ------------------------------------------------------------ symbol evaluation
def _resolve(expr, symbols, depth=0):
    if depth > 60:
        raise RecursionError("function nesting too deep")
    subs = {s: symbols[str(s)] for s in expr.free_symbols if str(s) in symbols}
    if not subs:
        return expr
    return _resolve(expr.subs(subs), symbols, depth + 1)


def eval_symbol(db, name, T):
    expr = _resolve(db.symbols[name], dict(db.symbols))
    val = expr.subs({s: T for s in expr.free_symbols if str(s) == "T"})
    return float(val)


def ghser_ref(db, cfg, x, T):
    missing = [f for f in cfg["ghser"].values() if f not in db.symbols]
    if missing:
        raise KeyError(f"missing GHSER function(s) in database: {missing}")
    return sum(x[el] * eval_symbol(db, cfg["ghser"][el], T) for el in cfg["elements"])


# ------------------------------------------------------------ equilibrium + fallback
def _phase_set(r):
    return tuple(sorted({str(n) for n, f in zip(r.Phase.values.reshape(-1),
                                                 r.NP.values.reshape(-1))
                         if n and np.isfinite(f) and f > 1e-4}))


def _eq(db, comps, phases, cond):
    try:
        r = equilibrium(db, comps, phases, cond)
        g = float(r.GM.values.squeeze())
        if np.isfinite(g):
            return _phase_set(r), g
    except Exception:
        pass
    return None


def solve(db, comps, cond):
    phases = sorted(db.phases)
    res = _eq(db, comps, phases, cond)
    if res is not None:
        return res[0], res[1], "direct"
    best = None
    for p in phases:
        r = _eq(db, comps, [q for q in phases if q != p], cond)
        if r is not None and (best is None or r[1] < best[1]):
            best = r
    if best is None:
        return None, None, "failed"
    return best[0], best[1], "fallback"


# ------------------------------------------------------------ one combination
_CFG = {}
_COMPS = []
_TEMPS = ()


def _init(cfg, comps, temps):
    global _CFG, _COMPS, _TEMPS
    _CFG, _COMPS, _TEMPS = cfg, comps, temps


def one_combo(args):
    combo, tdb_path = args
    t0 = time.time()
    rows = []
    try:
        db = Database(str(tdb_path))
        els = _CFG["elements"]
        for comp_id, x in _COMPS:
            for T in _TEMPS:
                ps, g, st = solve(db, els + ["VA"],
                                  {v.X(e): x[e] for e in els[1:]} | {v.T: T, v.P: 101325, v.N: 1})
                gref = ghser_ref(db, _CFG, x, T)
                dg = None if g is None else (g - gref) / 1000.0
                rows.append({"combo": combo, "comp_id": comp_id, "T": T, "status": st,
                             "phases": "+".join(ps) if ps else "",
                             "G_competing_J": None if g is None else round(g, 3),
                             "G_ref_J": round(gref, 3),
                             "dG_kJ_per_mol_atom": None if dg is None else round(dg, 5)})
    except Exception as e:                      # a whole combination failing is recorded, not dropped
        for comp_id, x in _COMPS:
            for T in _TEMPS:
                rows.append({"combo": combo, "comp_id": comp_id, "T": T,
                             "status": f"failed:{type(e).__name__}", "phases": "",
                             "G_competing_J": None, "G_ref_J": None,
                             "dG_kJ_per_mol_atom": None})
    for r in rows:
        r["seconds"] = round(time.time() - t0, 1)
    return rows


# ------------------------------------------------------------ main
def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_comps(system, rows_csv):
    if system == "alfemn":
        return [("alfemn_target", {"AL": 16 / 26, "FE": 5 / 26, "MN": 5 / 26})]
    seen, out = {}, []
    with open(rows_csv, newline="") as f:
        for r in csv.DictReader(f):
            key = (round(float(r["Ni_at"]), 3), round(float(r["Mn_at"]), 3), round(float(r["Sn_at"]), 3))
            if key not in seen:
                seen[key] = f"Ni{key[0]:g}_Mn{key[1]:g}_Sn{key[2]:g}"
                out.append((seen[key], {"NI": key[0] / 100, "MN": key[1] / 100, "SN": key[2] / 100}))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--run-dir", required=True, help="edge-check output folder (edge_check.csv, merged/)")
    ap.add_argument("--rows", default=None, help="nimnsn_rows.csv (system nimnsn)")
    ap.add_argument("--out", default=None, help="default: <run-dir>/thresholds")
    ap.add_argument("--temps", type=float, nargs="+", default=list(TEMPS_DEFAULT))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    cfg = SYSTEMS[a.system]
    run = Path(a.run_dir)
    out = Path(a.out or run / "thresholds")
    out.mkdir(parents=True, exist_ok=True)
    if a.system == "nimnsn" and not a.rows:
        sys.exit("--rows nimnsn_rows.csv is required for system nimnsn")

    with open(run / "edge_check.csv", newline="") as f:
        surv = [r["combo"] for r in csv.DictReader(f) if r["pass"] == "True"]
    surv = sorted(surv)
    if a.limit:
        surv = surv[: a.limit]
    comps = load_comps(a.system, a.rows)
    combos = []
    for c in surv:
        p = run / "merged" / f"{cfg['prefix']}__{c}.tdb"
        if not p.exists():
            sys.exit(f"merged file missing for surviving combination: {p}")
        combos.append((c, p))
    temps = tuple(a.temps)
    n_expected = len(combos) * len(comps) * len(temps)

    info = {"command": " ".join([Path(sys.executable).name] + sys.argv),
            "started": datetime.now().isoformat(timespec="seconds"),
            "pycalphad": pycalphad.__version__, "numpy": np.__version__,
            "system": a.system, "primary_T_K": temps[0], "temps_K": temps,
            "n_surviving_combinations": len(combos), "n_compositions": len(comps),
            "n_expected_rows": n_expected,
            "edge_check_csv_sha256": sha256(run / "edge_check.csv"),
            "rows_csv_sha256": sha256(a.rows) if a.rows else None,
            "compositions": {cid: x for cid, x in comps}}
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"Surviving combinations: {len(combos)}   compositions: {len(comps)}   "
          f"temps: {temps}   expected rows: {n_expected}", flush=True)

    csv_path = out / "thresholds.csv"
    done = set()
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            done = {r["combo"] for r in csv.DictReader(f)}
    todo = [c for c in combos if c[0] not in done]
    print(f"Already done: {len(done)}   to run: {len(todo)}", flush=True)
    fields = ["combo", "comp_id", "T", "status", "phases", "G_competing_J", "G_ref_J",
              "dG_kJ_per_mol_atom", "seconds"]
    t0 = time.time()
    n_failed = 0
    if todo:
        with Pool(a.workers, initializer=_init, initargs=(cfg, comps, temps)) as pool:
            for k, rows in enumerate(pool.imap_unordered(one_combo, todo), 1):
                new = not csv_path.exists() or csv_path.stat().st_size == 0
                with open(csv_path, "a", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=fields)
                    if new:
                        w.writeheader()
                    w.writerows(rows)
                nf = sum(r["status"].startswith("failed") for r in rows)
                n_failed += nf
                print(f"[{k}/{len(todo)}] {rows[0]['combo']}  failed points {nf}  "
                      f"{rows[0]['seconds']} s", flush=True)
    # completeness guard
    with open(csv_path, newline="") as f:
        allrows = list(csv.DictReader(f))
    n_rows = len(allrows)
    n_fail_all = sum(r["status"].startswith("failed") for r in allrows)
    n_fb = sum(r["status"] == "fallback" for r in allrows)
    info.update({"finished": datetime.now().isoformat(timespec="seconds"),
                 "n_rows": n_rows, "n_failed_points": n_fail_all, "n_fallback_points": n_fb})
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"\nRows {n_rows} of {n_expected}; failed points {n_fail_all}; fallback points {n_fb}; "
          f"{time.time() - t0:.0f} s. Results: {csv_path}")
    if n_rows != n_expected:
        sys.exit(f"INCOMPLETE: {n_rows} rows, expected {n_expected} (a partial output is a failed run)")
    if n_fail_all:
        print("WARNING: failed points present; see status column (handled by the gate script rule)")


if __name__ == "__main__":
    main()
