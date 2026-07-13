#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files
Handles different encodings and file formats
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
    
    # Try to find header with column names
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    # If no header, look for numeric data pattern
    if header_idx is None:
        # Find first line with numeric data
        for i, line in enumerate(lines[:50]):
            # Check if line has numbers and commas
            parts = line.strip().split(',')
            if len(parts) >= 3:
                try:
                    # Try to parse first few values as floats
                    [float(p.strip()) for p in parts[:3] if p.strip()]
                    header_idx = i - 1  # Assume header is one line above
                    break
                except:
                    continue
    
    # If still no header, assume first line is header
    if header_idx is None:
        header_idx = 0
    
    # Parse header to find column indices
    header = lines[header_idx].strip().split(',')
    field_idx = None
    moment_idx = None
    temp_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean or 'Field' in col_clean:
            if field_idx is None:
                field_idx = i
        elif 'Moment' in col_clean and 'M.' not in col_clean and 'Std' not in col_clean:
            moment_idx = i
        elif 'Temperature' in col_clean:
            temp_idx = i
    
    # If columns not found, try to detect from data
    if field_idx is None or moment_idx is None:
        # Find first data line with numbers
        for i in range(header_idx + 1, min(header_idx + 20, len(lines))):
            line = lines[i].strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) >= 2:
                try:
                    # Check if we can parse at least two values
                    vals = [float(p.strip()) for p in parts[:2] if p.strip()]
                    if len(vals) >= 2:
                        field_idx = 0
                        moment_idx = 1
                        break
                except:
                    continue
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data rows
    fields = []
    moments = []
    temps = []
    
    for line in lines[header_idx+1:]:
        line = line.strip()
        if not line or line.startswith(',') or line.startswith('Comment'):
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx, temp_idx if temp_idx else 0):
            continue
        
        try:
            field = float(parts[field_idx].strip())
            moment = float(parts[moment_idx].strip())
            fields.append(field)
            moments.append(moment)
            if temp_idx is not None and len(parts) > temp_idx:
                try:
                    temps.append(float(parts[temp_idx].strip()))
                except:
                    pass
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
    
    # Try to find mass from header or comments
    mass = None
    for line in lines[:50]:
        if 'Mass' in line and 'gram' in line:
            try:
                # Look for number in the line
                numbers = re.findall(r'[-+]?\d*\.?\d+', line)
                if numbers:
                    mass = float(numbers[0])
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


def get_vsm_summary(file_path):
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
    if result['hc']:
        print(f"  Coercivity (Hc): {result['hc']:.1f} Oe")
    else:
        print(f"  Coercivity (Hc): Not found")
    
    if result.get('mass'):
        print(f"  Mass: {result['mass']:.4f} g")
    if result.get('ms_per_g'):
        print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
