#!/usr/bin/env python3
"""
Interactive alloy entry tool.
Takes a formula, calculates masses, shows results, asks for confirmation,
then adds to database.
"""

from alloy_calculator import (
    parse_composition_with_unit, 
    calculate_masses, 
    ElementComponent,
    ATOMIC_WEIGHTS
)
from alloy_db import get_db
from datetime import datetime

def interactive_add_alloy():
    """Interactive tool to add a new alloy to the database"""
    
    print("\n" + "="*60)
    print("🧪 Alloy Entry Tool")
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
    
    # Step 4: Get target mass
    mass = input("\nTarget total mass in grams [10.0]: ").strip()
    mass = float(mass) if mass else 10.0
    
    # Step 5: Get material class
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
    
    # Step 6: Get sample ID
    date_str = datetime.now().strftime('%Y%m%d')
    default_id = f"NEW-{date_str}-001"
    sample_id = input(f"\nSample ID [{default_id}]: ").strip()
    if not sample_id:
        sample_id = default_id
    
    # Step 7: Get excess amounts (optional)
    print("\nOptional: Add excess for evaporation loss")
    print("Enter element:excess% (e.g., Co:5), or press Enter to skip")
    excess_input = input("Excess (e.g., Co:5): ").strip()
    
    excess_dict = {}
    if excess_input:
        for item in excess_input.split(','):
            if ':' in item:
                elem, pct = item.split(':')
                excess_dict[elem.strip()] = float(pct.strip())
    
    # Step 8: Build ElementComponent list
    elements = []
    for symbol, at_pct in at_composition.items():
        excess = excess_dict.get(symbol, 0.0)
        if symbol not in ATOMIC_WEIGHTS:
            print(f"❌ Unknown element: {symbol}")
            return
        elements.append(ElementComponent(
            symbol=symbol,
            at_pct=at_pct,
            excess_pct=excess
        ))
    
    # Step 9: Calculate masses
    print("\n📐 Calculating masses...")
    result = calculate_masses(
        total_mass_g=mass,
        elements=elements
    )
    
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
    
    # Step 11: Ask for confirmation
    print("\n" + "="*60)
    confirm = input("✅ Add this alloy to database? [y/N]: ").strip().lower()
    
    if confirm != 'y':
        print("❌ Cancelled.")
        return
    
    # Step 12: Add to database
    print("\n💾 Adding to database...")
    db = get_db()
    
    # Check if sample ID already exists
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
        notes=f"From alloy entry tool: {formula} as {unit}"
    )
    
    # Add compositions table entries
    sample_db_id = db.cursor.lastrowid if hasattr(db.cursor, 'lastrowid') else None
    
    print("\n✅ Alloy added successfully!")
    print(f"   Sample ID: {sample_id}")
    print(f"   Mass: {mass}g")
    print(f"   Class: {material_class}")
    print(f"   Composition: {', '.join([f'{k}={v:.2f} at%' for k,v in at_composition.items()])}")
    
    db.close()

if __name__ == "__main__":
    interactive_add_alloy()
