#!/usr/bin/env python3
"""
crfeni_analysis.py (18 Nov 2026) - class analysis of Cr-Fe-Ni Pilot-M. Refuses to run unless
<run-dir>/sigma/gate.json exists, the run is valid and all of G1-G3 passed.

Primary (900 K, valid survivors): class medians of S, C = max - min of the three class medians,
N = median over the Cr-Fe files with >= 5 survivors of the within-file IQR of S, N_eff = max(N, 0.05).
  C >= 2 N_eff -> "sigma convention MATTERS";  C <= N_eff -> "does NOT matter";  otherwise INCONCLUSIVE.
Also reported: eta^2 of S for each of the three edge files (share of the variance explained), and
the class medians with the number of survivors behind them.
Labelled sensitivity (never changes the verdict): 800 K and 1000 K; lineage-balanced medians
(each lineage combination weighted equally inside a class).
Rule-v3 sensitivity named in the draft is NOT implemented (edge_check script has no v3 output).

Usage: python crfeni_analysis.py --run-dir edge_check_crfeni
Writes <run-dir>/sigma/analysis.json and analysis.md.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

import crfeni_defs as D


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def eta2(vals, groups):
    vals = np.asarray(vals, float)
    tot = ((vals - vals.mean()) ** 2).sum()
    if tot == 0:
        return 0.0
    ss = 0.0
    for g in set(groups):
        x = vals[[i for i, k in enumerate(groups) if k == g]]
        ss += len(x) * (x.mean() - vals.mean()) ** 2
    return float(ss / tot)


def verdict(C, n_eff):
    if C >= D.MATTERS_FACTOR * n_eff:
        return "MATTERS"
    if C <= n_eff:
        return "DOES NOT MATTER"
    return "INCONCLUSIVE"


def analyse(rows, T):
    """rows: valid survivors with S at temperature T."""
    cls = defaultdict(list)
    for r in rows:
        cls[D.CLASS[r["CrFe"]]].append(r)
    med = {c: float(np.median([r["S"] for r in cls[c]])) for c in D.CLASSES if cls[c]}
    n = {c: len(cls[c]) for c in D.CLASSES}
    C = max(med.values()) - min(med.values()) if len(med) == 3 else None
    byfile = defaultdict(list)
    for r in rows:
        byfile[r["CrFe"]].append(r["S"])
    iqrs = {f: float(np.subtract(*np.percentile(v, [75, 25]))) for f, v in byfile.items()
            if len(v) >= D.G2_MIN_SURVIVORS_PER_FILE}
    N = float(np.median(list(iqrs.values()))) if iqrs else None
    n_eff = max(N, D.NOISE_FLOOR) if N is not None else None
    # lineage-balanced class medians: median of per-lineage-combination medians
    bal = {}
    for c in D.CLASSES:
        lc = defaultdict(list)
        for r in cls[c]:
            lc[tuple(D.LINEAGE[e][r[e]] for e in D.EDGES)].append(r["S"])
        if lc:
            bal[c] = float(np.median([np.median(v) for v in lc.values()]))
    C_bal = max(bal.values()) - min(bal.values()) if len(bal) == 3 else None
    eta = {e: round(eta2([r["S"] for r in rows], [r[e] for r in rows]), 4) for e in D.EDGES}
    return {"T_K": T, "n_rows": len(rows), "class_n": n, "class_median": {c: round(m, 4) for c, m in med.items()},
            "C": None if C is None else round(C, 4), "N_median_IQR": None if N is None else round(N, 4),
            "N_eff": None if n_eff is None else round(n_eff, 4),
            "iqr_per_file": {f: round(v, 4) for f, v in iqrs.items()},
            "eta2": eta,
            "verdict": verdict(C, n_eff) if C is not None and n_eff is not None else "NOT DEFINED",
            "lineage_balanced": {"class_median": {c: round(m, 4) for c, m in bal.items()},
                                 "C": None if C_bal is None else round(C_bal, 4),
                                 "verdict": verdict(C_bal, n_eff) if C_bal is not None and n_eff is not None
                                 else "NOT DEFINED"}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    run = Path(a.run_dir)
    gp = run / "sigma" / "gate.json"
    if not gp.exists():
        sys.exit("no gate.json: run crfeni_gate.py first")
    gate = json.loads(gp.read_text())
    if not gate.get("run_valid") or gate.get("failed_gates"):
        sys.exit(f"gate not passed ({gate.get('verdict')}): class analysis is not run")
    with open(run / "edge_check.csv", newline="") as f:
        surv = {r["combo"]: r for r in csv.DictReader(f) if r["pass"] == "True"}
    with open(run / "sigma" / "sigma_S.csv", newline="") as f:
        sg = list(csv.DictReader(f))
    by_T = defaultdict(list)
    for r in sg:
        S = fnum(r["S"])
        if r["status"] != "failed" and S is not None and r["combo"] in surv:
            by_T[fnum(r["T"])].append({**{e: surv[r["combo"]][e] for e in D.EDGES}, "S": S})
    res = {"primary": analyse(by_T[D.PRIMARY_T], D.PRIMARY_T),
           "sensitivity": {str(int(T)): analyse(by_T[T], T) for T in D.SENSITIVITY_T if by_T.get(T)}}
    (run / "sigma" / "analysis.json").write_text(json.dumps(res, indent=2))
    p = res["primary"]
    md = ["# Cr-Fe-Ni Pilot-M class analysis", "",
          f"Primary ({D.PRIMARY_T:.0f} K): **{p['verdict']}**  (C = {p['C']}, N_eff = {p['N_eff']}, kJ/mol-atom)", "",
          f"Class medians: {p['class_median']}  (n = {p['class_n']})",
          f"eta^2 by edge file: {p['eta2']}", "",
          "Sensitivity (labelled, does not change the verdict):",
          f"- lineage-balanced, 900 K: C = {p['lineage_balanced']['C']} -> {p['lineage_balanced']['verdict']}"]
    for T, s in res["sensitivity"].items():
        md.append(f"- {T} K: C = {s['C']}, N_eff = {s['N_eff']} -> {s['verdict']}")
    (run / "sigma" / "analysis.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
