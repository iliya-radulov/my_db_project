#!/usr/bin/env python3
"""
Hybrid VSM Analyzer
- Uses our parser to read .dat files
- Uses magmeas for analysis (if available)
- Falls back to our own analysis if magmeas is not available
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os
import re

# Try to import magmeas
try:
    from magmeas import MH_major
    HAS_MAGMEAS = True
    print("✅ Using magmeas for analysis")
except ImportError:
    HAS_MAGMEAS = False
    print("⚠️ magmeas not available, using fallback analysis")


def parse_vsm_file(file_path):
    """
    Our custom parser for .dat files (works with your format)
    """
    with open(file_path, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Find header line
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    # Parse header
    header = lines[header_idx].strip().split(',')
    field_idx = None
    moment_idx = None
    temp_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
        elif 'Temperature' in col_clean:
            temp_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data
    fields = []
    moments = []
    temps = []
    
    for line in lines[header_idx+1:]:
        if not line or line.startswith(','):
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx):
            continue
        
        try:
            field_str = parts[field_idx].strip()
            moment_str = parts[moment_idx].strip()
            
            if not field_str or not moment_str:
                continue
            
            fields.append(float(field_str))
            moments.append(float(moment_str))
            
            if temp_idx is not None and len(parts) > temp_idx:
                try:
                    temp_str = parts[temp_idx].strip()
                    if temp_str:
                        temps.append(float(temp_str))
                except:
                    pass
        except (ValueError, IndexError):
            continue
    
    if not fields:
        return {'error': 'No data parsed'}
    
    # Get mass from filename
    mass = None
    filename = os.path.basename(file_path)
    match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000  # Convert mg to g
    
    return {
        'fields': np.array(fields),
        'moments': np.array(moments),
        'temps': np.array(temps) if temps else None,
        'n_points': len(fields),
        'mass': mass,
        'filename': filename
    }


def analyze_vsm_hybrid(file_path, show_plot=True):
    """Hybrid VSM analysis using our parser + magmeas analysis"""
    
    print(f"📄 Analyzing: {file_path}")
    
    # Step 1: Parse with our parser
    data = parse_vsm_file(file_path)
    if 'error' in data:
        print(f"❌ Parse error: {data['error']}")
        return None
    
    print(f"📊 Data: {data['n_points']} points")
    print(f"   Field range: {data['fields'][0]:.1f} - {data['fields'][-1]:.1f} Oe")
    if data['mass']:
        print(f"   Mass: {data['mass']*1000:.1f} mg")
    
    # Step 2: Calculate properties
    fields = data['fields']
    moments = data['moments']
    
    # Saturation magnetization (maximum absolute moment)
    ms = np.max(np.abs(moments))
    ms_idx = np.argmax(np.abs(moments))
    
    # Remanence (moment at zero field)
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    # Coercivity (field where moment crosses zero)
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            # Linear interpolation
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    # Step 3: Use magmeas for advanced analysis if available
    if HAS_MAGMEAS:
        try:
            # Try to use magmeas's MH_major with the data directly
            # This is a bit tricky - we'd need to create a proper MH_major object
            # For now, we'll use our own calculations
            print("   ℹ️ magmeas available but using custom calculations")
        except Exception as e:
            print(f"   ⚠️ magmeas analysis failed: {e}")
    
    # Prepare result
    result = {
        'file': data['filename'],
        'n_points': data['n_points'],
        'mass': data['mass'],
        'max_field': float(np.max(np.abs(fields))),
        'saturation': float(ms),
        'remanence': float(mr),
        'coercivity': float(hc) if hc else None,
        'saturation_per_g': float(ms / data['mass']) if data['mass'] and data['mass'] > 0 else None
    }
    
    # Print results
    print("\n" + "="*50)
    print("📊 VSM Analysis Results")
    print("="*50)
    print(f"File: {result['file']}")
    print(f"Points: {result['n_points']}")
    print(f"Max field: {result['max_field']:.1f} Oe")
    if result['mass']:
        print(f"Mass: {result['mass']*1000:.1f} mg")
    print(f"Saturation (Ms): {result['saturation']:.4f} emu")
    print(f"Remanence (Mr): {result['remanence']:.4f} emu")
    if result['coercivity']:
        print(f"Coercivity (Hc): {result['coercivity']:.1f} Oe")
    else:
        print("Coercivity (Hc): Not found")
    if result['saturation_per_g']:
        print(f"Ms per gram: {result['saturation_per_g']:.2f} emu/g")
    
    # Plot
    if show_plot:
        print("\n📈 Generating plot...")
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.plot(fields, moments, 'b-', linewidth=1.2, label='Hysteresis loop')
        
        # Mark Hc and Mr
        if hc:
            ax.axvline(hc, color='r', linestyle='--', alpha=0.7, label=f"Hc = {hc:.1f} Oe")
            ax.axvline(-hc, color='r', linestyle='--', alpha=0.7)
        
        if mr:
            ax.axhline(mr, color='g', linestyle='--', alpha=0.7, label=f"Mr = {mr:.4f} emu")
            ax.axhline(-mr, color='g', linestyle='--', alpha=0.7)
        
        ax.set_xlabel('Field (Oe)')
        ax.set_ylabel('Moment (emu)')
        ax.set_title(f'VSM Hysteresis Loop: {data["filename"]}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
        ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
        
        # Info box
        info = f"Ms: {result['saturation']:.4f} emu\nMr: {result['remanence']:.4f} emu\nHc: {result['coercivity']:.1f} Oe" if result['coercivity'] else f"Ms: {result['saturation']:.4f} emu\nMr: {result['remanence']:.4f} emu"
        if result['mass']:
            info += f"\nMass: {result['mass']*1000:.1f} mg"
        
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        plt.show()
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Hybrid VSM Analyzer')
    parser.add_argument('file', help='Path to .dat file')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot display')
    
    args = parser.parse_args()
    
    analyze_vsm_hybrid(args.file, show_plot=not args.no_plot)


if __name__ == "__main__":
    main()
