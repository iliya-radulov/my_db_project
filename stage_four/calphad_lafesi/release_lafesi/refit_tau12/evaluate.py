#!/usr/bin/env python3
"""C3 gates (A3, A5) and reported descriptors for baseline vs refit TDB.
Usage: python evaluate.py baseline_eq.tdb optimized.tdb"""
import sys, warnings, numpy as np
warnings.filterwarnings('ignore')
from pycalphad import Database, equilibrium, variables as v
COMPS = ['LA', 'FE', 'SI', 'VA']
def eq(db, phases, la, si, T, pdens=2000):
    r = equilibrium(db, COMPS, phases, {v.X('LA'): la, v.X('SI'): si, v.T: T, v.P: 101325, v.N: 1},
                    calc_opts={'pdens': pdens})
    P = np.array(r.Phase).ravel(); N = np.array(r.NP).ravel()
    fr = {}
    for p, n in zip(P, N):
        if str(p) not in ('', 'nan') and not np.isnan(n) and n > 1e-4: fr[str(p)] = fr.get(str(p), 0) + float(n)
    return float(np.array(r.GM).ravel()[0]), fr
def run(path):
    db = Database(path); allp = list(db.phases); comp = [p for p in allp if p not in ('TAU1', 'TAU2')]
    res = {}
    g, fr = eq(db, allp, 1/14, 1.5/14, 1373.15)
    res['A3_tau1_present'] = 'TAU1' in fr and fr['TAU1'] > 0.01; res['A3_assemblage'] = fr
    res['GM_tau_point_1373K'] = g
    xs = np.arange(0.0, 0.401, 0.02); dom = []
    for x in xs:
        _, f = eq(db, allp, 1/14, 13*x/14, 1373.15, 1000)
        if f.get('TAU1', 0) >= 0.5: dom.append(round(float(x), 3))
    res['A5_tau1_dominant_x'] = (min(dom), max(dom)) if dom else None
    res['A5_overlap_0.096-0.229'] = bool(dom) and (max(dom) >= 0.096 and min(dom) <= 0.229)
    D = {}
    for x in (1.2, 1.4, 1.6, 1.8, 2.0):
        for Tc, Tk in {1050: 1323.15, 1150: 1423.15, 1200: 1473.15}.items():
            ga, _ = eq(db, allp, 1/14, x/14, Tk); gc, _ = eq(db, comp, 1/14, x/14, Tk)
            D[(x, Tc)] = gc - ga
    res['D'] = D
    return res
if __name__ == '__main__':
    out = {n: run(p) for n, p in (('baseline', sys.argv[1]), ('refit', sys.argv[2]))}
    for n, r in out.items():
        print('==', n)
        for k, val in r.items():
            if k != 'D': print(' ', k, val)
    print('D = G(competing, tau suspended) - G(all)  [J/mol-atom]')
    print('  x  T_C   baseline    refit    refit-baseline')
    for k in out['baseline']['D']:
        b, f = out['baseline']['D'][k], out['refit']['D'][k]
        print(f'  {k[0]:.1f} {k[1]:5d} {b:9.1f} {f:9.1f} {f-b:9.1f}')
