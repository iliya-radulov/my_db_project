"""Decisive in-memory test. Run from stage4_step1/:  python3 test_remove_added.py
Merge FeNd-16Che + FeB-19Wit + NdB-19Che, delete the four parameters the merge ADDED on the Fe-B edge
(B:VA end-members of BCC_A2/FCC_A1/HCP_A3 and B:B of NDB6_D21), no file export, then check the Fe-Nd and Fe-B edges.
PASS (<= 1 J/mol) on Fe-B proves these four parameters are the whole cause.  (The Nd-B edge is not checked: it legitimately changes.)
"""
import sys
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from tinydb import where
from tdb_merge import merge_databases, check_edges
bin_dir = Path("../../data/tdb/sgte_binary")
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
fe, wit, nb = f("FeNd-16Che"), f("FeB-19Wit"), f("NdB-19Che")
m = merge_databases([fe, wit, nb], report=lambda *a, **k: None)
targets = {("BCC_A2", (("B",), ("VA",))), ("FCC_A1", (("B",), ("VA",))), ("HCP_A3", (("B",), ("VA",))), ("NDB6_D21", (("B",), ("B",)))}
ids = []
for p in m._parameters.all():
    ca = tuple(tuple(getattr(sp, "name", str(sp)) for sp in sub) for sub in p["constituent_array"])
    if (p["phase_name"], ca) in targets and str(p["parameter_type"]) == "G" and p["parameter_order"] == 0:
        ids.append(p.doc_id)
print("removing", len(ids), "parameters")
m._parameters.remove(doc_ids=ids)
ok = check_edges(m, [fe, wit])
print("\nFe-B edge", "PASSES -> the four added parameters are the cause" if ok else "STILL FAILS -> something else contributes")
