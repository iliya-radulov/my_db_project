"""
stage_five/general_ensemble.py

System-agnostic Binary-Ensemble CALPHAD Screening Engine.
Generalizes the Stage 4 Track A protocol (audit -> merge -> edge-check v2 ->
threshold distribution -> pre-registered gates) to any ternary system in $SGTE_BINARY_DIR.

Usage:
    export SGTE_BINARY_DIR=/path/to/data/tdb/sgte_binary
    python stage_five/general_ensemble.py --elements FE ND B --comp 0.8235 0.1176 0.0588
    python stage_five/general_ensemble.py --elements AL FE MN --comp 0.6154 0.1923 0.1923 --workers 6
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import sys
import tempfile
import time
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

# NOTE: Removed the unused `combo_id` import that was crashing the module.
#from stage_three.stage4_step1.run_batch_v2_old import combo_id

warnings.filterwarnings("ignore")
import pycalphad
from pycalphad import Database, equilibrium, variables as v

# Reuse validated Track A merge & lookup utilities from stage_three
REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE3_DIR = REPO_ROOT / "stage_three"
if str(STAGE3_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE3_DIR))

from tdb_lookup import build_index, find_binaries
from tdb_merge import merge_databases

# ── Constants (Edge-check rule v2 & default temperature grid) ──────────────────
EDGE_TEMPS = (800.0, 1200.0, 1600.0)
EDGE_XS = tuple(float(x) for x in np.round(np.arange(0.05, 0.96, 0.1), 2))
EDGE_TOL_J = 1.0
MAX_UNVERIFIED = 2
DEFAULT_TEMPS = [800.0, 1000.0, 1100.0, 1200.0, 1300.0, 1375.0, 1450.0, 1600.0]

_NUM_RE = re.compile(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?")


# ── 1. Pre-merge Audit & Lineage Extraction ────────────────────────────────────

def extract_lineage(stem: str) -> str:
    """Infer assessment lineage from SGTE filename stem."""
    parts = stem.split("-")
    if len(parts) < 2:
        return stem
    tag = parts[1]
    m = re.match(r"^(\d{2})([A-Za-z]+)", tag)
    if m:
        return f"{m.group(2)}{m.group(1)}"
    return tag

def _ghser_norm(path: Path, symbol_name: str) -> str | None:
    """Normalised text of FUNCTION <symbol_name> for unary consistency screening."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    body = " ".join(ln.split("$", 1)[0] for ln in text.splitlines())
    for cmd in body.split("!"):
        toks = cmd.split(None, 2)
        if len(toks) == 3 and toks[0].upper().startswith("FUNC") and toks[1].upper() == symbol_name:
            compact = toks[2].upper().replace(" ", "").replace("\t", "")
            return _NUM_RE.sub(lambda m: f"{float(m.group()):.9g}", compact)
    return None

def _has_interstitial_site_defect(db: Database) -> str | None:
    """Detect ordered phases whose sublattice site ratios disagree with DIS_PART."""
    for pname, ph in db.phases.items():
        dis = ph.model_hints.get("disordered_part")
        if dis and dis in db.phases:
            ord_va = ph.sublattices[-1] if "VA" in [s.name for s in ph.constituents[-1]] else None
            dis_va = db.phases[dis].sublattices[-1] if "VA" in [s.name for s in db.phases[dis].constituents[-1]] else None
            if ord_va is not None and dis_va is not None and abs(float(ord_va) - float(dis_va)) > 1e-6:
                return f"{pname} interstitial ratio {ord_va} != {dis} ratio {dis_va}"
    return None

def audit_binary_candidates(elements: list[str], tdb_dir: Path) -> tuple[dict[str, list[Path]], list[dict]]:
    elements = [e.upper() for e in elements]
    index = build_index(tdb_dir)
    raw_pairs = find_binaries(elements, index)
    if len(raw_pairs) < 3:
        raise RuntimeError(f"Need 3 binary pairs for {elements}, found {len(raw_pairs)}")

    audit_log = []
    valid_by_pair: dict[str, list[Path]] = {}
    all_valid_files: list[Path] = []

    for pair_set, paths in sorted(raw_pairs.items(), key=lambda kv: "-".join(sorted(kv[0]))):
        pair_label = "-".join(sorted(pair_set))
        kept = []
        for p in paths:
            if "-3g" in p.stem.lower():
                audit_log.append({"file": p.name, "pair": pair_label, "status": "excluded", "reason": "3rd-generation assessment (-3g)"})
                continue
            try:
                db = Database(str(p))
            except Exception as e:
                audit_log.append({"file": p.name, "pair": pair_label, "status": "excluded", "reason": f"parse error: {type(e).__name__}"})
                continue
            defect = _has_interstitial_site_defect(db)
            if defect:
                audit_log.append({"file": p.name, "pair": pair_label, "status": "excluded", "reason": f"interstitial defect: {defect}"})
                continue
            kept.append(p)
            all_valid_files.append(p)
            audit_log.append({"file": p.name, "pair": pair_label, "status": "accepted", "lineage": extract_lineage(p.stem)})
        valid_by_pair[pair_label] = kept

    for el in elements:
        sym_candidates = [f"GHSER{el}", f"GHSER{el}{el}"]
        defs_by_file: dict[str, str] = {}
        for p in all_valid_files:
            pair_els = re.findall(r"[A-Z][a-z]?", p.stem.split("-", 1)[0])
            if el not in [x.upper() for x in pair_els]:
                continue
            for sym in sym_candidates:
                norm_txt = _ghser_norm(p, sym)
                if norm_txt is not None:
                    defs_by_file[p.name] = norm_txt
                    break
        distinct = defaultdict(list)
        for fname, txt in defs_by_file.items():
            distinct[txt].append(fname)
        if len(distinct) > 1:
            majority_files = set(max(distinct.values(), key=len))
            for pair_label in valid_by_pair:
                filtered = []
                for p in valid_by_pair[pair_label]:
                    if p.name in defs_by_file and p.name not in majority_files:
                        audit_log.append({"file": p.name, "pair": pair_label, "status": "excluded", "reason": f"conflicting GHSER{el}"})
                    else:
                        filtered.append(p)
                valid_by_pair[pair_label] = filtered

    return valid_by_pair, audit_log


# ── 2. Equilibrium & Edge-Check Rule v2 ────────────────────────────────────────

def _phase_set(res) -> tuple[str, ...]:
    return tuple(sorted({
        str(n) for n, f in zip(res.Phase.values.reshape(-1), res.NP.values.reshape(-1))
        if n and np.isfinite(f) and f > 1e-4
    }))

def _eq_point(db: Database, comps: list[str], phases: list[str], cond: dict) -> tuple[tuple[str, ...], float] | None:
    try:
        r = equilibrium(db, comps, phases, cond, calc_opts={"pdens": 500})
        g = float(r.GM.values.squeeze())
        if math.isfinite(g):
            return _phase_set(r), g
    except Exception:
        pass
    return None

def solve_with_fallback(db: Database, comps: list[str], cond: dict) -> tuple[tuple[str, ...] | None, float | None, str]:
    phases = sorted(db.phases.keys())
    direct = _eq_point(db, comps, phases, cond)
    if direct is not None:
        return direct[0], direct[1], "direct"
    best = None
    for drop_p in phases:
        sub = _eq_point(db, comps, [p for p in phases if p != drop_p], cond)
        if sub is not None and (best is None or sub[1] < best[1]):
            best = sub
    if best is None:
        return None, None, "failed"
    return best[0], best[1], "fallback"

def compute_binary_references(files: list[Path]) -> dict[str, dict]:
    refs = {}
    for p in files:
        db = Database(str(p))
        els = sorted(e for e in db.elements if e not in ("VA", "/-"))
        a, b = els[0], els[1]
        pts = []
        for T in EDGE_TEMPS:
            for x in EDGE_XS:
                ps, g, st = solve_with_fallback(db, [a, b, "VA"], {v.X(b): x, v.T: T, v.P: 101325, v.N: 1})
                pts.append({"T": T, "x": x, "phases": ps, "G": g, "status": st})
        refs[p.name] = {"edge": (a, b), "points": pts}
    return refs

def ser_function(db: Database, el: str) -> str:
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return name
    raise KeyError(f"No SER function for {el} in merged database")

def g_ser_at(db: Database, ser_names: dict[str, str], T_K: float, x_map: dict[str, float]) -> float:
    total = 0.0
    for el, xi in x_map.items():
        if xi > 1e-12:
            total += xi * float(db.symbols[ser_names[el]].subs({v.T: float(T_K)}))
    return total


# ── 3. Parallel Worker for One Combination ─────────────────────────────────────

_W_REFS = {}
_W_ELS = []
_W_XMAP = {}
_W_TEMPS = []
_W_SUPPRESS = []
_W_TMPDIR = ""

def _init_worker(refs, elements, x_map, temps, suppress, tmpdir):
    global _W_REFS, _W_ELS, _W_XMAP, _W_TEMPS, _W_SUPPRESS, _W_TMPDIR
    _W_REFS, _W_ELS, _W_XMAP, _W_TEMPS, _W_SUPPRESS, _W_TMPDIR = (
        refs, elements, x_map, temps, suppress, tmpdir
    )

def _evaluate_combo(args) -> dict:
    combo_id, paths = args
    t0 = time.time()
    out = {
        "combo_id": combo_id,
        "files": [p.name for p in paths],
        "lineages": [extract_lineage(p.stem) for p in paths],
        "survived": False,
        "failure_stage": None,
        "failure_reason": None,
        "thresholds_kJ": {},
        "assemblages": {},
        "runtime_s": 0.0,
    }
    
    tmp_tdb = Path(_W_TMPDIR) / f"merged_{combo_id}.tdb"
    
    try:
        conflicts = []
        db_m = merge_databases(paths, report=lambda msg: conflicts.append(msg.strip()))
        db_m.to_file(str(tmp_tdb), fmt="tdb", if_exists="overwrite", if_incompatible="ignore")
        db = Database(str(tmp_tdb))
    except Exception as e:
        out["failure_stage"] = "merge"
        out["failure_reason"] = f"{type(e).__name__}: {e}"[:250]
        out["runtime_s"] = round(time.time() - t0, 2)
        return out
    finally:
        tmp_tdb.unlink(missing_ok=True)

    # Edge-Check Rule v2
    for p in paths:
        ref = _W_REFS[p.name]
        a, b = ref["edge"]
        n_mis, n_unv = 0, 0
        for q in ref["points"]:
            ps_m, g_m, _ = solve_with_fallback(
                db, [a, b, "VA"], {v.X(b): q["x"], v.T: q["T"], v.P: 101325, v.N: 1}
            )
            if q["G"] is None or g_m is None:
                n_unv += 1
                continue
            if tuple(q["phases"]) != tuple(ps_m) or abs(g_m - q["G"]) > EDGE_TOL_J:
                n_mis += 1

        if n_mis > 0 or n_unv > MAX_UNVERIFIED:
            out["failure_stage"] = "edge_check"
            out["failure_reason"] = f"{a}-{b} ({p.name}): {n_mis} mismatches, {n_unv} unverified"
            out["runtime_s"] = round(time.time() - t0, 2)
            return out

    # Threshold Calculation
    try:
        ser_names = {el: ser_function(db, el) for el in _W_ELS}
        phases = [ph for ph in sorted(db.phases.keys()) if ph not in _W_SUPPRESS]
        comps = [e for e in _W_ELS + ["VA"] if e in db.elements]
        el1, el2 = _W_ELS[0], _W_ELS[1]

        for T in _W_TEMPS:
            cond = {v.X(el1): _W_XMAP[el1], v.X(el2): _W_XMAP[el2], v.T: float(T), v.P: 101325, v.N: 1}
            ps, g_comp, st = solve_with_fallback(db, comps, cond)
            
            if g_comp is None or not math.isfinite(g_comp):
                raise ValueError(f"Non-finite G_comp at T={T} K (status={st})")
                
            g_ser = g_ser_at(db, ser_names, T, _W_XMAP)
            thr_kj = (g_comp - g_ser) / 1000.0
            
            out["thresholds_kJ"][str(T)] = round(thr_kj, 4)
            out["assemblages"][str(T)] = list(ps) if ps else []
            
    except Exception as e:
        out["failure_stage"] = "threshold"
        out["failure_reason"] = f"{type(e).__name__}: {e}"[:250]
        out["runtime_s"] = round(time.time() - t0, 2)
        return out

    out["survived"] = True
    out["runtime_s"] = round(time.time() - t0, 2)
    return out


# ── 4. Gates & Statistical Summary ─────────────────────────────────────────────

def _eta2(vals: np.ndarray, groups: list[str]) -> float:
    tot = float(((vals - vals.mean()) ** 2).sum())
    if tot == 0.0:
        return 0.0
    by_g = defaultdict(list)
    for g, val in zip(groups, vals):
        by_g[g].append(val)
    ss = sum(len(v_list) * (np.mean(v_list) - vals.mean()) ** 2 for v_list in by_g.values())
    return float(ss / tot)

def evaluate_gates(
    results: list[dict],
    pair_names: list[str],
    min_survival_frac: float = 0.25,
    min_lineages_per_edge: int = 2,
) -> dict:
    n_total = len(results)
    survivors = [r for r in results if r["survived"]]
    n_surv = len(survivors)
    g1_min = max(1, math.ceil(n_total * min_survival_frac))
    g1_pass = n_surv >= g1_min
    lineages_by_edge = {}
    for idx, pair in enumerate(pair_names):
        surv_lins = sorted({r["lineages"][idx] for r in survivors})
        lineages_by_edge[pair] = surv_lins
    g2_pass = all(len(lins) >= min_lineages_per_edge for lins in lineages_by_edge.values())
    return {
        "gate_passed": bool(g1_pass and g2_pass),
        "G1_survival": {"survived": n_surv, "total": n_total, "min_required": g1_min, "pass": g1_pass},
        "G2_lineage_coverage": {
            "surviving_lineages_per_edge": lineages_by_edge,
            "min_required": min_lineages_per_edge,
            "pass": g2_pass,
        },
    }

def run_binary_ensemble(
    elements: list[str],
    fractions: list[float],
    temperatures: list[float] | None = None,
    tdb_dir: Path | None = None,
    suppress_phases: list[str] | None = None,
    workers: int = 1,
    min_survival_frac: float = 0.25,
    min_lineages_per_edge: int = 2,
) -> dict:
    elements = [e.upper() for e in elements]
    if len(elements) != 3 or len(fractions) != 3:
        raise ValueError("Exactly 3 elements and 3 mole fractions are required.")
    total_x = sum(fractions)
    if total_x <= 0:
        raise ValueError("Mole fractions must sum to a positive number.")
    norm_x = [f / total_x for f in fractions]
    x_map = dict(zip(elements, norm_x))
    temps = [float(t) for t in (temperatures or DEFAULT_TEMPS)]
    suppress = list(suppress_phases or [])
    tdb_root = Path(tdb_dir or os.environ.get("SGTE_BINARY_DIR", ""))
    if not tdb_root.is_dir():
        raise FileNotFoundError(f"SGTE_BINARY_DIR invalid or unset: {tdb_root!r}")
    valid_by_pair, audit_log = audit_binary_candidates(elements, tdb_root)
    pair_names = list(valid_by_pair.keys())
    pair_lists = [valid_by_pair[p] for p in pair_names]
    if any(len(lst) == 0 for lst in pair_lists):
        raise RuntimeError(f"At least one binary edge has 0 valid TDB files after audit: {valid_by_pair}")
    unique_files = sorted({p for lst in pair_lists for p in lst}, key=lambda p: p.name)
    refs = compute_binary_references(unique_files)
    
    combos = []
    for prod_paths in itertools.product(*pair_lists):
        cid = "___".join(p.stem for p in prod_paths)
        combos.append((cid, list(prod_paths)))
        
    with tempfile.TemporaryDirectory(prefix="calphad_ens_") as tmpdir:
        if workers <= 1:
            _init_worker(refs, elements, x_map, temps, suppress, tmpdir)
            results = [_evaluate_combo(c) for c in combos]
        else:
            with Pool(
                processes=workers,
                initializer=_init_worker,
                initargs=(refs, elements, x_map, temps, suppress, tmpdir),
            ) as pool:
                results = pool.map(_evaluate_combo, combos)
                
    gate_report = evaluate_gates(
        results,
        pair_names=pair_names,
        min_survival_frac=min_survival_frac,
        min_lineages_per_edge=min_lineages_per_edge,
    )
    
    survivors = [r for r in results if r["survived"]]
    summary_by_T = {}
    for T in temps:
        t_key = str(T)
        vals = np.array([r["thresholds_kJ"][t_key] for r in survivors], dtype=float)
        if len(vals) == 0:
            summary_by_T[t_key] = None
            continue
        eta2_edges = {
            pair_names[idx]: round(_eta2(vals, [r["files"][idx] for r in survivors]), 4)
            for idx in range(3)
        }
        
        asm_counts = defaultdict(int)
        for r in survivors:
            asm_counts["+".join(r["assemblages"][t_key])] += 1
        top_asm = max(asm_counts.items(), key=lambda kv: kv[1])[0]
        
        summary_by_T[t_key] = {
            "n": int(len(vals)),
            "median_kJ": round(float(np.median(vals)), 4),
            "q25_kJ": round(float(np.percentile(vals, 25)), 4),
            "q75_kJ": round(float(np.percentile(vals, 75)), 4),
            "iqr_kJ": round(float(np.percentile(vals, 75) - np.percentile(vals, 25)), 4),
            "p05_kJ": round(float(np.percentile(vals, 5)), 4),
            "p95_kJ": round(float(np.percentile(vals, 95)), 4),
            "min_kJ": round(float(vals.min()), 4),
            "max_kJ": round(float(vals.max()), 4),
            "eta2_by_edge": eta2_edges,
            "dominant_competing_assemblage": top_asm,
        }
        
    spec_payload = json.dumps({
        "elements": elements, 
        "x_map": x_map, 
        "temps": temps, 
        "suppress": suppress
    }, sort_keys=True)
    
    return {
        "system": "-".join(elements),
        "target_composition": {k: round(v, 6) for k, v in x_map.items()},
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pycalphad_version": pycalphad.__version__,
        "spec_sha256": hashlib.sha256(spec_payload.encode()).hexdigest(),
        "gates": gate_report,
        "threshold_distribution": summary_by_T,
        "audit_log": audit_log,
        "combinations": results,
    }

def main():
    ap = argparse.ArgumentParser(description="Generalized Binary-Ensemble CALPHAD Screening Engine")
    ap.add_argument("--elements", nargs=3, required=True, help="Three element symbols, e.g. FE ND B")
    ap.add_argument("--comp", nargs=3, type=float, required=True, help="Three mole fractions (or stoichiometry)")
    ap.add_argument("--temps", nargs="+", type=float, default=DEFAULT_TEMPS)
    ap.add_argument("--suppress", nargs="*", default=[], help="Optional phases to suppress")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--tdb-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = ap.parse_args()
    
    report = run_binary_ensemble(
        elements=args.elements,
        fractions=args.comp,
        temperatures=args.temps,
        tdb_dir=args.tdb_dir,
        suppress_phases=args.suppress,
        workers=args.workers,
    )
    
    g = report["gates"]
    print(f"\n=== Binary Ensemble: {report['system']} ===")
    print(f"G1 Survival : {g['G1_survival']['survived']}/{g['G1_survival']['total']} (pass={g['G1_survival']['pass']})")
    print(f"G2 Lineages : {g['G2_lineage_coverage']['surviving_lineages_per_edge']} (pass={g['G2_lineage_coverage']['pass']})")
    print(f"GATE VERDICT: {'PASS' if g['gate_passed'] else 'FAIL (stop rule triggered)'}\n")
    
    if g["gate_passed"]:
        print(f"{'T (K)':>7} | {'Median':>8} | {'5%-95% Band':>17} | {'IQR':>6} | Competing Assemblage")
        print("-" * 75)
        for T_str, s in report["threshold_distribution"].items():
            if s:
                print(f"{float(T_str):>7.0f} | {s['median_kJ']:>+8.3f} | "
                      f"[{s['p05_kJ']:>+6.2f}, {s['p95_kJ']:>+6.2f}] | "
                      f"{s['iqr_kJ']:>6.3f} | {s['dominant_competing_assemblage']}")
                      
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nSaved full report -> {args.out}")

if __name__ == "__main__":
    main()