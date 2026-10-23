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

# Nd2Fe14B reference lattice (tetragonal, P4_2/mnm, No. 136):
# a = 8.80 Å, c = 12.20 Å (Herbst et al., Phys. Rev. B 29 (1984) 4176;
# JCPDS 00-039-0473). Reflection positions are calculated from these
# rather than typed in by hand -- an earlier hand-typed table had every
# 2θ off by 20-40°.
ND2FE14B_A = 8.80
ND2FE14B_C = 12.20


def _allowed_p42mnm(h, k, l):
    """Reflection conditions of P4_2/mnm: 0kl / h0l need k+l / h+l even
    (which also covers h00, 0k0 and 00l)."""
    if h == 0 and (k + l) % 2:
        return False
    if k == 0 and (h + l) % 2:
        return False
    return True


def nd2fe14b_reflections(two_theta_min=20.0, two_theta_max=80.0,
                         a=ND2FE14B_A, c=ND2FE14B_C, wavelength=WAVELENGTH):
    """List of (h, k, l, 2θ) for allowed Nd2Fe14B reflections in the given
    range. Only h >= k is listed, since (hkl) and (khl) coincide for a
    tetragonal cell."""
    refl = []
    for h in range(0, 12):
        for k in range(0, h + 1):
            for l in range(0, 16):
                if (h, k, l) == (0, 0, 0) or not _allowed_p42mnm(h, k, l):
                    continue
                inv_d2 = (h**2 + k**2) / a**2 + l**2 / c**2
                s_theta = wavelength * np.sqrt(inv_d2) / 2
                if s_theta >= 1:
                    continue
                tt = 2 * np.degrees(np.arcsin(s_theta))
                if two_theta_min <= tt <= two_theta_max:
                    refl.append((h, k, l, tt))
    return sorted(refl, key=lambda r: r[3])


ND2FE14B_REFLECTIONS = nd2fe14b_reflections()

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

def calculate_lattice_parameters(peaks, tolerance_deg=0.3):
    """Estimate Nd2Fe14B lattice parameters a and c from peak positions.

    Quick visual-check tool only -- the validated XRD analysis is the
    Stage 2 pipeline (xrd_analyzer_dev1.py).

    Each peak is indexed to a calculated Nd2Fe14B reflection only when
    exactly one reflection lies within tolerance_deg (ambiguous peaks are
    skipped). a and c are then fitted together by least squares on the
    tetragonal relation 1/d^2 = (h^2 + k^2)/a^2 + l^2/c^2, so reflections
    with l != 0 are handled correctly. c is only reported when the matched
    set constrains it (at least one l != 0 reflection besides hk0 ones).
    """
    if len(peaks) < 3:
        return None

    matched = []
    for peak in peaks:
        two_theta = peak['two_theta']
        candidates = [r for r in ND2FE14B_REFLECTIONS if abs(two_theta - r[3]) < tolerance_deg]
        if len(candidates) != 1:
            continue
        h, k, l, expected_2theta = candidates[0]
        theta = np.radians(two_theta / 2)
        d = WAVELENGTH / (2 * np.sin(theta))
        matched.append({
            'hkl': f'({h},{k},{l})',
            'h2k2': h**2 + k**2,
            'l2': l**2,
            'two_theta': two_theta,
            'd': d,
            'expected': expected_2theta,
            'delta': two_theta - expected_2theta,
        })

    if len(matched) < 2:
        return None

    X = np.array([[m['h2k2'], m['l2']] for m in matched], dtype=float)
    y = np.array([1.0 / m['d']**2 for m in matched])
    has_c = np.linalg.matrix_rank(X) == 2 and np.any(X[:, 0] > 0)
    if not has_c:
        # Only hk0 (or only 00l) reflections: fit a from the hk0 ones alone.
        hk0 = X[:, 1] == 0
        if hk0.sum() < 2:
            return None
        X, y = X[hk0][:, :1], y[hk0]

    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    n, n_par = len(y), X.shape[1]
    if n > n_par:
        resid = y - X @ coef
        cov = (resid @ resid / (n - n_par)) * np.linalg.inv(X.T @ X)
        sigma = np.sqrt(np.diag(cov))
    else:
        sigma = np.full(n_par, np.nan)

    if coef[0] <= 0 or (has_c and coef[1] <= 0):
        return None
    a = coef[0] ** -0.5
    a_std = 0.5 * coef[0] ** -1.5 * sigma[0]
    c = c_std = None
    if has_c:
        c = coef[1] ** -0.5
        c_std = 0.5 * coef[1] ** -1.5 * sigma[1]

    return {
        'a': float(a),
        'a_std': float(a_std),
        'c': float(c) if c is not None else None,
        'c_std': float(c_std) if c_std is not None else None,
        'n_reflections': len(y),
        'matched_peaks': matched,
    }

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
        result['lattice_c'] = lattice['c']
        result['lattice_c_std'] = lattice['c_std']
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
        if result.get('lattice_c'):
            print(f"  c = {result['lattice_c']:.4f} ± {result.get('lattice_c_std', 0):.4f} Å")
        print(f"  (from {result.get('n_reflections', 0)} reflections)")
    
    print(f"\n🔍 Matched Peaks:")
    matched = result.get('matched_peaks', [])
    if matched:
        for m in matched[:10]:
            print(f"  {m['hkl']}: 2θ = {m['two_theta']:.2f}° (reference {m['expected']:.2f}°, Δ = {m['delta']:+.2f}°)")
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
