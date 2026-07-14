#!/usr/bin/env python3
"""
XRD, VSM, and SEM Plotting Module
- XRD: 2θ vs Intensity plot
- VSM: Hysteresis loop
- SEM: Display image
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from PIL import Image
from stage_one.parsers.parse_xrd_v1 import parse_xy_file, find_peaks
from stage_one.parsers.parse_vsm_v1 import parse_vsm_file

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
    
    hc = result.get('hc')
    mr = result.get('mr')
    ms = result.get('ms')

    # Get data ranges
    x_min, x_max = np.min(fields), np.max(fields)
    y_min, y_max = np.min(moments), np.max(moments)
    x_pad = (x_max - x_min) * 0.05
    y_pad = (y_max - y_min) * 0.05

    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)
    
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
    
    info = f"Ms: {ms:.4f} emu\nMr: {mr:.4f} emu\nHc: {hc:.1f} Oe"
    if result.get('mass'):
        info += f"\nMass: {result['mass']*1000:.1f} mg"
    if result.get('ms_per_g'):
        info += f"\nMs/g: {result['ms_per_g']:.2f} emu/g"
    
    ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    return fig, None


def plot_sem(file_path, figure=None):
    """Display SEM image from .tif file"""
    
    try:
        img = Image.open(file_path)
        
        if figure is not None:
            plt.close(figure)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Display the image
        ax.imshow(img, cmap='gray')
        ax.axis('off')
        ax.set_title(f'SEM Image: {Path(file_path).name}')
        
        # Add scale bar info from metadata if available
        from stage_one.parsers.parse_sem_v1 import parse_sem_file
        metadata = parse_sem_file(file_path)
        if metadata and not metadata.get('error'):
            info = []
            if metadata.get('magnification'):
                info.append(f"Mag: {metadata['magnification']}")
            if metadata.get('eht_kv'):
                info.append(f"EHT: {metadata['eht_kv']}")
            if metadata.get('working_distance_mm'):
                info.append(f"WD: {metadata['working_distance_mm']}")
            if metadata.get('pixel_size_nm'):
                info.append(f"Pixel: {metadata['pixel_size_nm']}")
            if info:
                ax.text(0.02, 0.98, '\n'.join(info), transform=ax.transAxes, fontsize=9,
                        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        return fig, None
        
    except Exception as e:
        return None, f"Error displaying SEM image: {str(e)}"


def close_figures():
    """Close all matplotlib figures to free memory"""
    plt.close('all')


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python plot_v1.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        sys.exit(1)
    
    if file_path.lower().endswith('.xy'):
        fig, error = plot_xrd(file_path)
    elif file_path.lower().endswith('.dat'):
        fig, error = plot_vsm(file_path)
    elif file_path.lower().endswith(('.tif', '.tiff')):
        fig, error = plot_sem(file_path)
    else:
        print("Unsupported file type")
        sys.exit(1)
    
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
