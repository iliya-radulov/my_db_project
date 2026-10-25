"""check_validation_step2.py — validation step 2 of the Stage 3 paper (Section 5.5).

Runs the equilibrium code on the two published ternary assessments of Fe-Nd-B at the Nd2Fe14B
composition and prints the stable phases from 800 to 1500 K. Expected (25 Oct 2026): FE14ND2B as the
only stable phase from 800 to 1450 K in both, FCC_A1 + LIQUID at 1500 K.

The TDB files are not part of this repository:
  Chen et al. 2019, Calphad 66, 101627            -> --chen PATH
  Hallemans et al. 1995, TDB from NIMS CPDDB     -> --hallemans PATH

Usage (main venv):  python check_validation_step2.py --chen PATH --hallemans PATH
"""
import argparse, warnings
import numpy as np
from pycalphad import Database, equilibrium, variables as v

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
ap.add_argument("--chen", required=True)
ap.add_argument("--hallemans", required=True)
args = ap.parse_args()
for label, f in (("Chen 2019", args.chen), ("Hallemans 1995", args.hallemans)):
    db = Database(f)
    for T in (800, 1000, 1200, 1300, 1400, 1450, 1500):
        r = equilibrium(db, ["FE", "ND", "B", "VA"], list(db.phases),
                        {v.X("FE"): 14 / 17, v.X("ND"): 2 / 17, v.T: T, v.P: 101325})
        ph = [(str(p), round(float(n), 3)) for p, n in zip(r.Phase.values.ravel(), r.NP.values.ravel())
              if p and np.isfinite(n) and n > 1e-4]
        print(f"{label:15s} {T:5d} K  {ph}")
