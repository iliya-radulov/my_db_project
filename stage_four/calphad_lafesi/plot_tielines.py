"""
plot_tielines.py

Ternary plots of the transcribed Niitsu & Kainuma tie-lines, one per
temperature, for visual comparison with the paper's Fig. 3 (the plots must
look like that figure; if they do not, the transcription is wrong).
Orientation as in the paper: Fe bottom-left, Si bottom-right, La top.

  python plot_tielines.py [out_dir]       (default results/)
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from niitsu2012 import load_tielines

SQ3 = 3 ** 0.5 / 2


def tern(la, si):
    """(La, Si) in at.% -> plot coordinates (Fe origin, Si right, La top)."""
    return si / 100 + la / 200, la / 100 * SQ3


def main(out_dir='results'):
    out = Path(__file__).resolve().parent / out_dir
    out.mkdir(exist_ok=True)
    rows = load_tielines()
    for t_k in (1173, 1373, 1573):
        fig, ax = plt.subplots(figsize=(7.5, 7))
        for r in rows:
            if r['T_K'] != t_k:
                continue
            pts = [tern(la, si) for _, la, si in r['phases'] if la is not None]
            if len(pts) == 3:
                ax.fill(*zip(*(pts + [pts[0]])), alpha=0.18, color='tab:blue')
                ax.plot(*zip(*(pts + [pts[0]])), lw=0.8, color='tab:blue')
            elif len(pts) == 2:
                ax.plot(*zip(*pts), lw=1.0, color='tab:green')
            ax.plot(*zip(*pts), 'o', ms=3.5, color='k')
            ax.plot(*tern(r['nominal_La'], r['nominal_Si']), '+', ms=6,
                    color='tab:red', mew=1.2)
        ax.plot([0, 1, 0.5, 0], [0, 0, SQ3, 0], 'k-', lw=1.2)
        for (x, y), t in (((-0.03, -0.025), 'Fe'), ((1.01, -0.025), 'Si'), ((0.5, SQ3 + 0.02), 'La')):
            ax.text(x, y, t, fontsize=13, weight='bold')
        ax.set_title(f'Fe-La-Si {t_k} K: tie-lines transcribed from Niitsu & Kainuma (2012)\n'
                     'dots: measured phase compositions; crosses: nominal alloys; '
                     'triangles: three-phase equilibria', fontsize=9)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.tight_layout()
        path = out / f'tielines_{t_k}K.png'
        fig.savefig(path, dpi=140)
        plt.close(fig)
        print(path)


if __name__ == '__main__':
    main(*sys.argv[1:])
