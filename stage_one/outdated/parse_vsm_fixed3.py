#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files - Fixed version
Skips empty rows and handles all data
"""

import numpy as np
import os
from pathlib import Path

def parse_vsm_file(file_path):
    """Parse a PPMS .dat file containing VSM data"""
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    lines = None
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            break
        except UnicodeDecodeError:
            continue
    
    if lines is None:
        return {'error': 'Could not decode file with any encoding'}
    
    # Find header line
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    # Parse data rows - skip empty values
    fields = []
    moments = []
    mass = None
    
    for line in lines[header_idx+1:]:
        line = line.strip()
        if not line or line.startswith(','):
            continue
        
        parts = line.split(',')
        if len(parts) < 5:
            continue
        
        # Check if this is a data row (has field and moment)
        try:
            field_str = parts[3].strip()  # Magnetic Field (Oe) is column 4 (index 3)
            moment_str = parts[4].strip()  # Moment (emu) is column 5 (index 4)
            
            if not field_str or not moment_str:
                continue
                
            field = float(field_str)
            moment = float(moment_str)
            
            fields.append(field)
            moments.append(moment)
            
        except (ValueError, IndexError):
            continue
    
    if not fields:
        return {'error': 'No data parsed'}
    
    # Convert to numpy arrays
    fields = np.array(fields)
    moments = np.array(moments)
    
    # Sort by field for proper hysteresis loop
    sort_idx = np.argsort(fields)
    fields_sorted = fields[sort_idx]
    moments_sorted = moments[sort_idx]
    
    # Saturation magnetization (maximum absolute moment)
    ms = np.max(np.abs(moments))
    
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
    
    # Try to get mass from the data (first row has mass in column 22)
    for line in lines[header_idx+1:header_idx+20]:
        parts = line.split(',')
        if len(parts) > 22:
            try:
                mass_str = parts[22].strip()  # Mass (grams) is column 23 (index 22)
                if mass_str:
                    mass = float(mass_str)
                    break
            except:
                pass
    
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
        print(f"  Mass: {result['mass']:.4f} g")
    if result.get('ms_per_g'):
        print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
