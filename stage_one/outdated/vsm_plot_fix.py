#!/usr/bin/env python3
"""
VSM Plotting - Fixed version
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from parse_vsm_my import parse_vsm_file


def plot_vsm(file_path, figure=None):
    """Plot VSM hysteresis loop with properly anchored Hc and Mr markers."""

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

    # Extract values
    hc = result.get('hc')
    mr = result.get('mr')
    ms = result.get('ms')

    # Data ranges
    x_min, x_max = np.min(fields), np.max(fields)
    y_min, y_max = np.min(moments), np.max(moments)

    x_pad = (x_max - x_min) * 0.05 if x_max > x_min else 1.0
    y_pad = (y_max - y_min) * 0.05 if y_max > y_min else 1.0

    # --- Hc: vertical lines at +/- Hc, labels near y = 0 ---
    if hc is not None:
        ax.axvline(hc, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
        ax.axvline(-hc, color='red', linestyle='--', alpha=0.7, linewidth=1.5)

        ax.annotate(
            f'Hc = {hc:.1f}',
            xy=(hc, 0),
            xycoords=ax.get_xaxis_transform(),
            xytext=(6, 6),
            textcoords='offset points',
            ha='left',
            va='bottom',
            color='red',
            fontsize=9
        )

        ax.annotate(
            f'Hc = {hc:.1f}',
            xy=(-hc, 0),
            xycoords=ax.get_xaxis_transform(),
            xytext=(-6, 6),
            textcoords='offset points',
            ha='right',
            va='bottom',
            color='red',
            fontsize=9
        )

        ax.plot([], [], 'r--', linewidth=1.5, label=f'Hc = {hc:.1f} Oe')

    # --- Mr: horizontal lines at +/- Mr, labels near x = 0 ---
    if mr is not None:
        ax.axhline(mr, color='green', linestyle='--', alpha=0.7, linewidth=1.5)
        ax.axhline(-mr, color='green', linestyle='--', alpha=0.7, linewidth=1.5)

        ax.annotate(
            f'Mr = {mr:.4f}',
            xy=(0, mr),
            xycoords=ax.get_yaxis_transform(),
            xytext=(6, 6),
            textcoords='offset points',
            ha='left',
            va='bottom',
            color='green',
            fontsize=9
        )

        ax.annotate(
            f'Mr = {mr:.4f}',
            xy=(0, -mr),
            xycoords=ax.get_yaxis_transform(),
            xytext=(6, -6),
            textcoords='offset points',
            ha='left',
            va='top',
            color='green',
            fontsize=9
        )

        ax.plot([], [], 'g--', linewidth=1.5, label=f'Mr = {mr:.4f} emu')

    # Axes limits
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)

    # Labels and styling
    ax.set_xlabel('Field (Oe)')
    ax.set_ylabel('Moment (emu)')
    ax.set_title(f'VSM Hysteresis Loop: {Path(file_path).name}')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.axvline(0, color='black', linewidth=0.5, alpha=0.3)
    ax.legend(loc='best')

    # Info box
    info_lines = []
    if ms is not None:
        info_lines.append(f"Ms: {ms:.4f} emu")
    if mr is not None:
        info_lines.append(f"Mr: {mr:.4f} emu")
    if hc is not None:
        info_lines.append(f"Hc: {hc:.1f} Oe")
    if result.get('mass'):
        info_lines.append(f"Mass: {result['mass'] * 1000:.1f} mg")
    if result.get('ms_per_g'):
        info_lines.append(f"Ms/g: {result['ms_per_g']:.2f} emu/g")

    info = "\n".join(info_lines)
    ax.text(
        0.02, 0.98, info,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
    )

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