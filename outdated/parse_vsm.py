#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files
Extracts magnetic properties: coercivity, remanence, saturation
"""

import numpy as np
import os
from pathlib import Path

def parse_vsm_file(file_path):
    """Parse a PPMS .dat file containing VSM data"""
    
    data = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find the header line (contains 'Magnetic Field' and 'Moment')
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    # Parse header to find column indices
    header = lines[header_idx].strip().split(',')
    field_idx = None
    moment_idx = None
    temp_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"')
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif 'Moment' in col_clean and 'M.' not in col_clean:
            moment_idx = i
        elif 'Temperature' in col_clean:
            temp_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data rows
    fields = []
    moments = []
    temps = []
    
    for line in lines[header_idx+1:]:
        line = line.strip()
        if not line or line.startswith(','):
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx, temp_idx if temp_idx else 0):
            continue
        
        try:
            field = float(parts[field_idx].strip())
            moment = float(parts[moment_idx].strip())
            fields.append(field)
            moments.append(moment)
            if temp_idx is not None:
                temps.append(float(parts[temp_idx].strip()))
        except (ValueError, IndexError):
            continue
    
    if not fields:
        return {'error': 'No data parsed'}
    
    # Convert to numpy arrays
    fields = np.array(fields)
    moments = np.array(moments)
    
    # Calculate properties
    # Find coercivity (field where moment crosses zero)
    # Find remanence (moment at zero field)
    # Find saturation moment (max moment)
    
    # Sort by field for proper hysteresis loop
    sort_idx = np.argsort(fields)
    fields_sorted = fields[sort_idx]
    moments_sorted = moments[sort_idx]
    
    # Saturation magnetization (maximum absolute moment)
    ms = np.max(np.abs(moments))
    ms_idx = np.argmax(np.abs(moments))
    
    # Remanence (moment at zero field)
    # Find closest to zero field
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    # Coercivity (field where moment crosses zero)
    # Find where moment changes sign
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            # Linear interpolation
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    # Mass normalization (if available)
    mass = None
    for line in lines[:20]:
        if 'Mass' in line and 'grams' in line:
            try:
                parts = line.split(',')
                for p in parts:
                    if 'Mass' in p:
                        mass_str = p.split('=')[-1].strip()
                        mass = float(mass_str)
                        break
            except:
                pass
    
    return {
        'fields': fields.tolist(),
        'moments': moments.tolist(),
        'n_points': len(fields),
        'max_field': float(np.max(np.abs(fields))),
        'ms': float(ms),  # Saturation moment (emu)
        'mr': float(mr),  # Remanence (emu)
        'hc': float(hc) if hc else None,  # Coercivity (Oe)
        'mass': mass,  # Mass in grams
        'ms_per_g': float(ms / mass) if mass and mass > 0 else None  # emu/g
    }


def get_vsm_summary(file_path):
    """Get a summary of VSM data"""
    data = parse_vsm_file(file_path)
    if 'error' in data:
        return {'error': data['error']}
    
    summary = {
        'file': os.path.basename(file_path),
        'n_points': data['n_points'],
        'max_field': data['max_field'],
        'saturation_moment': data['ms'],
        'remanence': data['mr'],
        'coercivity': data['hc'],
        'mass': data.get('mass'),
    }
    
    if data.get('ms_per_g'):
        summary['saturation_moment_per_g'] = data['ms_per_g']
    
    return summary


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
    print(f"  Coercivity (Hc): {result['hc']:.1f} Oe" if result['hc'] else "  Coercivity (Hc): Not found")
    
    if result.get('mass'):
        print(f"  Mass: {result['mass']:.4f} g")
        if result.get('ms_per_g'):
            print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
