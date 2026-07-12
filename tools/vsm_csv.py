#!/usr/bin/env python3
"""
VSM Parser using Python's csv module
Reads all rows correctly
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
import re
import sys
import os

def parse_vsm_csv(file_path):
    """Parse VSM file using csv module - handles all rows"""
    
    fields = []
    moments = []
    mass = None
    
    with open(file_path, 'r', encoding='latin-1') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if not rows:
        return {'error': 'Empty file'}
    
    # Find header row
    header_idx = None
    for i, row in enumerate(rows):
        if row and any('Magnetic Field' in col for col in row):
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'No header found'}
    
    print(f"Header at row: {header_idx}")
    
    # Find column indices
    header = rows[header_idx]
    field_idx = None
    moment_idx = None
    
    for i, col in enumerate(header):
        if 'Magnetic Field' in col:
            field_idx = i
        elif col == 'Moment (emu)':
            moment_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': f'Columns not found (field={field_idx}, moment={moment_idx})'}
    
    # Parse all data rows
    for i, row in enumerate(rows[header_idx+1:]):
        if len(row) <= max(field_idx, moment_idx):
            continue
        
        try:
            field_str = row[field_idx].strip()
            moment_str = row[moment_idx].strip()
            
            if not field_str or not moment_str:
                continue
            
            field = float(field_str)
            moment = float(moment_str)
            
            fields.append(field)
            moments.append(moment)
            
        except (ValueError, IndexError):
            continue
    
    if not fields:
        return {'error': 'No valid data found'}
    
    # Get mass from filename
    match = re.search(r'(\d+\.?\d*)\s*mg', os.path.basename(file_path), re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000
    
    return {
        'fields': np.array(fields),
        'moments': np.array(moments),
        'n_points': len(fields),
        'mass': mass
    }


def analyze(file_path):
    data = parse_vsm_csv(file_path)
    if 'error' in data:
        print(f"❌ {data['error']}")
        return
    
    fields = data['fields']
    moments = data['moments']
    
    print(f"📊 Points: {data['n_points']}")
    print(f"   Field range: {fields[0]:.1f} - {fields[-1]:.1f} Oe")
    if data['mass']:
        print(f"   Mass: {data['mass']*1000:.1f} mg")
    
    # Calculate properties
    ms = np.max(np.abs(moments))
    zero_idx = np.argmin(np.abs(fields))
    mr = moments[zero_idx]
    
    hc = None
    for i in range(1, len(moments)):
        if moments[i-1] * moments[i] < 0:
            hc = fields[i-1] - moments[i-1] * (fields[i] - fields[i-1]) / (moments[i] - moments[i-1])
            break
    
    print(f"\n📊 Results:")
    print(f"   Ms = {ms:.4f} emu")
    print(f"   Mr = {mr:.4f} emu")
    if hc:
        print(f"   Hc = {hc:.1f} Oe")
    if data['mass']:
        print(f"   Ms/g = {ms/data['mass']:.2f} emu/g")
    
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
    ax.set_title(f'VSM: {os.path.basename(file_path)}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        print("Usage: python vsm_csv.py <file.dat>")
