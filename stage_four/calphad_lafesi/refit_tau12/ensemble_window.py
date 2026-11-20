#!/usr/bin/env python3
"""Addendum E: tau1 window vs T for the 20 binary combinations. Usage: python ensemble_window.py WORKER NWORKERS OUT.tsv
Requires SGTE_BINARY_DIR; run from stage_four/calphad_lafesi (imports build_merged_tdb_fixed)."""
import sys, os, warnings, itertools, numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import build_merged_tdb_fixed as B
from pycalphad import equilibrium, variables as v
FELA = ['FeLa-09Pov', 'FeLa-23Su']; LASI = ['LaSi-10Zho', 'LaSi-20Xu']
FESI = ['FeSi-12Ohn', 'FeSi-14Yua', 'FeSi-17Cui', 'FeSi-23Wit', 'FeSi-91Lac-LB']
combos = list(itertools.product(FESI, FELA, LASI))
k, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
COMPS = ['LA', 'FE', 'SI', 'VA']; YS = np.arange(0.06, 0.3001, 0.005)
rows = []
for i, (fe, fl, ls) in enumerate(combos):
    if i % n != k: continue
    tag = f'{fl}+{ls}+{fe}'
    try:
        tmp = f'/tmp/claude-0/-home-user/3d4af583-9a98-5c1b-9aaa-880fc70dd97e/scratchpad/ens_{k}.tdb'
        _, db = B.build(fl, ls, fe, out=tmp); ph = list(db.phases)
    except Exception as e:
        rows.append(f'{tag}\tBUILD_FAIL\t\t\t{str(e)[:60]}'); print(rows[-1], flush=True); continue
    for T in (1173, 1373, 1573):
        ys = []
        try:
            for y in YS:
                r = equilibrium(db, COMPS, ph, {v.X('LA'): 1/14, v.X('SI'): 13*y/14, v.T: float(T), v.P: 101325, v.N: 1}, calc_opts={'pdens': 800})
                P = np.array(r.Phase).ravel(); N = np.array(r.NP).ravel()
                f = sum(float(a) for p, a in zip(P, N) if str(p) == 'TAU1' and not np.isnan(a))
                if f >= 0.98: ys.append(round(float(y), 3))
            rows.append(f'{tag}\t{T}\t{min(ys) if ys else ""}\t{max(ys) if ys else ""}\t{len(ys)}')
        except Exception as e:
            rows.append(f'{tag}\t{T}\tCALC_FAIL\t\t{str(e)[:60]}')
        print(rows[-1], flush=True)
open(out, 'w').write('combination\tT_K\ty_lo\ty_hi\tn_points\n' + '\n'.join(rows) + '\n')
