#!/usr/bin/env python3
"""Read-only: is any Nd-Fe-B input file third-generation? Prints matching header lines and the
lower temperature limit of the Fe / Nd / B unary functions. Usage: python tdb_gen_check.py DIR"""
import sys, re, pathlib
root = pathlib.Path(sys.argv[1])
names = ["FeNd-16Che","FeNd-16Wan","FeNd-95Hal-LB","FeB-20Tak","FeB-08Yos","FeB-01Pal","FeB-19Wit",
         "FeB-02Rom","FeB-91Pan","FeB-94Hal-LB","NdB-16Zho-corrected","NdB-98Che","NdB-95Hal-LB","NdB-19Che"]
pat = re.compile(r"3rd|third|3g|einstein|new magnetic|generation", re.I)
unary = re.compile(r"^\s*FUNCTION\s+(GHSER(FE|ND|B)|GHSERB)\s+([0-9.E+-]+)", re.I)
for n in names:
    hits = list(root.rglob(n + ".tdb")) + list(root.rglob(n + ".TDB"))
    print("=" * 70); print(n, "->", hits[0] if hits else "NOT FOUND")
    if not hits: continue
    seen = set()
    for line in hits[0].read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("$") and pat.search(s): print("  HEADER:", s[:150])
        m = unary.match(line)
        if m and m.group(1).upper() not in seen:
            seen.add(m.group(1).upper()); print("  ", m.group(1).upper(), "lower T limit:", m.group(3))
