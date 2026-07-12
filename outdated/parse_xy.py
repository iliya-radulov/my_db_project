#!/usr/bin/env python3
"""
XRD .xy file parser
Parses Bruker .xy files (2θ, intensity columns)
"""

import numpy as np
import os
from pathlib import Path

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
    
    # Convert to numpy arrays
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
        'mean_intensity': float(np.mean(intensity))
    }


def find_peaks(two_theta, intensity, prominence=50, distance=10):
    """Find peaks in XRD data"""
    from scipy.signal import find_peaks as scipy_find_peaks
    
    # Normalize intensity
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
            distance=distance
        )
    except:
        return []
    
    peak_results = []
    for idx in peaks:
        peak_results.append({
            'two_theta': float(two_theta[idx]),
            'intensity': float(intensity[idx]),
            'normalized_intensity': float(intensity_norm[idx]),
            'index': int(idx)
        })
    
    return peak_results


def get_summary(file_path):
    """Get a summary of the XRD data from a .xy file"""
    data = parse_xy_file(file_path)
    if data is None:
        return {'error': 'Failed to parse file'}
    
    peaks = find_peaks(data['two_theta'], data['intensity'])
    
    return {
        'file': os.path.basename(file_path),
        'n_points': data['n_points'],
        'range': [data['start'], data['end']],
        'step': data['step'],
        'max_intensity': data['max_intensity'],
        'n_peaks': len(peaks),
        'peaks': peaks[:10]  # First 10 peaks
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/xrd/0107.xy"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Parsing: {file_path}")
    data = parse_xy_file(file_path)
    
    if data is None:
        print("❌ Failed to parse file")
        sys.exit(1)
    
    print(f"\n📊 Data Summary:")
    print(f"  Points: {data['n_points']}")
    print(f"  Range: {data['start']:.2f}° - {data['end']:.2f}°")
    print(f"  Step: {data['step']:.4f}°")
    print(f"  Max intensity: {data['max_intensity']:.1f}")
    print(f"  Min intensity: {data['min_intensity']:.1f}")
    print(f"  Mean intensity: {data['mean_intensity']:.1f}")
    
    peaks = find_peaks(data['two_theta'], data['intensity'])
    print(f"\n🔍 Found {len(peaks)} peaks (first 5):")
    for peak in peaks[:5]:
        print(f"  2θ = {peak['two_theta']:.3f}°, intensity = {peak['intensity']:.1f}")

def calculate_lattice_parameters(peaks, phase='Nd2Fe14B'):
    """
    Calculate lattice parameters from XRD peaks
    For Nd2Fe14B (tetragonal, space group P4_2/mnm)
    """
    import numpy as np
    
    # Convert 2θ to d-spacing (using Cu Kα wavelength = 1.5406 Å)
    wavelength = 1.5406  # Cu Kα in Å
    
    lattice_params = []
    
    # Known reflections for Nd2Fe14B (hkl, 2θ approximate)
    # Using (hkl) and d-spacing
    reflections = {
        'Nd2Fe14B': [
            (4, 1, 0, 22.5),   # (410) around 22.5°
            (3, 1, 1, 23.5),   # (311) around 23.5°
            (4, 1, 1, 24.0),   # (411) around 24.0°
            (5, 1, 0, 25.0),   # (510) around 25.0°
            (4, 2, 0, 26.0),   # (420) around 26.0°
            (5, 1, 1, 26.5),   # (511) around 26.5°
            (4, 0, 2, 27.0),   # (402) around 27.0°
            (6, 0, 0, 30.5),   # (600) around 30.5°
            (6, 1, 1, 31.5),   # (611) around 31.5°
        ]
    }
    
    # For each peak, try to match to a reflection
    for peak in peaks[:20]:  # Check first 20 peaks
        two_theta = peak['two_theta']
        # Convert to d-spacing
        d = wavelength / (2 * np.sin(np.radians(two_theta) / 2))
        
        # Try to identify the peak
        for h, k, l, expected_2theta in reflections['Nd2Fe14B']:
            if abs(two_theta - expected_2theta) < 0.5:
                # Calculate lattice parameter for tetragonal
                # 1/d^2 = (h^2 + k^2)/a^2 + l^2/c^2
                # For h,k,l known, we can solve for a and c
                h2_k2 = h**2 + k**2
                if h2_k2 > 0:
                    a = d * np.sqrt(h2_k2)
                    lattice_params.append({
                        'hkl': f'({h}{k}{l})',
                        'two_theta': two_theta,
                        'd': d,
                        'a': a,
                        'c': None  # Need multiple peaks to solve for c
                    })
                break
    
    # Calculate average a
    a_values = [p['a'] for p in lattice_params if p.get('a') is not None]
    if a_values:
        avg_a = np.mean(a_values)
        return {
            'a': avg_a,
            'a_std': np.std(a_values),
            'n_reflections': len(a_values),
            'peaks_used': lattice_params
        }
    
    return None


def parse_and_analyze_xy(file_path):
    """Parse .xy file and analyze XRD data"""
    data = parse_xy_file(file_path)
    if data is None:
        return None
    
    peaks = find_peaks(data['two_theta'], data['intensity'])
    
    result = {
        'data': data,
        'peaks': peaks,
        'n_peaks': len(peaks),
        'max_intensity': data['max_intensity'],
        'range': [data['start'], data['end']],
    }
    
    # Calculate lattice parameters
    lattice = calculate_lattice_parameters(peaks)
    if lattice:
        result['lattice'] = lattice
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "/Users/r/desktop/ndfeb_data/sorted_v2/xrd/0107.xy"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    print(f"📄 Analyzing: {file_path}")
    result = parse_and_analyze_xy(file_path)
    
    if result is None:
        print("❌ Failed to parse file")
        sys.exit(1)
    
    print(f"\n📊 Data Summary:")
    print(f"  Points: {result['data']['n_points']}")
    print(f"  Range: {result['data']['start']:.2f}° - {result['data']['end']:.2f}°")
    print(f"  Peaks found: {result['n_peaks']}")
    
    if result.get('lattice'):
        print(f"\n📐 Lattice Parameters:")
        print(f"  a = {result['lattice']['a']:.4f} Å (from {result['lattice']['n_reflections']} reflections)")
        if result['lattice'].get('a_std'):
            print(f"  Std dev: {result['lattice']['a_std']:.4f} Å")
    
    print(f"\n🔍 First 10 peaks:")
    for peak in result['peaks'][:10]:
        print(f"  2θ = {peak['two_theta']:.3f}°, intensity = {peak['intensity']:.1f}")
