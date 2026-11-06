"""Which pure-boron end-member parameters differ between the merged TDB and its sources?
Run from stage4_step1/:  python3 diag_fcc_B.py
Adjust bin_dir if needed. Prints, for FCC_A1/BCC_A2/HCP_A3 parameters with constituent array (B):(VA),
the expression and its value at 1600 K in: FeB-19Wit, NdB-19Che, and the merged description.
"""
import sys
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from pycalphad import Database, variables as v
from tinydb import where

bin_dir = Path("../../data/tdb/sgte_binary")
merged = Path("results_v2/merged_tdbs/FENDB_merged_v4__FeNd-16Che___FeB-19Wit___NdB-19Che.tdb")
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
            ca = [tuple(x) for x in p["constituent_array"]]
            if ca and set(ca[0]) == {"B"} and p["parameter_type"] == "G":
                print(f"{ph:7s} {ca} order={p['parameter_order']}  G(1600K) = {val(db, p['parameter'])}")
                print(f"        expr: {str(p['parameter'])[:110]}")
    for sym in ("GBCCBB", "GHCPBB", "GFCCBB"):
        if sym in db.symbols:
            print(f"symbol {sym}: defined, value(1600K) = {val(db, db.symbols[sym])}")
        else:
            print(f"symbol {sym}: NOT defined")
