#!/usr/bin/env python3
"""
crfeni_posthoc_diag.py (19 Nov 2026) - POST-HOC diagnosis after the negative gate G3 of Cr-Fe-Ni Pilot-M (L010).
Read-only: reads edge_check_crfeni/edge_check.csv and merged/*.tdb, writes only diag_*.csv next to them.
Does NOT change, re-gate or re-interpret the gate. Questions fixed BEFORE running:
  Q1  Which phases are in equilibrium at x* = (Cr .45, Fe .45, Ni .10) for each of the 81 survivors,
      at 800, 900, 1000 K? (phase-set counts)
  Q2  How far is sigma from stability there? DF = driving force of sigma = max over the sigma energy grid of [sum x_i mu_i - G_sigma] with the
      equilibrium chemical potentials, kJ/mol-atom (DF <= 0: sigma not stable, -DF = distance; ~0: borderline). Same phase exclusions as the pilot (SIGMA_OLD, HIGH_SIGMA out).
  Q3  Is sigma stable on the binary Cr-Fe of each of the six Cr-Fe source files at x(Cr) = 0.45 and 0.50,
      T = 700, 800, 900, 1000 K (dG as in Q2)? Answers whether sigma is already absent on the edge.
Usage: python crfeni_posthoc_diag.py --run-dir edge_check_crfeni --tdb-dir $SGTE_BINARY_DIR [--limit N]
"""
import argparse, csv, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
from pycalphad import Database, equilibrium, calculate, variables as v

SIG, EXCL = "SIGMA_D8B", ("SIGMA_OLD", "HIGH_SIGMA")
CRFE = ["CrFe-82Her", "CrFe-87And-LB", "CrFe-21Laf", "CrFe-18Jac", "CrFe-20Ost", "CrFe-23Zha"]

def eq(db, comps, phases, cond):
    """(G, phase names, MU dict by element) or (None, None, None)."""
    try:
        r = equilibrium(db, comps, phases, cond)
        g = float(r.GM.values.squeeze())
        names = sorted({str(n) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1))
                        if n and np.isfinite(f) and f > 1e-4})
        mu = {str(c): float(m) for c, m in zip(r.coords["component"].values, r.MU.values.reshape(-1))}
        return (g, names, mu) if np.isfinite(g) else (None, None, None)
    except Exception:
        return None, None, None

def driving_force(db, comps, T, mu, sigma):
    """Max over the sigma energy grid of sum_i x_i mu_i - G  (J/mol-atom). > 0: sigma would be stable;
    <= 0: -value = how far sigma is from stability."""
    try:
        r = calculate(db, [c for c in comps], sigma, T=T, P=101325, N=1, pdens=2000)
        gm = r.GM.values.reshape(-1)
        xs = r.X.values.reshape(gm.shape[0], -1) if r.X.values.ndim > 1 else None
        els = [str(c) for c in r.coords["component"].values]
        x = r.X.values.reshape(-1, len(els))
        df = x @ np.array([mu[e] for e in els]) - gm
        return float(np.nanmax(df))
    except Exception:
        return None

def point(db, comps, x, T):
    allp = sorted(p for p in db.phases if p not in EXCL)
    cond = {v.T: T, v.P: 101325, v.N: 1, **{v.X(k): val for k, val in x.items()}}
    g, names, mu = eq(db, comps, allp, cond)
    if SIG not in db.phases or g is None:
        return g, names, None
    df = driving_force(db, comps, T, mu, SIG)
    return g, names, None if df is None else df / 1000.0     # kJ/mol-atom, >0 stable

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True); ap.add_argument("--tdb-dir", required=True)
    ap.add_argument("--limit", type=int); ap.add_argument("--sigma", default=SIG)
    a = ap.parse_args()
    globals()['SIG'] = a.sigma
    run = Path(a.run_dir)
    surv = [r for r in csv.DictReader(open(run / "edge_check.csv")) if r["pass"] == "True"]
    if a.limit: surv = surv[:a.limit]
    with open(run / "diag_ternary.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["combo", "CrFe", "T", "phases_in_eq", "sigma_in_eq", "DF_sigma_kJ"])
        for k, r in enumerate(surv, 1):
            db = Database(str(run / "merged" / f"CRFENI__{r['combo']}.tdb"))
            for T in (800.0, 900.0, 1000.0):
                g, names, dG = point(db, ["CR", "FE", "NI", "VA"], {"CR": 0.45, "NI": 0.10}, T)
                w.writerow([r["combo"], r["CrFe"], T, "+".join(names or []), SIG in (names or []),
                            "" if dG is None else round(dG, 4)])
            if k % 10 == 0: print(f"ternary [{k}/{len(surv)}]", flush=True)
    with open(run / "diag_binary.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["CrFe", "x_Cr", "T", "phases_in_eq", "sigma_in_eq", "DF_sigma_kJ"])
        for name in CRFE:
            db = Database(str(Path(a.tdb_dir) / f"{name}.tdb"))
            for xc in (0.45, 0.50):
                for T in (700.0, 800.0, 900.0, 1000.0):
                    g, names, dG = point(db, ["CR", "FE", "VA"], {"CR": xc}, T)
                    w.writerow([name, xc, T, "+".join(names or []), SIG in (names or []),
                                "" if dG is None else round(dG, 4)])
    print("done:", run / "diag_ternary.csv", run / "diag_binary.csv")

if __name__ == "__main__":
    main()
