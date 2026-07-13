#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files - Fixed version
Handles empty values and skips bad rows
"""

import numpy as np
import os
import re
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
    
    # Parse header to find column indices
    header = lines[header_idx].strip().split(',')
    field_idx = None
    moment_idx = None
    mass_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
        elif 'Mass' in col_clean:
            mass_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data rows - skip empty values
    fields = []
    moments = []
    mass = None
    
    for line in lines[header_idx+1:]:
        line = line.strip()
        if not line or line.startswith(','):
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx):
            continue
        
        # Try to parse field
        try:
            field_str = parts[field_idx].strip()
            if not field_str:
                continue
            field = float(field_str)
        except (ValueError, IndexError):
            continue
        
        # Try to parse moment
        try:
            moment_str = parts[moment_idx].strip()
            if not moment_str:
                continue
            moment = float(moment_str)
        except (ValueError, IndexError):
            continue
        
        fields.append(field)
        moments.append(moment)
        
        # Get mass if available (from first row with mass)
        if mass is None and mass_idx is not None and len(parts) > mass_idx:
            try:
                mass_str = parts[mass_idx].strip()
                if mass_str:
                    mass = float(mass_str)
            except:
                pass
    
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
