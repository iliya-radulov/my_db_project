#!/usr/bin/env python3
"""
XRD .xy file parser with lattice parameter calculation for Nd2Fe14B
"""

import numpy as np
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import re

# Cu Kα wavelength in Å
WAVELENGTH = 1.5406

# Nd2Fe14B reflections (hkl, 2θ approximate for Cu Kα)
# Based on JCPDS card 00-039-0473
ND2FE14B_REFLECTIONS = [
    (4, 1, 0, 22.5),
    (3, 1, 1, 23.5),
    (4, 1, 1, 24.0),
    (5, 1, 0, 25.0),
    (4, 2, 0, 26.0),
    (5, 1, 1, 26.5),
    (4, 0, 2, 27.0),
    (6, 0, 0, 30.5),
    (6, 1, 1, 31.5),
    (5, 2, 2, 32.5),
    (7, 1, 0, 34.0),
    (6, 2, 1, 34.5),
    (7, 1, 1, 35.0),
    (7, 2, 0, 36.5),
    (5, 3, 2, 38.5),
]

def parse_xy_file(file_path):
    """Parse a Bruker .xy file containing 2θ and intensity columns"""
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    two_theta = float(parts[0])
                    intensity = float(parts[1])
                    data.append((two_theta, intensity))
                except ValueError:
                    continue
    
    if not data:
        return None
    
    data = np.array(data)
    two_theta = data[:, 0]
    intensity = data[:, 1]
    
    return {
        'two_theta': two_theta,
        'intensity': intensity,
        'n_points': len(two_theta),
        'start': float(two_theta[0]),
        'end': float(two_theta[-1]),
        'step': float(two_theta[1] - two_theta[0]) if len(two_theta) > 1 else 0,
        'max_intensity': float(np.max(intensity)),
        'min_intensity': float(np.min(intensity)),
    }

def find_peaks(two_theta, intensity, prominence=50, distance=10):
    """Find peaks in XRD data using scipy"""
    from scipy.signal import find_peaks as scipy_find_peaks
    
    max_int = np.max(intensity)
    if max_int > 0:
        intensity_norm = intensity / max_int
    else:
        intensity_norm = intensity
    
    try:
        peaks, properties = scipy_find_peaks(
            intensity_norm,
            prominence=prominence / max_int if max_int > 0 else 0.05,
            height=0.05,
            distance=distance,
            width=1  # Minimum width in points
        )
    except:
        return []
    
    peak_results = []
    for idx in peaks:
        if idx < len(two_theta):
            peak_results.append({
                'two_theta': float(two_theta[idx]),
                'intensity': float(intensity[idx]),
                'normalized_intensity': float(intensity_norm[idx]),
                'index': int(idx)
            })
    
    return peak_results

def calculate_lattice_parameters(peaks):
    """Calculate lattice parameters for Nd2Fe14B from peak positions"""
    
    if len(peaks) < 3:
        return None
    
    # Find peaks that match known reflections
    matched = []
    for peak in peaks:
        two_theta = peak['two_theta']
        # Convert to d-spacing
        theta = np.radians(two_theta / 2)
        d = WAVELENGTH / (2 * np.sin(theta))
        
        # Try to match to known reflections
        for h, k, l, expected_2theta in ND2FE14B_REFLECTIONS:
            if abs(two_theta - expected_2theta) < 0.5:
                # Calculate a (for tetragonal, h²+k² term)
                h2_k2 = h**2 + k**2
                if h2_k2 > 0:
                    a = d * np.sqrt(h2_k2)
                    matched.append({
                        'hkl': f'({h},{k},{l})',
                        'two_theta': two_theta,
                        'd': d,
                        'a': a,
                        'expected': expected_2theta,
                        'delta': two_theta - expected_2theta
                    })
                break
    
    # Calculate average a
    a_values = [m['a'] for m in matched if m.get('a') is not None and m['a'] > 0]
    if len(a_values) >= 2:
        avg_a = np.mean(a_values)
        std_a = np.std(a_values)
        return {
            'a': avg_a,
            'a_std': std_a,
            'n_reflections': len(a_values),
            'matched_peaks': matched,
            'c': None  # Need c-axis reflections (00l) for c
        }
    
    return None

def parse_and_analyze_xy(file_path, sample_id=None):
    """Parse .xy file and analyze XRD data"""
    data = parse_xy_file(file_path)
    if data is None:
        return {'error': 'Failed to parse file'}
    
    peaks = find_peaks(data['two_theta'], data['intensity'])
    
    result = {
        'file': os.path.basename(file_path),
        'sample_id': sample_id,
        'n_points': data['n_points'],
        'range': [data['start'], data['end']],
        'step': data['step'],
        'max_intensity': data['max_intensity'],
        'n_peaks': len(peaks),
        'peaks': peaks[:20],  # Store first 20 peaks
    }
    
    # Calculate lattice parameters
    lattice = calculate_lattice_parameters(peaks)
    if lattice:
        result['lattice_a'] = lattice['a']
        result['lattice_a_std'] = lattice['a_std']
        result['n_reflections'] = lattice['n_reflections']
        result['matched_peaks'] = lattice['matched_peaks']
    
    return result

def print_xrd_report(result):
    """Print a formatted XRD analysis report"""
    print(f"\n{'='*60}")
    print(f"📄 XRD Analysis: {result.get('file', 'Unknown')}")
    print(f"{'='*60}")
    print(f"\n📊 Data Summary:")
    print(f"  Points: {result['n_points']}")
    print(f"  Range: {result['range'][0]:.2f}° - {result['range'][1]:.2f}°")
    print(f"  Step: {result['step']:.4f}°")
    print(f"  Max intensity: {result['max_intensity']:.1f}")
    print(f"  Peaks found: {result['n_peaks']}")
    
    if result.get('lattice_a'):
        print(f"\n📐 Lattice Parameters (Nd2Fe14B):")
        print(f"  a = {result['lattice_a']:.4f} ± {result.get('lattice_a_std', 0):.4f} Å")
        print(f"  (from {result.get('n_reflections', 0)} reflections)")
    
    print(f"\n🔍 Matched Peaks:")
    matched = result.get('matched_peaks', [])
    if matched:
        for m in matched[:10]:
            print(f"  {m['hkl']}: 2θ = {m['two_theta']:.2f}° (expected {m['expected']:.1f}°), a = {m['a']:.4f} Å")
    else:
        print("  No matches found for Nd2Fe14B reflections")
    
    print(f"\n📋 First 10 peaks:")
    for peak in result.get('peaks', [])[:10]:
        print(f"  2θ = {peak['two_theta']:.3f}°, intensity = {peak['intensity']:.1f}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/xrd/0107.xy"
        sample_id = "0107"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Analyzing: {file_path}")
    result = parse_and_analyze_xy(file_path, sample_id)
    print_xrd_report(result)
