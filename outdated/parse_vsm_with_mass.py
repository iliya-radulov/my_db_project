#!/usr/bin/env python3
"""
VSM Data Parser with mass from filename
"""

import numpy as np
import os
import re
import csv
from pathlib import Path

def parse_vsm_file(file_path, mass_override=None):
    """Parse PPMS .dat file, with optional mass override"""
    
    fields = []
    moments = []
    mass = None
    
    # Try to get mass from filename if not provided
    if mass_override is None:
        filename = os.path.basename(file_path)
        # Look for patterns like 50mg, 50.0mg, 50_mg
        match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
        if match:
            mass = float(match.group(1)) / 1000  # Convert mg to g
            print(f"📦 Mass from filename: {mass*1000:.0f} mg")
        else:
            # Look for mass in file (as before)
            mass = None
    else:
        mass = mass_override
        print(f"📦 Mass from override: {mass*1000:.0f} mg")
    
    with open(file_path, 'r', encoding='latin-1') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if not rows:
        return {'error': 'Empty file'}
    
    # Find header
    header_idx = None
    for i, row in enumerate(rows):
        if row and any('Magnetic Field' in col for col in row):
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    header = rows[header_idx]
    field_idx = None
    moment_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip()
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Columns not found'}
    
    # Parse data
    for row in rows[header_idx+1:]:
        if not row or len(row) <= max(field_idx, moment_idx):
            continue
        if row and row[0].strip().startswith('Comment'):
            continue
        
        try:
            field_str = row[field_idx].strip()
            moment_str = row[moment_idx].strip()
            if not field_str or not moment_str:
                continue
            fields.append(float(field_str))
            moments.append(float(moment_str))
        except (ValueError, IndexError):
            continue
    
    if not fields:
        return {'error': 'No data parsed'}
    
    fields = np.array(fields)
    moments = np.array(moments)
    
    ms = np.max(np.abs(moments))
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    return {
        'fields': fields.tolist(),
        'moments': moments.tolist(),
        'n_points': len(fields),
        'max_field': float(np.max(np.abs(fields))),
        'ms': float(ms),
        'mr': float(mr),
        'hc': float(hc) if hc else None,
        'mass': mass,
        'ms_per_g': float(ms / mass) if mass and mass > 0 else None
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/mh/20230630_SPS_sample1_50mg.dat"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Parsing: {file_path}")
    result = parse_vsm_file(file_path)
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)
    
    print(f"\n📊 VSM Data Summary:")
    print(f"  Points: {result['n_points']}")
    print(f"  Max field: {result['max_field']:.1f} Oe")
    print(f"  Saturation moment (Ms): {result['ms']:.6f} emu")
    print(f"  Remanence (Mr): {result['mr']:.6f} emu")
    if result['hc']:
        print(f"  Coercivity (Hc): {result['hc']:.1f} Oe")
    else:
        print(f"  Coercivity (Hc): Not found")
    
    if result.get('mass'):
        print(f"  Mass: {result['mass']:.4f} g ({result['mass']*1000:.1f} mg)")
    if result.get('ms_per_g'):
        print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
