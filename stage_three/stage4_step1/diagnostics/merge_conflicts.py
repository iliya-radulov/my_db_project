"""Print every conflict the parsed-database merge reports for a failing and two passing combinations.
Run from anywhere:  python3 merge_conflicts.py
"""
import sys
from _common import BIN_DIR, RESULTS, S4
from pathlib import Path
from tdb_merge import merge_databases
bin_dir = BIN_DIR
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
cases = {
 "FAILS   (Wit + NdB-19Che, lacking x supplying)": ("FeNd-16Che", "FeB-19Wit", "NdB-19Che"),
 "PASSES  (Tak + NdB-19Che, both supply)":         ("FeNd-16Che", "FeB-20Tak", "NdB-19Che"),
 "PASSES  (Wit + NdB-95Hal-LB, neither supplies)": ("FeNd-16Che", "FeB-19Wit", "NdB-95Hal-LB"),
}
for label, ids in cases.items():
    print(f"\n===== {label}")
    merge_databases([f(i) for i in ids], report=print)
