"""
alloy_screening.py
Quick composition screening using VEC, δ, and ΔH_mix
No external dependencies - uses only element property tables.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Complete ELEMENT_PROPERTIES - includes all elements with data
# valence electrons, atomic radius (Å), electronegativity (Pauling)
ELEMENT_PROPERTIES = {
    # Period 1
    'H': {'valence': 1, 'radius': 0.53, 'en': 2.20},
    'He': {'valence': 2, 'radius': 0.31, 'en': 4.16},
    
    # Period 2
    'Li': {'valence': 1, 'radius': 1.52, 'en': 0.98},
    'Be': {'valence': 2, 'radius': 1.12, 'en': 1.57},
    'B': {'valence': 3, 'radius': 0.87, 'en': 2.04},
    'C': {'valence': 4, 'radius': 0.77, 'en': 2.55},
    'N': {'valence': 5, 'radius': 0.75, 'en': 3.04},
    'O': {'valence': 6, 'radius': 0.73, 'en': 3.44},
    'F': {'valence': 7, 'radius': 0.71, 'en': 3.98},
    'Ne': {'valence': 8, 'radius': 0.69, 'en': 4.79},
    
    # Period 3
    'Na': {'valence': 1, 'radius': 1.86, 'en': 0.93},
    'Mg': {'valence': 2, 'radius': 1.60, 'en': 1.31},
    'Al': {'valence': 3, 'radius': 1.43, 'en': 1.61},
    'Si': {'valence': 4, 'radius': 1.17, 'en': 1.90},
    'P': {'valence': 5, 'radius': 1.10, 'en': 2.19},
    'S': {'valence': 6, 'radius': 1.04, 'en': 2.58},
    'Cl': {'valence': 7, 'radius': 0.99, 'en': 3.16},
    'Ar': {'valence': 8, 'radius': 0.98, 'en': 3.24},
    
    # Period 4
    'K': {'valence': 1, 'radius': 2.27, 'en': 0.82},
    'Ca': {'valence': 2, 'radius': 1.97, 'en': 1.00},
    'Sc': {'valence': 3, 'radius': 1.62, 'en': 1.36},
    'Ti': {'valence': 4, 'radius': 1.47, 'en': 1.54},
    'V': {'valence': 5, 'radius': 1.35, 'en': 1.63},
    'Cr': {'valence': 6, 'radius': 1.28, 'en': 1.66},
    'Mn': {'valence': 7, 'radius': 1.27, 'en': 1.55},
    'Fe': {'valence': 8, 'radius': 1.26, 'en': 1.83},
    'Co': {'valence': 9, 'radius': 1.25, 'en': 1.88},
    'Ni': {'valence': 10, 'radius': 1.24, 'en': 1.91},
    'Cu': {'valence': 11, 'radius': 1.28, 'en': 1.90},
    'Zn': {'valence': 12, 'radius': 1.33, 'en': 1.65},
    'Ga': {'valence': 3, 'radius': 1.36, 'en': 1.81},
    'Ge': {'valence': 4, 'radius': 1.22, 'en': 2.01},
    'As': {'valence': 5, 'radius': 1.21, 'en': 2.18},
    'Se': {'valence': 6, 'radius': 1.17, 'en': 2.55},
    'Br': {'valence': 7, 'radius': 1.14, 'en': 2.96},
    'Kr': {'valence': 8, 'radius': 1.12, 'en': 3.00},
    
    # Period 5
    'Rb': {'valence': 1, 'radius': 2.48, 'en': 0.82},
    'Sr': {'valence': 2, 'radius': 2.15, 'en': 0.95},
    'Y': {'valence': 3, 'radius': 1.80, 'en': 1.22},
    'Zr': {'valence': 4, 'radius': 1.60, 'en': 1.33},
    'Nb': {'valence': 5, 'radius': 1.46, 'en': 1.60},
    'Mo': {'valence': 6, 'radius': 1.39, 'en': 2.16},
    'Tc': {'valence': 7, 'radius': 1.36, 'en': 1.90},
    'Ru': {'valence': 8, 'radius': 1.34, 'en': 2.20},
    'Rh': {'valence': 9, 'radius': 1.34, 'en': 2.28},
    'Pd': {'valence': 10, 'radius': 1.37, 'en': 2.20},
    'Ag': {'valence': 11, 'radius': 1.44, 'en': 1.93},
    'Cd': {'valence': 12, 'radius': 1.49, 'en': 1.69},
    'In': {'valence': 3, 'radius': 1.63, 'en': 1.78},
    'Sn': {'valence': 4, 'radius': 1.40, 'en': 1.96},
    'Sb': {'valence': 5, 'radius': 1.40, 'en': 2.05},
    'Te': {'valence': 6, 'radius': 1.37, 'en': 2.10},
    'I': {'valence': 7, 'radius': 1.33, 'en': 2.66},
    'Xe': {'valence': 8, 'radius': 1.31, 'en': 2.60},
    
    # Period 6 (Lanthanides)
    'Cs': {'valence': 1, 'radius': 2.65, 'en': 0.79},
    'Ba': {'valence': 2, 'radius': 2.22, 'en': 0.89},
    'La': {'valence': 3, 'radius': 1.87, 'en': 1.10},
    'Ce': {'valence': 3, 'radius': 1.82, 'en': 1.12},
    'Pr': {'valence': 3, 'radius': 1.82, 'en': 1.13},
    'Nd': {'valence': 3, 'radius': 1.82, 'en': 1.14},
    'Pm': {'valence': 3, 'radius': 1.81, 'en': 1.13},
    'Sm': {'valence': 3, 'radius': 1.80, 'en': 1.17},
    'Eu': {'valence': 2, 'radius': 1.80, 'en': 1.20},
    'Gd': {'valence': 3, 'radius': 1.79, 'en': 1.20},
    'Tb': {'valence': 3, 'radius': 1.77, 'en': 1.10},
    'Dy': {'valence': 3, 'radius': 1.77, 'en': 1.22},
    'Ho': {'valence': 3, 'radius': 1.77, 'en': 1.23},
    'Er': {'valence': 3, 'radius': 1.76, 'en': 1.24},
    'Tm': {'valence': 3, 'radius': 1.75, 'en': 1.25},
    'Yb': {'valence': 2, 'radius': 1.74, 'en': 1.10},
    'Lu': {'valence': 3, 'radius': 1.73, 'en': 1.27},
    
    # Period 6 (Transition metals)
    'Hf': {'valence': 4, 'radius': 1.59, 'en': 1.30},
    'Ta': {'valence': 5, 'radius': 1.46, 'en': 1.50},
    'W': {'valence': 6, 'radius': 1.39, 'en': 2.36},
    'Re': {'valence': 7, 'radius': 1.37, 'en': 1.90},
    'Os': {'valence': 8, 'radius': 1.35, 'en': 2.20},
    'Ir': {'valence': 9, 'radius': 1.36, 'en': 2.20},
    'Pt': {'valence': 10, 'radius': 1.39, 'en': 2.28},
    'Au': {'valence': 11, 'radius': 1.44, 'en': 2.54},
    'Hg': {'valence': 12, 'radius': 1.50, 'en': 2.00},
    'Tl': {'valence': 3, 'radius': 1.71, 'en': 1.80},
    'Pb': {'valence': 4, 'radius': 1.75, 'en': 2.33},
    'Bi': {'valence': 5, 'radius': 1.55, 'en': 2.02},
    'Po': {'valence': 6, 'radius': 1.53, 'en': 2.00},
    'At': {'valence': 7, 'radius': 1.50, 'en': 2.20},
    'Rn': {'valence': 8, 'radius': 1.48, 'en': 2.60},
    
    # Period 7 (Actinides)
    'Fr': {'valence': 1, 'radius': 2.70, 'en': 0.70},
    'Ra': {'valence': 2, 'radius': 2.23, 'en': 0.90},
    'Ac': {'valence': 3, 'radius': 1.95, 'en': 1.10},
    'Th': {'valence': 4, 'radius': 1.80, 'en': 1.30},
    'Pa': {'valence': 5, 'radius': 1.61, 'en': 1.50},
    'U': {'valence': 6, 'radius': 1.54, 'en': 1.38},
    'Np': {'valence': 6, 'radius': 1.55, 'en': 1.36},
    'Pu': {'valence': 6, 'radius': 1.53, 'en': 1.28},
    'Am': {'valence': 3, 'radius': 1.52, 'en': 1.13},
    'Cm': {'valence': 3, 'radius': 1.50, 'en': 1.28},
    'Bk': {'valence': 3, 'radius': 1.48, 'en': 1.30},
    'Cf': {'valence': 3, 'radius': 1.47, 'en': 1.30},
    'Es': {'valence': 3, 'radius': 1.45, 'en': 1.30},
    'Fm': {'valence': 3, 'radius': 1.44, 'en': 1.30},
    'Md': {'valence': 3, 'radius': 1.43, 'en': 1.30},
    'No': {'valence': 3, 'radius': 1.42, 'en': 1.30},
    'Lr': {'valence': 3, 'radius': 1.41, 'en': 1.30},
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


def screen_composition(composition_at_frac):
    """
    Run all three screening calculations on a composition
    composition_at_frac: {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    """
    vec = calculate_vec(composition_at_frac)
    delta = calculate_delta(composition_at_frac)
    delta_h = calculate_mixing_enthalpy(composition_at_frac)
    
    return {
        'VEC': vec,
        'delta': delta,
        'Delta_H_mix': delta_h
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
