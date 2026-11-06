"""Print every conflict the parsed-database merge reports for a failing and two passing combinations.
Run from stage4_step1/:  python3 merge_conflicts.py
"""
import sys
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from tdb_merge import merge_databases
bin_dir = Path("../../data/tdb/sgte_binary")
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
cases = {
 "FAILS   (Wit + NdB-19Che, lacking x supplying)": ("FeNd-16Che", "FeB-19Wit", "NdB-19Che"),
 "PASSES  (Tak + NdB-19Che, both supply)":         ("FeNd-16Che", "FeB-20Tak", "NdB-19Che"),
 "PASSES  (Wit + NdB-95Hal-LB, neither supplies)": ("FeNd-16Che", "FeB-19Wit", "NdB-95Hal-LB"),
}
for label, ids in cases.items():
    print(f"\n===== {label}")
    merge_databases([f(i) for i in ids], report=print)
