"""Decisive test of the end-member hypothesis. Run from stage4_step1/:  python3 test_endmember_hypothesis.py
Part 1: which of the 14 binary files define G(FCC_A1/BCC_A2/HCP_A3, B:VA; 0), and where does GBCCBB/GHCPBB appear?
Part 2: merge FeNd-16Che + FeB-19Wit + NdB-19Che with those three NdB-19Che parameters REMOVED; run the edge check.
        If the Fe-B edge now passes (<= 1 J/mol), the three Nd-B end-member parameters are the cause.
"""
import sys, tempfile
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from pycalphad import Database
from tinydb import where
from tdb_merge import merge_databases, check_edges

bin_dir = Path("../../data/tdb/sgte_binary")
PH = ("FCC_A1", "BCC_A2", "HCP_A3")
def is_B_end(p):
    ca = [tuple(getattr(sp, "name", str(sp)) for sp in sub) for sub in p["constituent_array"]]
    return len(ca) == 2 and ca[0] == ("B",) and ca[1] == ("VA",) and str(p["parameter_type"]) == "G"

print("=== Part 1: explicit pure-B end-members in FCC_A1/BCC_A2/HCP_A3, and use of GBCCBB/GHCPBB")
for f in sorted(bin_dir.rglob("*.tdb")):
    if not f.name.startswith(("FeB-", "NdB-")): continue
    db = Database(str(f)); txt = f.read_text(errors="ignore")
    have = sorted({p["phase_name"] for ph in PH for p in db._parameters.search(where("phase_name") == ph) if is_B_end(p)})
    print(f"{f.name:28s} B:VA end-members: {(', '.join(have) if have else 'none'):28} GBCCBB in text: {txt.count('GBCCBB'):2d}  GHCPBB: {txt.count('GHCPBB'):2d}")

print("\n=== Part 2: remove the three NdB-19Che end-members, re-merge, re-check edges")
fe, feb, nb = (next(bin_dir.rglob(n)) for n in ("FeNd-16Che.tdb", "FeB-19Wit.tdb", "NdB-19Che.tdb"))
dbn = Database(str(nb))
rem = [p for ph in PH for p in dbn._parameters.search(where("phase_name") == ph) if is_B_end(p)]
for p in rem: dbn._parameters.remove(doc_ids=[p.doc_id])
print("removed", len(rem), "parameters")
with tempfile.TemporaryDirectory() as td:
    mod = Path(td) / "NdB-19Che_noBend.tdb"
    dbn.to_file(str(mod), fmt="tdb", if_exists="overwrite", if_incompatible="ignore")
    merged = merge_databases([fe, feb, mod])
    ok = check_edges(merged, [fe, feb, nb])
print("\nEDGE CHECK", "PASSES -> end-member parameters are the cause" if ok else "STILL FAILS -> cause is elsewhere")
