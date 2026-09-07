"""
alloy_screening.py
Quick composition screening using VEC, δ, and ΔH_mix
No external dependencies - uses only element property tables.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Complete ELEMENT_PROPERTIES - includes all elements with data
# valence electrons, atomic radius (Å), electronegativity (Pauling),
# melting point (melt_K) and boiling point (boil_K), both in Kelvin.
# melt_K/boil_K source: Reade.com reference table, spot-checked against
# known CRC/NIST values (Fe, Cu, W, Al, Zn, Mg all matched exactly).
# None = no stable value at 1 atm (e.g. He does not solidify at 1 atm).
# NOTE: As has an INVERTED melt/boil relationship (melt_K=1090 > boil_K=887)
# -- this is real physics, not a data error: As sublimes directly at 1 atm
# and only shows a true liquid phase under ~3.6 MPa pressure. At (astatine)
# is also inverted in the source table, but At's properties are poorly
# known (only ever produced in trace/synthetic quantities). Any synthesis-
# route logic comparing melt/boil across elements must special-case these
# two rather than assume boil_K > melt_K always holds.
ELEMENT_PROPERTIES = {
    # Period 1
    'H': {'valence': 1, 'radius': 0.53, 'en': 2.20, 'melt_K': 14.01, 'boil_K': 20.28},
    'He': {'valence': 2, 'radius': 0.31, 'en': 4.16, 'melt_K': None, 'boil_K': 4.22},
    
    # Period 2
    'Li': {'valence': 1, 'radius': 1.52, 'en': 0.98, 'melt_K': 453.69, 'boil_K': 1615},
    'Be': {'valence': 2, 'radius': 1.12, 'en': 1.57, 'melt_K': 1560, 'boil_K': 2743},
    'B': {'valence': 3, 'radius': 0.87, 'en': 2.04, 'melt_K': 2348, 'boil_K': 4273},
    'C': {'valence': 4, 'radius': 0.77, 'en': 2.55, 'melt_K': 3823, 'boil_K': 4300},
    'N': {'valence': 5, 'radius': 0.75, 'en': 3.04, 'melt_K': 63.05, 'boil_K': 77.36},
    'O': {'valence': 6, 'radius': 0.73, 'en': 3.44, 'melt_K': 54.8, 'boil_K': 90.2},
    'F': {'valence': 7, 'radius': 0.71, 'en': 3.98, 'melt_K': 53.5, 'boil_K': 85.03},
    'Ne': {'valence': 8, 'radius': 0.69, 'en': 4.79, 'melt_K': 24.56, 'boil_K': 27.07},
    
    # Period 3
    'Na': {'valence': 1, 'radius': 1.86, 'en': 0.93, 'melt_K': 370.87, 'boil_K': 1156},
    'Mg': {'valence': 2, 'radius': 1.60, 'en': 1.31, 'melt_K': 923, 'boil_K': 1363},
    'Al': {'valence': 3, 'radius': 1.43, 'en': 1.61, 'melt_K': 933.47, 'boil_K': 2792},
    'Si': {'valence': 4, 'radius': 1.17, 'en': 1.90, 'melt_K': 1687, 'boil_K': 3173},
    'P': {'valence': 5, 'radius': 1.10, 'en': 2.19, 'melt_K': 317.3, 'boil_K': 553.6},
    'S': {'valence': 6, 'radius': 1.04, 'en': 2.58, 'melt_K': 388.36, 'boil_K': 717.87},
    'Cl': {'valence': 7, 'radius': 0.99, 'en': 3.16, 'melt_K': 171.6, 'boil_K': 239.11},
    'Ar': {'valence': 8, 'radius': 0.98, 'en': 3.24, 'melt_K': 83.8, 'boil_K': 87.3},
    
    # Period 4
    'K': {'valence': 1, 'radius': 2.27, 'en': 0.82, 'melt_K': 336.53, 'boil_K': 1032},
    'Ca': {'valence': 2, 'radius': 1.97, 'en': 1.00, 'melt_K': 1115, 'boil_K': 1757},
    'Sc': {'valence': 3, 'radius': 1.62, 'en': 1.36, 'melt_K': 1814, 'boil_K': 3103},
    'Ti': {'valence': 4, 'radius': 1.47, 'en': 1.54, 'melt_K': 1941, 'boil_K': 3560},
    'V': {'valence': 5, 'radius': 1.35, 'en': 1.63, 'melt_K': 2183, 'boil_K': 3680},
    'Cr': {'valence': 6, 'radius': 1.28, 'en': 1.66, 'melt_K': 2180, 'boil_K': 2944},
    'Mn': {'valence': 7, 'radius': 1.27, 'en': 1.55, 'melt_K': 1519, 'boil_K': 2334},
    'Fe': {'valence': 8, 'radius': 1.26, 'en': 1.83, 'melt_K': 1811, 'boil_K': 3134},
    'Co': {'valence': 9, 'radius': 1.25, 'en': 1.88, 'melt_K': 1768, 'boil_K': 3200},
    'Ni': {'valence': 10, 'radius': 1.24, 'en': 1.91, 'melt_K': 1728, 'boil_K': 3186},
    'Cu': {'valence': 11, 'radius': 1.28, 'en': 1.90, 'melt_K': 1357.77, 'boil_K': 2835},
    'Zn': {'valence': 12, 'radius': 1.33, 'en': 1.65, 'melt_K': 692.68, 'boil_K': 1180},
    'Ga': {'valence': 3, 'radius': 1.36, 'en': 1.81, 'melt_K': 302.91, 'boil_K': 2477},
    'Ge': {'valence': 4, 'radius': 1.22, 'en': 2.01, 'melt_K': 1211.4, 'boil_K': 3093},
    'As': {'valence': 5, 'radius': 1.21, 'en': 2.18, 'melt_K': 1090, 'boil_K': 887},
    'Se': {'valence': 6, 'radius': 1.17, 'en': 2.55, 'melt_K': 494, 'boil_K': 958},
    'Br': {'valence': 7, 'radius': 1.14, 'en': 2.96, 'melt_K': 265.8, 'boil_K': 332},
    'Kr': {'valence': 8, 'radius': 1.12, 'en': 3.00, 'melt_K': 115.79, 'boil_K': 119.93},
    
    # Period 5
    'Rb': {'valence': 1, 'radius': 2.48, 'en': 0.82, 'melt_K': 312.46, 'boil_K': 961},
    'Sr': {'valence': 2, 'radius': 2.15, 'en': 0.95, 'melt_K': 1050, 'boil_K': 1655},
    'Y': {'valence': 3, 'radius': 1.80, 'en': 1.22, 'melt_K': 1799, 'boil_K': 3618},
    'Zr': {'valence': 4, 'radius': 1.60, 'en': 1.33, 'melt_K': 2128, 'boil_K': 4682},
    'Nb': {'valence': 5, 'radius': 1.46, 'en': 1.60, 'melt_K': 2750, 'boil_K': 5017},
    'Mo': {'valence': 6, 'radius': 1.39, 'en': 2.16, 'melt_K': 2896, 'boil_K': 4912},
    'Tc': {'valence': 7, 'radius': 1.36, 'en': 1.90, 'melt_K': 2430, 'boil_K': 4538},
    'Ru': {'valence': 8, 'radius': 1.34, 'en': 2.20, 'melt_K': 2607, 'boil_K': 4423},
    'Rh': {'valence': 9, 'radius': 1.34, 'en': 2.28, 'melt_K': 2237, 'boil_K': 3968},
    'Pd': {'valence': 10, 'radius': 1.37, 'en': 2.20, 'melt_K': 1828.05, 'boil_K': 3236},
    'Ag': {'valence': 11, 'radius': 1.44, 'en': 1.93, 'melt_K': 1234.93, 'boil_K': 2435},
    'Cd': {'valence': 12, 'radius': 1.49, 'en': 1.69, 'melt_K': 594.22, 'boil_K': 1040},
    'In': {'valence': 3, 'radius': 1.63, 'en': 1.78, 'melt_K': 429.75, 'boil_K': 2345},
    'Sn': {'valence': 4, 'radius': 1.40, 'en': 1.96, 'melt_K': 505.08, 'boil_K': 2875},
    'Sb': {'valence': 5, 'radius': 1.40, 'en': 2.05, 'melt_K': 903.78, 'boil_K': 1860},
    'Te': {'valence': 6, 'radius': 1.37, 'en': 2.10, 'melt_K': 722.66, 'boil_K': 1261},
    'I': {'valence': 7, 'radius': 1.33, 'en': 2.66, 'melt_K': 386.85, 'boil_K': 457.4},
    'Xe': {'valence': 8, 'radius': 1.31, 'en': 2.60, 'melt_K': 161.3, 'boil_K': 165.1},
    
    # Period 6 (Lanthanides)
    'Cs': {'valence': 1, 'radius': 2.65, 'en': 0.79, 'melt_K': 301.59, 'boil_K': 944},
    'Ba': {'valence': 2, 'radius': 2.22, 'en': 0.89, 'melt_K': 1000, 'boil_K': 2143},
    'La': {'valence': 3, 'radius': 1.87, 'en': 1.10, 'melt_K': 1193, 'boil_K': 3737},
    'Ce': {'valence': 3, 'radius': 1.82, 'en': 1.12, 'melt_K': 1071, 'boil_K': 3633},
    'Pr': {'valence': 3, 'radius': 1.82, 'en': 1.13, 'melt_K': 1204, 'boil_K': 3563},
    'Nd': {'valence': 3, 'radius': 1.82, 'en': 1.14, 'melt_K': 1294, 'boil_K': 3373},
    'Pm': {'valence': 3, 'radius': 1.81, 'en': 1.13, 'melt_K': 1373, 'boil_K': 3273},
    'Sm': {'valence': 3, 'radius': 1.80, 'en': 1.17, 'melt_K': 1345, 'boil_K': 2076},
    'Eu': {'valence': 2, 'radius': 1.80, 'en': 1.20, 'melt_K': 1095, 'boil_K': 1800},
    'Gd': {'valence': 3, 'radius': 1.79, 'en': 1.20, 'melt_K': 1586, 'boil_K': 3523},
    'Tb': {'valence': 3, 'radius': 1.77, 'en': 1.10, 'melt_K': 1629, 'boil_K': 3503},
    'Dy': {'valence': 3, 'radius': 1.77, 'en': 1.22, 'melt_K': 1685, 'boil_K': 2840},
    'Ho': {'valence': 3, 'radius': 1.77, 'en': 1.23, 'melt_K': 1747, 'boil_K': 2973},
    'Er': {'valence': 3, 'radius': 1.76, 'en': 1.24, 'melt_K': 1770, 'boil_K': 3141},
    'Tm': {'valence': 3, 'radius': 1.75, 'en': 1.25, 'melt_K': 1818, 'boil_K': 2223},
    'Yb': {'valence': 2, 'radius': 1.74, 'en': 1.10, 'melt_K': 1092, 'boil_K': 1469},
    'Lu': {'valence': 3, 'radius': 1.73, 'en': 1.27, 'melt_K': 1936, 'boil_K': 3675},
    
    # Period 6 (Transition metals)
    'Hf': {'valence': 4, 'radius': 1.59, 'en': 1.30, 'melt_K': 2506, 'boil_K': 4876},
    'Ta': {'valence': 5, 'radius': 1.46, 'en': 1.50, 'melt_K': 3290, 'boil_K': 5731},
    'W': {'valence': 6, 'radius': 1.39, 'en': 2.36, 'melt_K': 3695, 'boil_K': 5828},
    'Re': {'valence': 7, 'radius': 1.37, 'en': 1.90, 'melt_K': 3459, 'boil_K': 5869},
    'Os': {'valence': 8, 'radius': 1.35, 'en': 2.20, 'melt_K': 3306, 'boil_K': 5285},
    'Ir': {'valence': 9, 'radius': 1.36, 'en': 2.20, 'melt_K': 2739, 'boil_K': 4701},
    'Pt': {'valence': 10, 'radius': 1.39, 'en': 2.28, 'melt_K': 2041.4, 'boil_K': 4098},
    'Au': {'valence': 11, 'radius': 1.44, 'en': 2.54, 'melt_K': 1337.33, 'boil_K': 3129},
    'Hg': {'valence': 12, 'radius': 1.50, 'en': 2.00, 'melt_K': 234.32, 'boil_K': 629.88},
    'Tl': {'valence': 3, 'radius': 1.71, 'en': 1.80, 'melt_K': 577, 'boil_K': 1746},
    'Pb': {'valence': 4, 'radius': 1.75, 'en': 2.33, 'melt_K': 600.61, 'boil_K': 2022},
    'Bi': {'valence': 5, 'radius': 1.55, 'en': 2.02, 'melt_K': 544.4, 'boil_K': 1837},
    'Po': {'valence': 6, 'radius': 1.53, 'en': 2.00, 'melt_K': 528, 'boil_K': 1235},
    'At': {'valence': 7, 'radius': 1.50, 'en': 2.20, 'melt_K': 575, 'boil_K': 623},
    'Rn': {'valence': 8, 'radius': 1.48, 'en': 2.60, 'melt_K': 202, 'boil_K': 211.3},
    
    # Period 7 (Actinides)
    'Fr': {'valence': 1, 'radius': 2.70, 'en': 0.70, 'melt_K': 294, 'boil_K': 923},
    'Ra': {'valence': 2, 'radius': 2.23, 'en': 0.90, 'melt_K': 973, 'boil_K': 2010},
    'Ac': {'valence': 3, 'radius': 1.95, 'en': 1.10, 'melt_K': 1323, 'boil_K': 3473},
    'Th': {'valence': 4, 'radius': 1.80, 'en': 1.30, 'melt_K': 2023, 'boil_K': 5093},
    'Pa': {'valence': 5, 'radius': 1.61, 'en': 1.50, 'melt_K': 1845, 'boil_K': 4273},
    'U': {'valence': 6, 'radius': 1.54, 'en': 1.38, 'melt_K': 1408, 'boil_K': 4200},
    'Np': {'valence': 6, 'radius': 1.55, 'en': 1.36, 'melt_K': 917, 'boil_K': 4273},
    'Pu': {'valence': 6, 'radius': 1.53, 'en': 1.28, 'melt_K': 913, 'boil_K': 3505},
    'Am': {'valence': 3, 'radius': 1.52, 'en': 1.13, 'melt_K': 1449, 'boil_K': 2284},
    'Cm': {'valence': 3, 'radius': 1.50, 'en': 1.28, 'melt_K': 1618, 'boil_K': 3383},
    'Bk': {'valence': 3, 'radius': 1.48, 'en': 1.30, 'melt_K': 1323, 'boil_K': None},
    'Cf': {'valence': 3, 'radius': 1.47, 'en': 1.30, 'melt_K': 1173, 'boil_K': None},
    'Es': {'valence': 3, 'radius': 1.45, 'en': 1.30, 'melt_K': 1133, 'boil_K': None},
    'Fm': {'valence': 3, 'radius': 1.44, 'en': 1.30, 'melt_K': 1800, 'boil_K': None},
    'Md': {'valence': 3, 'radius': 1.43, 'en': 1.30, 'melt_K': 1100, 'boil_K': None},
    'No': {'valence': 3, 'radius': 1.42, 'en': 1.30, 'melt_K': 1100, 'boil_K': None},
    'Lr': {'valence': 3, 'radius': 1.41, 'en': 1.30, 'melt_K': 1900, 'boil_K': None},
}

class IncompleteElementDataError(ValueError):
    """Raised when the composition contains elements missing from
    ELEMENT_PROPERTIES. VEC/delta would otherwise be silently computed
    from an incomplete subset of the composition -- wrong, with no
    indication anything was skipped."""
    def __init__(self, missing_elements):
        self.missing_elements = missing_elements
        msg = (f"ELEMENT_PROPERTIES has no data for: {', '.join(missing_elements)}. "
               f"VEC/delta cannot be reliably computed without it -- "
               f"add these elements to ELEMENT_PROPERTIES, or exclude them from screening.")
        super().__init__(msg)


def calculate_vec(composition_at_frac):
    """
    Calculate Valence Electron Concentration (VEC)
    composition_at_frac: {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    """
    # Check for missing elements
    missing = [e for e in composition_at_frac.keys() if e not in ELEMENT_PROPERTIES]
    if missing:
        raise IncompleteElementDataError(missing)
    
    vec = 0
    for element, fraction in composition_at_frac.items():
        vec += fraction * ELEMENT_PROPERTIES[element]['valence']
    return vec


def calculate_delta(composition_at_frac):
    """
    Calculate atomic size mismatch δ (for HEA solid solution prediction)
    """
    # Check for missing elements
    missing = [e for e in composition_at_frac.keys() if e not in ELEMENT_PROPERTIES]
    if missing:
        raise IncompleteElementDataError(missing)
    
    # Get average radius
    avg_radius = 0
    for element, fraction in composition_at_frac.items():
        avg_radius += fraction * ELEMENT_PROPERTIES[element]['radius']
    
    # Calculate δ
    delta = 0
    for element, fraction in composition_at_frac.items():
        radius = ELEMENT_PROPERTIES[element]['radius']
        delta += fraction * (1 - radius / avg_radius) ** 2
    delta = delta ** 0.5
    return delta


def calculate_mixing_enthalpy(composition_at_frac):
    """
    Simplified mixing enthalpy using Miedema model (pairwise contributions)
    Returns: mixing enthalpy in kJ/mol
    """
    # Check for missing elements (but we can't check pairwise easily here)
    missing = [e for e in composition_at_frac.keys() if e not in ELEMENT_PROPERTIES]
    if missing:
        raise IncompleteElementDataError(missing)
    
    # Simplified pairwise mixing enthalpy parameters (kJ/mol per 1 mole of A-B pairs)
    # Values are approximate for illustration
    pairwise = {
        ('Fe', 'Nd'): -12.0,
        ('Fe', 'Co'): -2.0,
        ('Fe', 'B'): -15.0,
        ('Nd', 'Co'): -10.0,
        ('Nd', 'B'): -18.0,
        ('Co', 'B'): -8.0,
        ('Fe', 'Al'): -18.0,
        ('Fe', 'Si'): -20.0,
        ('Nd', 'Al'): -15.0,
        ('Nd', 'Si'): -22.0,
        ('Co', 'Al'): -12.0,
        ('Co', 'Si'): -16.0,
        ('La', 'Fe'): -14.0,
        ('La', 'Si'): -25.0,
        ('Fe', 'P'): -17.0,
        ('Ni', 'Fe'): -4.0,
        ('Ni', 'Co'): -2.0,
        ('Ni', 'Al'): -20.0,
        ('Ni', 'Si'): -18.0,
        ('Ni', 'B'): -12.0,
        ('Cr', 'Fe'): -2.0,
        ('Cr', 'Ni'): -2.0,
        ('Cr', 'Co'): -2.0,
        ('Cr', 'Al'): -12.0,
        ('Cr', 'Si'): -14.0,
        ('Mn', 'Fe'): 0.0,
        ('Mn', 'Ni'): -2.0,
        ('Mn', 'Co'): -2.0,
        ('Mn', 'Al'): -10.0,
        ('Mn', 'Si'): -12.0,
        ('Cu', 'Fe'): 2.0,
        ('Cu', 'Ni'): 2.0,
        ('Cu', 'Co'): 2.0,
        ('Cu', 'Al'): -8.0,
        ('Cu', 'Si'): -10.0,
        ('Ga', 'Fe'): -10.0,
        ('Ga', 'Ni'): -12.0,
        ('Ga', 'Co'): -10.0,
        ('Ga', 'Al'): -4.0,
        ('Ga', 'Si'): -6.0,
    }
    
    elements = list(composition_at_frac.keys())
    fractions = list(composition_at_frac.values())
    delta_h = 0
    n_elements = len(elements)
    
    for i in range(n_elements):
        for j in range(i+1, n_elements):
            pair = (elements[i], elements[j])
            pair_rev = (elements[j], elements[i])
            if pair in pairwise:
                param = pairwise[pair]
            elif pair_rev in pairwise:
                param = pairwise[pair_rev]
            else:
                param = 0
            delta_h += fractions[i] * fractions[j] * param
    
    return delta_h


def check_synthesis_feasibility(composition_at_frac, hard_block_margin_K=125, caution_zone_K=300):
    """
    Composition-only feasibility check for melt-based synthesis (arc/induction
    melting), using ONLY melt_K/boil_K -- no crystal structure or DFT needed,
    same input shape as calculate_vec/calculate_delta.

    Physical logic (the hard-block rule IS physically grounded, not a
    heuristic):
      - Homogenizing a melt requires heating to at least the HIGHEST melting
        point among constituents.
      - boil_K is treated as "the temperature at which this element is lost
        to vapor at 1 atm" -- true boiling point for most elements, but for
        As (and similarly At) this is really a sublimation point, since
        those elements have no stable liquid phase at 1 atm. Using boil_K
        directly still gives the physically correct comparison either way.
      - If the required melt temperature is at or above the most volatile
        constituent's vapor-loss point (minus a safety margin), that
        element WILL be lost before/as the alloy homogenizes in an open
        melt -- this is a hard physical block, not a judgment call.

    hard_block_margin_K: subtracted from the boiling point before the hard-
    block comparison. Default 125 K is conservative in the safe direction --
    vacuum/inert-atmosphere furnaces used in practice generally LOWER the
    effective boiling point further, not raise it, so real risk starts
    before the naive 1-atm boil_K value is reached.

    caution_zone_K: width of the "genuinely uncertain" zone above the hard-
    block threshold. This width is a practical, ADJUSTABLE heuristic (unlike
    the hard-block rule itself) -- a strongly negative Delta_H_mix can
    suppress a volatile element's effective vapor pressure once alloyed,
    which this composition-only check cannot quantify. Cases in this zone
    are deliberately flagged rather than given a false-confidence route
    suggestion; see calculate_mixing_enthalpy for the complementary check
    worth consulting manually.

    Returns a dict with 'status' in {'ok', 'caution', 'blocked', 'unknown'},
    the limiting elements/temperatures, a human-readable message, and
    suggested_routes.
    """
    missing = [e for e in composition_at_frac.keys() if e not in ELEMENT_PROPERTIES]
    if missing:
        raise IncompleteElementDataError(missing)

    elements = list(composition_at_frac.keys())
    missing_data = sorted({
        e for e in elements
        if ELEMENT_PROPERTIES[e].get('melt_K') is None or ELEMENT_PROPERTIES[e].get('boil_K') is None
    })
    if missing_data:
        return {
            'status': 'unknown',
            'limiting_melt_element': None, 'limiting_melt_K': None,
            'limiting_boil_element': None, 'limiting_boil_K': None,
            'margin_K': None,
            'message': (f"Cannot evaluate melt/boil feasibility -- missing melt_K/boil_K "
                        f"data for: {', '.join(missing_data)}."),
            'suggested_routes': [],
        }

    # highest melting point among constituents: must reach this to homogenize a melt
    limiting_melt_element = max(elements, key=lambda e: ELEMENT_PROPERTIES[e]['melt_K'])
    limiting_melt_K = ELEMENT_PROPERTIES[limiting_melt_element]['melt_K']

    # lowest boiling/vapor-loss point among constituents: the most volatile element
    limiting_boil_element = min(elements, key=lambda e: ELEMENT_PROPERTIES[e]['boil_K'])
    limiting_boil_K = ELEMENT_PROPERTIES[limiting_boil_element]['boil_K']

    margin_K = limiting_boil_K - limiting_melt_K  # positive = boil point comfortably above required melt temp

    if margin_K <= hard_block_margin_K:
        status = 'blocked'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, at or above "
            f"{limiting_boil_element}'s vapor-loss point ({limiting_boil_K:.0f} K, "
            f"hard-block margin {hard_block_margin_K} K). {limiting_boil_element} would be "
            f"lost to vapor before/as the alloy homogenizes in an open melt -- this is a "
            f"physical block, not a soft warning."
        )
        suggested_routes = ['mechanical alloying (ball milling)', 'powder sintering', 'diffusion bonding']
    elif margin_K <= hard_block_margin_K + caution_zone_K:
        status = 'caution'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, only "
            f"{margin_K:.0f} K below {limiting_boil_element}'s vapor-loss point "
            f"({limiting_boil_K:.0f} K). Pure-element numbers alone aren't sufficient to call "
            f"this either way -- a strongly negative Delta_H_mix can suppress "
            f"{limiting_boil_element}'s effective vapor pressure once alloyed. Check "
            f"calculate_mixing_enthalpy(), search for literature precedent, or run a small "
            f"test melt before committing a full batch."
        )
        suggested_routes = ['arc/induction melting (monitor mass loss)', 'literature precedent check', 'small-scale test melt']
    else:
        status = 'ok'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, comfortably "
            f"below {limiting_boil_element}'s vapor-loss point ({limiting_boil_K:.0f} K, "
            f"margin {margin_K:.0f} K). No melt-based volatility concern from composition alone."
        )
        suggested_routes = ['arc/induction melting']

    return {
        'status': status,
        'limiting_melt_element': limiting_melt_element,
        'limiting_melt_K': limiting_melt_K,
        'limiting_boil_element': limiting_boil_element,
        'limiting_boil_K': limiting_boil_K,
        'margin_K': margin_K,
        'message': message,
        'suggested_routes': suggested_routes,
    }


def screen_composition(composition_at_frac):
    """
    Run all three screening calculations on a composition
    composition_at_frac: {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    """
    vec = calculate_vec(composition_at_frac)
    delta = calculate_delta(composition_at_frac)
    delta_h = calculate_mixing_enthalpy(composition_at_frac)
    synthesis = check_synthesis_feasibility(composition_at_frac)
    
    return {
        'VEC': vec,
        'delta': delta,
        'Delta_H_mix': delta_h,
        'synthesis_feasibility': synthesis
    }


def interpret_screening(results):
    """
    Provide basic interpretation of screening results
    """
    vec = results['VEC']
    delta = results['delta']
    delta_h = results['Delta_H_mix']
    
    print("\n📊 Screening Interpretation:")
    print("-" * 40)
    
    # VEC interpretation
    if vec > 8:
        print(f"VEC = {vec:.2f} → Likely FCC or BCC solid solution")
    elif vec > 6:
        print(f"VEC = {vec:.2f} → Likely BCC solid solution")
    else:
        print(f"VEC = {vec:.2f} → Likely intermetallic or complex phases")
    
    # δ interpretation
    if delta < 5:
        print(f"δ = {delta:.3f} → Small atomic mismatch: solid solution likely")
    else:
        print(f"δ = {delta:.3f} → Large atomic mismatch: intermetallic likely")
    
    # ΔH_mix interpretation
    if delta_h < -20:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Strong compound formation likely")
    elif delta_h < -5:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Moderate compound formation likely")
    else:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Weak compound formation")

    # Synthesis feasibility (melt/boil check)
    synth = results.get('synthesis_feasibility')
    if synth:
        status_icon = {'ok': '✅', 'caution': '⚠️', 'blocked': '🚫', 'unknown': '❓'}.get(synth['status'], '')
        print(f"\n{status_icon} Synthesis feasibility [{synth['status']}]: {synth['message']}")
        if synth['suggested_routes']:
            print(f"   Suggested routes: {', '.join(synth['suggested_routes'])}")


# Test the screening
if __name__ == "__main__":
    # Test with NdFeB composition
    test_composition = {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    print("Testing NdFeB composition:", test_composition)
    results = screen_composition(test_composition)
    print("\nResults:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    interpret_screening(results)
    
    # Test with Phosphorus
    print("\n" + "="*50)
    print("Testing Fe2P composition:")
    test_fe2p = {'Fe': 0.667, 'P': 0.333}
    try:
        results = screen_composition(test_fe2p)
        print("Results:")
        for key, value in results.items():
            print(f"  {key}: {value}")
        interpret_screening(results)
    except IncompleteElementDataError as e:
        print(f"✅ Expected error caught: {e}")
