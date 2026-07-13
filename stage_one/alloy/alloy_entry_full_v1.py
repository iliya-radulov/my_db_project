#!/usr/bin/env python3
"""
Full alloy entry tool with:
1. Formula parsing
2. Mass calculation
3. MP lookup
4. VEC/δ/ΔH_mix screening
5. Database insertion
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import datetime


from stage_one.alloy.alloy_calculator_v1 import parse_composition_with_unit, calculate_masses, ElementComponent
from stage_one.alloy.alloy_db_v1 import get_db
from stage_one.alloy.alloy_screening_v1 import screen_composition, interpret_screening, IncompleteElementDataError
from stage_one.lookup.mp_lookup_v1 import lookup as mp_lookup, print_report as mp_print_report
from stage_one.lookup.oqmd_lookup_v1 import lookup as oqmd_lookup, print_report as oqmd_print_report
from stage_one.lookup.lookup_common_v1 import from_mp_results, from_oqmd_results, dedup_by_formula


def get_api_key():
    key_file = Path('../../back_up/API') / 'MP_API_KEY.txt'
    if key_file.exists():
        return key_file.read_text().strip()
    return None

def interactive_add_alloy_full():
    print("\n" + "="*60)
    print("🧪 Alloy Entry Tool (Full Version)")
    print("    Includes: Calculator | MP Lookup | VEC/δ/ΔH_mix Screening")
    print("="*60)
    
    # Step 1: Formula
    formula = input("\nEnter alloy formula (e.g., Fe65Nd30Co5): ").strip()
    if not formula:
        print("❌ No formula entered. Exiting.")
        return
    
    unit = input("Is this at% or wt%? [at%]: ").strip() or 'at%'
    if unit.lower() not in ['at%', 'wt%']:
        print("❌ Unit must be 'at%' or 'wt%'. Defaulting to at%.")
        unit = 'at%'
    
    # Step 2: Parse
    print(f"\n📊 Parsing {formula} as {unit}...")
    at_composition = parse_composition_with_unit(formula, unit)
    print(f"   Atomic %: {', '.join([f'{k}={v:.2f}' for k,v in at_composition.items()])}")
    
    # Step 3: VEC/δ/ΔH_mix screening
    print("\n📐 Running VEC/δ/ΔH_mix screening...")
    comp_frac = {k: v/100 for k, v in at_composition.items()}
    try:
        screening_results = screen_composition(comp_frac)
        interpret_screening(screening_results)
    except IncompleteElementDataError as e:
        print(f"   ⚠️  Skipping screening: {e}")
        screening_results = None
    
    # Step 4: MP Lookup
    print("\n🔍 Checking Materials Project...")
    api_key = get_api_key()
    if api_key:
        mp_results = mp_lookup(comp_frac, api_key=api_key)
        mp_print_report(comp_frac, mp_results)
    else:
        print("   ⚠️  No API key found. Skipping MP lookup.")
        mp_results = None

    # Step 4b: OQMD Lookup (no API key needed)
    print("\n🔍 Checking OQMD...")
    try:
        oqmd_results = oqmd_lookup(comp_frac)
        oqmd_print_report(comp_frac, oqmd_results)
    except Exception as e:
        print(f"   ⚠️  OQMD lookup failed: {e}")
        oqmd_results = None
    
    # Step 5: Mass calculation
    mass = input("\nTarget total mass in grams [10.0]: ").strip()
    mass = float(mass) if mass else 10.0
    
    # Step 6: Material class
    print("\nAvailable material classes:")
    print("  1. Permanent Magnet")
    print("  2. Soft Magnetic")
    print("  3. High Entropy Alloy")
    print("  4. Heusler")
    print("  5. Single Crystal")
    
    class_choice = input("Select class [1]: ").strip() or '1'
    class_map = {'1': 'Permanent Magnet', '2': 'Soft Magnetic', '3': 'High Entropy Alloy', '4': 'Heusler', '5': 'Single Crystal'}
    material_class = class_map.get(class_choice, 'Permanent Magnet')
    
    # Step 7: Sample ID
    date_str = datetime.now().strftime('%Y%m%d')
    default_id = f"NEW-{date_str}-001"
    sample_id = input(f"\nSample ID [{default_id}]: ").strip()
    if not sample_id:
        sample_id = default_id
    
    # Step 8: Excess
    print("\nOptional: Add excess for evaporation loss")
    excess_input = input("Excess (e.g., Co:5): ").strip()
    
    excess_dict = {}
    if excess_input:
        for item in excess_input.split(','):
            if ':' in item:
                elem, pct = item.split(':')
                excess_dict[elem.strip()] = float(pct.strip())
    
    # Step 9: Calculate
    elements = []
    for symbol, at_pct in at_composition.items():
        excess = excess_dict.get(symbol, 0.0)
        elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
    
    print("\n📐 Calculating masses...")
    result = calculate_masses(total_mass_g=mass, elements=elements)
    
    print("\n" + "="*60)
    print("📋 Calculation Results")
    print("="*60)
    print(f"\nEffective molar mass: {result.effective_molar_mass:.3f} g/mol")
    print(f"Total target mass: {result.total_mass_g:.4f} g\n")
    
    print(f"{'Element':<10}{'at%':>8}{'wt%':>8}{'target(g)':>10}{'weigh(g)':>10}")
    print("-" * 46)
    for e in result.elements:
        print(f"{e.symbol:<10}{e.at_pct:>8.2f}{e.wt_pct:>8.2f}{e.grams:>10.4f}{e.weigh_grams:>10.4f}")
    
    # Step 10: Confirm
    print("\n" + "="*60)
    confirm = input("✅ Add this alloy to database? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled.")
        return
    
    # Step 11: Add to DB
    print("\n💾 Adding to database...")
    db = get_db()
    
    existing = db.get_sample(sample_id)
    if existing:
        override = input(f"⚠️ Sample {sample_id} already exists. Override? [y/N]: ").strip().lower()
        if override != 'y':
            print("❌ Cancelled.")
            db.close()
            return
    
    composition_frac = {k: v/100 for k, v in at_composition.items()}
    sample_db_id = db.add_sample(
        sample_id=sample_id,
        composition=composition_frac,
        material_class=material_class,
        source_type='experimental',
        mass_grams=mass,
        notes=f"Full workflow: {formula} as {unit}",
        vec=screening_results['VEC'] if screening_results else None,
        delta=screening_results['delta'] if screening_results else None,
        delta_h_mix=screening_results['Delta_H_mix'] if screening_results else None
    )
    
    print(f"\n✅ Alloy added successfully!")
    print(f"   Sample ID: {sample_id}")
    print(f"   Mass: {mass}g")
    print(f"   Class: {material_class}")
    if screening_results:
        print(f"   VEC: {screening_results['VEC']:.2f}")
        print(f"   δ: {screening_results['delta']:.3f}")
        print(f"   ΔH_mix: {screening_results['Delta_H_mix']:.2f} kJ/mol")
    else:
        print(f"   Screening: skipped (missing element data)")

    # Step 12: Store deduped literature check results, linked to this sample
    print("\n💾 Storing literature check results...")
    if mp_results:
        for c in dedup_by_formula(from_mp_results(mp_results)):
            db.add_literature_check(
                sample_db_id=sample_db_id, source_db='materials_project',
                tier=c.tier, match_formula=c.formula, match_id=c.match_id,
                stability=c.stability, experimentally_known=c.experimentally_known,
                composition_distance=c.composition_distance
            )
    if oqmd_results:
        for c in dedup_by_formula(from_oqmd_results(oqmd_results)):
            db.add_literature_check(
                sample_db_id=sample_db_id, source_db='oqmd',
                tier=c.tier, match_formula=c.formula, match_id=c.match_id,
                stability=c.stability, experimentally_known=c.experimentally_known,
                composition_distance=c.composition_distance
            )

    db.close()

if __name__ == "__main__":
    interactive_add_alloy_full()
