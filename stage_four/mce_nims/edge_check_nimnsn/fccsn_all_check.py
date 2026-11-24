#!/usr/bin/env python3
"""Read-only check of the fcc-Sn reference value in every merged Ni-Mn-Sn TDB
and cross-tabulation against the edge-check results.

Usage (from the folder that holds edge_check.csv and merged/):
    python fccsn_all_check.py [edge_check.csv] [merged_dir] [out.csv]

Defaults: edge_check.csv  merged  fccsn_all_check_result.csv
Nothing is modified; one CSV is written.
"""
import csv, re, sys, glob, os
from collections import Counter, defaultdict

edge = sys.argv[1] if len(sys.argv) > 1 else "edge_check.csv"
mdir = sys.argv[2] if len(sys.argv) > 2 else "merged"
out  = sys.argv[3] if len(sys.argv) > 3 else "fccsn_all_check_result.csv"

LABELS = {(5510.0, 8.46): "89Fec", (4150.0, 5.2): "91Din"}
PAT = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*([+-])\s*(\d+(?:\.\d+)?)\s*\*\s*T')

def statements(txt):
    # join text into statements ending with "!"
    return [s for s in txt.replace("\r", "").split("!")]

def fccsn_values(path):
    txt = open(path, errors="replace").read()
    vals, raw = set(), []
    for st in statements(txt):
        s = " ".join(st.split())
        u = s.upper()
        if not (u.startswith("FUNCTION GFCCSN") or "PARAMETER G(FCC_A1,SN:VA" in u):
            continue
        raw.append(s)
        m = PAT.search(s)
        if m:
            a = float(m.group(1)); b = float(m.group(3)) * (1 if m.group(2) == "+" else -1)
            b = abs(b) if m.group(2) == "-" else b
            vals.add((a, abs(b)))   # stored as (A, B) with G = A - B*T
    labs = sorted(LABELS.get(v, "other%s" % (v,)) for v in vals)
    return ("+".join(labs) if labs else "none"), raw

rows = list(csv.DictReader(open(edge)))
by_combo = {r["combo"]: r for r in rows}
files = sorted(glob.glob(os.path.join(mdir, "*.tdb")) + glob.glob(os.path.join(mdir, "*.TDB")))
print(f"edge_check rows: {len(rows)}; merged files: {len(files)}")

res, matched = [], set()
for f in files:
    stem = os.path.splitext(os.path.basename(f))[0]
    combo = stem[len("NIMNSN__"):] if stem.startswith("NIMNSN__") else stem
    r = by_combo.get(combo)
    lab, raw = fccsn_values(f)
    if r is None:
        print("NO edge_check row for", stem); continue
    matched.add(combo)
    res.append(dict(combo=combo, NiSn=r["NiSn"], MnSn=r["MnSn"], MnNi=r["MnNi"],
                    fccSn=lab, merge_conflicts=r["merge_conflicts"],
                    MNNI_pass=r["MNNI_pass"], NISN_pass=r["NISN_pass"],
                    MNSN_pass=r["MNSN_pass"], passed=r["pass"], n_stmts=len(raw)))
missing = [c for c in by_combo if c not in matched]
print(f"edge_check rows without merged file: {len(missing)}")
for c in missing[:10]: print("  ", c)

with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
print("written:", out)

def T(x): return str(x).strip().lower() == "true"

print("\n== fcc-Sn value in merged file x overall pass ==")
c = Counter((r["fccSn"], T(r["passed"])) for r in res)
for k in sorted(c): print(f"  {k[0]:>12}  pass={k[1]!s:5}  n={c[k]}")

print("\n== fcc-Sn value x Sn-edge result (Ni-Sn and Mn-Sn edges both ok?) ==")
c = Counter((r["fccSn"], T(r["NISN_pass"]) and T(r["MNSN_pass"])) for r in res)
for k in sorted(c): print(f"  {k[0]:>12}  Sn edges ok={k[1]!s:5}  n={c[k]}")

print("\n== by Ni-Sn file ==")
d = defaultdict(Counter)
for r in res:
    d[r["NiSn"]][(r["fccSn"], T(r["passed"]))] += 1
for k in sorted(d):
    print(f"  {k:12}", dict(d[k]))

print("\n== counterexamples to the mechanism ==")
a = [r for r in res if r["fccSn"] == "89Fec" and T(r["NISN_pass"]) and T(r["MNSN_pass"])]
b = [r for r in res if r["fccSn"] == "91Din" and not (T(r["NISN_pass"]) and T(r["MNSN_pass"]))]
o = [r for r in res if r["fccSn"] not in ("89Fec", "91Din")]
print("  89Fec but both Sn edges ok:", len(a)); [print("    ", r["combo"]) for r in a[:10]]
print("  91Din but a Sn edge fails :", len(b)); [print("    ", r["combo"]) for r in b[:10]]
print("  neither / other / both    :", len(o)); [print("    ", r["combo"], r["fccSn"]) for r in o[:10]]
nf = sum(1 for r in res if not T(r["passed"]))
nf89 = sum(1 for r in res if not T(r["passed"]) and r["fccSn"] == "89Fec")
print(f"\nfailing combinations: {nf}; of these with 89Fec in merged file: {nf89}")
