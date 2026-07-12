#!/usr/bin/env python3
"""Standalone XRD Viewer"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from plot_xrd_v4 import plot_xrd
import matplotlib.pyplot as plt

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python xrd_viewer.py <file.xy>")
        sys.exit(1)
    fig, error = plot_xrd(sys.argv[1])
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
