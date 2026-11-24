#!/usr/bin/env python3
"""Per-equilibrium residuals (FROZEN_SPEC.md Addendum C).
Usage: python residuals.py TIELINES.csv OUT.csv LABEL=TDB [LABEL=TDB ...]"""
import sys, csv, warnings, numpy as np
warnings.filterwarnings('ignore')
from pycalphad import Database, equilibrium, variables as v
from make_inputs import MAP, TER_MAP
ALL = dict(MAP, **TER_MAP)
SOL = {'BCC_A2', 'FCC_A1', 'LIQUID', 'TAU1', 'TAU2'}
COMPS = ['LA', 'FE', 'SI', 'VA']
def calc(db, la, si, T):
    r = equilibrium(db, COMPS, list(db.phases), {v.X('LA'): la, v.X('SI'): si, v.T: T, v.P: 101325, v.N: 1},
                    calc_opts={'pdens': 2000})
    P = np.array(r.Phase).ravel(); N = np.array(r.NP).ravel()
    XL = np.array(r.X.sel(component='LA')).ravel(); XS = np.array(r.X.sel(component='SI')).ravel()
    out = {}
    for p, n, a, b in zip(P, N, XL, XS):
        if str(p) in ('', 'nan') or np.isnan(n) or n <= 1e-3: continue
        out.setdefault(str(p), (float(n), float(a), float(b)))
    return out
def main(ties, out, models):
    rows = list(csv.DictReader(open(ties, encoding='utf-8')))
    dbs = {k: Database(p) for k, p in models}
    res = []
    for i, r in enumerate(rows):
        if any(r[f'phase{j}'] and (r[f'La{j}'] == '' or r[f'Si{j}'] == '') for j in (1, 2, 3)): continue  # n.d. rows
        ph = [(r[f'phase{j}'], float(r[f'La{j}']) / 100, float(r[f'Si{j}']) / 100) for j in (1, 2, 3) if r[f'phase{j}']]
        if any(p not in ALL for p, _, _ in ph): continue
        exp = {ALL[p]: (la, si) for p, la, si in ph}
        for k, db in dbs.items():
            if any(n not in db.phases for n in exp): continue   # model cannot evaluate this equilibrium
            try: c = calc(db, float(r['nominal_La']) / 100, float(r['nominal_Si']) / 100, float(r['T_K']))
            except Exception as e: res.append([k, i, r['T_K'], '', 'ERR', str(e)[:40]]); continue
            match = set(c) == set(exp)
            dS = [(n, 100 * (c[n][2] - exp[n][1]), 100 * (c[n][1] - exp[n][0])) for n in exp if n in SOL and n in c]
            ok = match and all(abs(a) <= 2.0 and abs(b) <= 1.0 for _, a, b in dS)
            res.append([k, i, r['T_K'], '+'.join(sorted(exp)), '+'.join(sorted(c)), int(match), int(ok),
                        ';'.join(f'{n}:{a:+.1f}/{b:+.1f}' for n, a, b in dS)])
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['model', 'row', 'T_K', 'exp_phases', 'calc_phases', 'set_match', 'within_scatter', 'dSi/dLa_at%'])
        w.writerows(res)
    for k in dbs:
        m = [x for x in res if x[0] == k and x[4] != 'ERR']
        print(f'{k}: n={len(m)} set-match {sum(x[5] for x in m)} within-scatter {sum(x[6] for x in m)}')
    for k in dbs:
        for tau in ('TAU1', 'TAU2'):
            d = [float(s.split(':')[1].split('/')[0]) for x in res if x[0] == k and len(x) > 7 for s in x[7].split(';') if s.startswith(tau)]
            if d:
                print(f'  {k} {tau}: n={len(d)} mean dSi {np.mean(d):+.2f} frac_same_sign {max(np.mean(np.array(d) > 0), np.mean(np.array(d) < 0)):.2f}')
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], [a.split('=', 1) for a in sys.argv[3:]])
