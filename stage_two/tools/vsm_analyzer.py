#!/usr/bin/env python3
"""
VSM Analyzer using magmeas
Standalone tool for magnetic measurement analysis
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys
import os
import json

try:
    from magmeas import MH_major
    HAS_MAGMEAS = True
except ImportError:
    HAS_MAGMEAS = False
    print("⚠️ magmeas not installed. Run: pip install magmeas")


def analyze_vsm(file_path, show_plot=True):
    """
    Analyze VSM data using magmeas
    """
    
    if not HAS_MAGMEAS:
        print("❌ magmeas not available")
        return None
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    print(f"📄 Analyzing: {file_path}")
    
    try:
        # Load the VSM data
        mh = MH_major(file_path)
        
        # Extract properties
        result = {
            'file': os.path.basename(file_path),
            'coercivity': None,
            'remanence': None,
            'saturation': None,
            'bhmax': None
        }
        
        # Try to get properties
        try:
            result['coercivity'] = float(mh.coercivity)
            print(f"   Hc = {result['coercivity']:.1f} Oe")
        except:
            print("   ⚠️ Coercivity not available")
        
        try:
            result['remanence'] = float(mh.remanence)
            print(f"   Mr = {result['remanence']:.4f} emu")
        except:
            print("   ⚠️ Remanence not available")
        
        try:
            result['saturation'] = float(mh.saturation)
            print(f"   Ms = {result['saturation']:.4f} emu")
        except:
            print("   ⚠️ Saturation not available")
        
        try:
            result['bhmax'] = float(mh.BHmax)
            print(f"   BHmax = {result['bhmax']:.1f} kJ/m³")
        except:
            print("   ⚠️ BHmax not available")
        
        # Show plot
        if show_plot:
            print("\n📈 Generating plot...")
            try:
                fig, ax1, ax2 = mh.plot(unit=("MA/m", "T"), linestyle="-", label=os.path.basename(file_path))
                ax1.set_title(f"VSM Hysteresis Loop: {os.path.basename(file_path)}")
                ax1.legend()
                plt.tight_layout()
                plt.show()
            except Exception as e:
                print(f"   ⚠️ Plot error: {e}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def analyze_multiple_vsm(file_paths):
    """Analyze multiple VSM files"""
    results = []
    for fp in file_paths:
        print(f"\n{'='*40}")
        result = analyze_vsm(fp, show_plot=False)
        if result:
            results.append(result)
    
    # Print summary
    print("\n" + "="*50)
    print("📊 VSM Analysis Summary")
    print("="*50)
    print(f"{'File':<35} {'Hc (Oe)':<12} {'Mr (emu)':<12} {'Ms (emu)':<12}")
    print("-"*71)
    for r in results:
        if r:
            name = r['file'][:35]
            hc = f"{r['coercivity']:.1f}" if r['coercivity'] else "N/A"
            mr = f"{r['remanence']:.4f}" if r['remanence'] else "N/A"
            ms = f"{r['saturation']:.4f}" if r['saturation'] else "N/A"
            print(f"{name:<35} {hc:<12} {mr:<12} {ms:<12}")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='VSM Analyzer using magmeas')
    parser.add_argument('file', nargs='+', help='Path to .dat file(s)')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot display')
    
    args = parser.parse_args()
    
    if len(args.file) == 1:
        analyze_vsm(args.file[0], show_plot=not args.no_plot)
    else:
        analyze_multiple_vsm(args.file)


if __name__ == "__main__":
    main()
