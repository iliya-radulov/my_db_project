#!/usr/bin/env python3
"""
PowerXRD Analyzer - Standalone tool
Uses PowerXRD for professional XRD analysis
"""

import powerxrd as xrd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
import os
import json

def analyze_xrd_powerxrd(file_path, peak_range=[18, 22], show_plot=True):
    """
    Analyze XRD using PowerXRD's SchPeak method
    """
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    print(f"📄 Analyzing: {file_path}")
    
    # Load data
    data = xrd.Data(file_path).importfile()
    chart = xrd.Chart(*data)
    
    print(f"📊 Data: {len(data[0])} points, 2θ: {data[0][0]:.1f}° - {data[0][-1]:.1f}°")
    
    # Background subtraction
    print("🔧 Subtracting background...")
    chart.backsub(tol=1.0, show=False)
    
    # Run SchPeak
    print(f"\n🔍 Analyzing peak in range {peak_range[0]}-{peak_range[1]}°...")
    
    # Capture output
    import io
    import sys as sys_module
    old_stdout = sys_module.stdout
    sys_module.stdout = io.StringIO()
    
    try:
        # SchPeak prints to stdout, we capture it
        chart.SchPeak(xrange=peak_range, verbose=True, show=False)
        output = sys_module.stdout.getvalue()
    except Exception as e:
        sys_module.stdout = old_stdout
        print(f"❌ Error: {e}")
        return None
    finally:
        sys_module.stdout = old_stdout
    
    # Parse the output
    result = {
        'file': os.path.basename(file_path),
        'peak_range': peak_range,
        'raw_output': output,
        'fwhm': None,
        'scherrer_width': None,
        'max_two_theta': None,
        'fit_params': {}
    }
    
    # Extract values from output
    for line in output.split('\n'):
        if 'FWHM == sigma*2*sqrt(2*ln(2)):' in line:
            try:
                result['fwhm'] = float(line.split(':')[-1].strip().split()[0])
            except:
                pass
        if 'SCHERRER WIDTH:' in line:
            try:
                result['scherrer_width'] = float(line.split(':')[-1].strip().split()[0])
            except:
                pass
        if 'max 2-theta:' in line:
            try:
                result['max_two_theta'] = float(line.split(':')[-1].strip().split()[0])
            except:
                pass
    
    # Print results
    print("\n" + "="*50)
    print("📊 PowerXRD Analysis Results")
    print("="*50)
    print(f"File: {result['file']}")
    print(f"Peak range: {peak_range[0]}° - {peak_range[1]}°")
    print(f"Peak position (2θ): {result.get('max_two_theta', 'N/A')}")
    print(f"FWHM: {result.get('fwhm', 'N/A')}°")
    print(f"Scherrer width: {result.get('scherrer_width', 'N/A')} nm")
    
    # Show plot
    if show_plot:
        print("\n📈 Generating plot...")
        chart.backsub(tol=1.0, show=True)
        chart.SchPeak(xrange=peak_range, verbose=False, show=True)
        plt.title(f'XRD Analysis: {os.path.basename(file_path)}')
        plt.show()
    
    return result


def analyze_multiple_peaks(file_path, peak_ranges=None, show_plot=True):
    """
    Analyze multiple peaks using PowerXRD
    """
    if peak_ranges is None:
        # Default ranges for common peaks
        peak_ranges = [
            [18, 22],    # Main peak region
            [30, 35],    # Secondary peaks
            [40, 45],    # Higher angle peaks
        ]
    
    results = []
    for p_range in peak_ranges:
        print(f"\n{'='*30}")
        print(f"Analyzing range: {p_range[0]}° - {p_range[1]}°")
        result = analyze_xrd_powerxrd(file_path, p_range, show_plot=False)
        if result:
            results.append(result)
    
    # Print summary
    print("\n" + "="*50)
    print("📊 Multiple Peak Analysis Summary")
    print("="*50)
    print(f"File: {os.path.basename(file_path)}")
    print(f"{'Range':<20} {'2θ':<10} {'FWHM':<10} {'Scherrer (nm)':<15}")
    print("-"*55)
    for r in results:
        if r and r.get('max_two_theta'):
            print(f"{r['peak_range'][0]:.0f}-{r['peak_range'][1]:.0f}°{' ':<14} "
                  f"{r['max_two_theta']:.2f}{' ':<8} "
                  f"{r['fwhm']:.3f}{' ':<7} "
                  f"{r['scherrer_width']:.2f}")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='PowerXRD Analyzer')
    parser.add_argument('file', help='Path to .xy file')
    parser.add_argument('--range', nargs=2, type=float, default=[18, 22],
                        help='Peak range to analyze (default: 18 22)')
    parser.add_argument('--multi', action='store_true',
                        help='Analyze multiple peak ranges')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot display')
    
    args = parser.parse_args()
    
    if args.multi:
        analyze_multiple_peaks(args.file, show_plot=not args.no_plot)
    else:
        analyze_xrd_powerxrd(args.file, args.range, show_plot=not args.no_plot)


if __name__ == "__main__":
    main()
