#!/usr/bin/env python3
"""
Interactive alloy entry with Materials Project lookup.
Checks if composition is known before adding to database.
"""

from alloy_calculator import parse_composition_with_unit, calculate_masses, ElementComponent
from alloy_db import get_db
from mp_lookup import lookup, print_report
from datetime import datetime
from pathlib import Path

def get_api_key():
    """Read MP API key from file"""
    key_file = Path('../../back_up/API') / 'MP_API_KEY.txt'
    if key_file.exists():
        return key_file.read_text().strip()
    return None

def interactive_add_alloy_with_mp():
    """Interactive tool with MP lookup"""
    
    print("\n" + "="*60)
    print("🧪 Alloy Entry Tool with Materials Project Lookup")
    print("="*60)
    
    # Step 1: Get formula
    formula = input("\nEnter alloy formula (e.g., Fe65Nd30Co5): ").strip()
    if not formula:
        print("❌ No formula entered. Exiting.")
        return
    
    # Step 2: Get unit
    unit = input("Is this at% or wt%? [at%]: ").strip() or 'at%'
    if unit.lower() not in ['at%', 'wt%']:
        print("❌ Unit must be 'at%' or 'wt%'. Defaulting to at%.")
        unit = 'at%'
    
    # Step 3: Parse composition
    print(f"\n📊 Parsing {formula} as {unit}...")
    at_composition = parse_composition_with_unit(formula, unit)
    print(f"   Atomic %: {', '.join([f'{k}={v:.2f}' for k,v in at_composition.items()])}")
    
    # Step 4: MP Lookup
    print("\n🔍 Checking Materials Project...")
    api_key = get_api_key()
    if api_key:
        # Convert to fraction format for MP
        mp_composition = {k: v/100 for k, v in at_composition.items()}
        results = lookup(mp_composition, api_key=api_key)
        print_report(mp_composition, results)
        
        # Show best match
        best = results[0] if results else None
        if best and best.tier in [1, 2]:
            print(f"\n💡 Best match: {best.formula} (Tier {best.tier})")
            if best.energy_above_hull is not None and best.energy_above_hull < 0.05:
                print("   ✅ This composition is likely stable!")
            elif best.energy_above_hull is not None:
                print(f"   ⚠️  This composition is {best.energy_above_hull:.3f} eV/atom above hull")
            else:
                print("   ℹ️  Stability information not available")
        elif best and best.tier == 3:
            print(f"\n💡 Partial match: {best.formula} (Tier 3)")
            print("   A subsystem is known, but not this exact composition.")
        else:
            print("\n💡 No matches found. This could be a new composition!")
    else:
        print("   ⚠️  No API key found. Skipping MP lookup.")
    
    # Step 5: Get target mass
    mass = input("\nTarget total mass in grams [10.0]: ").strip()
    mass = float(mass) if mass else 10.0
    
    # Step 6: Get material class
    print("\nAvailable material classes:")
    print("  1. Permanent Magnet")
    print("  2. Soft Magnetic")
    print("  3. High Entropy Alloy")
    print("  4. Heusler")
    print("  5. Single Crystal")
    
    class_choice = input("Select class [1]: ").strip() or '1'
    class_map = {
        '1': 'Permanent Magnet',
        '2': 'Soft Magnetic',
        '3': 'High Entropy Alloy',
        '4': 'Heusler',
        '5': 'Single Crystal'
    }
    material_class = class_map.get(class_choice, 'Permanent Magnet')
    
    # Step 7: Get sample ID
    date_str = datetime.now().strftime('%Y%m%d')
    default_id = f"NEW-{date_str}-001"
    sample_id = input(f"\nSample ID [{default_id}]: ").strip()
    if not sample_id:
        sample_id = default_id
    
    # Step 8: Get excess amounts
    print("\nOptional: Add excess for evaporation loss")
    print("Enter element:excess% (e.g., Co:5), or press Enter to skip")
    excess_input = input("Excess (e.g., Co:5): ").strip()
    
    excess_dict = {}
    if excess_input:
        for item in excess_input.split(','):
            if ':' in item:
                elem, pct = item.split(':')
                excess_dict[elem.strip()] = float(pct.strip())
    
    # Step 9: Build elements and calculate
    elements = []
    for symbol, at_pct in at_composition.items():
        excess = excess_dict.get(symbol, 0.0)
        elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
    
    print("\n📐 Calculating masses...")
    result = calculate_masses(total_mass_g=mass, elements=elements)
    
    # Step 10: Show results
    print("\n" + "="*60)
    print("📋 Calculation Results")
    print("="*60)
    print(f"\nEffective molar mass: {result.effective_molar_mass:.3f} g/mol")
    print(f"Total target mass: {result.total_mass_g:.4f} g\n")
    
    print(f"{'Element':<10}{'at%':>8}{'wt%':>8}{'target(g)':>10}{'weigh(g)':>10}")
    print("-" * 46)
    for e in result.elements:
        print(f"{e.symbol:<10}{e.at_pct:>8.2f}{e.wt_pct:>8.2f}{e.grams:>10.4f}{e.weigh_grams:>10.4f}")
    
    # Step 11: Confirm
    print("\n" + "="*60)
    confirm = input("✅ Add this alloy to database? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled.")
        return
    
    # Step 12: Add to database
    print("\n💾 Adding to database...")
    db = get_db()
    
    # Check if sample exists
    existing = db.get_sample(sample_id)
    if existing:
        print(f"⚠️ Sample {sample_id} already exists!")
        override = input("Override? [y/N]: ").strip().lower()
        if override != 'y':
            print("❌ Cancelled.")
            db.close()
            return
    
    # Add sample
    composition_frac = {k: v/100 for k, v in at_composition.items()}
    db.add_sample(
        sample_id=sample_id,
        composition=composition_frac,
        material_class=material_class,
        source_type='experimental',
        mass_grams=mass,
        notes=f"From MP-enhanced entry tool: {formula} as {unit}"
    )
    
    print(f"\n✅ Alloy added successfully!")
    print(f"   Sample ID: {sample_id}")
    print(f"   Mass: {mass}g")
    print(f"   Class: {material_class}")
    print(f"   Composition: {', '.join([f'{k}={v:.2f} at%' for k,v in at_composition.items()])}")
    
    db.close()

if __name__ == "__main__":
    interactive_add_alloy_with_mp()
