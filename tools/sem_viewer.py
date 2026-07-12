#!/usr/bin/env python3
"""Standalone SEM Viewer"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from plot_xrd_v4 import plot_sem
import matplotlib.pyplot as plt

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sem_viewer.py <file.tif>")
        sys.exit(1)
    fig, error = plot_sem(sys.argv[1])
    if error:
        print(f"Error: {error}")
    else:
        plt.show()
