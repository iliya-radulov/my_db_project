#!/usr/bin/env python3
"""
VSM Analyzer - Fixed version
Skips bad rows and continues parsing
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os
import re

def parse_vsm_file_fixed(file_path):
    """Parse VSM file, skipping bad rows"""
    
    with open(file_path, 'r', encoding='latin-1') as f:
        lines = f.readlines()
    
    # Find header
    header_idx = None
    for i, line in enumerate(lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break
    
    if header_idx is None:
        return {'error': 'Could not find header row'}
    
    # Find column indices
    header = lines[header_idx].strip().split(',')
    field_idx = None
    moment_idx = None
    
    for i, col in enumerate(header):
        col_clean = col.strip().strip('"').strip("'")
        if 'Magnetic Field' in col_clean:
            field_idx = i
        elif col_clean == 'Moment (emu)':
            moment_idx = i
    
    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find columns'}
    
    # Parse data - skip bad rows
    fields = []
    moments = []
    skipped = 0
    
    for i, line in enumerate(lines[header_idx+1:]):
        if not line or line.startswith(','):
            skipped += 1
            continue
        
        parts = line.split(',')
        if len(parts) <= max(field_idx, moment_idx):
            skipped += 1
            continue
        
        try:
            field_str = parts[field_idx].strip()
            moment_str = parts[moment_idx].strip()
            
            if not field_str or not moment_str:
                skipped += 1
                continue
            
            field = float(field_str)
            moment = float(moment_str)
            
            fields.append(field)
            moments.append(moment)
            
        except (ValueError, IndexError):
            skipped += 1
            continue
    
    if not fields:
        return {'error': f'No valid data parsed (skipped {skipped} rows)'}
    
    # Get mass from filename
    mass = None
    filename = os.path.basename(file_path)
    match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000
    
    return {
        'fields': np.array(fields),
        'moments': np.array(moments),
        'n_points': len(fields),
        'skipped': skipped,
        'mass': mass,
        'filename': filename
    }


def analyze_vsm(file_path, show_plot=True):
    """Analyze VSM data"""
    
    print(f"📄 Analyzing: {file_path}")
    
    data = parse_vsm_file_fixed(file_path)
    if 'error' in data:
        print(f"❌ Error: {data['error']}")
        return None
    
    fields = data['fields']
    moments = data['moments']
    
    print(f"📊 Data: {data['n_points']} points (skipped {data['skipped']} bad rows)")
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
    
    print("\n" + "="*50)
    print("📊 VSM Analysis Results")
    print("="*50)
    print(f"Points: {result['n_points']}")
    print(f"Max field: {result['max_field']:.1f} Oe")
    if result['mass']:
        print(f"Mass: {result['mass']*1000:.1f} mg")
    print(f"Saturation (Ms): {result['saturation']:.4f} emu")
    print(f"Remanence (Mr): {result['remanence']:.4f} emu")
    if result['coercivity']:
        print(f"Coercivity (Hc): {result['coercivity']:.1f} Oe")
    if result['saturation_per_g']:
        print(f"Ms per gram: {result['saturation_per_g']:.2f} emu/g")
    
    if show_plot:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(fields, moments, 'b-', linewidth=1.2)
        
        if hc:
            ax.axvline(hc, color='r', linestyle='--', alpha=0.7, label=f"Hc = {hc:.1f} Oe")
            ax.axvline(-hc, color='r', linestyle='--', alpha=0.7)
        if mr:
            ax.axhline(mr, color='g', linestyle='--', alpha=0.7, label=f"Mr = {mr:.4f} emu")
            ax.axhline(-mr, color='g', linestyle='--', alpha=0.7)
        
        ax.set_xlabel('Field (Oe)')
        ax.set_ylabel('Moment (emu)')
        ax.set_title(f'VSM: {data["filename"]}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
        ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
        
        info = f"Ms: {result['saturation']:.4f} emu\nMr: {result['remanence']:.4f} emu"
        if result['coercivity']:
            info += f"\nHc: {result['coercivity']:.1f} Oe"
        if result['mass']:
            info += f"\nMass: {result['mass']*1000:.1f} mg"
        
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        plt.show()
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to .dat file')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot')
    args = parser.parse_args()
    
    analyze_vsm(args.file, show_plot=not args.no_plot)


if __name__ == "__main__":
    main()
