"""
alloy_screening.py
Quick composition screening using VEC, δ, and ΔH_mix
No external dependencies - uses only element property tables.
"""

# Element properties: valence electrons, atomic radius (in Å), and electronegativity
ELEMENT_PROPERTIES = {
    'Fe': {'valence': 8, 'radius': 1.26, 'en': 1.83},
    'Nd': {'valence': 3, 'radius': 1.82, 'en': 1.14},
    'Co': {'valence': 9, 'radius': 1.25, 'en': 1.88},
    'B': {'valence': 3, 'radius': 0.87, 'en': 2.04},
    'Al': {'valence': 3, 'radius': 1.43, 'en': 1.61},
    'Si': {'valence': 4, 'radius': 1.17, 'en': 1.90},
    'Ni': {'valence': 10, 'radius': 1.24, 'en': 1.91},
    'Cr': {'valence': 6, 'radius': 1.28, 'en': 1.66},
    'Mn': {'valence': 7, 'radius': 1.27, 'en': 1.55},
    'Cu': {'valence': 11, 'radius': 1.28, 'en': 1.90},
    'La': {'valence': 3, 'radius': 1.87, 'en': 1.10},
    'Ga': {'valence': 3, 'radius': 1.36, 'en': 1.81},
}

def calculate_vec(composition_at_frac):
    """
    Calculate Valence Electron Concentration (VEC)
    composition_at_frac: {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    """
    vec = 0
    for element, fraction in composition_at_frac.items():
        if element in ELEMENT_PROPERTIES:
            vec += fraction * ELEMENT_PROPERTIES[element]['valence']
    return vec

def calculate_delta(composition_at_frac):
    """
    Calculate atomic size mismatch δ (for HEA solid solution prediction)
    """
    # Get average radius
    avg_radius = 0
    for element, fraction in composition_at_frac.items():
        if element in ELEMENT_PROPERTIES:
            avg_radius += fraction * ELEMENT_PROPERTIES[element]['radius']
    
    # Calculate δ
    delta = 0
    for element, fraction in composition_at_frac.items():
        if element in ELEMENT_PROPERTIES:
            radius = ELEMENT_PROPERTIES[element]['radius']
            delta += fraction * (1 - radius / avg_radius) ** 2
    delta = delta ** 0.5
    return delta

def calculate_mixing_enthalpy(composition_at_frac):
    """
    Simplified mixing enthalpy using Miedema model (pairwise contributions)
    Returns: mixing enthalpy in kJ/mol
    """
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
