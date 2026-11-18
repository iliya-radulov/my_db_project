#!/usr/bin/env python3
"""
nimnsn_gate.py (18 Nov 2026) - gate G1-G3 of Ni-Mn-Sn Pilot-v1, applied once, after the edge
check and the thresholds, before the test. Definitions as in the frozen pre-registration:

  G1  >= 40 of the 154 raw combinations pass edge-check rule v2 (`pass` in edge_check.csv).
  G2  >= 2 lineages survive on each of the three edges (a lineage survives on an edge if one
      of its files is part of at least one surviving combination).
  G3  per row (25 pure-ternary rows, duplicates counted): m_r = median and q_r = IQR of the
      threshold at 1000 K over the surviving combinations; S = IQR over the rows of {m_r};
      N = median over the rows of {q_r}; pass if S >= 2*N. Quantiles: numpy linear (type 7).

Run validity (not a gate): every row needs a finite threshold from >= 80 % of the surviving
combinations; otherwise the run is INVALID (a failed run, handled by the implementation-and-
environment fault rule), not a gate failure.

Also reported, labelled sensitivity, never gating: survival per lineage combination, G3 with
lineage-balanced weights, G3 at 800 and 1200 K.

Usage: python nimnsn_gate.py --run-dir edge_check_nimnsn --rows nimnsn_rows.csv
Writes <run-dir>/thresholds/gate.json and gate.md. Exit code 0 = gates evaluated (pass or
fail is in the file), 3 = run invalid.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

G1_MIN, G1_TOTAL = 40, 154
LINEAGE = {
    "MnNi": {"MnNi-01Mie": "Mie01", "MnNi-07Fra": "Fra07", "MnNi-07Fra-2SL": "Fra07",
             "MnNi-07Fra-no-wildcards": "Fra07", "MnNi-08Liu": "Liu08", "MnNi-19Wal": "Liu08",
             "MnNi-19Wal-4sl": "Liu08"},
    "NiSn": {"NiSn-99Gho": "Gho99", "NiSn-03Mie": "Gho99", "NiSn-05Liu": "Gho99",
             "NiSn-04Liu": "Liu04", "NiSn-12Zem": "Liu04", "NiSn-13Don": "Liu04", "NiSn-16Ber": "Liu04",
             "NiSn-13Liu": "Liu13", "NiSn-13Liu-fractional": "Liu13", "NiSn-21Zha": "Liu13",
             "NiSn-22Lia": "Liu13"},
    "MnSn": {"MnSn-01Mie": "Mie01", "MnSn-04Liu": "Liu04"},
}
EDGES = ["MnNi", "NiSn", "MnSn"]
VALID_FRACTION = 0.8


def wquantile(x, w, q):
    """Weighted quantile (linear interpolation on the weighted CDF midpoints)."""
    o = np.argsort(x)
    x, w = np.asarray(x)[o], np.asarray(w)[o]
    c = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, c, x))


def g3(values_by_row, weights_by_row=None):
    m, q = [], []
    for r, vals in values_by_row.items():
        vals = np.asarray(vals, float)
        if weights_by_row is None:
            m.append(np.median(vals))
            q.append(np.percentile(vals, 75) - np.percentile(vals, 25))
        else:
            w = np.asarray(weights_by_row[r], float)
            m.append(wquantile(vals, w, 0.5))
            q.append(wquantile(vals, w, 0.75) - wquantile(vals, w, 0.25))
    S = float(np.percentile(m, 75) - np.percentile(m, 25))
    N = float(np.median(q))
    return S, N, S >= 2 * N, m, q


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--thr", default=None, help="default: <run-dir>/thresholds/thresholds.csv")
    a = ap.parse_args()
    run = Path(a.run_dir)
    thr_path = Path(a.thr or run / "thresholds" / "thresholds.csv")
    out_dir = thr_path.parent

    ec = list(csv.DictReader(open(run / "edge_check.csv", newline="")))
    n_total = len(ec)
    surv = [r for r in ec if r["pass"] == "True"]
    surv_ids = {r["combo"] for r in surv}
    res = {"n_combinations_in_edge_check": n_total, "n_surviving": len(surv)}

    # ---- G1
    res["G1"] = {"surviving": len(surv), "of": G1_TOTAL, "threshold": G1_MIN,
                 "pass": len(surv) >= G1_MIN and n_total == G1_TOTAL}
    if n_total != G1_TOTAL:
        res["G1"]["note"] = f"edge_check.csv has {n_total} combinations, expected {G1_TOTAL}"
    res["failed_combinations_with_reason"] = [{"combo": r["combo"], "failure": r.get("failure", "")}
                                              for r in ec if r.get("failure")]

    # ---- G2
    lin = {}
    for e in EDGES:
        s = {LINEAGE[e][r[e]] for r in surv}
        lin[e] = sorted(s)
    res["G2"] = {"lineages_surviving": lin, "n": {e: len(lin[e]) for e in EDGES},
                 "pass": all(len(lin[e]) >= 2 for e in EDGES)}

    # ---- lineage combinations (sensitivity)
    lc_all, lc_surv, lc_size = set(), set(), defaultdict(int)
    for r in ec:
        k = tuple(LINEAGE[e][r[e]] for e in EDGES)
        lc_all.add(k)
        if r["pass"] == "True":
            lc_surv.add(k)
            lc_size[k] += 1
    res["lineage_combinations"] = {"total": len(lc_all), "with_survivor": len(lc_surv)}

    # ---- thresholds
    rows = list(csv.DictReader(open(a.rows, newline="")))
    comp_of_row = {}
    for r in rows:
        comp_of_row[r["row_id"]] = (f"Ni{round(float(r['Ni_at']), 3):g}_Mn{round(float(r['Mn_at']), 3):g}"
                                    f"_Sn{round(float(r['Sn_at']), 3):g}")
    tab = defaultdict(dict)       # (comp, T) -> combo -> value
    for r in csv.DictReader(open(thr_path, newline="")):
        if r["combo"] in surv_ids and not r["status"].startswith("failed") and r["dG_kJ_per_mol_atom"] not in ("", "None"):
            tab[(r["comp_id"], float(r["T"]))][r["combo"]] = float(r["dG_kJ_per_mol_atom"])
    lc_of = {r["combo"]: tuple(LINEAGE[e][r[e]] for e in EDGES) for r in surv}

    def per_row(T):
        vals, wts, nfin = {}, {}, {}
        for rid, cid in comp_of_row.items():
            d = tab.get((cid, T), {})
            nfin[rid] = len(d)
            vals[rid] = list(d.values())
            wts[rid] = [1.0 / lc_size[lc_of[c]] for c in d]
        return vals, wts, nfin

    sens, valid = {}, True
    for T in (1000.0, 800.0, 1200.0):
        vals, wts, nfin = per_row(T)
        ok = all(n >= VALID_FRACTION * len(surv) and n > 0 for n in nfin.values())
        if T == 1000.0:
            valid = ok
            res["run_valid"] = ok
            res["finite_per_row_min"] = min(nfin.values()) if nfin else 0
        if not ok:
            sens[str(int(T))] = {"valid": False}
            continue
        S, N, p, m, q = g3(vals)
        Sw, Nw, pw, _, _ = g3(vals, wts)
        sens[str(int(T))] = {"S": S, "N": N, "ratio": S / N if N > 0 else None, "pass": p,
                             "lineage_balanced": {"S": Sw, "N": Nw, "pass": pw}}
        if T == 1000.0:
            res["row_medians_1000K"] = dict(zip(vals.keys(), [float(x) for x in m]))
            res["row_iqr_1000K"] = dict(zip(vals.keys(), [float(x) for x in q]))
    res["G3"] = {"primary_T_K": 1000, **sens.get("1000", {})}
    res["sensitivity_T"] = sens
    res["run_valid"] = valid
    if valid:
        res["verdict"] = ("PASS: proceed to the test" if res["G1"]["pass"] and res["G2"]["pass"]
                          and res["G3"]["pass"] else
                          "FAIL: descriptor not informative for this system; close the topic")
        res["failed_gates"] = [g for g in ("G1", "G2", "G3") if not res[g]["pass"]]
    else:
        res["verdict"] = "INVALID RUN: not a gate result (see the implementation-and-environment fault rule)"
    (out_dir / "gate.json").write_text(json.dumps(res, indent=2))
    md = [f"# Ni-Mn-Sn Pilot-v1 gate", "",
          f"Verdict: **{res['verdict']}**", "",
          f"- G1: {res['G1']['surviving']} of {G1_TOTAL} (>= {G1_MIN}): {'pass' if res['G1']['pass'] else 'FAIL'}",
          f"- G2: lineages {res['G2']['n']}: {'pass' if res['G2']['pass'] else 'FAIL'}",
          (f"- G3 (1000 K): S = {res['G3'].get('S')}, N = {res['G3'].get('N')}, ratio {res['G3'].get('ratio')}: "
           f"{'pass' if res['G3'].get('pass') else 'FAIL'}" if valid else "- G3: not evaluated (invalid run)"),
          f"- lineage combinations with a survivor: {res['lineage_combinations']['with_survivor']} of "
          f"{res['lineage_combinations']['total']} (sensitivity, not gating)"]
    (out_dir / "gate.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    if not valid:
        sys.exit(3)


if __name__ == "__main__":
    main()
