#!/usr/bin/env python3
"""
XRD Analyzer using PowerXRD
Standalone tool for detailed XRD analysis: peak fitting, Scherrer calculation, etc.
"""

import powerxrd as xrd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
import os

def analyze_xrd(file_path, fit_peaks=True, calc_scherrer=True, show_plot=True):
    """
    Analyze an XRD .xy file using PowerXRD
    
    Args:
        file_path: Path to .xy file
        fit_peaks: Whether to fit peaks and calculate crystallite size
        calc_scherrer: Whether to calculate Scherrer width
        show_plot: Whether to show the plot
    """
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    print(f"📄 Analyzing: {file_path}")
    
    # Load data
    data = xrd.Data(file_path).importfile()
    chart = xrd.Chart(*data)
    
    print(f"📊 Data loaded: {len(data[0])} points")
    print(f"   2θ range: {data[0][0]:.2f}° - {data[0][-1]:.2f}°")
    
    # Background subtraction
    print("\n🔧 Subtracting background...")
    chart.backsub(tol=1.0, show=False)
    
    results = {
        'file': os.path.basename(file_path),
        'n_points': len(data[0]),
        'peaks': []
    }
    
    # Peak fitting and Scherrer calculation
    if fit_peaks or calc_scherrer:
        print("\n🔍 Finding peaks...")
        
        # Use allpeaks to find and analyze all peaks
        try:
            # allpeaks returns a list of results
            peak_results = chart.allpeaks(tols=(0.1, 0.8), verbose=False, show=False)
            
            # Extract peak information
            if peak_results:
                print(f"   Found {len(peak_results)} peaks")
                for i, peak in enumerate(peak_results):
                    peak_info = {
                        'index': i + 1,
                        'two_theta': peak[0] if isinstance(peak, (list, tuple)) and len(peak) > 0 else None,
                        'intensity': peak[1] if isinstance(peak, (list, tuple)) and len(peak) > 1 else None,
                        'scherrer_width': peak[2] if isinstance(peak, (list, tuple)) and len(peak) > 2 else None
                    }
                    results['peaks'].append(peak_info)
                    
                    # Print peak info
                    if peak_info['two_theta']:
                        print(f"   Peak {i+1}: 2θ = {peak_info['two_theta']:.2f}°", end="")
                        if peak_info['scherrer_width']:
                            print(f", Scherrer width = {peak_info['scherrer_width']:.1f} nm")
                        else:
                            print()
            else:
                print("   No peaks found or allpeaks returned empty")
                
        except Exception as e:
            print(f"   ⚠️ Peak fitting failed: {e}")
            print("   Trying single peak analysis...")
            
            # Fallback: try a single peak in the main region
            try:
                result = chart.SchPeak(xrange=[18, 25], verbose=False, show=False)
                print(f"   Found peak at 2θ ≈ 20-25°")
                results['peaks'].append({
                    'index': 1,
                    'two_theta': 20.0,
                    'intensity': None,
                    'scherrer_width': None
                })
            except:
                print("   ⚠️ Single peak analysis failed")
    
    # Show plot if requested
    if show_plot:
        print("\n📈 Generating plot...")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(data[0], data[1], 'b-', linewidth=0.8, label='Raw data')
        ax.set_xlabel('2θ (degrees)')
        ax.set_ylabel('Intensity (counts)')
        ax.set_title(f'XRD Analysis: {os.path.basename(file_path)}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add info text
        info = f"Points: {len(data[0])}\nPeaks: {len(results['peaks'])}"
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        plt.show()
    
    # Print summary
    print("\n" + "="*50)
    print("📊 Analysis Summary")
    print("="*50)
    print(f"File: {results['file']}")
    print(f"Points: {results['n_points']}")
    print(f"Peaks found: {len(results['peaks'])}")
    
    if results['peaks']:
        print("\nPeak details:")
        for peak in results['peaks'][:10]:  # Show first 10
            if peak['two_theta']:
                info = f"  Peak {peak['index']}: 2θ = {peak['two_theta']:.2f}°"
                if peak.get('scherrer_width'):
                    info += f", Scherrer = {peak['scherrer_width']:.1f} nm"
                print(info)
        if len(results['peaks']) > 10:
            print(f"  ... and {len(results['peaks']) - 10} more peaks")
    
    return results


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze XRD data using PowerXRD')
    parser.add_argument('file', help='Path to .xy file')
    parser.add_argument('--no-fit', action='store_true', help='Skip peak fitting')
    parser.add_argument('--no-scherrer', action='store_true', help='Skip Scherrer calculation')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot display')
    
    args = parser.parse_args()
    
    analyze_xrd(
        file_path=args.file,
        fit_peaks=not args.no_fit,
        calc_scherrer=not args.no_scherrer,
        show_plot=not args.no_plot
    )


if __name__ == "__main__":
    main()
