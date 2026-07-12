#!/usr/bin/env python3
"""
VSM Parser using pandas (magmeas-style)
Handles missing values gracefully
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
import sys
import os

def parse_vsm_pandas(file_path):
    """Parse VSM file using pandas (like magmeas does)"""
    
    # Find the header row (where 'Magnetic Field' appears)
    with open(file_path, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'No header found'}
    
    # Use pandas to read the data (skiprows=header_idx+1)
    # This handles missing values automatically
    df = pd.read_csv(
        file_path,
        skiprows=header_idx,
        encoding='latin-1',
        on_bad_lines='skip'
    )
    
    # Find the correct columns
    field_col = None
    moment_col = None
    temp_col = None
    
    for col in df.columns:
        if 'Magnetic Field' in col:
            field_col = col
        elif col == 'Moment (emu)':
            moment_col = col
        elif 'Temperature' in col:
            temp_col = col
    
    if field_col is None or moment_col is None:
        return {'error': f'Columns not found: field={field_col}, moment={moment_col}'}
    
    # Extract data (pandas handles NaN automatically)
    fields = df[field_col].values
    moments = df[moment_col].values
    temps = df[temp_col].values if temp_col else None
    
    # Remove NaN values (pandas already did this, but just in case)
    valid = ~np.isnan(fields) & ~np.isnan(moments)
    fields = fields[valid]
    moments = moments[valid]
    if temps is not None:
        temps = temps[valid]
    
    if len(fields) == 0:
        return {'error': 'No valid data found'}
    
    # Get mass from filename
    mass = None
    match = re.search(r'(\d+\.?\d*)\s*mg', os.path.basename(file_path), re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000
    
    return {
        'fields': fields,
        'moments': moments,
        'temps': temps,
        'n_points': len(fields),
        'mass': mass,
        'filename': os.path.basename(file_path)
    }


def analyze(file_path):
    data = parse_vsm_pandas(file_path)
    if 'error' in data:
        print(f"❌ {data['error']}")
        return
    
    fields = data['fields']
    moments = data['moments']
    
    print(f"📊 Points: {data['n_points']}")
    print(f"   Field range: {fields[0]:.1f} - {fields[-1]:.1f} Oe")
    if data['mass']:
        print(f"   Mass: {data['mass']*1000:.1f} mg")
    
    # Calculate properties (same as our previous parser)
    ms = np.max(np.abs(moments))
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    print(f"\n📊 Results (CGS units):")
    print(f"   Ms = {ms:.4f} emu")
    print(f"   Mr = {mr:.4f} emu")
    if hc:
        print(f"   Hc = {hc:.1f} Oe")
    if data['mass']:
        print(f"   Ms/g = {ms/data['mass']:.2f} emu/g")
    
    # Convert to SI units (matching magmeas)
    print(f"\n📊 Results (SI units, matching magmeas):")
    # Hc: Oe → MA/m (1 Oe = 79.577 A/m = 0.079577 kA/m = 0.000079577 MA/m)
    if hc:
        hc_si = hc * 79.577 / 1e6  # Oe → MA/m
        print(f"   Hc = {hc_si:.4f} MA/m")
    # Mr: emu/g → T (1 emu/g = 4π/1000 T ≈ 0.012566 T)
    if data['mass'] and mr:
        mr_si = (mr / data['mass']) * 4 * np.pi / 1000  # emu/g → T
        print(f"   Mr = {mr_si:.4f} T")
    # Ms: emu/g → T
    if data['mass'] and ms:
        ms_si = (ms / data['mass']) * 4 * np.pi / 1000  # emu/g → T
        print(f"   Ms = {ms_si:.4f} T")
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(fields, moments, 'b-', linewidth=1.2)
    if hc:
        ax.axvline(hc, color='r', linestyle='--', label=f"Hc = {hc:.1f} Oe")
        ax.axvline(-hc, color='r', linestyle='--')
    if mr:
        ax.axhline(mr, color='g', linestyle='--', label=f"Mr = {mr:.4f} emu")
        ax.axhline(-mr, color='g', linestyle='--')
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM: {data["filename"]}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        print("Usage: python vsm_magmeas_style.py <file.dat>")
