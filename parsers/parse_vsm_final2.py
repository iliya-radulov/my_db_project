#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files - Final version 2
- Robust data parsing with empty value handling
- Mass from filename has priority over header mass
- Only extracts: Temperature, Field, Moment, Error
"""

import numpy as np
import os
import re
from pathlib import Path

def parse_vsm_file(file_path):
    """Parse PPMS .dat file, keeping only Temperature, Field, Moment, Error"""
    
    with open(file_path, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Check if file has [Header] section
    header_mode = False
    data_mode = False
    header_lines = []
    data_lines = []
    
    for line in lines:
        line = line.strip()
        if line == '[Header]':
            header_mode = True
            data_mode = False
            continue
        elif line == '[Data]':
            header_mode = False
            data_mode = True
            continue
        
        if header_mode:
            header_lines.append(line)
        elif data_mode:
            if line and not line.startswith(';'):
                data_lines.append(line)
        else:
            # No [Header] section, treat as old format
            data_lines = [l for l in lines if l.strip() and not l.startswith(';')]
            break
    
    # Parse header for metadata (mass fallback only)
    mass_from_header = None
    if header_lines:
        for line in header_lines:
            if 'SAMPLE_MASS' in line:
                parts = line.split(',')
                if len(parts) > 1:
                    try:
                        mass_from_header = float(parts[1].strip())
                    except:
                        pass
    
    # Mass from filename (priority)
    mass = None
    filename = os.path.basename(file_path)
    match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000  # Convert mg to g
    else:
        mass = mass_from_header
    
    # Find header line in data
    header_idx = None
    for i, line in enumerate(data_lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    # Parse header to find column indices
    header = data_lines[header_idx].split(',')
    field_idx = None
    moment_idx = None
    temp_idx = None
    error_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
        elif 'Temperature' in col_clean:
            temp_idx = i
        elif 'M. Std. Err' in col_clean or 'Std. Err' in col_clean:
            error_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data rows - skip empty values
    fields = []
    moments = []
    temps = []
    errors = []
    
    for line in data_lines[header_idx+1:]:
        # Skip empty lines
        if not line or line.strip() == '':
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx):
            continue
        
        # Check if this is a data row (has field and moment)
        try:
            field_str = parts[field_idx].strip()
            moment_str = parts[moment_idx].strip()
            
            # Skip if either is empty
            if not field_str or not moment_str:
                continue
                
            field = float(field_str)
            moment = float(moment_str)
            
            fields.append(field)
            moments.append(moment)
            
            # Temperature (optional)
            if temp_idx is not None and len(parts) > temp_idx:
                try:
                    temp_str = parts[temp_idx].strip()
                    if temp_str:
                        temps.append(float(temp_str))
                    else:
                        temps.append(None)
                except:
                    temps.append(None)
            else:
                temps.append(None)
            
            # Error (optional)
            if error_idx is not None and len(parts) > error_idx:
                try:
                    error_str = parts[error_idx].strip()
                    if error_str:
                        errors.append(float(error_str))
                    else:
                        errors.append(None)
                except:
                    errors.append(None)
            else:
                errors.append(None)
            
        except (ValueError, IndexError):
            # Skip this row and continue
            continue
    
    if not fields:
        return {'error': 'No data parsed'}
    
    # Convert to numpy arrays
    fields = np.array(fields)
    moments = np.array(moments)
    
    # Calculate properties
    ms = np.max(np.abs(moments))
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    # Coercivity
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    return {
        'fields': fields.tolist(),
        'moments': moments.tolist(),
        'temps': [t for t in temps if t is not None],
        'errors': [e for e in errors if e is not None],
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
        file_path = "/Users/r/Desktop/NdFeB_data/sorted_v2/mh/20230630_SPS_sample1_50mg.dat"
    
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
        mass_source = 'filename' if '50mg' in result.get('file', '') else 'header'
        print(f"  Mass: {result['mass']:.4f} g ({result['mass']*1000:.1f} mg) from {mass_source}")
    if result.get('ms_per_g'):
        print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
