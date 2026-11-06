"""Second candidate: phase-level model settings (magnetic constants etc.) taken from a different source file by the merge.
Run from stage4_step1/:  python3 phase_models.py
Part 1: per phase, compare site ratios / model_hints / Fe-B-edge constituents between FeB-19Wit and the merged description
        (and show what FeNd-16Che and NdB-19Che declare, to see which file the merge took them from).
Part 2: copy FeB-19Wit's model_hints onto the merged phases where they differ and re-check the Fe-B edge, with and without
        the four parameters added by the Nd-B file.
"""
import sys
sys.path.insert(0, "../stage_three"); sys.path.insert(0, ".")
from pathlib import Path
from pycalphad import Database
from tinydb import where
from tdb_merge import merge_databases, check_edges
bin_dir = Path("../../data/tdb/sgte_binary")
f = lambda n: next(bin_dir.rglob(n + ".tdb"))
fe, wit, nb = f("FeNd-16Che"), f("FeB-19Wit"), f("NdB-19Che")
dW, dF, dN = Database(str(wit)), Database(str(fe)), Database(str(nb))
def fresh(): return merge_databases([fe, wit, nb], report=lambda *a, **k: None)
M = fresh()
ALLOWED = {"FE", "B", "VA"}
def cons(ph):
    return tuple(tuple(sorted(str(c) for c in sub if str(c) in ALLOWED)) for sub in ph.constituents)
print("=== Part 1: phases whose settings differ between FeB-19Wit and MERGED (Fe-B-edge view)")
diff = []
for name in sorted(M.phases):
    if name not in dW.phases: continue
    a, b = dW.phases[name], M.phases[name]
    d = []
    if list(a.sublattices) != list(b.sublattices): d.append(f"sites wit={list(a.sublattices)} merged={list(b.sublattices)}")
    if dict(a.model_hints) != dict(b.model_hints): d.append(f"model_hints wit={dict(a.model_hints)} merged={dict(b.model_hints)}")
    if cons(a) != cons(b): d.append(f"constituents(FE,B,VA) wit={cons(a)} merged={cons(b)}")
    if d:
        diff.append(name); print(name); [print("   ", x) for x in d]
        for lab, db in (("FeNd-16Che", dF), ("NdB-19Che", dN)):
            if name in db.phases: print(f"    {lab:11s} model_hints={dict(db.phases[name].model_hints)}")
print("phases differing:", diff or "none")
def apply_hints(m):
    for n in diff:
        if "model_hints" in " ".join(["x"]):  pass
        m.phases[n].model_hints = dict(dW.phases[n].model_hints)
targets = {("BCC_A2", (("B",), ("VA",))), ("FCC_A1", (("B",), ("VA",))), ("HCP_A3", (("B",), ("VA",))), ("NDB6_D21", (("B",), ("B",)))}
def drop_added(m):
    ids = [p.doc_id for p in m._parameters.all()
           if (p["phase_name"], tuple(tuple(getattr(sp, "name", str(sp)) for sp in s) for s in p["constituent_array"])) in targets
           and str(p["parameter_type"]) == "G" and p["parameter_order"] == 0]
    m._parameters.remove(doc_ids=ids)
print("\n=== Part 2A: merged + Wit's model_hints (4 added parameters kept)")
m = fresh(); apply_hints(m); check_edges(m, [wit])
print("\n=== Part 2B: merged + Wit's model_hints + 4 added parameters removed")
m = fresh(); apply_hints(m); drop_added(m); ok = check_edges(m, [wit])
print("\nRESULT 2B:", "PASSES (<=1 J/mol): added parameters + phase settings explain the whole failure" if ok else "STILL FAILS")
