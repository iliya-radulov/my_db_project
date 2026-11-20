#!/usr/bin/env python3
"""Addendum E evaluation (rules frozen in FROZEN_SPEC.md). Usage: python ensemble_analysis.py DIR"""
import sys, glob, collections
d = sys.argv[1]; R = collections.defaultdict(dict); fails = []
for f in sorted(glob.glob(f'{d}/ens_w*.tsv')):
    for ln in open(f).read().splitlines()[1:]:
        c, T, lo, hi, n = (ln.split('\t') + ['']*5)[:5]
        if T == 'BUILD_FAIL' or lo == 'CALC_FAIL': fails.append(ln); continue
        R[c][int(T)] = (float(lo), float(hi)) if lo else None
rows = ['combination | y_lo 1173/1373/1573 | y_hi 1173/1373/1573 | shift s | width 1373 | class']; cls = collections.Counter(); ok = []
for c in sorted(R):
    t = R[c]
    if any(t.get(T) is None for T in (1173, 1373, 1573)): fails.append(c + ' incomplete'); continue
    s = t[1573][0] - t[1173][0]
    k = 'flat' if abs(s) <= 0.01 else ('temperature-dependent' if s >= 0.04 else ('reversed' if s <= -0.01 else 'intermediate'))
    cls[k] += 1; ok.append(c)
    rows.append(f'{c} | {t[1173][0]:.3f}/{t[1373][0]:.3f}/{t[1573][0]:.3f} | {t[1173][1]:.3f}/{t[1373][1]:.3f}/{t[1573][1]:.3f} | {s:+.3f} | {t[1373][1]-t[1373][0]:.3f} | {k}')
n = len(ok); N = cls['flat']
rows.append(f'\nn computed = {n} of 20; failures: {len(fails)} {fails}')
rows.append('classes: ' + ', '.join(f'{k} {v}' for k, v in cls.items()))
m0 = R.get('FeLa-23Su+LaSi-10Zho+FeSi-17Cui', {})
chk = {1173: (0.090, 0.235), 1373: (0.085, 0.235), 1573: (0.085, 0.240)}
valid = bool(m0) and all(m0.get(T) and abs(m0[T][0]-chk[T][0]) <= 0.005 and abs(m0[T][1]-chk[T][1]) <= 0.005 for T in chk)
rows.append(f'M0 consistency check (within 0.005): {"PASS" if valid else "FAIL -> INVALID RUN"}  M0 = {m0}')
lo1373 = [R[c][1373][0] for c in ok]; w1373 = [R[c][1373][1]-R[c][1373][0] for c in ok]
rows.append(f'y_lo(1373 K) range {min(lo1373):.3f}-{max(lo1373):.3f}; width(1373 K) range {min(w1373):.3f}-{max(w1373):.3f} (measured: 0.096, 0.133); any combination reproducing measured shift (s>=0.04): {cls["temperature-dependent"]>0}')
frac = N / n if n else float('nan')
sent = ('the flat window is NOT a binary-choice effect (it comes with the Feng tau parameters)' if frac >= 0.90 else
        'the flat window is specific to the M0 binary choice' if frac <= 0.10 else 'the flatness is partly a binary-choice effect')
rows.append(f'flat {N}/{n} = {frac:.2f} -> {sent}')
open(f'{d}/ens_analysis.txt', 'w').write('\n'.join(rows) + '\n'); print('\n'.join(rows))
