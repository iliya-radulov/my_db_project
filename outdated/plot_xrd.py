from pathlib import Path
#!/usr/bin/env python3
"""
XRD Plotting Module
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from parse_xy_v2 import parse_xy_file, find_peaks

def plot_xrd(file_path, figure=None):
    """Plot XRD data with peaks marked"""
    
    data = parse_xy_file(file_path)
    if data is None:
        return None, "Failed to parse file"
    
    two_theta = data['two_theta']
    intensity = data['intensity']
    
    # Find peaks
    peaks = find_peaks(two_theta, intensity)
    
    if figure is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = figure
        ax = fig.add_subplot(111)
    
    # Plot data
    ax.plot(two_theta, intensity, 'b-', linewidth=0.8, label='XRD pattern')
    
    # Mark peaks
    for peak in peaks[:20]:  # Show first 20 peaks
        ax.axvline(peak['two_theta'], color='r', linestyle='--', alpha=0.5, linewidth=0.8)
        ax.text(peak['two_theta'], peak['intensity'] * 0.9, 
                f'{peak["two_theta"]:.1f}°', 
                rotation=90, fontsize=8, ha='center', va='bottom')
    
    ax.set_xlabel('2θ (degrees)')
    ax.set_ylabel('Intensity (counts)')
    ax.set_title(f'XRD Pattern: {Path(file_path).name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Add info text
    info = f"Peaks: {len(peaks)}\nMax: {data['max_intensity']:.0f}\nRange: {data['start']:.1f}° - {data['end']:.1f}°"
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig, None


def plot_vsm(file_path, figure=None):
    """Plot VSM hysteresis loop"""
    
    from parse_vsm_with_mass import parse_vsm_file
    
    result = parse_vsm_file(file_path)
    if 'error' in result:
        return None, result['error']
    
    fields = np.array(result['fields'])
    moments = np.array(result['moments'])
    
    if figure is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = figure
        ax = fig.add_subplot(111)
    
    # Plot hysteresis loop
    ax.plot(fields, moments, 'b-', linewidth=1.2)
    
    # Mark Hc and Mr
    if result.get('hc'):
        ax.axvline(result['hc'], color='r', linestyle='--', alpha=0.5, label=f"Hc = {result['hc']:.1f} Oe")
        ax.axvline(-result['hc'], color='r', linestyle='--', alpha=0.5)
    
    if result.get('mr'):
        ax.axhline(result['mr'], color='g', linestyle='--', alpha=0.5, label=f"Mr = {result['mr']:.4f} emu")
        ax.axhline(-result['mr'], color='g', linestyle='--', alpha=0.5)
    
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Add info text
    info = f"Ms: {result['ms']:.4f} emu\nMr: {result['mr']:.4f} emu\nHc: {result['hc']:.1f} Oe"
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig, None


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Usage: python plot_xrd.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if file_path.lower().endswith('.xy'):
        fig, error = plot_xrd(file_path)
        if error:
            print(f"Error: {error}")
        else:
            plt.show()
    elif file_path.lower().endswith('.dat'):
        fig, error = plot_vsm(file_path)
        if error:
            print(f"Error: {error}")
        else:
            plt.show()
    else:
        print("Unsupported file type")
