#!/usr/bin/env python3
"""
nimnsn_edge_check.py  (18 Nov 2026) - generalised from edge_check_batch.py (Al-Fe-Mn, 14 Nov 2026).
Systems: "nimnsn" (Ni-Mn-Sn Pilot-v1, 7 x 11 x 2 = 154 combinations) and
"alfemn_2g" (validation: must reproduce the Al-Fe-Mn rule-v2 result).
The edge-check rule v2 below is unchanged from edge_check_batch.py. Changes: (a) any exception
in a combination (merge, load, equilibrium) becomes a FAILED row with a reason, never a crash and
never a silent drop; (b) at the end the number of rows is checked against the number of
combinations (non-zero exit if different); (c) edge tags come from the files, file sets from SYSTEMS.

Original docstring:
edge_check_batch.py  (v1, 14 Nov 2026) - Al-Fe-Mn Pilot-v1, edge-check stage

Merges every combination of the pilot binary files with tdb_merge.merge_databases
(unchanged Track A merge) and checks that the merged description reproduces each
binary on its edge. Track A's tdb_merge.py is NOT modified; this script adds the
edge-check rule v2 agreed on 14 Nov 2026:

  Edge-check rule v2
  ------------------
  Grid: T = 800, 1200, 1600 K; x = 0.05 ... 0.95 step 0.1 (30 points per edge,
        identical to tdb_merge.check_edges).
  1. Compute the equilibrium with all phases.
  2. If it does not converge (exception or NaN), recompute leaving out one phase
     at a time and take the lowest converged Gibbs energy ("fallback").
     Applied to the binary reference AND to the merged description.
  3. If the fallback also fails, the point is "unverified" (not "failed").
  4. A verified point matches if the phase sets are equal and |dG| <= 1 J/mol.
  5. An edge passes if it has 0 mismatches and <= 2 unverified points of 30.
     A combination passes if all three edges pass.
  Motivation: AlMn-07Du at 800 K, x_Mn = 0.05 - fcc + Al6Mn and fcc + Al12Mn
  differ by 1.7 J/mol just above the Al12Mn decomposition (~785 K); pycalphad
  fails to converge with all three phases present, but converges (correctly)
  when any one is removed. A solver failure is not a merge failure.

  --strict reproduces the old tdb_merge.check_edges behaviour (no fallback,
  any non-converged point is a mismatch).

File selection (Pilot-v1 section 2a, option A, 14 Nov 2026):
  AlFe 4 x AlMn 6 x FeMn 7 = 168 combinations. AlMn-12Dju, -18Zhe, -18Zhe-mod
  excluded: pycalphad cannot compute them (BCC_4SL interstitial ratio 1 vs
  disordered A2_BCC ratio 3). FeMn-23Wal-3g excluded: does not load.

Outputs (in --out, default edge_check_alfemn/):
  run_info.json      command line, time, pycalphad version, rule, file SHA-256
  references.json    binary reference results (computed once per file)
  edge_check.csv     one row per combination (appended; reruns skip done rows)
  mismatches.jsonl   every mismatch / unverified point with details
  merge_conflicts.jsonl  every conflict message reported by merge_databases
  merged/            merged TDB files (what the threshold stage will load)

Usage (from data/, where tdb_merge.py is):
  python edge_check_batch.py --limit 3          # test run: first 3 combinations
  python edge_check_batch.py --workers 6        # full run, resumable
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
import sys
import time
import warnings
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
import pycalphad
from pycalphad import Database, equilibrium, variables as v

from tdb_merge import merge_databases

_ALFE = ["AlFe-09Sun", "AlFe-09Sun-no-option-F", "AlFe-17Zhe", "AlFe-21Mur"]
_ALMN = ["AlMn-07Du", "AlMn-17Cui", "AlMn-19Mie", "AlMn-92Jan", "AlMn-98Jan",
         "AlMn-99Liu-LB"]
# Each system: ordered edge groups -> file stems; prefix for merged TDB names.
# nimnsn: file set fixed by the file-text check of 17-18 Nov 2026 (all 20 files carry the
# same second-generation unary set); no file is excluded a priori. A file that cannot be
# computed gives failed combinations, which count as non-surviving (G1 denominator stays 154).
SYSTEMS = {
    "alfemn_2g": {"prefix": "ALFEMN",
                  "groups": {"AlFe": _ALFE, "AlMn": _ALMN,
                             "FeMn": ["FeMn-04Wit", "FeMn-23Jac", "FeMn-87Hua", "FeMn-89Hua-LB",
                                       "FeMn-89Hua-modified", "FeMn-89Lee"]}},      # 144
    "nimnsn": {"prefix": "NIMNSN",
               "groups": {"MnNi": ["MnNi-01Mie", "MnNi-07Fra", "MnNi-07Fra-2SL",
                                    "MnNi-07Fra-no-wildcards", "MnNi-08Liu",
                                    "MnNi-19Wal", "MnNi-19Wal-4sl"],                 # 7
                          "NiSn": ["NiSn-03Mie", "NiSn-04Liu", "NiSn-05Liu", "NiSn-12Zem",
                                    "NiSn-13Don", "NiSn-13Liu", "NiSn-13Liu-fractional",
                                    "NiSn-16Ber", "NiSn-21Zha", "NiSn-22Lia",
                                    "NiSn-99Gho"],                                   # 11
                          "MnSn": ["MnSn-01Mie", "MnSn-04Liu"]}},                    # 2
}
TEMPS = (800.0, 1200.0, 1600.0)
XS = tuple(float(x) for x in np.round(np.arange(0.05, 0.96, 0.1), 2))
TOL = 1.0
MAX_UNVERIFIED = 2

_REFS: dict = {}       # filled per worker by _init
_STRICT = False
_PREFIX = "X"
_TAGS: list = []      # edge tags in group order, e.g. ["MNNI", "NISN", "MNSN"]
_GROUPS: list = []    # group names in order


# ---------------------------------------------------------------- equilibrium

def _phase_set(r):
    return tuple(sorted({str(n) for n, f in zip(r.Phase.values.reshape(-1),
                                                  r.NP.values.reshape(-1))
                         if n and np.isfinite(f) and f > 1e-4}))


def _eq(db, comps, phases, cond):
    try:
        r = equilibrium(db, comps, phases, cond)
        g = float(r.GM.values.squeeze())
        if np.isfinite(g):
            return _phase_set(r), g
    except Exception:
        pass
    return None


def solve(db, comps, cond, strict=False):
    """Return (phase_set, G, status) with status direct | fallback | failed."""
    phases = sorted(db.phases)
    res = _eq(db, comps, phases, cond)
    if res is not None:
        return res[0], res[1], "direct"
    if strict:
        return None, None, "failed"
    best = None
    for p in phases:
        r = _eq(db, comps, [q for q in phases if q != p], cond)
        if r is not None and (best is None or r[1] < best[1]):
            best = r
    if best is None:
        return None, None, "failed"
    return best[0], best[1], "fallback"


def _cond(b, T, x):
    return {v.X(b): x, v.T: T, v.P: 101325, v.N: 1}


def edge_elements(db):
    return sorted(e for e in db.elements if e not in ("VA", "/-"))


# ---------------------------------------------------------------- references

def compute_references(paths, strict):
    refs = {}
    for p in paths:
        db = Database(str(p))
        a, b = edge_elements(db)
        pts = []
        for T in TEMPS:
            for x in XS:
                ps, g, st = solve(db, [a, b, "VA"], _cond(b, T, x), strict)
                pts.append({"T": T, "x": x, "phases": list(ps) if ps else None,
                            "G": g, "status": st})
        refs[p.name] = {"edge": [a, b], "points": pts}
        n_fb = sum(q["status"] == "fallback" for q in pts)
        n_f = sum(q["status"] == "failed" for q in pts)
        print(f"  reference {p.name:28s} {a}-{b}: fallback {n_fb}, failed {n_f}",
              flush=True)
    return refs


# ---------------------------------------------------------------- one combination

def _init(refs, strict, prefix, tags, groups):
    global _REFS, _STRICT, _PREFIX, _TAGS, _GROUPS
    _REFS, _STRICT, _PREFIX, _TAGS, _GROUPS = refs, strict, prefix, tags, groups


def _failed_row(combo_id, paths, reason, t0):
    row = {"combo": combo_id}
    for g, p in zip(_GROUPS, paths):
        row[g] = p.stem
    row["merge_conflicts"] = None
    for tag in _TAGS:
        row.update({f"{tag}_max_dG": None, f"{tag}_mismatch": None, f"{tag}_unverified": None,
                    f"{tag}_fallback": None, f"{tag}_pass": False})
    row["pass"] = False
    row["seconds"] = round(time.time() - t0, 1)
    row["failure"] = reason
    return row


def check_combination(args):
    combo_id, paths, merged_dir = args
    t0 = time.time()
    try:
        return _check_combination(combo_id, paths, merged_dir, t0)
    except Exception as e:           # never crash the pool, never drop a combination silently
        return (_failed_row(combo_id, paths, f"{type(e).__name__}: {e}"[:300], t0), [],
                [f"EXCEPTION {type(e).__name__}: {e}"[:300]])


def _check_combination(combo_id, paths, merged_dir, t0):
    conflicts = []
    db_m = merge_databases(paths, report=lambda s: conflicts.append(s.strip()))
    conflicts = [c for c in conflicts if not c.startswith("merged ")]
    out = Path(merged_dir) / f"{_PREFIX}__{combo_id}.tdb"
    db_m.to_file(str(out), fmt="tdb", if_exists="overwrite", if_incompatible="ignore")
    db_m = Database(str(out))                    # check what later stages will load

    row = {"combo": combo_id}
    for g, p in zip(_GROUPS, paths):
        row[g] = p.stem
    row["merge_conflicts"] = len(conflicts)
    details, combo_pass = [], True
    for p in paths:
        ref = _REFS[p.name]
        a, b = ref["edge"]
        tag = f"{a}{b}"
        worst, n_mis, n_unv, n_fb = 0.0, 0, 0, 0
        for q in ref["points"]:
            ps_m, g_m, st_m = solve(db_m, [a, b, "VA"], _cond(b, q["T"], q["x"]), _STRICT)
            n_fb += (q["status"] == "fallback") + (st_m == "fallback")
            if q["G"] is None or g_m is None:
                if _STRICT:
                    n_mis += 1
                    kind = "mismatch"
                else:
                    n_unv += 1
                    kind = "unverified"
                details.append({"combo": combo_id, "edge": tag, "T": q["T"], "x": q["x"],
                                "kind": kind, "ref_status": q["status"],
                                "merged_status": st_m})
                continue
            d = g_m - q["G"]
            worst = max(worst, abs(d))
            if tuple(q["phases"]) != tuple(ps_m) or abs(d) > TOL:
                n_mis += 1
                details.append({"combo": combo_id, "edge": tag, "T": q["T"], "x": q["x"],
                                "kind": "mismatch", "ref_phases": q["phases"],
                                "merged_phases": list(ps_m), "dG": round(d, 3),
                                "ref_status": q["status"], "merged_status": st_m})
        edge_pass = n_mis == 0 and n_unv <= MAX_UNVERIFIED
        combo_pass &= edge_pass
        row.update({f"{tag}_max_dG": round(worst, 3), f"{tag}_mismatch": n_mis,
                    f"{tag}_unverified": n_unv, f"{tag}_fallback": n_fb,
                    f"{tag}_pass": edge_pass})
    row["pass"] = combo_pass
    row["seconds"] = round(time.time() - t0, 1)
    row["failure"] = ""
    return row, details, conflicts


# ---------------------------------------------------------------- main

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tdb-dir", default=os.environ.get("SGTE_BINARY_DIR"),
                    help="folder with the binary TDB files (default: $SGTE_BINARY_DIR; "
                         "no hard-coded fallback)")
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS),
                    help="nimnsn (154 combinations) or alfemn_2g (144, validation)")
    ap.add_argument("--out", default=None, help="default: edge_check_<system>")
    ap.add_argument("--limit", type=int, default=None, help="only the first N combinations")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--strict", action="store_true", help="old rule: no fallback")
    args = ap.parse_args()

    if not args.tdb_dir or not Path(args.tdb_dir).is_dir():
        sys.exit("TDB folder not set or not a folder: pass --tdb-dir or set SGTE_BINARY_DIR")
    tdb = Path(args.tdb_dir)
    system = SYSTEMS[args.system]
    out = Path(args.out or f"edge_check_{args.system}")
    (out / "merged").mkdir(parents=True, exist_ok=True)
    groups = {k: [tdb / f"{s}.tdb" for s in v_] for k, v_ in system["groups"].items()}
    missing = [str(p) for g in groups.values() for p in g if not p.exists()]
    if missing:
        sys.exit("Missing files:\n  " + "\n  ".join(missing))
    all_files = [p for g in groups.values() for p in g]

    gnames = list(groups)
    combos = []
    for fs in itertools.product(*groups.values()):
        combos.append(("___".join(f.stem for f in fs), list(fs)))
    if args.limit:
        combos = combos[: args.limit]

    info = {"command": " ".join([Path(sys.executable).name] + sys.argv),
            "started": datetime.now().isoformat(timespec="seconds"),
            "pycalphad": pycalphad.__version__,
            "system": args.system,
            "groups": {k: [p.name for p in g] for k, g in groups.items()},
            "file_set_rule": "all files second-generation SGTE unaries (file-text check); "
                             "a non-computable file gives failed combinations, which count "
                             "as non-surviving",
            "rule": {"temps": TEMPS, "x": XS, "tol_J_per_mol": TOL,
                     "max_unverified_per_edge": MAX_UNVERIFIED,
                     "fallback": not args.strict},
            "n_combinations": len(combos),
            "files_sha256": {p.name: sha256(p) for p in all_files}}
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"Combinations: {len(combos)}   rule: {'strict' if args.strict else 'v2 (fallback)'}")

    ref_file = out / ("references_strict.json" if args.strict else "references.json")
    if ref_file.exists():
        refs = json.loads(ref_file.read_text())
        print(f"References loaded from {ref_file}")
    else:
        print("Computing binary references (once per file):")
        refs = compute_references(all_files, args.strict)
        ref_file.write_text(json.dumps(refs, indent=1))

    tags = [f"{refs[g[0].name]['edge'][0]}{refs[g[0].name]['edge'][1]}" for g in groups.values()]
    csv_path = out / ("edge_check_strict.csv" if args.strict else "edge_check.csv")
    done = set()
    if csv_path.exists():
        with open(csv_path, newline="") as f:
            done = {r["combo"] for r in csv.DictReader(f)}
    todo = [(cid, paths, str(out / "merged")) for cid, paths in combos if cid not in done]
    print(f"Already done: {len(done)}   to run: {len(todo)}")
    if not todo:
        return

    fields = None
    n_pass = n_run = 0
    t0 = time.time()
    with Pool(args.workers, initializer=_init, initargs=(refs, args.strict, system["prefix"], tags, gnames)) as pool, \
            open(out / "mismatches.jsonl", "a") as fdet, \
            open(out / "merge_conflicts.jsonl", "a") as fcon:
        for row, details, conflicts in pool.imap_unordered(check_combination, todo):
            for c in conflicts:
                fcon.write(json.dumps({"combo": row["combo"], "conflict": c}) + "\n")
            new = not csv_path.exists() or csv_path.stat().st_size == 0
            with open(csv_path, "a", newline="") as f:
                fields = fields or list(row)
                w = csv.DictWriter(f, fieldnames=fields)
                if new:
                    w.writeheader()
                w.writerow(row)
            for d in details:
                fdet.write(json.dumps(d) + "\n")
            n_run += 1
            n_pass += row["pass"]
            edges = "  ".join(f"{e}:{'ok' if row[f'{e}_pass'] else 'FAIL'}"
                              f"(mis {row[f'{e}_mismatch']}, unv {row[f'{e}_unverified']})"
                              for e in tags)
            if row.get("failure"):
                edges += f"  FAILED: {row['failure']}"
            print(f"[{n_run}/{len(todo)}] {'PASS' if row['pass'] else 'FAIL'}  "
                  f"{row['combo']}  conflicts {row['merge_conflicts']}  {edges}  "
                  f"{row['seconds']} s", flush=True)
    print(f"\nDone: {n_pass}/{n_run} passed in {time.time() - t0:.0f} s. "
          f"Results: {csv_path}")
    # silent-failure guard: every combination must have exactly one row
    with open(csv_path, newline="") as f:
        n_rows = len({r["combo"] for r in csv.DictReader(f)})
    if n_rows != len(combos):
        sys.exit(f"INCOMPLETE: {n_rows} rows for {len(combos)} combinations "
                 f"(rerun resumes; a partial output is a failed run)")


if __name__ == "__main__":
    main()
