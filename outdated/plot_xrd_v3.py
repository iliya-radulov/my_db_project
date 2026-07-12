#!/usr/bin/env python3
"""
XRD and VSM Plotting Module - Fixed hysteresis loop markers
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from parse_xy_v2 import parse_xy_file, find_peaks
from parse_vsm_final2 import parse_vsm_file

def plot_xrd(file_path, figure=None):
    """Plot XRD data with peaks marked"""
    
    data = parse_xy_file(file_path)
    if data is None:
        return None, "Failed to parse file"
    
    two_theta = data['two_theta']
    intensity = data['intensity']
    peaks = find_peaks(two_theta, intensity)
    
    if figure is not None:
        plt.close(figure)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(two_theta, intensity, 'b-', linewidth=0.8, label='XRD pattern')
    
    for peak in peaks[:20]:
        ax.axvline(peak['two_theta'], color='r', linestyle='--', alpha=0.5, linewidth=0.8)
        ax.text(peak['two_theta'], peak['intensity'] * 0.9, 
                f'{peak["two_theta"]:.1f}°', 
                rotation=90, fontsize=8, ha='center', va='bottom')
    
    ax.set_xlabel('2θ (degrees)')
    ax.set_ylabel('Intensity (counts)')
    ax.set_title(f'XRD Pattern: {Path(file_path).name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    info = f"Peaks: {len(peaks)}\nMax: {data['max_intensity']:.0f}\nRange: {data['start']:.1f}° - {data['end']:.1f}°"
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig, None


def plot_vsm(file_path, figure=None):
    """Plot VSM hysteresis loop with proper Hc and Mr markers"""
    
    result = parse_vsm_file(file_path)
    if 'error' in result:
        return None, result['error']
    
    fields = np.array(result['fields'])
    moments = np.array(result['moments'])
    
    if figure is not None:
        plt.close(figure)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Main hysteresis loop
    ax.plot(fields, moments, 'b-', linewidth=1.2, label='Hysteresis loop')
    
    # Get values
    hc = result.get('hc')
    mr = result.get('mr')
    ms = result.get('ms')
    
    # Get current limits (will be adjusted after loop)
    x_min = np.min(fields) * 1.1
    x_max = np.max(fields) * 1.1
    y_min = np.min(moments) * 1.1
    y_max = np.max(moments) * 1.1
    
    # Set limits FIRST so lines span correctly
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    
    # --- Hc: red line at zero moment (x-axis crossing) ---
    if hc:
        ax.axvline(hc, color='r', linestyle='--', alpha=0.7, linewidth=1.5, label=f'Hc = {hc:.1f} Oe')
        ax.axvline(-hc, color='r', linestyle='--', alpha=0.7, linewidth=1.5)
        ax.text(hc, 0, f' Hc={hc:.1f}', fontsize=8, ha='left', va='center', color='red')
        ax.text(-hc, 0, f' Hc={hc:.1f}', fontsize=8, ha='right', va='center', color='red')
    
    # --- Mr: green line at zero field (y-axis crossing) ---
    if mr:
        ax.axhline(mr, color='g', linestyle='--', alpha=0.7, linewidth=1.5, label=f'Mr = {mr:.4f} emu')
        ax.axhline(-mr, color='g', linestyle='--', alpha=0.7, linewidth=1.5)
        ax.text(0, mr, f' Mr={mr:.4f}', fontsize=8, ha='left', va='bottom', color='green')
        ax.text(0, -mr, f' Mr={mr:.4f}', fontsize=8, ha='left', va='top', color='green')
    
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Info box
    info = f"Ms: {ms:.4f} emu\nMr: {mr:.4f} emu\nHc: {hc:.1f} Oe"
    if result.get('mass'):
        info += f"\nMass: {result['mass']*1000:.1f} mg"
    if result.get('ms_per_g'):
        info += f"\nMs/g: {result['ms_per_g']:.2f} emu/g"
    
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig, None


def close_figures():
    """Close all matplotlib figures to free memory"""
    plt.close('all')


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python plot_xrd_v3.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    if file_path.lower().endswith('.xy'):
        fig, error = plot_xrd(file_path)
    elif file_path.lower().endswith('.dat'):
        fig, error = plot_vsm(file_path)
    else:
        print("Unsupported file type. Use .xy for XRD or .dat for VSM.")
        sys.exit(1)
    
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
