#!/usr/bin/env python3
"""
XRD Analyzer v3 - Improved peak fitting
"""

import numpy as np
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os

try:
    import powerxrd as xrd
    HAS_POWERXRD = True
except ImportError:
    HAS_POWERXRD = False


def gaussian(x, amp, cen, wid, offset):
    """Gaussian function for peak fitting (wid > 0 enforced)"""
    if wid <= 0:
        wid = 0.01  # Prevent negative width
    return amp * np.exp(-(x - cen)**2 / (2 * wid**2)) + offset


def load_xy_file(file_path):
    data = np.loadtxt(file_path)
    return data[:, 0], data[:, 1]


def find_peaks_robust(x, y, prominence=0.03, distance=10):
    y_norm = y / np.max(y)
    
    peaks, properties = find_peaks(
        y_norm,
        prominence=prominence,
        height=0.03,
        distance=distance,
        width=2
    )
    
    peak_list = []
    for idx in peaks:
        widths = peak_widths(y_norm, [idx], rel_height=0.5)
        fwhm = widths[0][0] * (x[1] - x[0]) if len(widths[0]) > 0 else 0
        
        peak_list.append({
            'index': idx,
            'two_theta': x[idx],
            'intensity': y[idx],
            'normalized_intensity': y_norm[idx],
            'fwhm_raw': fwhm
        })
    
    return peak_list


def fit_peak(x, y, peak_info, fit_range=1.5):
    center = peak_info['two_theta']
    x_min = center - fit_range
    x_max = center + fit_range
    
    mask = (x >= x_min) & (x <= x_max)
    x_fit = x[mask]
    y_fit = y[mask]
    
    if len(x_fit) < 5:
        return None
    
    # Estimate background as minimum value in the range
    offset = np.min(y_fit)
    y_fit_bg = y_fit - offset
    
    amp = np.max(y_fit_bg)
    wid = 0.3
    
    try:
        popt, _ = curve_fit(
            lambda x, amp, cen, wid: amp * np.exp(-(x - cen)**2 / (2 * wid**2)),
            x_fit, y_fit_bg,
            p0=[amp, center, wid],
            bounds=([0, center-1, 0.01], [np.inf, center+1, 2.0]),
            maxfev=2000
        )
        return {
            'amplitude': popt[0],
            'center': popt[1],
            'sigma': popt[2],
            'offset': offset,
            'fwhm': 2.355 * popt[2]
        }
    except:
        return None


def analyze_xrd(file_path, prominence=0.03, distance=10):
    print(f"📄 Analyzing: {file_path}")
    
    x, y = load_xy_file(file_path)
    
    if HAS_POWERXRD:
        try:
            chart = xrd.Chart(x, y)
            y_bg = chart.backsub(tol=1.0, inplace=False)[1]
            y = y_bg
            print("🔧 Background subtracted")
        except:
            print("⚠️ Using raw data")
    
    print(f"📊 Data: {len(x)} points, 2θ: {x[0]:.1f}° - {x[-1]:.1f}°")
    
    peaks = find_peaks_robust(x, y, prominence=prominence, distance=distance)
    print(f"🔍 Found {len(peaks)} peaks")
    
    # Fit peaks
    fitted_peaks = []
    for peak in peaks:
        fit = fit_peak(x, y, peak)
        if fit and fit['fwhm'] > 0 and fit['fwhm'] < 10:
            peak['fit'] = fit
            fitted_peaks.append(peak)
    
    print(f"📐 Fitted {len(fitted_peaks)} peaks")
    
    print("\n" + "="*50)
    print("📊 Analysis Summary")
    print("="*50)
    print(f"File: {os.path.basename(file_path)}")
    print(f"Peaks found: {len(peaks)}")
    print(f"Peaks fitted: {len(fitted_peaks)}")
    
    if fitted_peaks:
        print("\n📋 Fitted peaks:")
        for i, p in enumerate(fitted_peaks[:10]):
            fit = p['fit']
            print(f"  {i+1}. 2θ = {fit['center']:.3f}°, FWHM = {fit['fwhm']:.3f}°, I = {p['intensity']:.0f}")
        if len(fitted_peaks) > 10:
            print(f"  ... and {len(fitted_peaks) - 10} more")
    
    return {'peaks': peaks, 'fitted_peaks': fitted_peaks, 'x': x, 'y': y}


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to .xy file')
    parser.add_argument('--prominence', type=float, default=0.03)
    parser.add_argument('--distance', type=int, default=10)
    
    args = parser.parse_args()
    
    result = analyze_xrd(args.file, args.prominence, args.distance)
    
    # Plot
    x, y = load_xy_file(args.file)
    plt.figure(figsize=(10, 5))
    plt.plot(x, y, 'b-', linewidth=0.8, label='XRD pattern')
    
    if result['fitted_peaks']:
        peak_x = [p['fit']['center'] for p in result['fitted_peaks']]
        peak_y = [p['intensity'] for p in result['fitted_peaks']]
        plt.plot(peak_x, peak_y, 'rv', markersize=6, label=f'{len(peak_x)} fitted peaks')
    
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity (counts)')
    plt.title(f'XRD Analysis: {os.path.basename(args.file)}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
