#!/usr/bin/env python3
"""Plot dark-phase area (k = 4) vs annealing temperature and time, two independent fields per condition.
Usage: plot_dark_phase.py dark_phase_results_two_fields.csv out.png"""
import csv, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows = list(csv.DictReader(open(sys.argv[1])))
xs = [1.2, 1.4, 1.6, 1.8, 2.0]
cols = ['#1b6ca8', '#d95f02', '#1b9e77', '#7570b3', '#666666']
fig, ax = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
for panel, (series, key, lab) in enumerate([('temperature', 'T_C', 'Annealing temperature (°C)'),
                                            ('time', 't_h', 'Annealing time (h) at 1100 °C')]):
    a = ax[panel]
    for x, c in zip(xs, cols):
        pts = {}
        for r in rows:
            if r['series'] == series and float(r['x']) == x:
                pts.setdefault(float(r[key]), {})[r['source'][:7]] = float(r['area_pct_k4'])
        t = sorted(pts)
        a.plot(t, [sum(pts[k].values()) / len(pts[k]) for k in t], '-', color=c, lw=1.4, label=f'x = {x}')
        a.plot(t, [pts[k].get('field A') for k in t], 'o', color=c, ms=5)
        a.plot(t, [pts[k].get('field B') for k in t], '^', color=c, ms=5, mfc='none')
    a.set_xlabel(lab); a.set_xticks(sorted({float(r[key]) for r in rows if r['series'] == series})); a.grid(alpha=.25)
ax[0].set_ylabel('Dark-phase area (% of image)'); ax[0].legend(frameon=False, fontsize=9, loc='upper right')
ax[0].set_title('Temperature series (12 h per folder name; 2000×, 15 kV)', fontsize=10)
ax[1].set_title('Time series (2000×, 30 kV, half pixel density)', fontsize=10)
fig.text(.5, -.02, 'Line = mean of two fields at threshold k = 4. Circle = analysed set, open triangle = fields from the presentation decks. Dark phase not confirmed as α-Fe.',
         ha='center', fontsize=8)
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=160, bbox_inches='tight')
