"""thresholds_assessments.py — data for Figure 5 of the Stage 3 paper (Section 6.5).

For each full ternary assessment of Fe-Nd-B: the Gibbs energy of the binary-phase assemblage at the
14:2:1 composition (ternary phases removed) and the Gibbs energy of Phi (FE14ND2B), both relative to
sum x_i GHSER_i. The reference sum is computed by pycalphad itself through an appended line compound
REFX, so it is extrapolated above the last temperature range exactly like every phase.

The two TDB files are not part of this repository (obtain them from their sources):
  Chen et al. 2019, Calphad 66, 101627            -> --chen PATH
  Hallemans et al. 1995, TDB from NIMS CPDDB     -> --hallemans PATH

Usage (stage_three/paper_figures/, main venv):
    python thresholds_assessments.py --chen PATH --hallemans PATH   # writes thresholds_assessments.json
"""
import argparse, json, tempfile, warnings
from pathlib import Path
import numpy as np
from pycalphad import Database, equilibrium, calculate, variables as v

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
T_GRID = np.linspace(800, 1800, 15)
X = {"FE": 14 / 17, "ND": 2 / 17, "B": 1 / 17}
TERN = {"FE14ND2B", "FE4NDB4", "FE2ND5B6"}

ap = argparse.ArgumentParser()
ap.add_argument("--chen", required=True, type=Path)
ap.add_argument("--hallemans", required=True, type=Path)
args = ap.parse_args()
cases = {"Chen 2019": args.chen, "Hallemans 1995": args.hallemans}

out = {}
for label, f in cases.items():
    db0 = Database(str(f))
    ser = {e: next(n for n in (f"GHSER{e}", f"GHSER{e}{e}") if n in db0.symbols) for e in X}
    ref = (f"\nPHASE REFX % 3 14 2 1 !\nCONSTITUENT REFX :FE:ND:B: !\n"
           f"PARAMETER G(REFX,FE:ND:B;0) 298.15 14*{ser['FE']}+2*{ser['ND']}+{ser['B']}; 6000 N !\n")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "with_ref.tdb"
        tmp.write_text(Path(f).read_text(errors="replace") + ref)
        db = Database(str(tmp))
    comps = ["FE", "ND", "B", "VA"]
    BIN = sorted(set(db0.phases) - TERN)
    rows = []
    for T in map(float, T_GRID):
        g_ref = float(calculate(db, comps, "REFX", T=T, P=101325, N=1, output="GM").GM.values.squeeze())
        r = equilibrium(db, comps, BIN, {v.X("ND"): X["ND"], v.X("B"): X["B"], v.T: T, v.P: 101325, v.N: 1})
        gb = float(r.GM.values.squeeze())
        mix = sorted(str(n) for n, fr in zip(r.Phase.values.ravel(), r.NP.values.ravel()) if n and fr > 1e-3)
        gp = float(calculate(db, comps, "FE14ND2B", T=T, P=101325, N=1, output="GM").GM.values.squeeze())
        rows.append({"T": T, "threshold": (gb - g_ref) / 1e3, "phi": (gp - g_ref) / 1e3,
                     "margin": (gp - gb) / 1e3, "mix": "+".join(mix)})
        print(f"{label:15s} {T:6.0f}  threshold {(gb - g_ref) / 1e3:7.2f}  Phi {(gp - g_ref) / 1e3:7.2f}  "
              f"margin {(gp - gb) / 1e3:6.2f}  {'+'.join(mix)}", flush=True)
    out[label] = rows
(HERE / "thresholds_assessments.json").write_text(json.dumps(out, indent=1))
print("written: thresholds_assessments.json")
