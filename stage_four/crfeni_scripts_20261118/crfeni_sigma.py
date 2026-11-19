#!/usr/bin/env python3
"""
crfeni_sigma.py (18 Nov 2026) - observable stage of Cr-Fe-Ni Pilot-M.

    S(T) = ( G_eq(sigma suspended) - G_eq(sigma allowed) ) / 1000       [kJ per mol of atoms]

for every surviving combination of the edge check (rule v2 = column `pass` of edge_check.csv),
at x* = (Cr 0.45, Fe 0.45, Ni 0.10) and T = 900 K (primary), 800 and 1000 K (labelled sensitivity).
G_eq = equilibrium GM (pycalphad), P = 101325 Pa, N = 1. Phase set = all phases of the merged
database, minus SIGMA_OLD and HIGH_SIGMA in BOTH calculations (legacy phases of CrFe-87And-LB);
"sigma suspended" = additionally minus SIGMA_D8B. No Cr-Ni or Fe-Ni file carries sigma, so sigma
always comes from the Cr-Fe file.

Numerical rules (pre-registration section 2):
  * direct equilibrium with the phase set; if it does not converge: fallback = leave out one phase
    at a time and take the lowest converged energy (sigma itself is never left out in the
    "allowed" calculation);
  * S_raw in [-0.05, 0) kJ/mol-atom (solver noise floor) -> S = 0, status "clipped";
  * S_raw < -0.05 -> both energies are recomputed with the leave-one-out minimum; if still below
    -0.05, or if any energy is non-finite, status "failed" (value empty, row kept, never dropped).

Guards: output must hold exactly n_survivors x n_temperatures rows, otherwise exit code 3 (a
partial output is a failed run); the number of failed points is printed and written to run_info.json.

Systems:
  crfeni      the pre-registered Pilot-M observable (288 combinations from crfeni_edge_check.py).
  alfemn_test TEST ONLY, no Cr-Fe-Ni file: the Al-Fe-Mn merged databases of the validation run, with
              AL8MN5_D810 in the role of sigma at the Pilot-v1 composition; used to test the code.

Usage:
  python crfeni_sigma.py --system crfeni --run-dir edge_check_crfeni --workers 6
  python crfeni_sigma.py --system alfemn_test --run-dir val_alfemn --limit 4        (test)
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

NOISE_FLOOR = 0.05      # kJ/mol-atom

SYSTEMS = {
    "crfeni": {"prefix": "CRFENI", "groups": ["CrFe", "CrNi", "FeNi"],
               "comps": ["CR", "FE", "NI", "VA"], "x": {"CR": 0.45, "NI": 0.10},
               "sigma": "SIGMA_D8B", "exclude": ("SIGMA_OLD", "HIGH_SIGMA"),
               "temps": (900.0, 800.0, 1000.0)},                       # 900 K primary
    "alfemn_test": {"prefix": "ALFEMN", "groups": ["AlFe", "AlMn", "FeMn"],
                    "comps": ["AL", "FE", "MN", "VA"], "x": {"AL": 16 / 26, "MN": 5 / 26},
                    "sigma": "AL8MN5_D810", "exclude": (),
                    "temps": (800.0, 1000.0, 1200.0)},
}


def _phase_set(r):
    return tuple(sorted({str(n) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1))
                         if n and np.isfinite(f) and f > 1e-4}))


def _eq(db, comps, phases, cond):
    try:
        r = equilibrium(db, comps, phases, cond)
        g = float(r.GM.values.squeeze())
        if np.isfinite(g):
            return g, _phase_set(r)
    except Exception:
        pass
    return None


def best(db, comps, phases, cond, protect=(), force_fallback=False):
    """(G, phase_set, status): direct, else (or when forced) lowest leave-one-out energy."""
    d = None if force_fallback else _eq(db, comps, phases, cond)
    if d is not None:
        return d[0], d[1], "direct"
    bestr = None
    for p in phases:
        if p in protect:
            continue
        r = _eq(db, comps, [q for q in phases if q != p], cond)
        if r is not None and (bestr is None or r[0] < bestr[0]):
            bestr = r
    if force_fallback:                     # forced pass may only lower the energy
        d0 = _eq(db, comps, phases, cond)
        if d0 is not None and (bestr is None or d0[0] <= bestr[0]):
            return d0[0], d0[1], "direct"
    if bestr is None:
        return None, None, "failed"
    return bestr[0], bestr[1], "fallback"


def observable(db, cfg, T):
    """One point: returns dict with G_with, G_without, S_raw, S, sigma_in_eq, status, n_fallback."""
    cond = {v.T: T, v.P: 101325, v.N: 1}
    for el, xv in cfg["x"].items():
        cond[v.X(el)] = xv
    sig = cfg["sigma"]
    allp = sorted(p for p in db.phases if p not in cfg["exclude"])
    if sig not in allp:
        raise ValueError(f"phase {sig} not in the merged database")
    with_p = allp
    wo_p = [p for p in allp if p != sig]
    n_fb = 0
    g1, ps1, s1 = best(db, cfg["comps"], with_p, cond, protect=(sig,))
    g0, ps0, s0 = best(db, cfg["comps"], wo_p, cond)
    n_fb += (s1 == "fallback") + (s0 == "fallback")
    out = {"T": T, "G_with": g1, "G_without": g0, "S_raw": None, "S": None,
           "sigma_in_eq": None, "status": "failed", "n_fallback": n_fb}
    if g1 is None or g0 is None:
        return out
    s_raw = (g0 - g1) / 1000.0
    if s_raw < -NOISE_FLOOR:                      # retry: leave-one-out minimum in both
        g1b, ps1b, _ = best(db, cfg["comps"], with_p, cond, protect=(sig,), force_fallback=True)
        g0b, ps0b, _ = best(db, cfg["comps"], wo_p, cond, force_fallback=True)
        n_fb += 2
        if g1b is not None and g0b is not None:
            g1, g0, ps1 = g1b, g0b, ps1b
            s_raw = (g0 - g1) / 1000.0
        out.update({"G_with": g1, "G_without": g0, "n_fallback": n_fb})
        if not np.isfinite(s_raw) or s_raw < -NOISE_FLOOR:
            out["S_raw"] = s_raw if np.isfinite(s_raw) else None
            return out
    out["S_raw"] = s_raw
    if s_raw < 0:
        out["S"] = 0.0
        out["status"] = "clipped"
    else:
        out["S"] = s_raw
        out["status"] = "fallback" if n_fb else "direct"
    out["sigma_in_eq"] = bool(ps1 is not None and sig in ps1)
    return out


_CFG = None
_RUN = None


def _init(cfg, run_dir):
    global _CFG, _RUN
    _CFG, _RUN = cfg, run_dir


def work(row):
    combo = row["combo"]
    path = Path(_RUN) / "merged" / f"{_CFG['prefix']}__{combo}.tdb"
    res = []
    try:
        db = Database(str(path))
        for T in _CFG["temps"]:
            try:
                o = observable(db, _CFG, T)
            except Exception as e:
                o = {"T": T, "G_with": None, "G_without": None, "S_raw": None, "S": None,
                     "sigma_in_eq": None, "status": "failed", "n_fallback": 0,
                     "error": f"{type(e).__name__}: {e}"[:200]}
            res.append(o)
    except Exception as e:
        for T in _CFG["temps"]:
            res.append({"T": T, "G_with": None, "G_without": None, "S_raw": None, "S": None,
                        "sigma_in_eq": None, "status": "failed", "n_fallback": 0,
                        "error": f"load {type(e).__name__}: {e}"[:200]})
    return row, res


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--run-dir", required=True, help="edge-check output folder (edge_check.csv, merged/)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None, help="only the first N survivors (tests)")
    a = ap.parse_args()
    cfg = SYSTEMS[a.system]
    run = Path(a.run_dir)
    ec = run / "edge_check.csv"
    if not ec.exists():
        sys.exit(f"missing {ec}")
    with open(ec, newline="") as f:
        rows = list(csv.DictReader(f))
    surv = [r for r in rows if r["pass"] == "True"]
    if a.limit:
        surv = surv[: a.limit]
    out = run / "sigma"
    out.mkdir(exist_ok=True)
    info = {"command": " ".join([Path(sys.executable).name] + sys.argv),
            "started": datetime.now().isoformat(timespec="seconds"), "pycalphad": pycalphad.__version__,
            "numpy": np.__version__, "system": a.system, "x_star": cfg["x"], "sigma_phase": cfg["sigma"],
            "excluded_in_both": list(cfg["exclude"]), "temps": cfg["temps"], "primary_T": cfg["temps"][0],
            "noise_floor_kJ_per_mol_atom": NOISE_FLOOR, "n_edge_check_rows": len(rows),
            "n_survivors": len(surv), "script_sha256": sha256(__file__)}
    print(f"Survivors: {len(surv)} of {len(rows)} edge-check rows; temperatures {cfg['temps']}")
    t0 = time.time()
    fields = ["combo"] + cfg["groups"] + ["T", "G_with", "G_without", "S_raw", "S", "sigma_in_eq",
                                          "status", "n_fallback", "error"]
    n_out = n_fail = 0
    with Pool(a.workers, initializer=_init, initargs=(cfg, str(run))) as pool, \
            open(out / "sigma_S.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for k, (row, res) in enumerate(pool.imap_unordered(work, surv), 1):
            for o in res:
                rec = {"combo": row["combo"], **{g: row.get(g, "") for g in cfg["groups"]}, **o}
                for key in ("G_with", "G_without", "S_raw", "S"):
                    if rec.get(key) is not None:
                        rec[key] = round(rec[key], 6)
                w.writerow(rec)
                n_out += 1
                n_fail += o["status"] == "failed"
            f.flush()
            if k % 10 == 0 or k == len(surv):
                print(f"[{k}/{len(surv)}] failed points so far: {n_fail}", flush=True)
    info.update({"finished": datetime.now().isoformat(timespec="seconds"), "rows_written": n_out,
                 "rows_expected": len(surv) * len(cfg["temps"]), "failed_points": n_fail,
                 "seconds": round(time.time() - t0)})
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"Done: {n_out} rows ({n_fail} failed points) in {time.time() - t0:.0f} s -> {out / 'sigma_S.csv'}")
    if n_out != len(surv) * len(cfg["temps"]):
        sys.exit(3)


if __name__ == "__main__":
    main()
