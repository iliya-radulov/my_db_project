"""Refined hypothesis: the merge UNITES the constituents of shared phases. FeB-19Wit has B only on the interstitial sublattice of
FCC_A1/BCC_A2/HCP_A3, i.e. (FE)(B,VA); NdB-19Che puts B also on sublattice 1. The merged phase is (B,FE)(B,VA): a new
configuration (B on sublattice 1) that FeB-19Wit does not contain.   Run from stage4_step1/:  python3 constituent_union_test.py
Part 1: sublattice-1 / sublattice-2 constituents of FCC_A1, BCC_A2, HCP_A3 in all 11 Fe-B and Nd-B files (supplementary table).
Part 2: restore FeB-19Wit's constituents on the merged phases (A: keep the 4 added parameters; B: also remove them) and re-check Fe-B.
"""
import sys
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from pycalphad import Database
from tdb_merge import merge_databases, check_edges
bin_dir = Path("../../data/tdb/sgte_binary")
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
SHOW = {"FE", "ND", "B", "VA"}
PH = ("FCC_A1", "BCC_A2", "HCP_A3")
def desc(db, ph):
    if ph not in db.phases: return "-"
    return " ".join("(" + ",".join(sorted(str(c) for c in sub if str(c) in SHOW)) + ")" for sub in db.phases[ph].constituents)
print("=== Part 1: constituents per sublattice")
print(f"{'file':26s}" + "".join(f"{p:24s}" for p in PH))
for p in sorted(bin_dir.rglob("*.tdb")):
    if p.name.startswith(("FeB-", "NdB-")):
        db = Database(str(p)); print(f"{p.name[:-4]:26s}" + "".join(f"{desc(db, ph):24s}" for ph in PH))
fe, wit, nb = f("FeNd-16Che"), f("FeB-19Wit"), f("NdB-19Che")
dW = Database(str(wit)); fresh = lambda: merge_databases([fe, wit, nb], report=lambda *a, **k: None)
M = fresh(); print("\nMERGED (Che/Wit/NdB-19Che):" + " " * 0 + "".join(f"  {ph}: {desc(M, ph)}" for ph in PH))
def restore(m):
    for ph in PH:
        wc = [set(s) for s in dW.phases[ph].constituents]
        target = m.phases[ph]
        new = []
        for k, sub in enumerate(target.constituents):
            keep = {sp for sp in sub if str(sp) not in ("B",) or any(str(x) == "B" for x in wc[k])}
            new.append(keep)
        try: target.constituents = new
        except Exception: object.__setattr__(target, "constituents", new)
targets = {("BCC_A2", (("B",), ("VA",))), ("FCC_A1", (("B",), ("VA",))), ("HCP_A3", (("B",), ("VA",))), ("NDB6_D21", (("B",), ("B",)))}
def drop_added(m):
    ids = [p.doc_id for p in m._parameters.all()
           if (p["phase_name"], tuple(tuple(getattr(sp, "name", str(sp)) for sp in s) for s in p["constituent_array"])) in targets
           and str(p["parameter_type"]) == "G" and p["parameter_order"] == 0]
    m._parameters.remove(doc_ids=ids)
print("\n=== Part 2A: Wit's constituents restored, parameters kept")
m = fresh(); restore(m); print("  after restore:", "".join(f"  {ph}: {desc(m, ph)}" for ph in PH)); okA = check_edges(m, [wit])
print("\n=== Part 2B: Wit's constituents restored AND the 4 added parameters removed")
m = fresh(); restore(m); drop_added(m); okB = check_edges(m, [wit])
print("\nRESULT: A", "PASS" if okA else "FAIL", "| B", "PASS" if okB else "FAIL")
