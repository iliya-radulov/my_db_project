#!/usr/bin/env python3
"""
VSM Plotting - Fixed version
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from parse_vsm_final2 import parse_vsm_file

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
    
    # Get data ranges
    x_min, x_max = np.min(fields), np.max(fields)
    y_min, y_max = np.min(moments), np.max(moments)
    
    # Add some padding
    x_pad = (x_max - x_min) * 0.05
    y_pad = (y_max - y_min) * 0.05
    
    # --- Hc: red line at zero moment ---
    if hc:
        ax.plot([hc, hc], [y_min - y_pad, y_max + y_pad], 'r--', alpha=0.7, linewidth=1.5)
        ax.plot([-hc, -hc], [y_min - y_pad, y_max + y_pad], 'r--', alpha=0.7, linewidth=1.5)
        # Label at zero
        ax.text(hc, 0, f' Hc={hc:.1f}', fontsize=9, ha='left', va='center', color='red')
        ax.text(-hc, 0, f' Hc={hc:.1f}', fontsize=9, ha='right', va='center', color='red')
        ax.plot([], [], 'r--', linewidth=1.5, label=f'Hc = {hc:.1f} Oe')
    
    # --- Mr: green line at zero field ---
    if mr:
        ax.plot([x_min - x_pad, x_max + x_pad], [mr, mr], 'g--', alpha=0.7, linewidth=1.5)
        ax.plot([x_min - x_pad, x_max + x_pad], [-mr, -mr], 'g--', alpha=0.7, linewidth=1.5)
        # Label at zero
        ax.text(0, mr, f' Mr={mr:.4f}', fontsize=9, ha='left', va='bottom', color='green')
        ax.text(0, -mr, f' Mr={mr:.4f}', fontsize=9, ha='left', va='top', color='green')
        ax.plot([], [], 'g--', linewidth=1.5, label=f'Mr = {mr:.4f} emu')
    
    # Set limits
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)
    
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
    
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


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python plot_vsm_only.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    fig, error = plot_vsm(file_path)
    
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
