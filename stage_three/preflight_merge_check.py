#!/usr/bin/env python3
"""
preflight_merge_check.py  (v1)

Before merging binary TDBs into a ternary, report everything that can make
the 1 J/mol edge-check fail:

  1. FUNCTION conflicts   - same function name (e.g. GHSERMN, GBCCAL) defined
                            with different expressions in different files.
  2. TYPE_DEFINITION conflicts - e.g. magnetic AFM factor -1 vs -3.
  3. Shared PHASE conflicts - same phase name in several files but with a
                            different sublattice count or site ratios.
  4. Target phase as pycalphad sees it (constituents per sublattice), to
     resolve the "(parser empty)" CONSTITUENT lines from the earlier check.

Read-only. Does not merge or modify anything.

Usage:
  python preflight_merge_check.py \
      tdb/sgte_binary/AlFe-09Sun.tdb \
      tdb/sgte_binary/AlMn-12Dju.tdb \
      tdb/sgte_binary/FeMn-89Hua-LB.tdb \
      --phases AL8FE5_D82 AL8MN5_D810
"""

import argparse
import os
import re
from collections import defaultdict


def strip_comments(text):
    return "\n".join(l.split("$", 1)[0] for l in text.splitlines())


def blocks(text, keyword):
    """Yield whole '!'-terminated statements starting with keyword."""
    kw = re.compile(r"^\s*" + keyword + r"\b", re.IGNORECASE)
    buf, inside = [], False
    for line in text.splitlines():
        s = line.strip()
        if not inside and kw.match(s):
            inside, buf = True, [s]
        elif inside:
            buf.append(s)
        if inside and s.endswith("!"):
            yield re.sub(r"\s+", " ", " ".join(buf)).rstrip("!").strip()
            inside = False


def norm_expr(s):
    # Normalise whitespace, case and trailing reference tags for comparison.
    s = s.upper()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\bN\b\s+\S+\s*$", "", s)   # drop trailing 'N REF'
    s = s.replace("+-", "-").replace(" ", "")
    return s


def parse(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = strip_comments(f.read())
    funcs, types, phases = {}, {}, {}
    for b in blocks(text, r"FUNC(?:TION)?"):
        m = re.match(r"FUNC(?:TION)?\s+(\S+)\s+(.*)$", b, re.IGNORECASE)
        if m:
            funcs[m.group(1).upper()] = norm_expr(m.group(2))
    for b in blocks(text, r"TYPE_DEF(?:INITION)?"):
        m = re.match(r"TYPE_DEF(?:INITION)?\s+(\S+)\s+(.*)$", b, re.IGNORECASE)
        if m:
            types[m.group(1)] = norm_expr(m.group(2))
    for b in blocks(text, r"PHASE"):
        m = re.match(r"PHASE\s+(\S+)\s+(\S+)\s+(\d+)\s+(.*)$", b, re.IGNORECASE)
        if m:
            name = m.group(1).upper().split(":")[0]
            phases[name] = (int(m.group(3)), m.group(4).strip())
    return funcs, types, phases


def report_conflicts(title, per_file):
    owners = defaultdict(dict)
    for fname, d in per_file.items():
        for k, v in d.items():
            owners[k][fname] = v
    shared = {k: v for k, v in owners.items() if len(v) > 1}
    conflicts = {k: v for k, v in shared.items() if len(set(v.values())) > 1}
    print(f"\n=== {title}: {len(shared)} shared, {len(conflicts)} conflicting ===")
    for k in sorted(conflicts):
        print(f"  {k}")
        for fname, v in conflicts[k].items():
            print(f"     {fname:30s} {str(v)[:90]}")
    return conflicts


def pycalphad_view(paths, target_phases):
    try:
        from pycalphad import Database
    except ImportError:
        print("\n(pycalphad not importable here - skipping step 4)")
        return
    print("\n=== Target phases as pycalphad reads them ===")
    for p in paths:
        try:
            db = Database(p)
        except Exception as e:
            print(f"  {os.path.basename(p)}: LOAD FAILED - {e}")
            continue
        for ph in target_phases:
            if ph in db.phases:
                obj = db.phases[ph]
                cons = [sorted(str(c) for c in s) for s in obj.constituents]
                print(f"  {os.path.basename(p):30s} {ph:14s} "
                      f"sites={list(obj.sublattices)} constituents={cons}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--phases", nargs="*", default=["AL8FE5_D82", "AL8MN5_D810"])
    args = ap.parse_args()

    F, T, P = {}, {}, {}
    for p in args.files:
        n = os.path.basename(p)
        F[n], T[n], P[n] = parse(p)
        print(f"{n:30s} functions={len(F[n]):4d} types={len(T[n]):3d} phases={len(P[n]):3d}")

    fc = report_conflicts("FUNCTION", F)
    tc = report_conflicts("TYPE_DEFINITION", T)
    pc = report_conflicts("PHASE (sublattices, site ratios)", P)
    pycalphad_view(args.files, args.phases)

    print("\n=== Verdict ===")
    unary = [k for k in fc if k.startswith("GHSER") or re.match(r"G(BCC|FCC|HCP|LIQ)", k)]
    if not (fc or tc or pc):
        print("  No conflicts. Merge should reproduce each binary edge; run the edge-check.")
    else:
        if unary:
            print(f"  Unary/lattice-stability conflicts: {unary}")
            print("  -> These shift every phase on the affected edge; edge-check will fail")
            print("     unless the merge keeps each binary's own unary data (it cannot).")
        if pc:
            print(f"  Shared-phase model conflicts: {sorted(pc)}")
            print("  -> Same name, different sublattice model: one file's definition wins;")
            print("     the other edge loses its model. Likely edge-check failure.")
        if tc:
            print(f"  Type-definition conflicts: {sorted(tc)} (check magnetic AFM factors).")
        other = [k for k in fc if k not in unary]
        if other:
            print(f"  Other function conflicts (may be harmless if file-local names): {other}")


if __name__ == "__main__":
    main()
