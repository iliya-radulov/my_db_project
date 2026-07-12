#!/usr/bin/env python3
"""
XRD Analyzer using scipy + PowerXRD
Hybrid approach for better peak detection on real data
"""

import numpy as np
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os

# PowerXRD for background subtraction if available
try:
    import powerxrd as xrd
    HAS_POWERXRD = True
except ImportError:
    HAS_POWERXRD = False


def gaussian(x, amp, cen, wid, offset):
    """Gaussian function for peak fitting"""
    return amp * np.exp(-(x - cen)**2 / (2 * wid**2)) + offset


def load_xy_file(file_path):
    """Load .xy file (2θ, intensity)"""
    data = np.loadtxt(file_path)
    return data[:, 0], data[:, 1]


def find_peaks_robust(x, y, prominence=0.05, distance=15):
    """Find peaks robustly using scipy"""
    # Normalize intensity
    y_norm = y / np.max(y)
    
    # Find peaks
    peaks, properties = find_peaks(
        y_norm,
        prominence=prominence,
        height=0.05,
        distance=distance,
        width=2
    )
    
    peak_list = []
    for idx in peaks:
        # Get peak width
        widths = peak_widths(y_norm, [idx], rel_height=0.5)
        fwhm = widths[0][0] * (x[1] - x[0]) if len(widths[0]) > 0 else 0
        
        peak_list.append({
            'index': idx,
            'two_theta': x[idx],
            'intensity': y[idx],
            'normalized_intensity': y_norm[idx],
            'fwhm': fwhm
        })
    
    return peak_list


def fit_peak(x, y, peak_info, fit_range=2.0):
    """Fit a single peak with Gaussian"""
    center = peak_info['two_theta']
    x_min = center - fit_range
    x_max = center + fit_range
    
    # Select data around the peak
    mask = (x >= x_min) & (x <= x_max)
    x_fit = x[mask]
    y_fit = y[mask]
    
    if len(x_fit) < 5:
        return None
    
    # Initial guess
    amp = np.max(y_fit) - np.min(y_fit)
    wid = 0.5
    offset = np.min(y_fit)
    
    try:
        popt, _ = curve_fit(
            gaussian, x_fit, y_fit,
            p0=[amp, center, wid, offset],
            maxfev=2000
        )
        return {
            'amplitude': popt[0],
            'center': popt[1],
            'sigma': popt[2],
            'offset': popt[3],
            'fwhm': 2.355 * popt[2],  # FWHM = 2.355 * sigma
            'r_squared': None  # Could add R² calculation
        }
    except:
        return None


def analyze_xrd(file_path, prominence=0.05, distance=15, fit_peaks=True):
    """
    Analyze XRD data with robust peak detection
    """
    
    print(f"📄 Analyzing: {file_path}")
    
    # Load data
    x, y = load_xy_file(file_path)
    
    # Background subtraction using PowerXRD if available
    if HAS_POWERXRD:
        try:
            print("🔧 Subtracting background using PowerXRD...")
            chart = xrd.Chart(x, y)
            y_bg = chart.backsub(tol=1.0, inplace=False)[1]
            y = y_bg
            print("   ✅ Background subtracted")
        except:
            print("   ⚠️ PowerXRD background subtraction failed, using raw data")
    
    print(f"📊 Data loaded: {len(x)} points")
    print(f"   2θ range: {x[0]:.2f}° - {x[-1]:.2f}°")
    
    # Find peaks
    print("\n🔍 Finding peaks...")
    peaks = find_peaks_robust(x, y, prominence=prominence, distance=distance)
    print(f"   Found {len(peaks)} peaks")
    
    # Fit peaks
    if fit_peaks and peaks:
        print("\n📐 Fitting peaks with Gaussian...")
        for peak in peaks[:10]:  # Fit first 10 peaks
            fit_result = fit_peak(x, y, peak)
            if fit_result:
                peak['fit'] = fit_result
    
    results = {
        'file': os.path.basename(file_path),
        'n_points': len(x),
        'x_range': [float(x[0]), float(x[-1])],
        'n_peaks': len(peaks),
        'peaks': peaks
    }
    
    # Print summary
    print("\n" + "="*50)
    print("📊 Analysis Summary")
    print("="*50)
    print(f"File: {results['file']}")
    print(f"Points: {results['n_points']}")
    print(f"2θ range: {results['x_range'][0]:.1f}° - {results['x_range'][1]:.1f}°")
    print(f"Peaks found: {results['n_peaks']}")
    
    if peaks:
        print("\n📋 Peak details (first 10):")
        for i, peak in enumerate(peaks[:10]):
            info = f"  {i+1}. 2θ = {peak['two_theta']:.3f}°"
            info += f", I = {peak['intensity']:.0f}"
            if peak.get('fit'):
                info += f", FWHM = {peak['fit']['fwhm']:.3f}°"
            print(info)
        
        if len(peaks) > 10:
            print(f"  ... and {len(peaks) - 10} more peaks")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze XRD data (hybrid approach)')
    parser.add_argument('file', help='Path to .xy file')
    parser.add_argument('--prominence', type=float, default=0.05, help='Peak prominence (default: 0.05)')
    parser.add_argument('--distance', type=int, default=15, help='Minimum distance between peaks (default: 15)')
    parser.add_argument('--no-fit', action='store_true', help='Skip peak fitting')
    
    args = parser.parse_args()
    
    results = analyze_xrd(
        file_path=args.file,
        prominence=args.prominence,
        distance=args.distance,
        fit_peaks=not args.no_fit
    )
    
    # Basic plot
    x, y = load_xy_file(args.file)
    plt.figure(figsize=(10, 5))
    plt.plot(x, y, 'b-', linewidth=0.8, label='XRD pattern')
    
    # Mark peaks
    if results['peaks']:
        peak_x = [p['two_theta'] for p in results['peaks']]
        peak_y = [p['intensity'] for p in results['peaks']]
        plt.plot(peak_x, peak_y, 'rv', markersize=6, label=f'{len(peak_x)} peaks')
    
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity (counts)')
    plt.title(f'XRD Analysis: {os.path.basename(args.file)}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
