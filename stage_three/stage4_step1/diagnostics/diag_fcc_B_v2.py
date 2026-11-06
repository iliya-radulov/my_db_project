"""Which pure-boron end-member parameters differ between the merged TDB and its sources?
Run from anywhere:  python3 diag_fcc_B.py
Adjust bin_dir if needed. Prints, for FCC_A1/BCC_A2/HCP_A3 parameters with constituent array (B):(VA),
the expression and its value at 1600 K in: FeB-19Wit, NdB-19Che, and the merged description.
"""
import sys
from _common import BIN_DIR, RESULTS, S4
from pathlib import Path
from pycalphad import Database, variables as v
from tinydb import where

bin_dir = BIN_DIR
merged = RESULTS / ("merged_tdbs/FENDB_merged_v4__FeNd-16Che___FeB-19Wit___NdB-19Che.tdb")
files = {"FeB-19Wit": next(bin_dir.rglob("FeB-19Wit.tdb")),
         "NdB-19Che": next(bin_dir.rglob("NdB-19Che.tdb")),
         "MERGED": merged}

def val(db, expr, T=1600.0):
    try:
        e = expr
        for _ in range(6):                      # resolve nested symbols
            e = e.subs({v.T: T}).subs({k: s for k, s in db.symbols.items()})
        return float(e)
    except Exception as ex:
        return f"n/a ({type(ex).__name__})"

for label, path in files.items():
    db = Database(str(path))
    print(f"\n=== {label}")
    for ph in ("FCC_A1", "BCC_A2", "HCP_A3", "LIQUID"):
        for p in db._parameters.search(where("phase_name") == ph):
            ca = [tuple(getattr(sp, "name", str(sp)) for sp in sub) for sub in p["constituent_array"]]
            if ca and set(ca[0]) == {"B"} and str(p["parameter_type"]) == "G":
                print(f"{ph:7s} {ca} order={p['parameter_order']}  G(1600K) = {val(db, p['parameter'])}")
                print(f"        expr: {str(p['parameter'])[:110]}")
    for sym in ("GBCCBB", "GHCPBB", "GFCCBB"):
        if sym in db.symbols:
            print(f"symbol {sym}: defined, value(1600K) = {val(db, db.symbols[sym])}")
        else:
            print(f"symbol {sym}: NOT defined")
