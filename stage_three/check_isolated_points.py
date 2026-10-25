"""
check_isolated_points.py — are the three isolated Fe17Nd2 + Fe2B points of the 1375 K grid real? (25 Oct 2026)

In cache/FENDB_1375K_N200_v3.pkl three grid points returned only FE17ND2 + M2B_C16:
    (x_Fe, x_Nd) = (0.71, 0.02), (0.775, 0.05), (0.84, 0.08)
All three lie exactly on the line between the two compounds. The first two border the
FE17ND2+LIQUID+M2B_C16 field; the third lies INSIDE the FCC_A1+FE17ND2+LIQUID field (all eight
neighbours). If the third is a stuck minimiser, the neighbours' assemblage must have a LOWER
Gibbs energy at the same composition.

For each point this prints:
  A  equilibrium with all phases (what the grid did)
  B  equilibrium with only FE17ND2 + M2B_C16
  C  equilibrium without M2B_C16 (the neighbours' assemblage can form)
  D  all phases at a composition shifted by 0.001 off the line
A lower G in C than in A means the grid point is not the true minimum.

Usage (stage_three/, main venv):  python check_isolated_points.py
"""
import warnings

import numpy as np
from pycalphad import Database, equilibrium, variables as v

from tdb_merge import merged_tdb_path

warnings.filterwarnings("ignore")
T = 1375
POINTS = [(0.71, 0.02), (0.775, 0.05), (0.84, 0.08)]

db = Database(str(merged_tdb_path(["FE", "ND", "B"])))      # same merged file as the grid
ELS = ["FE", "ND", "B", "VA"]
ALL = list(db.phases.keys())


def eq(xfe, xnd, phases):
    r = equilibrium(db, ELS, phases, {v.X("FE"): xfe, v.X("ND"): xnd, v.T: T, v.P: 101325})
    ph = [(str(p), float(n)) for p, n in zip(r.Phase.values.ravel(), r.NP.values.ravel())
          if p and np.isfinite(n) and n > 1e-6]
    return float(r.GM.values.ravel()[0]), ph


def show(tag, g, ph, ref=None):
    d = "" if ref is None or not np.isfinite(g) else f"   G - G(A) = {g - ref:+9.2f} J/mol"
    print(f"   {tag}  G = {g:12.2f} J/mol{d}   " + ", ".join(f"{p} {n:.4f}" for p, n in ph))


for xfe, xnd in POINTS:
    print(f"\nx_Fe = {xfe}, x_Nd = {xnd}, T = {T} K")
    gA, phA = eq(xfe, xnd, ALL)
    show("A all phases        ", gA, phA)
    show("B Fe17Nd2 + Fe2B    ", *eq(xfe, xnd, ["FE17ND2", "M2B_C16"]), ref=gA)
    show("C without M2B_C16   ", *eq(xfe, xnd, [p for p in ALL if p != "M2B_C16"]), ref=gA)
    show("D all, x_Fe + 0.001 ", *eq(xfe + 0.001, xnd, ALL))
print("\nNote: the grid drops phases with a fraction below 1e-3; a third phase near zero appears here.")
