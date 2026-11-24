#!/usr/bin/env python3
"""Addendum D: tau1/tau2 single-phase ranges along La(Fe1-ySiy)13 vs Niitsu, and WP4b descriptor sensitivity.
Usage: python tau1_window.py M0.tdb OUT_PREFIX"""
import sys, warnings, numpy as np
warnings.filterwarnings('ignore')
from pycalphad import Database, equilibrium, variables as v
db = Database(sys.argv[1]); out = sys.argv[2]
COMPS = ['LA', 'FE', 'SI', 'VA']; ALL = list(db.phases); COMP = [p for p in ALL if p not in ('TAU1', 'TAU2')]
def frac(phases, la, si, T, pd=800):
    r = equilibrium(db, COMPS, phases, {v.X('LA'): la, v.X('SI'): si, v.T: T, v.P: 101325, v.N: 1}, calc_opts={'pdens': pd})
    P = np.array(r.Phase).ravel(); N = np.array(r.NP).ravel(); f = {}
    for p, n in zip(P, N):
        if str(p) not in ('', 'nan') and not np.isnan(n) and n > 1e-4: f[str(p)] = f.get(str(p), 0) + float(n)
    return f, float(np.array(r.GM).ravel()[0])
TS = [1173, 1273, 1323, 1373, 1423, 1473, 1523, 1573]; YS = np.arange(0.0, 0.4501, 0.005)
rng = {}; lines = ['T_K\tphase\tcalc_ylow\tcalc_yhigh\tn_points']
for T in TS:
    fr = {'TAU1': [], 'TAU2': []}
    for y in YS:
        f, _ = frac(ALL, 1/14, 13*y/14, float(T))
        for t in fr:
            if f.get(t, 0) >= 0.98: fr[t].append(round(float(y), 3))
    for t, ys in fr.items():
        rng[(T, t)] = (min(ys), max(ys)) if ys else None
        lines.append(f'{T}\t{t}\t{min(ys) if ys else ""}\t{max(ys) if ys else ""}\t{len(ys)}'); print(lines[-1], flush=True)
open(out + '_ranges.tsv', 'w').write('\n'.join(lines) + '\n')
# descriptor D(x,T)
Dl = ['T_K\tx\tD_J_per_molatom']
D = {}
for Tc, Tk in ((1050, 1323.15), (1150, 1423.15), (1200, 1473.15)):
    for x in (1.2, 1.4, 1.6, 1.8, 2.0):
        _, ga = frac(ALL, 1/14, x/14, Tk, 2000); _, gc = frac(COMP, 1/14, x/14, Tk, 2000)
        D[(Tk, x)] = gc - ga; Dl.append(f'{Tk}\t{x}\t{gc-ga:.1f}'); print(Dl[-1], flush=True)
open(out + '_D.tsv', 'w').write('\n'.join(Dl) + '\n')
