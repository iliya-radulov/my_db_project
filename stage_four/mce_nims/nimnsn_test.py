#!/usr/bin/env python3
"""
nimnsn_test.py (18 Nov 2026) - the pre-registered test of Ni-Mn-Sn Pilot-v1. Runs only if the
gate (nimnsn_gate.py) has passed.

Primary: two-sided Spearman partial correlation of the row median threshold (1000 K) with the
martensite-start temperature T_tr (FOPT line of S6), controlling e/a, 25 pure-ternary rows.
(rank-based: Pearson correlation of the rank residuals after regressing the ranks of each
variable on the ranks of e/a; ties get average ranks.)
Null: Freedman-Lane permutation, unit = paper (rows of one paper stay together; papers are
shuffled among papers with the same number of rows), 100 000 permutations, seed 20261118;
p = (1 + #{|rho*| >= |rho|}) / (1 + n_perm).
Run condition: >= 20 FOPT rows, >= 12 distinct compositions, >= 15 papers.
Verdict: PASS if |rho| >= 0.5 and p <= 0.05 and the sign of rho agrees with the primary in
>= 75 % of the surviving raw combinations (each tested separately); FAIL if |rho| <= 0.3;
otherwise INCONCLUSIVE.
Reported, not decisive: unconditioned rho; e/a vs T_tr; the test against dS (FOPT line,
signed) as secondary; 800 and 1200 K; without the single-crystal row and without the
approximate-T row; leave-one-paper-out range; SOPT (Curie) partial rho (n = 9, no p-value).

Usage: python nimnsn_test.py --run-dir edge_check_nimnsn --rows nimnsn_rows.csv
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

SEED, NPERM = 20261118, 100_000
EDGES = ["MnNi", "NiSn", "MnSn"]


def _resid(y, z):
    A = np.column_stack([np.ones(len(z)), z])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return y - A @ beta, A @ beta


def partial_spearman(x, y, z):
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)
    ex, _ = _resid(rx, rz)
    ey, _ = _resid(ry, rz)
    d = np.sqrt((ex @ ex) * (ey @ ey))
    return float(ex @ ey / d) if d > 0 else float("nan")


def perm_p(x, y, z, paper, rho, nperm=NPERM, seed=SEED):
    rng = np.random.default_rng(seed)
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)
    ex, _ = _resid(rx, rz)
    ey, fy = _resid(ry, rz)
    groups = defaultdict(list)                    # paper -> row indices
    for i, p in enumerate(paper):
        groups[p].append(i)
    by_size = defaultdict(list)                   # size -> papers
    for p, idx in groups.items():
        by_size[len(idx)].append(p)
    A = np.column_stack([np.ones(len(z)), rz])
    M = np.eye(len(z)) - A @ np.linalg.pinv(A)    # projector onto the residual space of [1, rank(e/a)]
    count = 0
    for _ in range(nperm):
        ystar = np.empty_like(ey)
        for size, papers in by_size.items():
            perm = rng.permutation(len(papers))
            for src, dst in zip(papers, [papers[k] for k in perm]):
                ystar[groups[dst]] = ey[groups[src]]      # block moves, order inside the paper kept
        e2 = M @ (fy + ystar)          # Freedman-Lane: refit after permuting
        d = np.sqrt((ex @ ex) * (e2 @ e2))
        r = ex @ e2 / d if d > 0 else 0.0
        count += abs(r) >= abs(rho) - 1e-12
    return (1 + count) / (1 + nperm)


def verdict(rho, p, agree):
    a = abs(rho)
    if a <= 0.3:
        return "FAIL"
    if a >= 0.5 and p <= 0.05 and agree >= 0.75:
        return "PASS"
    return "INCONCLUSIVE"


def fnum(s):
    s = (s or "").strip().replace("~", "")
    try:
        return float(s)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--nperm", type=int, default=NPERM, help="default 100000 (pre-registered)")
    a = ap.parse_args()
    run = Path(a.run_dir)
    tdir = run / "thresholds"
    gate = json.loads((tdir / "gate.json").read_text())
    if not str(gate.get("verdict", "")).startswith("PASS"):
        sys.exit(f"Gate not passed ({gate.get('verdict')}): the test is not run.")

    rows = list(csv.DictReader(open(a.rows, newline="")))
    surv = [r["combo"] for r in csv.DictReader(open(run / "edge_check.csv", newline="")) if r["pass"] == "True"]
    sset = set(surv)
    cid = lambda r: (f"Ni{round(float(r['Ni_at']), 3):g}_Mn{round(float(r['Mn_at']), 3):g}"
                     f"_Sn{round(float(r['Sn_at']), 3):g}")
    tab = defaultdict(dict)
    for r in csv.DictReader(open(tdir / "thresholds.csv", newline="")):
        if r["combo"] in sset and not r["status"].startswith("failed") and r["dG_kJ_per_mol_atom"] not in ("", "None"):
            tab[(r["comp_id"], float(r["T"]))][r["combo"]] = float(r["dG_kJ_per_mol_atom"])

    fopt = [r for r in rows if "FOPT" in r["types"].split()]
    n_comp = len({cid(r) for r in fopt})
    n_pap = len({r["ref"] for r in fopt})
    out = {"n_fopt_rows": len(fopt), "n_distinct_compositions": n_comp, "n_papers": n_pap}
    if len(fopt) < 20 or n_comp < 12 or n_pap < 15:
        out["verdict"] = "NOT RUN: run condition not met"
        (tdir / "test_result.json").write_text(json.dumps(out, indent=2))
        sys.exit(f"Run condition not met: {len(fopt)} rows, {n_comp} compositions, {n_pap} papers")

    ea = np.array([float(r["e_a"]) for r in fopt])
    ttr = np.array([float(r["T_fopt_K"]) for r in fopt])
    paper = [r["ref"] for r in fopt]
    comps = [cid(r) for r in fopt]

    def medians(T):
        return np.array([np.median(list(tab[(c, T)].values())) for c in comps])

    thr = medians(1000.0)
    rho = partial_spearman(thr, ttr, ea)
    p = perm_p(thr, ttr, ea, paper, rho, a.nperm)

    # per-combination sign agreement
    signs, n_used = [], 0
    for c in surv:
        vals = [tab[(cc, 1000.0)].get(c) for cc in comps]
        if any(v is None for v in vals):
            continue
        n_used += 1
        r_c = partial_spearman(np.array(vals), ttr, ea)
        signs.append(np.sign(r_c) == np.sign(rho) and r_c != 0)
    agree = float(np.mean(signs)) if signs else 0.0
    out.update({"rho_partial": rho, "p_two_sided": p, "n_perm": a.nperm, "seed": SEED,
                "sign_agreement": agree, "n_combinations_used_for_agreement": n_used,
                "n_surviving": len(surv), "verdict": verdict(rho, p, agree)})

    # reported, not decisive
    rep = {}
    rep["rho_threshold_vs_Ttr_unconditioned"] = float(np.corrcoef(rankdata(thr), rankdata(ttr))[0, 1])
    rep["rho_ea_vs_Ttr"] = float(np.corrcoef(rankdata(ea), rankdata(ttr))[0, 1])
    ds = [fnum(r["dS_fopt"]) for r in fopt]
    if all(v is not None for v in ds):
        dsv = np.array(ds)
        rho_ds = partial_spearman(thr, dsv, ea)
        rep["dS_secondary"] = {"rho_partial": rho_ds, "p": perm_p(thr, dsv, ea, paper, rho_ds, a.nperm),
                               "no_verdict": True}
    else:
        rep["dS_secondary"] = {"note": "some dS values not numeric: " + str(sum(v is None for v in ds))}
    for T in (800.0, 1200.0):
        t2 = medians(T)
        r2 = partial_spearman(t2, ttr, ea)
        rep[f"T{int(T)}K"] = {"rho": r2, "p": perm_p(t2, ttr, ea, paper, r2, a.nperm)}
    keep = np.array([r["single_crystal"] == "0" and r["T_fopt_approx"] == "0" for r in fopt])
    r3 = partial_spearman(thr[keep], ttr[keep], ea[keep])
    rep["without_single_crystal_and_approx_T_rows"] = {"n": int(keep.sum()), "rho": r3}
    loo = []
    for pp in sorted(set(paper)):
        k = np.array([q != pp for q in paper])
        loo.append(partial_spearman(thr[k], ttr[k], ea[k]))
    rep["leave_one_paper_out_rho_range"] = [float(np.nanmin(loo)), float(np.nanmax(loo))]
    sopt = [(i, r) for i, r in enumerate(fopt) if r["T_sopt_K"]]
    if len(sopt) >= 5:
        ii = [i for i, _ in sopt]
        rep["SOPT_curie_partial_rho"] = {"n": len(ii), "rho": partial_spearman(
            thr[ii], np.array([float(r["T_sopt_K"]) for _, r in sopt]), ea[ii]), "no_p_value": True}
    out["reported_not_decisive"] = rep
    (tdir / "test_result.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("verdict", "rho_partial", "p_two_sided", "sign_agreement",
                                           "n_fopt_rows", "n_distinct_compositions", "n_papers")}, indent=2))


if __name__ == "__main__":
    main()
