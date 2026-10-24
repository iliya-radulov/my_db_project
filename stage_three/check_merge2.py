"""
check_merge2.py — do the duplicated parameters of the merge change the results?   (read-only, ~2-3 min)

check_merge.py found 17 parameters that occur twice in the merged Fe-Nd-B database (the pure
elements' G, TC and BMAGN of LIQUID, BCC_A2, FCC_A1, HCP_A3 and DHCP: each element comes with
two of the three binary files). pycalphad ADDS duplicated parameters, so such a phase may have
twice its Gibbs energy. This script:
  1. prints the two expressions of a few duplicated parameters (are they identical?);
  2. compares the Gibbs energy of the pure elements at 800 K: merged vs their own binary file;
  3. builds a FIXED merge that also keeps each PARAMETER only once (first file wins), and
     compares the binary-phase assemblage and its energy at Nd2Fe14B (800, 1000, 1200 K):
     current merge vs fixed merge. The energy is the feasibility threshold of Section 6.

Usage (stage_three/, MAIN venv with pycalphad):   python check_merge2.py
"""
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tdb_lookup import build_index, find_binaries, select_preferred   # noqa: E402
from phase_diagram_ternary_v3 import merge_tdb_files                   # noqa: E402
from pycalphad import Database, calculate, equilibrium, variables as v  # noqa: E402

TDB_DIR = HERE.parent / "data" / "tdb" / "sgte_binary"
ELS = ["FE", "ND", "B"]
PKEY = re.compile(r"^\s*PARA\w*\s+(\w+)\s*\(([^)]*)\)", re.I)
PURE = [("BCC_A2", "FE"), ("FCC_A1", "FE"), ("DHCP", "ND"), ("LIQUID", "FE"), ("LIQUID", "ND"),
        ("LIQUID", "B"), ("BETA_RHOMBO_B", "B")]


def dedup_parameters(db):
    """Keep each parameter (phase, constituents, order, type) only once: first file wins."""
    seen, keep = set(), []
    for p in db._parameters.all():
        key = (p["phase_name"], str(p["constituent_array"]), p["parameter_order"],
               p["parameter_type"], str(p.get("diffusing_species")))
        if key not in seen:
            seen.add(key)
            keep.append(dict(p))
    n_before = len(db._parameters.all())
    db._parameters.truncate()
    db._parameters.insert_multiple(keep)
    return n_before, len(keep)


def load(text, tag):
    p = HERE / f"_check_merge2_{tag}.tdb"
    p.write_text(text, encoding="utf-8")
    try:
        return Database(str(p))
    finally:
        p.unlink(missing_ok=True)


def ghser(db, el, T):
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return float(db.symbols[name].subs({v.T: T}))
    raise KeyError(el)


def g_pure(db, phase, el, T=800.0):
    """G of pure *el* in *phase* (kJ/mol), from the end member of a full calculation."""
    if phase not in db.phases or el not in db.elements:
        return None
    comps = [e for e in ELS if e in db.elements] + ["VA"]
    try:
        r = calculate(db, comps, phase, T=T, P=101325, N=1, output="GM")
    except Exception as e:
        return f"{type(e).__name__}"
    X = r.X.values.reshape(-1, len(r.component))
    gm = r.GM.values.reshape(-1)
    k = [str(c) for c in r.component.values].index(el)
    sel = X[:, k] > 0.9999
    return float(gm[sel].min()) / 1000 if sel.any() else "no pure end member"


def mix(db, T):
    x = {"FE": 14 / 17, "ND": 2 / 17, "B": 1 / 17}
    r = equilibrium(db, ELS + ["VA"], list(db.phases),
                    {v.X("ND"): x["ND"], v.X("B"): x["B"], v.T: T, v.P: 101325, v.N: 1})
    ph = {str(n): round(float(f), 3) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1))
          if n and f > 1e-3}
    ser = sum(x[e] * ghser(db, e, T) for e in ELS)
    return (float(r.GM.values.squeeze()) - ser) / 1000, ph


def main():
    index = build_index(TDB_DIR)
    sel = {p: select_preferred(f) for p, f in find_binaries(ELS, index).items()}
    paths = sorted(sel.values(), key=lambda p: p.name)
    cur = merge_tdb_files(paths)
    print("Files:", ", ".join(p.name for p in paths))
    db_cur, db_fix = load(cur, "cur"), load(cur, "fix")
    n0, n1 = dedup_parameters(db_fix)
    print(f"Parameters: current merge {n0}, fixed merge {n1} (duplicates removed: {n0 - n1})")
    singles = [Database(str(pth)) for pth in paths]

    print("\n0. Phase definitions (sites; constituents per sublattice)")
    for ph in ("BCC_A2", "FCC_A1", "DHCP", "LIQUID"):
        for tag, d in [("merged", db_cur)] + [(pth.name, sd) for pth, sd in zip(paths, singles)]:
            if ph in d.phases:
                cons = [sorted(str(c).split("(")[0] if False else c.name for c in sub) for sub in d.phases[ph].constituents]
                print(f"   {ph:7s} {tag:16s} {list(d.phases[ph].sublattices)}  {cons}")

    print("\n1. Duplicated parameters (both expressions, first 110 characters):")
    for phase, el in [("BCC_A2", "FE"), ("DHCP", "ND"), ("LIQUID", "ND")]:
        for p in db_cur._parameters.all():
            if p["phase_name"] == phase and p["parameter_type"] == "G" and p["parameter_order"] == 0 \
                    and [str(s[0]) for s in p["constituent_array"]][0].startswith(el) \
                    and len(p["constituent_array"][0]) == 1:
                print(f"   {phase:7s} {el}: {str(p['parameter'])[:110]}")

    print("\n2. Pure elements at 800 K, kJ/mol      current merge   fixed merge   own binary file(s)")
    fmt = lambda g: f"{g:10.2f}" if isinstance(g, float) else f"{str(g):>10s}"
    for phase, el in PURE:
        own = [g_pure(d, phase, el) for d in singles]
        own = ", ".join(fmt(g).strip() for g in own if g is not None)
        gc, gf = g_pure(db_cur, phase, el), g_pure(db_fix, phase, el)
        if gc is None and gf is None:
            continue
        flag = ("   <-- DOUBLED?" if isinstance(gc, float) and isinstance(gf, float) and abs(gc - gf) > 0.01
                else "")
        print(f"   {phase:14s} {el:3s} {fmt(gc)} {fmt(gf)}      {own}{flag}")

    print("\n3. Binary-phase assemblage at Nd2Fe14B (energy vs GHSER = feasibility threshold, kJ/mol-atom)")
    for T in (800.0, 1000.0, 1200.0):
        ec, pc = mix(db_cur, T)
        ef, pf = mix(db_fix, T)
        print(f"   {T:.0f} K  current {ec:7.2f}  {pc}")
        print(f"          fixed   {ef:7.2f}  {pf}")


if __name__ == "__main__":
    main()
