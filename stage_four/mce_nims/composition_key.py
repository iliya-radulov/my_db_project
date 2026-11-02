"""
composition_key.py

One composition key for every source (roadmap §4 step A), so that a
literature record and one of the lab's own samples with the same
composition can be found with a plain SQL join.

Rule:
  - H, C, N and B count as interstitials. Everything else is a "metal"
    (host-lattice) element.
  - Metal elements are normalised to 100 at.% among themselves.
  - Interstitials are given in at.% relative to the metal total (the NIMS
    convention: H = 3.57 for La(Fe,Si)13H0.5, i.e. 0.5 / 14 * 100).
  - Elements are sorted alphabetically within each part; values are
    rounded to 0.1 at.%.

  {"La": 7.14, "Fe": 81.43, "Si": 11.43}            -> "Fe81.4-La7.1-Si11.4"
  same + {"H": 3.57}                                 -> "Fe81.4-La7.1-Si11.4+H3.6"

The rule is applied the same way to every source, including Nd–Fe–B
samples (B then appears after '+'). The key is for exact matches; near
matches (e.g. EDX vs nominal composition) use composition_distance().

0.1 at.% resolves the composition steps that matter here: one step of
0.1 in x for LaFe(13-x)M(x) is 0.71 at.%. Two compositions that straddle
a rounding boundary get different keys even if they differ by 0.01 at.% --
which is why near matches are reported separately.
"""
INTERSTITIALS = ('H', 'C', 'N', 'B')
DECIMALS = 1
ELEMENTS = set('''H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co
Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba
La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At
Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr'''.split())


def split_composition(composition):
    """Any element -> amount mapping (fractions, at.%, or formula units)
    -> (metal at.% summing to 100, interstitial at.% relative to metals).
    Raises ValueError on negative amounts or no metal element."""
    comp = {str(e).strip(): float(v) for e, v in composition.items() if v is not None and float(v) != 0.0}
    unknown = [e for e in comp if e not in ELEMENTS]
    if unknown:
        # e.g. the GUI's {'placeholder': 1.0} for samples created by a file import
        raise ValueError(f"not element symbols: {unknown}")
    if any(v < 0 for v in comp.values()):
        raise ValueError(f"negative amount in {composition}")
    metals = {e: v for e, v in comp.items() if e not in INTERSTITIALS}
    total = sum(metals.values())
    if total <= 0:
        raise ValueError(f"no metal element in {composition}")
    metal_pct = {e: 100.0 * v / total for e, v in metals.items()}
    inter_pct = {e: 100.0 * v / total for e, v in comp.items() if e in INTERSTITIALS}
    return metal_pct, inter_pct


def composition_key(composition, interstitials=None, decimals=DECIMALS):
    """Canonical key. Either pass one mapping with all elements, or the
    metal part and the interstitial part separately (the latter already in
    at.% relative to the metals, as stored by the NIMS import)."""
    if interstitials is None:
        metal_pct, inter_pct = split_composition(composition)
    else:
        metal_pct, _ = split_composition(composition)
        inter_pct = {e: float(v) for e, v in interstitials.items() if v}

    def fmt(part):
        items = [(e, round(v, decimals)) for e, v in sorted(part.items())]
        return '-'.join(f"{e}{v:.{decimals}f}" for e, v in items if v != 0)

    key = fmt(metal_pct)
    if inter_pct and fmt(inter_pct):
        key += '+' + fmt(inter_pct)
    return key


def composition_distance(a, b):
    """Largest difference in at.% over all elements of two compositions
    (same metal/interstitial split as the key). 0.0 = identical."""
    ma, ia = split_composition(a)
    mb, ib = split_composition(b)
    diffs = [abs(ma.get(e, 0) - mb.get(e, 0)) for e in set(ma) | set(mb)]
    diffs += [abs(ia.get(e, 0) - ib.get(e, 0)) for e in set(ia) | set(ib)]
    return max(diffs) if diffs else 0.0


if __name__ == '__main__':
    checks = [
        ({'La': 7.14, 'Fe': 81.43, 'Si': 11.43}, 'Fe81.4-La7.1-Si11.4'),
        ({'La': 1, 'Fe': 11.4, 'Si': 1.6}, 'Fe81.4-La7.1-Si11.4'),                 # formula units
        ({'La': 1 / 14, 'Fe': 11.4 / 14, 'Si': 1.6 / 14}, 'Fe81.4-La7.1-Si11.4'),   # fractions
        ({'La': 1, 'Fe': 11.44, 'Si': 1.56, 'H': 0.5}, 'Fe81.7-La7.1-Si11.1+H3.6'),
        ({'Nd': 2, 'Fe': 14, 'B': 1}, 'Fe87.5-Nd12.5+B6.2'),
    ]
    for comp, expected in checks:
        got = composition_key(comp)
        assert got == expected, (comp, got, expected)
    assert composition_key({'La': 7.14, 'Fe': 81.43, 'Si': 11.43}, {'H': 3.57}) == 'Fe81.4-La7.1-Si11.4+H3.6'
    assert composition_distance({'La': 1, 'Fe': 11.6, 'Si': 1.4}, {'La': 1, 'Fe': 11.5, 'Si': 1.5}) < 0.72
    for bad in ({'placeholder': 1.0}, {}, {'H': 1.0}, {'Fe': -1.0}):
        try:
            composition_key(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} should be rejected")
    print("composition_key self-test passed")
