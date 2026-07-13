#!/usr/bin/env python3
"""
VSM Data Parser for PPMS .dat files
Handles both header formats (with [Header] section or without)
"""

import numpy as np
import os
import re
from pathlib import Path

def parse_vsm_file(file_path):
    """Parse PPMS .dat file with optional header section"""
    
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
    
    # Parse header for metadata
    mass = None
    if header_lines:
        for line in header_lines:
            if 'SAMPLE_MASS' in line:
                parts = line.split(',')
                if len(parts) > 1:
                    try:
                        mass = float(parts[1].strip())
                    except:
                        pass
    
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
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}
    
    # Parse data rows
    fields = []
    moments = []
    
    for line in data_lines[header_idx+1:]:
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
    
    # If mass not found in header, try filename
    if mass is None:
        filename = os.path.basename(file_path)
        match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
        if match:
            mass = float(match.group(1)) / 1000
    
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
        print(f"  Mass: {result['mass']:.4f} g ({result['mass']*1000:.1f} mg)")
    if result.get('ms_per_g'):
        print(f"  Ms per gram: {result['ms_per_g']:.4f} emu/g")
