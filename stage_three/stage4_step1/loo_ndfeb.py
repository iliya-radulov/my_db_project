#!/usr/bin/env python3
"""
loo_ndfeb.py  (v1, 15 Nov 2026) - Nd-Fe-B closure analyses on the released
Track A ensemble (78 survivors of 84). Pure post-processing of
results_v2/batch_results.csv; no new equilibrium calculations.

Analyses
--------
1. Consistency: full-78 medians vs the released summary.json values
   (hard-coded below from the release), must agree to < 0.001.
2. Leave-one-assessment-out (LOO): for each of the 14 binary files, the
   median shift at each temperature when all its combinations are removed.
3. Extreme ownership: which files own the min/max end of the range
   (range shrink > 0.15 kJ when the file is removed).
4. Variance decomposition: eta^2 per edge per temperature (which edge
   drives the spread), plus the additively-explained share.
5. Null model: permutation test (default 2000 shuffles) of
   "thresholds are independent of file identity".
6. Hallemans provenance: medians grouped by the number of Hallemans-
   lineage files (FeNd-95Hal-LB, FeB-94Hal-LB, NdB-95Hal-LB) per combo.

Usage:  python loo_ndfeb.py results_v2/batch_results.csv
"""
import csv
import sys
from collections import defaultdict

import numpy as np

TEMPS = ["800K", "1000K", "1300K", "1375K", "1450K", "1600K"]
EDGES = {"FeNd": "binary_FeNd", "FeB": "binary_FeB", "NdB": "binary_NdB"}
RELEASED_MEDIANS = {"800K": -8.791, "1000K": -7.88, "1300K": -6.941,
                    "1375K": -7.065, "1450K": -7.452, "1600K": -8.764}
N_PERM = 2000


def eta2(y, labels):
    tot = ((y - y.mean()) ** 2).sum()
    g = defaultdict(list)
    for lab, yy in zip(labels, y):
        g[lab].append(yy)
    return sum(len(v) * (np.mean(v) - y.mean()) ** 2 for v in g.values()) / tot


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "results_v2/batch_results.csv"
    rows = list(csv.DictReader(open(path)))
    surv = [r for r in rows if r["survived"] == "True"]
    for r in surv:
        for T in TEMPS:
            r[T] = float(r[f"threshold_at_{T}"])
    print(f"combinations: {len(rows)} total, {len(surv)} survived")

    print("\n1) consistency vs released summary.json")
    ok = True
    for T in TEMPS:
        m = float(np.median([r[T] for r in surv]))
        d = abs(m - RELEASED_MEDIANS[T])
        ok &= d < 1e-3
        print(f"   {T:>6s}: computed {m:8.3f}  released {RELEASED_MEDIANS[T]:8.3f}  diff {d:.4f}")
    print("   -> " + ("CONSISTENT" if ok else "MISMATCH - do not trust the rest"))

    full_med = {T: np.median([r[T] for r in surv]) for T in TEMPS}
    full_rng = {T: (min(r[T] for r in surv), max(r[T] for r in surv)) for T in TEMPS}
    files = {e: sorted({r[c] for r in rows}) for e, c in EDGES.items()}

    print("\n2) leave-one-assessment-out median shifts [kJ/mol-atom]")
    print(f"   {'file':28s} {'n_left':>6s} " + " ".join(f"{T:>8s}" for T in TEMPS) + "  max|shift|")
    for e, c in EDGES.items():
        for f in files[e]:
            rem = [r for r in surv if r[c] != f]
            sh = [float(np.median([r[T] for r in rem]) - full_med[T]) for T in TEMPS]
            print(f"   {f:28s} {len(rem):6d} " + " ".join(f"{s:+8.3f}" for s in sh)
                  + f"  {max(abs(s) for s in sh):.3f}")

    print("\n3) extreme ownership (range shrink > 0.15 kJ on removal)")
    for e, c in EDGES.items():
        for f in files[e]:
            rem = [r for r in surv if r[c] != f]
            for T in TEMPS:
                lo, hi = min(r[T] for r in rem), max(r[T] for r in rem)
                dlo = lo - full_rng[T][0]
                dhi = full_rng[T][1] - hi
                if max(dlo, dhi) > 0.15:
                    side = "min" if dlo > dhi else "max"
                    print(f"   {f:26s} {T:>6s}: owns {side} end, shrink {max(dlo, dhi):.3f}")

    print("\n4) variance decomposition: eta^2 per edge")
    print(f"   {'T':>6s} {'FeNd':>7s} {'FeB':>7s} {'NdB':>7s} {'sum':>7s}  dominant")
    for T in TEMPS:
        y = np.array([r[T] for r in surv])
        etas = {e: eta2(y, [r[c] for r in surv]) for e, c in EDGES.items()}
        dom = max(etas, key=etas.get)
        print(f"   {T:>6s} {etas['FeNd']:7.1%} {etas['FeB']:7.1%} {etas['NdB']:7.1%} "
              f"{sum(etas.values()):7.1%}  {dom}")

    print(f"\n5) null model: permutation test ({N_PERM} shuffles)")
    rng = np.random.default_rng(7)
    print(f"   {'T':>6s} {'observed':>9s} {'null 99th':>10s} {'p':>9s}")
    for T in TEMPS:
        y = np.array([r[T] for r in surv])
        labels = [[r[c] for r in surv] for c in EDGES.values()]
        obs = sum(eta2(y, lab) for lab in labels)
        null = np.array([sum(eta2(rng.permutation(y), lab) for lab in labels)
                         for _ in range(N_PERM)])
        p = (null >= obs).mean()
        ptxt = f"<{1.0 / N_PERM:.4f}" if p == 0 else f"{p:.4f}"
        print(f"   {T:>6s} {obs:9.1%} {np.percentile(null, 99):10.1%} {ptxt:>9s}")

    print("\n6) Hallemans-lineage grouping (shared-author files)")
    def nhal(r):
        return sum("Hal-LB" in r[c] for c in EDGES.values())
    g = defaultdict(list)
    for r in surv:
        g[nhal(r)].append(r)
    for k in sorted(g):
        meds = " ".join(f"{np.median([r[T] for r in g[k]]):8.3f}" for T in TEMPS)
        print(f"   n_Hal={k}: {len(g[k]):2d} combos  medians: {meds}")


if __name__ == "__main__":
    main()
