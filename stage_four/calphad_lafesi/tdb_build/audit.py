"""
audit.py — validate the reconstructed TDB against the frozen acceptance
test (FROZEN_SPEC.md §4) and compute the WP4 descriptor.

  python audit.py            # runs A1-A5, computes dG_f, writes the section plot
"""
import os
import numpy as np
import sympy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pycalphad import Database, equilibrium, variables as v

HERE = os.path.dirname(os.path.abspath(__file__))
TDB = os.path.join(HERE, 'LaFeSi_feng2023.tdb')
T = sympy.Symbol('T')
COMPS = ['LA', 'FE', 'SI', 'VA']
XLA, XFE, XSI = 1/14, 11.5/14, 1.5/14          # frozen La(Fe11.5Si1.5)
UNARY_REF = {'GHSERLA': [-70980.2, -119873.4], 'GHSERFE': [-41450.4, -80562.9],
             'GHSERSI': [-30381.7, -56966.0]}


def stable(db, phases, xLa, xSi, Tk=1373, thr=0.01):
    eq = equilibrium(db, COMPS, phases,
                     {v.X('LA'): xLa, v.X('SI'): xSi, v.T: Tk, v.P: 101325, v.N: 1},
                     calc_opts={'pdens': 2000})
    ph = np.array(eq.Phase).ravel()
    npf = np.array(eq.NP).ravel()
    out = {}
    for p, n in zip(ph, npf):
        if p and str(p) not in ('nan', '') and not np.isnan(n) and n > thr:
            out[str(p)] = out.get(str(p), 0.0) + float(n)
    return out, float(np.array(eq.GM).ravel()[0])


def main():
    db = Database(TDB)
    phases = list(db.phases.keys())
    print(f"A1 parse+compute: {len(phases)} phases loaded")

    print("\nA2 unary consistency (numeric, 1000/1500 K):")
    for n, exp in UNARY_REF.items():
        got = [round(float(sympy.sympify(db.symbols[n]).xreplace({T: TT})), 1) for TT in (1000, 1500)]
        print(f"   {n}: {got} {'OK' if got == exp else 'MISMATCH'}")

    print("\nA3 tau1 at frozen point La(Fe11.5Si1.5) 1373 K:")
    d, gm = stable(db, phases, XLA, XSI)
    print(f"   {d}  -> {'PASS' if d.get('TAU1', 0) > 0.99 else 'CHECK'}")

    print("\nA4 Feng Table 4 tau1-bearing alloys:")
    feng = {10: (9, 66, 25, 'tau3,tau1'), 11: (7, 78, 15, 'tau1,aFe,tau5'),
            13: (7, 71, 22, 'tau1,tau2,tau3'), 17: (6, 75, 19, 'tau1,aFe'),
            21: (9, 71, 20, 'tau3,tau1')}
    for a, (la, fe, si, rep) in feng.items():
        d, _ = stable(db, phases, la/100, si/100)
        print(f"   #{a}: reported[{rep}] computed[{', '.join(sorted(d))}]")

    print("\nA5 tau1/tau2 window along La(Fe1-xSix)13, 1373 K (lit: tau1 0.096-0.229, tau2 0.266+):")
    for xs in [0.08, 0.10, 0.15, 0.20, 0.23, 0.27, 0.30]:
        d, _ = stable(db, phases, 1/14, (13*xs)/14)
        print(f"   x={xs:.2f}: {', '.join(f'{k}:{v:.2f}' for k, v in sorted(d.items()))}")

    print("\nWP4 descriptor dG_f(tau1) at La(Fe11.5Si1.5) vs SER elements:")
    for Tann in (1173, 1273, 1373, 1473):
        d, gm = stable(db, phases, XLA, XSI, Tann)
        gser = {n: float(sympy.sympify(db.symbols[n]).xreplace({T: Tann}))
                for n in ('GHSERLA', 'GHSERFE', 'GHSERSI')}
        ref = XLA*gser['GHSERLA'] + XFE*gser['GHSERFE'] + XSI*gser['GHSERSI']
        single = 'TAU1' if d.get('TAU1', 0) > 0.99 else '+'.join(sorted(d))
        print(f"   T={Tann}K: dG_f={gm-ref:9.1f} J/mol-atom   ({single})")

    section_plot(db, phases)


def section_plot(db, phases, Tk=1373):
    sq3 = 3 ** 0.5 / 2
    fig, ax = plt.subplots(figsize=(8, 7))
    labels = {}
    step = 0.035
    for xfe in np.arange(0.02, 0.98, step):
        for xsi in np.arange(0.02, 0.98 - xfe, step):
            xla = 1 - xfe - xsi
            if xla < 0.01:
                continue
            d, _ = stable(db, phases, xla, xsi, Tk, thr=0.02)
            key = '+'.join(sorted(d))
            labels.setdefault(key, []).append((xsi + xla/2, xla*sq3))
    cmap = plt.get_cmap('tab20', max(len(labels), 1))
    for i, (key, pts) in enumerate(sorted(labels.items())):
        xs, ys = zip(*pts)
        ax.scatter(xs, ys, s=16, color=cmap(i), label=key[:42] or 'none')
    ax.plot([0, 1, 0.5, 0], [0, 0, sq3, 0], 'k-', lw=1.2)
    for (x, y), t in (((-0.03, -0.03), 'Fe'), ((1.01, -0.03), 'Si'), ((0.5, sq3+0.02), 'La')):
        ax.text(x, y, t, fontsize=13, weight='bold')
    ax.set_title(f'La-Fe-Si {Tk} K, reconstructed from Feng et al. (2023)\n'
                 'tau1/tau2 + solution + compounds (tau3-tau6 deferred)', fontsize=9)
    ax.legend(fontsize=5, loc='upper right', ncol=2)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.tight_layout()
    out = os.path.join(HERE, f'section_{Tk}K.png')
    fig.savefig(out, dpi=130)
    print(f"\nwrote {out}")


if __name__ == '__main__':
    main()
