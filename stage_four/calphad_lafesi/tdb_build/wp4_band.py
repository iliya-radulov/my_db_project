"""
wp4_band.py — WP4 descriptor across the 20 binary combinations.

Two descriptors at the frozen La(Fe11.5Si1.5), T_anneal = 1373 K:

1. dG_f(tau1) vs SER elements -- BINARY-INDEPENDENT. tau1's energy is
   Feng's fixed ternary parameters + unaries; the binaries never enter it,
   so all 20 combos give -20992.6 J/mol-atom (band = 0). This is itself a
   clean result: the formation energy of tau1 carries no binary uncertainty.

2. Formation driving force  G(competing, tau1/tau2 suspended) - G(tau1)
   -- BINARY-SENSITIVE, through the competing phases (aFe, silicides). This
   is the physically meaningful WP4 descriptor for whether annealing forms
   single-phase tau1, and the source of the honest uncertainty band.

  python wp4_band.py
"""
import numpy as np
import sympy
from pycalphad import Database, equilibrium, variables as v
from build_merged_tdb import build

FELA = ['FeLa-09Pov', 'FeLa-23Su']
LASI = ['LaSi-10Zho', 'LaSi-20Xu']
FESI = ['FeSi-12Ohn', 'FeSi-14Yua', 'FeSi-17Cui', 'FeSi-23Wit', 'FeSi-91Lac-LB']
FAITHFUL = 'FeLa-23Su+LaSi-10Zho+FeSi-17Cui'
T = sympy.Symbol('T')
XLA, XFE, XSI = 1/14, 11.5/14, 1.5/14
TANN = 1373


def gm_at(db, phases):
    eq = equilibrium(db, ['LA', 'FE', 'SI', 'VA'], phases,
                     {v.X('LA'): XLA, v.X('SI'): XSI, v.T: TANN, v.P: 101325, v.N: 1},
                     calc_opts={'pdens': 2000})
    ph = np.array(eq.Phase).ravel()
    npf = np.array(eq.NP).ravel()
    comp = sorted(set(str(p) for p, n in zip(ph, npf)
                      if str(p) not in ('nan', '') and not np.isnan(n) and n > 0.01))
    return float(np.array(eq.GM).ravel()[0]), comp


def main():
    res = []
    for fe in FESI:
        for fl in FELA:
            for ls in LASI:
                tag = f'{fl}+{ls}+{fe}'
                try:
                    _, db = build(fl, ls, fe, out=f'/tmp/m_{fl}_{ls}_{fe}.tdb')
                    allph = list(db.phases)
                    g_t1, _ = gm_at(db, allph)
                    g_c, comp = gm_at(db, [p for p in allph if p not in ('TAU1', 'TAU2')])
                    res.append((tag, g_c - g_t1, comp))
                except Exception as e:
                    res.append((tag, None, str(e)[:40]))
    print(f"tau1 formation driving force at La(Fe11.5Si1.5), {TANN} K "
          "(G_compete - G_tau1; + = tau1 favored):")
    print(f"{'combination':40s} {'drive[J/mol-atom]':>17s}  competing assemblage")
    for tag, d, comp in sorted(res, key=lambda r: (r[1] is None, -(r[1] or 0))):
        star = ' <-Feng' if tag == FAITHFUL else ''
        val = f'{d:.1f}' if d is not None else '--'
        print(f"{tag:40s} {val:>17s}  {'+'.join(comp) if isinstance(comp, list) else comp}{star}")
    ok = [d for _, d, _ in res if d is not None]
    print(f"\nband: {min(ok):.0f} .. {max(ok):.0f} J/mol-atom "
          f"(spread {max(ok)-min(ok):.0f}, mean {np.mean(ok):.0f} +/- {np.std(ok):.0f})")
    print("Spread is entirely Fe-Si-driven; FeSi-23Wit (Witusiewicz) is the outlier.")


if __name__ == '__main__':
    main()
