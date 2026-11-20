#!/usr/bin/env python3
"""Addendum D evaluation (rules frozen in FROZEN_SPEC.md before the run). Usage: python addD_analysis.py DIR"""
import sys, csv, numpy as np
d = sys.argv[1]
EXP = {1173: {'TAU1': (0.086, 0.211), 'TAU2': (0.251, 0.398)}, 1373: {'TAU1': (0.096, 0.229), 'TAU2': (0.266, 0.402)},
       1573: {'TAU1': (0.162, 0.279), 'TAU2': (0.291, 0.376)}}          # Niitsu 2012 section 4.1 (text_facts.csv)
calc = {}
for r in csv.DictReader(open(f'{d}/M0_ranges.tsv'), delimiter='\t'):
    calc[(int(r['T_K']), r['phase'])] = (float(r['calc_ylow']), float(r['calc_yhigh']))
out = ['== calculated vs measured single-phase ranges (y = Si/(Fe+Si)); measured only at 1173/1373/1573 K']
out.append('T_K phase | calc lo-hi (width) | exp lo-hi (width) | d_lo  d_hi  d_width')
for T in (1173, 1373, 1573):
    for t in ('TAU1', 'TAU2'):
        c, e = calc[(T, t)], EXP[T][t]
        out.append(f'{T} {t} | {c[0]:.3f}-{c[1]:.3f} ({c[1]-c[0]:.3f}) | {e[0]:.3f}-{e[1]:.3f} ({e[1]-e[0]:.3f}) | {c[0]-e[0]:+.3f} {c[1]-e[1]:+.3f} {(c[1]-c[0])-(e[1]-e[0]):+.3f}')
out.append('calc tau1 lower/upper boundary vs T: ' + ', '.join(f'{T}K {calc[(T,"TAU1")][0]:.3f}/{calc[(T,"TAU1")][1]:.3f}' for T in (1173, 1273, 1323, 1373, 1423, 1473, 1523, 1573)))
Ts = np.array([1173, 1373, 1573.0]); lo_exp = np.array([EXP[int(t)]['TAU1'][0] for t in Ts]); hi_exp = np.array([EXP[int(t)]['TAU1'][1] for t in Ts])
D = {}
for r in csv.DictReader(open(f'{d}/M0_D.tsv'), delimiter='\t'): D[(float(r['T_K']), float(r['x']))] = float(r['D_J_per_molatom'])
xs = [1.2, 1.4, 1.6, 1.8, 2.0]
out.append('\n== descriptor sensitivity (per-temperature bias; exp boundary LINEARLY INTERPOLATED between measured temperatures)')
out.append('T_K | exp_lo(interp) calc_lo d_lo | dD/dy | per x: dD_est (J/mol-atom), dD/D, class  [material >25 %, borderline 10-25 %, not <=10 %]')
for Tk in (1323.15, 1423.15, 1473.15):
    T = round(Tk)
    elo = float(np.interp(Tk, Ts, lo_exp)); clo = float(np.interp(Tk, [1323, 1373, 1423, 1473], [calc[(1323,'TAU1')][0], calc[(1373,'TAU1')][0], calc[(1423,'TAU1')][0], calc[(1473,'TAU1')][0]]))
    dy = clo - elo
    slope = (D[(Tk, 2.0)] - D[(Tk, 1.2)]) / ((2.0 - 1.2) / 13)
    cells = []
    for x in xs:
        dD = slope * dy; rel = abs(dD) / D[(Tk, x)]
        cls = 'MATERIAL' if rel > 0.25 else ('not material' if rel <= 0.10 else 'borderline')
        cells.append(f'x={x}: {dD:+.0f}, {100*rel:.0f} %, {cls}')
    out.append(f'{T} | {elo:.4f} {clo:.3f} {dy:+.4f} | {slope:.0f} | ' + ' ; '.join(cells))
open(f'{d}/addD_analysis.txt', 'w').write('\n'.join(out) + '\n'); print('\n'.join(out))
