#!/usr/bin/env python3
"""crfeni_binary_S_check.py (23 Nov 2026) - POST-HOC, read-only diagnostic for Cr-Fe-Ni Pilot-M (L010).
S = (G_eq without SIGMA_D8B - G_eq with SIGMA_D8B)/1000 kJ/mol-atom on the six Cr-Fe SOURCE files (binary, not merged),
x(Cr) = 0.45, 0.50; T = 800, 900, 1000 K; SIGMA_OLD and HIGH_SIGMA excluded in both. Does not touch the gate.
Usage: python crfeni_binary_S_check.py --tdb-dir $SGTE_BINARY_DIR"""
import argparse, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
import pycalphad
from pycalphad import Database, equilibrium, variables as v
SIG, EXCL = "SIGMA_D8B", ("SIGMA_OLD", "HIGH_SIGMA")
FILES = ["CrFe-82Her", "CrFe-87And-LB", "CrFe-21Laf", "CrFe-18Jac", "CrFe-20Ost", "CrFe-23Zha"]
def G(db, phases, cond):
    try:
        g = float(equilibrium(db, ["CR", "FE", "VA"], phases, cond).GM.values.squeeze())
        return g if np.isfinite(g) else None
    except Exception:
        return None
ap = argparse.ArgumentParser(); ap.add_argument("--tdb-dir", required=True); a = ap.parse_args()
print("pycalphad", pycalphad.__version__, "numpy", np.__version__)
print("file, xCr, S(800K), S(900K), S(1000K)  [kJ/mol-atom]")
for f in FILES:
    db = Database(str(Path(a.tdb_dir) / f"{f}.tdb"))
    allp = sorted(p for p in db.phases if p not in EXCL); nos = [p for p in allp if p != SIG]
    for x in (0.45, 0.50):
        out = []
        for T in (800.0, 900.0, 1000.0):
            c = {v.T: T, v.P: 101325, v.N: 1, v.X("CR"): x}
            g1, g0 = G(db, allp, c), G(db, nos, c)
            out.append("NA" if g1 is None or g0 is None else f"{(g0 - g1) / 1000:.4f}")
        print(f, x, *out)
