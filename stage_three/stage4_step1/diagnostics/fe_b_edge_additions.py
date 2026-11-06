"""Exactly what does the merge add to / change on the Fe-B edge?  Run from anywhere:  python3 fe_b_edge_additions.py
Merges FeNd-16Che + FeB-19Wit + NdB-19Che, then lists (a) every parameter living on the Fe-B edge (constituents only FE, B, VA)
that is absent from FeB-19Wit alone or has a different expression, and (b) every symbol whose definition differs from FeB-19Wit
or that FeB-19Wit does not define.
"""
import sys
from _common import BIN_DIR, RESULTS, S4
from pathlib import Path
from pycalphad import Database
from tdb_merge import merge_databases
bin_dir = BIN_DIR
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
wit = Database(str(f("FeB-19Wit")))
merged = merge_databases([f("FeNd-16Che"), f("FeB-19Wit"), f("NdB-19Che")], report=lambda *a, **k: None)
ALLOWED = {"FE", "B", "VA"}
def key(p):
    ca = tuple(tuple(getattr(sp, "name", str(sp)) for sp in sub) for sub in p["constituent_array"])
    return (p["phase_name"], ca, str(p["parameter_type"]), p["parameter_order"]), ca
def table(db):
    t = {}
    for p in db._parameters.all():
        k, ca = key(p)
        if all(c in ALLOWED for sub in ca for c in sub):
            t[k] = str(p["parameter"])
    return t
tw, tm = table(wit), table(merged)
print("=== (a) Fe-B-edge parameters in MERGED that are absent from / differ from FeB-19Wit alone")
n = 0
for k, e in sorted(tm.items(), key=lambda kv: str(kv[0])):
    if k not in tw:        print("ADDED   ", k, "\n          ", e[:140]); n += 1
    elif tw[k] != e:       print("CHANGED ", k, "\n   wit:   ", tw[k][:140], "\n   merged:", e[:140]); n += 1
print(f"-> {n} difference(s); (parameters in Wit but missing in merged: {[k for k in tw if k not in tm]})")
print("\n=== (b) symbols: not defined in FeB-19Wit, or different there")
for name, expr in sorted(merged.symbols.items()):
    if name not in wit.symbols:            print("NEW      ", name, "=", str(expr)[:100])
    elif str(wit.symbols[name]) != str(expr): print("DIFFERENT", name, "\n   wit:   ", str(wit.symbols[name])[:100], "\n   merged:", str(expr)[:100])
