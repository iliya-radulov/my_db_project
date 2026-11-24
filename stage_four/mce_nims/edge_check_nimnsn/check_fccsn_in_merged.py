#!/usr/bin/env python3
"""Read-only. For one or more merged Ni-Mn-Sn TDB files, print which fcc-Sn lattice stability
the merged database carries: '5510 - 8.46 T' (89Fec) or '4150 - 5.2 T' (91Din).
Usage: python check_fccsn_in_merged.py merged1.tdb [merged2.tdb ...]
Pick at least one FAILING and one SURVIVING combination (e.g. one with 04Liu, one with 99Gho)."""
import re, sys
pat = re.compile(r"(GFCCSN|G\(\s*FCC_A1\s*,\s*SN\s*:\s*VA)", re.I)
for f in sys.argv[1:]:
    print("=" * 70); print(f)
    txt = open(f, errors="replace").read()
    # join continuation lines: statements end with '!'
    for stmt in re.split(r"!", txt):
        s = " ".join(stmt.split())
        if pat.search(s) and ("FUNCTION" in s.upper() or "PARAMETER" in s.upper()):
            tag = []
            if re.search(r"5510", s) and re.search(r"8\.46", s): tag.append("89Fec value (5510, 8.46)")
            if re.search(r"4150", s) and re.search(r"5\.2\b", s): tag.append("91Din value (4150, 5.2)")
            print("  ", s[:220], "->", ", ".join(tag) if tag else "(no match to either value)")
