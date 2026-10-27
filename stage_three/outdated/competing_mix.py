"""
competing_mix.py — which binary phases compete with Nd2Fe14B in the corrected merge?   (read-only, ~1-2 min)

Merges the three SGTE binaries with tdb_merge.py (the corrected merge), then computes the
equilibrium at the 14:2:1 composition (no ternary phase exists in the merged description) and prints
  - the stable phases and their fractions,
  - the energy of that assemblage relative to the GHSER functions (kJ/mol-atom).
That energy is the feasibility threshold, so it must reproduce the feasibility table:
-9.7 (800 K), -9.0 (1014), -8.5 (1300), -9.8 (1514), -13.5 (1800).

Usage (stage_three/, main venv):   python competing_mix.py
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tdb_merge import merged_tdb_path                         # noqa: E402
from pycalphad import Database, equilibrium, variables as v   # noqa: E402

ELS = ["FE", "ND", "B"]
X = {"FE": 14 / 17, "ND": 2 / 17, "B": 1 / 17}
EXPECTED = {800: -9.7, 1014: -9.0, 1300: -8.5, 1514: -9.8, 1800: -13.5}


def ghser(db, el, T):
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return float(db.symbols[name].subs({v.T: T}))
    raise KeyError(f"no GHSER function for {el}")


def main():
    db = Database(str(merged_tdb_path(ELS, check=False)))
    print()
    for T in (800.0, 1014.2857, 1300.0, 1514.2857, 1800.0):
        r = equilibrium(db, ELS + ["VA"], list(db.phases),
                        {v.X("ND"): X["ND"], v.X("B"): X["B"], v.T: T, v.P: 101325, v.N: 1})
        phases = {str(n): round(float(f), 3)
                  for n, f in zip(r.Phase.values.ravel(), r.NP.values.ravel()) if n and f > 1e-3}
        ref = sum(X[e] * ghser(db, e, T) for e in ELS)
        e = (float(r.GM.values.squeeze()) - ref) / 1000
        print(f"{T:6.0f} K  energy {e:6.2f} kJ/mol-atom (table: {EXPECTED[round(T)]:+.1f})  {phases}")


if __name__ == "__main__":
    main()
