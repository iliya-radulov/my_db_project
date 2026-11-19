#!/usr/bin/env python3
"""
crfeni_gate.py (18 Nov 2026) - gate G1-G3 of Cr-Fe-Ni Pilot-M, applied once, after the edge check and
the observable stage and before any class analysis. Definitions in crfeni_defs.py (numbers) and in the
pre-registration:

  G1  >= 60 of the 288 raw combinations pass edge-check rule v2 (`pass` in edge_check.csv).
  G2  each sigma class (A, B, C) has >= 1 Cr-Fe file with >= 5 surviving combinations.
  G3  S > 0.05 kJ/mol-atom at the primary temperature (900 K) in >= 80 % of the survivors with a valid S.

Run validity (not a gate): the edge check must hold exactly 288 rows, sigma_S.csv exactly
3 x survivors rows, and >= 80 % of the survivors need a valid S at 900 K; otherwise the run is INVALID
(failed run: implementation-and-environment fault rule), exit code 3.

Reported, labelled sensitivity, never gating: survival per file, per class and per lineage combination;
G3 at 800 and 1000 K.

Usage: python crfeni_gate.py --run-dir edge_check_crfeni
Writes <run-dir>/sigma/gate.json and gate.md. Exit code 0 = gates evaluated (pass/fail in the file),
3 = run invalid.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import crfeni_defs as D


def load(run):
    with open(run / "edge_check.csv", newline="") as f:
        ec = list(csv.DictReader(f))
    with open(run / "sigma" / "sigma_S.csv", newline="") as f:
        sg = list(csv.DictReader(f))
    return ec, sg


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    run = Path(a.run_dir)
    ec, sg = load(run)
    problems = []
    combos = {r["combo"] for r in ec}
    if len(combos) != D.N_COMBINATIONS or len(ec) != D.N_COMBINATIONS:
        problems.append(f"edge_check.csv has {len(ec)} rows / {len(combos)} combinations, expected {D.N_COMBINATIONS}")
    surv = [r for r in ec if r["pass"] == "True"]
    temps = sorted({fnum(r["T"]) for r in sg})
    if len(sg) != len(surv) * 3:
        problems.append(f"sigma_S.csv has {len(sg)} rows, expected {len(surv) * 3} (survivors x 3 temperatures)")
    s_at = defaultdict(dict)                       # T -> combo -> S (valid only)
    for r in sg:
        S = fnum(r["S"])
        if r["status"] != "failed" and S is not None:
            s_at[fnum(r["T"])][r["combo"]] = S
    valid_primary = sum(1 for r in surv if r["combo"] in s_at[D.PRIMARY_T])
    valid_frac = valid_primary / len(surv) if surv else 0.0
    if surv and valid_frac < D.VALID_FRACTION:
        problems.append(f"only {valid_primary}/{len(surv)} survivors have a valid S at {D.PRIMARY_T:.0f} K "
                        f"(< {D.VALID_FRACTION:.0%})")
    if not surv:
        problems.append("no surviving combination")
    res = {"n_combinations_in_edge_check": len(ec), "n_surviving": len(surv),
           "valid_S_primary": valid_primary, "valid_fraction": round(valid_frac, 4)}
    if problems:
        res.update({"run_valid": False, "problems": problems,
                    "verdict": "INVALID RUN: not a gate result (fault rule applies)"})
        (run / "sigma").mkdir(exist_ok=True)
        (run / "sigma" / "gate.json").write_text(json.dumps(res, indent=2))
        print("INVALID RUN:\n  " + "\n  ".join(problems))
        sys.exit(3)

    # G1
    g1 = {"surviving": len(surv), "of": D.N_COMBINATIONS, "threshold": D.G1_MIN, "pass": len(surv) >= D.G1_MIN}
    # G2
    per_file = Counter(r["CrFe"] for r in surv)
    g2_cls = {}
    for c in D.CLASSES:
        files = sorted(f for f, cl in D.CLASS.items() if cl == c)
        counts = {f: per_file.get(f, 0) for f in files}
        g2_cls[c] = {"files": counts, "best": max(counts.values()),
                     "pass": max(counts.values()) >= D.G2_MIN_SURVIVORS_PER_FILE}
    g2 = {"per_class": g2_cls, "threshold_per_file": D.G2_MIN_SURVIVORS_PER_FILE,
          "pass": all(v["pass"] for v in g2_cls.values())}

    # G3 (primary 900 K) and sensitivity
    def g3_at(T):
        vals = [s_at[T][r["combo"]] for r in surv if r["combo"] in s_at[T]]
        n_pos = sum(1 for s in vals if s > D.G3_S_MIN)
        frac = n_pos / len(vals) if vals else 0.0
        return {"T_K": T, "n_valid": len(vals), "n_S_above_floor": n_pos, "fraction": round(frac, 4),
                "pass": frac >= D.G3_FRACTION}
    g3 = g3_at(D.PRIMARY_T)
    sens = {str(int(T)): g3_at(T) for T in D.SENSITIVITY_T if T in s_at}

    # descriptive survival tables (labelled sensitivity)
    surv_file = {e: dict(Counter(r[e] for r in surv)) for e in D.EDGES}
    surv_class = dict(Counter(D.CLASS[r["CrFe"]] for r in surv))
    lin = Counter(tuple(D.LINEAGE[e][r[e]] for e in D.EDGES) for r in surv)
    n_lin_total = (len(set(D.LINEAGE["CrFe"].values())) * len(set(D.LINEAGE["CrNi"].values())) *
                   len(set(D.LINEAGE["FeNi"].values())))
    failed = [k for k, g in (("G1", g1), ("G2", g2), ("G3", g3)) if not g["pass"]]
    res.update({"run_valid": True, "G1": g1, "G2": g2, "G3": g3, "sensitivity_T_G3": sens,
                "survivors_per_file": surv_file, "survivors_per_class": surv_class,
                "lineage_combinations": {"total": n_lin_total, "with_survivor": len(lin)},
                "primary_T_K": D.PRIMARY_T,
                "verdict": ("PASS: proceed to the class analysis" if not failed else
                            "FAIL: sigma stabilisation not informative for the class question in this system; "
                            "close the topic"),
                "failed_gates": failed})
    (run / "sigma" / "gate.json").write_text(json.dumps(res, indent=2))
    md = ["# Cr-Fe-Ni Pilot-M gate", "", f"Verdict: **{res['verdict']}**", "",
          "| Gate | Result | Criterion | Pass |", "|---|---|---|---|",
          f"| G1 survival | {g1['surviving']} of {g1['of']} | >= {D.G1_MIN} | {g1['pass']} |",
          f"| G2 coverage | best file per class A/B/C: " +
          "/".join(str(g2_cls[c]['best']) for c in D.CLASSES) + f" | >= {D.G2_MIN_SURVIVORS_PER_FILE} each | {g2['pass']} |",
          f"| G3 sigma visible ({D.PRIMARY_T:.0f} K) | {g3['n_S_above_floor']}/{g3['n_valid']} "
          f"({g3['fraction']:.0%}) with S > {D.G3_S_MIN} | >= {D.G3_FRACTION:.0%} | {g3['pass']} |", "",
          f"Lineage combinations with a survivor: {len(lin)} of {n_lin_total} (sensitivity, not gating)."]
    (run / "sigma" / "gate.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
