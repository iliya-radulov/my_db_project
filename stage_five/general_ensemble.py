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

# Gate defaults. These are Stage-5 engineering defaults, NOT the numbers pre-registered in the
# Stage 4 pilots (Cr-Fe-Ni: >= 60 of 288 = 20.8 %, per-class coverage). Register the values you
# use before running a study; they are part of the spec hash and are written to the report.
DEFAULT_MIN_SURVIVAL_FRAC = 0.25
DEFAULT_MIN_LINEAGES_PER_EDGE = 2

# A threshold G(competing) - G(SER mixture) above this is physically impossible when the
# reference phases are in the database (no equilibrium lies above the mechanical mixture of the
# pure elements). It is FLAGGED per combination, not used as a survival criterion.
BOUND_TOL_KJ = 0.05

# Bump when a rule or a default changes the results; it is part of the spec hash (cache key).
ENGINE_RULES_VERSION = "stage5-engine/edge-rule-v2/fix1-2026-11-23"

_NUM_RE = re.compile(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?")


def compute_spec_sha256(
    elements: list[str],
    fractions: list[float],
    temperatures: list[float] | None = None,
    suppress: list[str] | None = None,
    min_survival_frac: float = DEFAULT_MIN_SURVIVAL_FRAC,
    min_lineages_per_edge: int = DEFAULT_MIN_LINEAGES_PER_EDGE,
) -> str:
    """Hash of everything that defines a screening run (also the cache key of the desktop hook).

    `elements` is in merge-priority order (see audit_binary_candidates): the order is part of the
    spec because the first file wins on conflicting parameters. Mole fractions are normalised and
    rounded to 12 decimals so that float noise cannot change the hash. The TDB collection itself is
    NOT hashed here (the report carries `tdb_collection_sha256` separately).
    """
    els = [e.upper() for e in elements]
    total = float(sum(fractions))
    x_map = {el: round(float(f) / total, 12) for el, f in zip(els, fractions)}
    payload = json.dumps({
        "engine_rules_version": ENGINE_RULES_VERSION,
        "elements": els,
        "x_map": x_map,
        "temps": [float(t) for t in (temperatures or DEFAULT_TEMPS)],
        "suppress": sorted(s.upper() for s in (suppress or [])),
        "min_survival_frac": float(min_survival_frac),
        "min_lineages_per_edge": int(min_lineages_per_edge),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


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

    # MERGE PRIORITY. merge_databases() keeps the FIRST file's definition when two files define the
    # same parameter differently (e.g. G(FCC_A1,ND:VA) in NdB-19Che vs FeNd-16Che), so the survivor
    # set depends on the order of the three edges. The order is therefore explicit and follows the
    # order of `elements`: (e1-e2), (e1-e3), (e2-e3). For `FE ND B` this is Fe-Nd, Fe-B, Nd-B, the
    # order of the Stage 4 Nd-Fe-B reference run (78 of 84 survivors); the previous alphabetical
    # order (B-Fe, B-Nd, Fe-Nd) gave 52 of 84 on the same data.
    priority = [
        "-".join(sorted((elements[i], elements[j]))) for i, j in ((0, 1), (0, 2), (1, 2))
    ]
    missing = [p for p in priority if p not in valid_by_pair]
    if missing:
        raise RuntimeError(f"No binary files found for edge(s) {missing} of system {elements}")
    valid_by_pair = {p: valid_by_pair[p] for p in priority}

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

def solve_with_fallback(
    db: Database, comps: list[str], cond: dict, phases: list[str] | None = None
) -> tuple[tuple[str, ...] | None, float | None, str]:
    """Equilibrium with leave-one-phase-out fallback.

    `phases` restricts the phase set (used to suppress phases); None = all phases of `db`.
    """
    phases = sorted(db.phases.keys()) if phases is None else sorted(phases)
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


def ser_reference_kJ(elements: list[str], files: list[Path], temps: list[float]) -> dict[str, dict[str, float]]:
    """GHSER_i(T) in kJ/mol of every element, read once from the first accepted file that defines it
    (the audit has shown the definitions are identical across the accepted files). Stored in the report so
    that the SISSO side can be put on the SER axis (see dft_sisso_predictor.sisso_reference_offset_kJ)."""
    out: dict[str, dict[str, float]] = {}
    for el in elements:
        for p in files:
            try:
                db = Database(str(p))
                name = ser_function(db, el)
            except Exception:
                continue
            out[el] = {str(float(T)): round(float(db.symbols[name].subs({v.T: float(T)})) / 1000.0, 6) for T in temps}
            break
    return out


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

def _threshold_block(db: Database, elements: list[str], x_map: dict[str, float],
                     temps: list[float], suppress_phases: list[str]) -> dict:
    """Threshold ΔG*(T) = G_comp - Σ x_i GHSER_i (kJ/mol-atom) of one merged database at composition `x_map`
    (suppressed phases really removed). Shared by the ensemble and by the composition-matched re-evaluation."""
    out = {"thresholds_kJ": {}, "assemblages": {}, "bound_violations": []}
    ser_names = {el: ser_function(db, el) for el in elements}
    suppress = {s.upper() for s in suppress_phases}
    out["suppressed_phases"] = sorted(ph for ph in db.phases if ph.upper() in suppress)
    out["suppress_absent"] = sorted(suppress - {ph.upper() for ph in db.phases})
    phases = [ph for ph in sorted(db.phases.keys()) if ph.upper() not in suppress]
    comps = [e for e in elements + ["VA"] if e in db.elements]
    el1, el2 = elements[0], elements[1]
    for T in temps:
        cond = {v.X(el1): x_map[el1], v.X(el2): x_map[el2], v.T: float(T), v.P: 101325, v.N: 1}
        ps, g_comp, st = solve_with_fallback(db, comps, cond, phases=phases)
        if g_comp is None or not math.isfinite(g_comp):
            raise ValueError(f"Non-finite G_comp at T={T} K (status={st})")
        g_ser = g_ser_at(db, ser_names, T, x_map)
        thr_kj = (g_comp - g_ser) / 1000.0
        if thr_kj > BOUND_TOL_KJ and not suppress:
            # Physical bound: with the reference phases present the equilibrium cannot lie above
            # the pure-element mixture. (Not checked when phases are suppressed on purpose.)
            out["bound_violations"].append({"T": float(T), "threshold_kJ": round(thr_kj, 4)})
        out["thresholds_kJ"][str(T)] = round(thr_kj, 4)
        out["assemblages"][str(T)] = list(ps) if ps else []
    return out


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
        "merge_priority": [p.name for p in paths],   # first file wins on conflicting parameters
        "merge_conflicts": [],                        # messages of tdb_merge (what the first file overrode)
        "n_merge_conflicts": 0,
        "suppressed_phases": [],                      # requested suppressions that exist in this merge
        "suppress_absent": [],                        # requested suppressions NOT present in this merge
        "bound_violations": [],                       # thresholds above BOUND_TOL_KJ (flag only)
        "runtime_s": 0.0,
    }

    tmp_tdb = Path(_W_TMPDIR) / f"merged_{combo_id}.tdb"

    try:
        conflicts = []
        db_m = merge_databases(paths, report=lambda msg: conflicts.append(msg.strip()))
        out["merge_conflicts"] = [c for c in conflicts if not c.startswith("merged ")][:20]
        out["n_merge_conflicts"] = sum(1 for c in conflicts if not c.startswith("merged "))
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
        blk = _threshold_block(db, _W_ELS, _W_XMAP, _W_TEMPS, _W_SUPPRESS)
        out.update(blk)
    except Exception as e:
        out["failure_stage"] = "threshold"
        out["failure_reason"] = f"{type(e).__name__}: {e}"[:250]
        out["runtime_s"] = round(time.time() - t0, 2)
        return out

    out["survived"] = True
    out["runtime_s"] = round(time.time() - t0, 2)
    return out


# ── 3b. Composition-matched re-evaluation (prototype step) ─────────────────────

MIN_X_FLOOR = 1e-6      # an element absent from the prototype is kept at this fraction (renormalised)


def _rethreshold_combo(args) -> dict:
    """Merge the files of one SURVIVING combination and evaluate the threshold at the composition in the
    worker globals. No edge check: it does not depend on composition."""
    combo_id, paths = args
    out = {"combo_id": combo_id, "ok": False, "thresholds_kJ": {}, "assemblages": {}, "reason": None}
    tmp_tdb = Path(_W_TMPDIR) / f"matched_{combo_id}.tdb"
    try:
        db_m = merge_databases(paths, report=lambda msg: None)
        db_m.to_file(str(tmp_tdb), fmt="tdb", if_exists="overwrite", if_incompatible="ignore")
        db = Database(str(tmp_tdb))
        blk = _threshold_block(db, _W_ELS, _W_XMAP, _W_TEMPS, _W_SUPPRESS)
        out.update(ok=True, thresholds_kJ=blk["thresholds_kJ"], assemblages=blk["assemblages"])
    except Exception as e:
        out["reason"] = f"{type(e).__name__}: {e}"[:200]
    finally:
        tmp_tdb.unlink(missing_ok=True)
    return out


def summarize_thresholds(vals, assemblages: list[str]) -> dict:
    arr = np.asarray(vals, dtype=float)
    counts = defaultdict(int)
    for a in assemblages:
        counts[a] += 1
    return {
        "n": int(len(arr)),
        "median_kJ": round(float(np.median(arr)), 4),
        "p05_kJ": round(float(np.percentile(arr, 5)), 4),
        "p95_kJ": round(float(np.percentile(arr, 95)), 4),
        "min_kJ": round(float(arr.min()), 4),
        "max_kJ": round(float(arr.max()), 4),
        "dominant_competing_assemblage": max(counts.items(), key=lambda kv: kv[1])[0] if counts else None,
    }


def rethreshold_at_composition(
    ensemble_report: dict,
    fractions: dict[str, float],
    tdb_dir: Path | None = None,
    temperatures: list[float] | None = None,
    suppress_phases: list[str] | None = None,
    workers: int = 1,
) -> dict:
    """Threshold band at ANOTHER composition (a nearest prototype), reusing the surviving combinations
    of `ensemble_report`. Returns {"composition", "n_in", "n_ok", "threshold_distribution": {T: stats}};
    the distribution of a temperature is None if no combination could be evaluated."""
    elements = [e.upper() for e in ensemble_report["elements_priority_order"]]
    raw = {e: max(float(fractions.get(e, 0.0)), MIN_X_FLOOR) for e in elements}
    tot = sum(raw.values())
    x_map = {e: v / tot for e, v in raw.items()}
    temps = [float(t) for t in (temperatures or [float(t) for t in ensemble_report["threshold_distribution"]])]
    suppress = sorted({str(x).upper() for x in (suppress_phases or [])})
    tdb_root = Path(tdb_dir or os.environ.get("SGTE_BINARY_DIR", ""))
    if not tdb_root.is_dir():
        raise FileNotFoundError(f"SGTE_BINARY_DIR invalid or unset: {tdb_root!r}")
    valid_by_pair, _ = audit_binary_candidates(elements, tdb_root)
    by_name = {p.name: p for lst in valid_by_pair.values() for p in lst}
    todo = []
    for r in ensemble_report["combinations"]:
        if r["survived"]:
            todo.append((r["combo_id"], [by_name[n] for n in r["files"]]))
    with tempfile.TemporaryDirectory(prefix="calphad_matched_") as tmpdir:
        if workers <= 1:
            _init_worker({}, elements, x_map, temps, suppress, tmpdir)
            results = [_rethreshold_combo(c) for c in todo]
        else:
            with Pool(processes=workers, initializer=_init_worker,
                      initargs=({}, elements, x_map, temps, suppress, tmpdir)) as pool:
                results = sorted(pool.imap_unordered(_rethreshold_combo, todo), key=lambda r: r["combo_id"])
    ok = [r for r in results if r["ok"]]
    dist = {}
    for T in temps:
        t_key = str(T)
        vals = [r["thresholds_kJ"][t_key] for r in ok if t_key in r["thresholds_kJ"]]
        dist[t_key] = (summarize_thresholds(vals, ["+".join(r["assemblages"][t_key]) for r in ok
                                                   if t_key in r["assemblages"]]) if vals else None)
    return {"composition": {e: round(v, 6) for e, v in x_map.items()}, "n_in": len(todo), "n_ok": len(ok),
            "failures": sorted({r["reason"] for r in results if not r["ok"]})[:5],
            "threshold_distribution": dist}


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
    min_survival_frac: float = DEFAULT_MIN_SURVIVAL_FRAC,
    min_lineages_per_edge: int = DEFAULT_MIN_LINEAGES_PER_EDGE,
    progress_callback=None,
) -> dict:
    """G1: survivors >= ceil(min_survival_frac * total). G2: every edge keeps >= min_lineages_per_edge
    distinct lineages among the survivors. The defaults are Stage-5 engineering defaults (not the
    pre-registered Stage 4 numbers); the values used are returned under "parameters"."""
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
        "parameters": {
            "min_survival_frac": min_survival_frac,
            "min_lineages_per_edge": min_lineages_per_edge,
            "preregistered": False,   # engineering defaults; register your own before a study
        },
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
    min_survival_frac: float = DEFAULT_MIN_SURVIVAL_FRAC,
    min_lineages_per_edge: int = DEFAULT_MIN_LINEAGES_PER_EDGE,
    progress_callback=None,
) -> dict:
    """`elements` are in merge-priority order: the edges are merged (e1-e2), (e1-e3), (e2-e3) and
    the first file wins on conflicting parameters, so the order can change which combinations
    survive. The order is recorded in the report (`edge_priority`) and is part of the spec hash."""
    elements = [e.upper() for e in elements]
    if len(elements) != 3 or len(fractions) != 3:
        raise ValueError("Exactly 3 elements and 3 mole fractions are required.")
    total_x = sum(fractions)
    if total_x <= 0:
        raise ValueError("Mole fractions must sum to a positive number.")
    norm_x = [f / total_x for f in fractions]
    x_map = dict(zip(elements, norm_x))
    temps = [float(t) for t in (temperatures or DEFAULT_TEMPS)]
    suppress = sorted({str(x).upper() for x in (suppress_phases or [])})
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
        
    total_combos = len(combos)
    if progress_callback:
        progress_callback(0, total_combos)
    with tempfile.TemporaryDirectory(prefix="calphad_ens_") as tmpdir:
        if workers <= 1:
            _init_worker(refs, elements, x_map, temps, suppress, tmpdir)
            results = []
            for idx, c in enumerate(combos, 1):
                results.append(_evaluate_combo(c))
                if progress_callback:
                    progress_callback(idx, total_combos)
        else:
            with Pool(
                processes=workers,
                initializer=_init_worker,
                initargs=(refs, elements, x_map, temps, suppress, tmpdir),
            ) as pool:
                results = []
                for idx, res in enumerate(pool.imap_unordered(_evaluate_combo, combos), 1):
                    results.append(res)
                    if progress_callback:
                        progress_callback(idx, total_combos)
            results.sort(key=lambda r: r["combo_id"])
                
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
        
    spec_sha = compute_spec_sha256(
        elements, [x_map[e] for e in elements], temps, suppress, min_survival_frac, min_lineages_per_edge
    )
    fails = [r for r in results if not r["survived"]]
    failure_summary = {
        "by_stage": dict(defaultdict(int, {k: sum(1 for r in fails if r["failure_stage"] == k)
                                           for k in {r["failure_stage"] for r in fails}})),
        "by_file": {
            p.name: {"failed": sum(1 for r in fails if p.name in r["files"]),
                     "total": sum(1 for r in results if p.name in r["files"])}
            for p in unique_files
        },
    }
    collection = hashlib.sha256()
    for p in unique_files:
        collection.update(p.name.encode() + b"\0" + hashlib.sha256(p.read_bytes()).digest())

    return {
        "system": "-".join(sorted(elements)),          # canonical (alphabetical) name
        "edge_priority": pair_names,                    # merge order: first file wins on conflicts
        "elements_priority_order": elements,
        "target_composition": {k: round(v, 6) for k, v in x_map.items()},
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pycalphad_version": pycalphad.__version__,
        "engine_rules_version": ENGINE_RULES_VERSION,
        "spec_sha256": spec_sha,
        "tdb_collection_sha256": collection.hexdigest(),   # accepted binary files (not part of spec_sha256)
        "gates": gate_report,
        "failure_summary": failure_summary,
        "ser_reference_kJ": ser_reference_kJ(elements, unique_files, temps),
        "n_bound_violations": sum(1 for r in results if r["bound_violations"]),
        "threshold_distribution": summary_by_T,
        "audit_log": audit_log,
        "combinations": results,
    }

def main():
    ap = argparse.ArgumentParser(description="Generalized Binary-Ensemble CALPHAD Screening Engine")
    ap.add_argument("--elements", nargs=3, required=True,
                    help="Three element symbols in MERGE-PRIORITY order, e.g. FE ND B: the edges are merged "
                         "Fe-Nd, Fe-B, Nd-B and the first file wins on conflicting parameters")
    ap.add_argument("--comp", nargs=3, type=float, required=True, help="Three mole fractions (or stoichiometry)")
    ap.add_argument("--temps", nargs="+", type=float, default=DEFAULT_TEMPS)
    ap.add_argument("--suppress", nargs="*", default=[], help="Optional phases to suppress")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--tdb-dir", type=Path, default=None)
    ap.add_argument("--min-survival-frac", type=float, default=DEFAULT_MIN_SURVIVAL_FRAC,
                    help="G1: required fraction of surviving combinations (engineering default, not pre-registered)")
    ap.add_argument("--min-lineages", type=int, default=DEFAULT_MIN_LINEAGES_PER_EDGE,
                    help="G2: required surviving lineages per edge (engineering default, not pre-registered)")
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = ap.parse_args()
    
    report = run_binary_ensemble(
        elements=args.elements,
        fractions=args.comp,
        temperatures=args.temps,
        tdb_dir=args.tdb_dir,
        suppress_phases=args.suppress,
        workers=args.workers,
        min_survival_frac=args.min_survival_frac,
        min_lineages_per_edge=args.min_lineages,
    )
    
    g = report["gates"]
    print(f"\n=== Binary Ensemble: {report['system']} ===")
    print(f"Merge priority (first file wins): {' > '.join(report['edge_priority'])}")
    fs = report["failure_summary"]
    if fs["by_stage"]:
        print(f"Non-survivors by stage: {fs['by_stage']}")
        worst = sorted(((v["failed"], k, v["total"]) for k, v in fs["by_file"].items() if v["failed"]), reverse=True)[:5]
        print("Files in most failed combinations: " + ", ".join(f"{k} ({n}/{t})" for n, k, t in worst))
    if report["n_bound_violations"]:
        print(f"WARNING: {report['n_bound_violations']} combination(s) have a threshold above the physical bound")
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