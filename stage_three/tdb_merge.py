"""
tdb_merge.py — merge binary TDB files into one ternary description, correctly.

Replaces the text merge `merge_tdb_files` (phase_diagram_ternary_v3.py, also copied into
feasibility.py and advisor_app/calphad_query.py), which had three defects (found 24 Oct 2026):
  1. CONSTITUENT statements were not merged: the last file's list won, so in Fe-Nd-B the phases
     LIQUID, BCC_A2 and FCC_A1 contained only B and Nd — iron could not dissolve in them at all;
  2. PARAMETER statements were not de-duplicated, and pycalphad ADDS duplicates: parameters that
     two binary files share (the pure elements) were counted twice, e.g. pure Nd;
  3. FUNCTION definitions were taken from the first file without checking that the others agree.

This module merges the PARSED databases instead of their text:
  - elements, species and reference states: united;
  - functions: first file wins; any file defining the same name differently is reported;
  - phases: site ratios and model hints must agree; constituents are the union per sublattice;
  - parameters: each (phase, constituents, order, type) once; differing duplicates are reported.
check_edges() then verifies the merge: along each edge the merged database must reproduce the
binary file it came from (same phases, same Gibbs energy).

Usage (stage_three/, main venv):
    python tdb_merge.py FE ND B              # merge, write FENDB_merged_v4.tdb, check all three edges
    python tdb_merge.py FE ND B --compare-old # also run the edge check on the old text merge
In code:
    from tdb_merge import merged_tdb_path, merged_text
    path = merged_tdb_path(["FE", "ND", "B"])   # checked TDB file, for pycalphad's Database()
    text = merged_text(paths)                    # TDB text, replaces merge_tdb_files(paths)
"""
from __future__ import annotations

import sys
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
from pycalphad import Database, equilibrium, variables as v

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
TDB_DIR = HERE.parent / "data" / "tdb" / "sgte_binary"


def _names(sub):
    return tuple(sorted(getattr(s, "name", str(s)) for s in sub))


def _pkey(p):
    return (p["phase_name"], tuple(_names(sub) for sub in p["constituent_array"]),
            p["parameter_order"], p["parameter_type"],
            getattr(p.get("diffusing_species"), "name", p.get("diffusing_species")))


def merge_databases(paths, report=print) -> Database:
    """Merge the TDB files in *paths* (order = priority) into one pycalphad Database."""
    dbs = [(Path(p).name, Database(str(p))) for p in paths]
    out = Database()
    phase_def: dict[str, dict] = {}
    kept_params: dict = {}
    problems = 0
    for fname, db in dbs:
        out.elements |= set(db.elements)
        out.species |= set(db.species)
        for k, val in db.refstates.items():
            out.refstates.setdefault(k, val)
        for name, expr in db.symbols.items():
            if name not in out.symbols:
                out.symbols[name] = expr
            elif str(out.symbols[name]) != str(expr):
                problems += 1
                report(f"  FUNCTION {name}: {fname} defines it differently — first definition kept")
        for name, ph in db.phases.items():
            subl = tuple(float(s) for s in ph.sublattices)
            cons = [set(_names(sub)) for sub in ph.constituents]
            if name not in phase_def:
                phase_def[name] = {"hints": dict(ph.model_hints), "subl": subl, "cons": cons, "from": fname}
                continue
            d = phase_def[name]
            if d["subl"] != subl:
                problems += 1
                report(f"  PHASE {name}: site ratios {subl} in {fname} differ from {d['subl']} "
                       f"in {d['from']} — phase from {fname} ignored")
                continue
            for k, val in ph.model_hints.items():
                if k in d["hints"] and str(d["hints"][k]) != str(val):
                    problems += 1
                    report(f"  PHASE {name}: model hint {k} differs in {fname} — first kept")
                d["hints"].setdefault(k, val)
            for i, sub in enumerate(cons):
                d["cons"][i] |= sub
        for p in db._parameters.all():
            key = _pkey(p)
            if key not in kept_params:
                kept_params[key] = dict(p)
            elif str(kept_params[key]["parameter"]) != str(p["parameter"]):
                problems += 1
                report(f"  PARAMETER {key[3]}({key[0]},{':'.join(','.join(s) for s in key[1])};{key[2]}): "
                       f"differs in {fname} — first kept")
    for name, d in phase_def.items():
        out.add_phase(name, d["hints"], d["subl"])
        out.add_phase_constituents(name, [sorted(s) for s in d["cons"]])
    out._parameters.insert_multiple(list(kept_params.values()))
    report(f"  merged {len(dbs)} files: {len(out.phases)} phases, {len(kept_params)} parameters, "
           f"{problems} conflicts")
    return out


def selected_binaries(elements):
    sys.path.insert(0, str(HERE))
    from tdb_lookup import build_index, find_binaries, select_preferred
    index = build_index(TDB_DIR)
    cand = find_binaries([e.upper() for e in elements], index)
    if len(cand) < 3:
        raise RuntimeError(f"need 3 binary TDB files for {elements}, found {len(cand)}")
    return sorted((select_preferred(f) for f in cand.values()), key=lambda p: p.name)


def _phase_set(r):
    return frozenset(str(n) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1))
                     if n and np.isfinite(f) and f > 1e-4)


def check_edges(db_merged, paths, temps=(800.0, 1200.0, 1600.0), report=print) -> bool:
    """Along every edge, the merged database must reproduce its binary file."""
    ok_all = True
    for path in paths:
        db_bin = Database(str(path))
        a, b = sorted(e for e in db_bin.elements if e not in ("VA", "/-"))
        comps = [a, b, "VA"]
        worst, mismatches, n = 0.0, [], 0
        for T in temps:
            for x in np.round(np.arange(0.05, 0.96, 0.1), 2):
                cond = {v.X(b): float(x), v.T: T, v.P: 101325, v.N: 1}
                try:
                    r1 = equilibrium(db_bin, comps, list(db_bin.phases), cond)
                    r2 = equilibrium(db_merged, comps, list(db_merged.phases), cond)
                except Exception as e:
                    mismatches.append(f"T={T:.0f} x_{b}={x}: error {type(e).__name__}")
                    continue
                n += 1
                g1, g2 = float(r1.GM.values.squeeze()), float(r2.GM.values.squeeze())
                worst = max(worst, abs(g1 - g2))
                p1, p2 = _phase_set(r1), _phase_set(r2)
                if p1 != p2 or abs(g1 - g2) > 1.0:
                    mismatches.append(f"T={T:.0f} x_{b}={x}: binary {'+'.join(sorted(p1))} "
                                      f"vs merged {'+'.join(sorted(p2))}, dG={g2 - g1:+.0f} J/mol")
        ok = not mismatches
        ok_all &= ok
        report(f"  {a}-{b} ({path.name}): {n} points, largest |dG| {worst:.1f} J/mol, "
               f"{len(mismatches)} mismatches -> {'OK' if ok else 'FAILED'}")
        for m in mismatches[:4]:
            report(f"      {m}")
    return ok_all


def merged_text(paths, report=print) -> str:
    """TDB text of the merged description (drop-in replacement for the old merge_tdb_files)."""
    return merge_databases(paths, report=report).to_string(fmt="tdb", if_incompatible="ignore")


def merged_tdb_path(elements, out_dir=HERE, check=True) -> Path:
    """Merge, write and (by default) check the description for *elements*; return the TDB path."""
    paths = selected_binaries(elements)
    db = merge_databases(paths)
    out = Path(out_dir) / f"{''.join(e.upper() for e in elements)}_merged_v4.tdb"
    db.to_file(str(out), fmt="tdb", if_exists="overwrite", if_incompatible="ignore")
    if check:
        reread = Database(str(out))                   # check what the workers will actually load
        if not check_edges(reread, paths):
            raise RuntimeError(f"{out.name}: merged description does not reproduce its binaries")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    elements = [e.upper() for e in (args or ["FE", "ND", "B"])]
    paths = selected_binaries(elements)
    print("Binary files:", ", ".join(p.name for p in paths))
    if "--compare-old" in sys.argv:
        from phase_diagram_ternary_v3 import merge_tdb_files
        tmp = HERE / "_old_merge.tdb"
        tmp.write_text(merge_tdb_files(paths), encoding="utf-8")
        print("\nOLD text merge — edge check:")
        check_edges(Database(str(tmp)), paths)
        tmp.unlink(missing_ok=True)
    print("\nNEW merge:")
    out = merged_tdb_path(elements, check=False)
    print(f"  written: {out.name}\n\nNEW merge (re-read from file) — edge check:")
    ok = check_edges(Database(str(out)), paths)
    print("\nRESULT:", "the merged file reproduces all three binaries" if ok else "PROBLEMS — see above")


if __name__ == "__main__":
    main()
