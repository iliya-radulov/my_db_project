#!/usr/bin/env python3
"""
demo/calphad-3d-explorer/tools/check_dataset.py

Step 3 checks of a dataset written by export_ternary.py. Two kinds, reported separately:

A. Does the dataset reproduce the model in the TDB?  (pipeline checks, pass/fail)
   A1  the TDB file still has the SHA-256 recorded in the dataset;
   A2  corners: liquidus and solidus of each pure element in the dataset agree with a separate
       single-element calculation from the same TDB;
   A3  binary edges: every edge point of the dataset agrees with a separate two-element
       calculation from the same TDB (independent temperature scan: coarse, then 1 K steps
       around each crossing), for liquidus, solidus and primary phase.
   Tolerance: the dataset's temperature step + 2 K (its liquidus/solidus are interpolated
   between grid temperatures). Every point that differs is listed. (Datasets written before the
   export computed edges as binaries carry 1e-4 of the third element on the edges; in La-Fe-Si
   that trace precipitates TAU1/TAU2 and moves the Fe-Si liquidus by up to ~250 K.)

B. Does the model agree with reference data?  (comparison, reported, no pass/fail of the code)
   B1  pure-element melting points of the model against the SGTE unary values (table below);
   B2  optional reference points from a CSV you fill with sourced values (see
       reference_points_TEMPLATE.csv). Every point is computed directly with pycalphad at the
       given composition (not read from the dataset grid, which rarely contains it):
         t_liquidus_K, t_solidus_K   at a composition;
         phases_at_T                 phase set at a composition and T (phases below a minimum
                                     fraction, default 0.01, are listed but not counted);
         solubility_limit            edge of the single-phase region of a phase along one
                                     element, the others fixed (e.g. TAU1, x(LA) = 1/14, Si-poor
                                     edge); reports the model edge and the signed difference;
         t_upper_stability_K         highest temperature at which a phase is present.
       Each row carries its own tolerance, source and an optional class (hard / soft).
       B2 can be run without a dataset (--elements instead of --dataset), e.g. for TDBs that
       have no dataset yet.

Usage (repository root):
    python demo/calphad-3d-explorer/tools/check_dataset.py \
        --dataset demo/calphad-3d-explorer/datasets/lafesi_paperbuild.json \
        --tdb stage_four/calphad_lafesi/refit_tau12/results_addD/paperbuild_FeLa-23Su_LaSi-10Zho_FeSi-12Ohn.tdb \
        [--refs my_reference_points.csv] --workers 4 --out demo/calphad-3d-explorer/datasets/lafesi_paperbuild_check

    # reference points only, no dataset:
    python demo/calphad-3d-explorer/tools/check_dataset.py --tdb <file.tdb> --elements FE LA SI \
        --refs my_reference_points.csv --tmin 800 --tmax 2600 --workers 4 --out <report>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_ternary import (LIQ_FULL, LIQ_NONE, crossing_down, crossing_up,  # noqa: E402
                            non_minimal_points, sha256_file)

# Melting points of the SGTE unary database (Dinsdale, Calphad 15 (1991) 317), K.
SGTE_MELTING_K = {
    "AL": 933.47, "CO": 1768.0, "CU": 1357.77, "FE": 1811.0, "LA": 1193.0,
    "MG": 923.0, "NI": 1728.0, "SI": 1687.0, "TI": 1941.0,
}
COARSE_STEP = 20.0
FINE_STEP = 1.0
EDGE_EPS = 1e-4

# B2 reference points (defaults; written into the report)
MIN_FRACTION = 0.01      # phases_at_T: phases below this fraction are listed, not counted
SINGLE_PHASE = 0.999     # solubility_limit: fraction counted as single phase
PRESENT = 0.001          # t_upper_stability_K: fraction counted as present
X_STEP = 0.002           # solubility_limit: coarse composition step (edge then refined to X_STEP/20)
UPPER_COARSE_K = 10.0    # t_upper_stability_K: coarse step, then 1 K


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def edge_nodes(nodes, n):
    """Dataset nodes on the three binary edges, without corners.
    Dataset convention: i = steps of B, j = steps of C, A = the rest."""
    edges = {"A-B": [], "A-C": [], "B-C": []}
    for nd in nodes:
        i, j = nd["i"], nd["j"]
        corner = (i, j) in ((0, 0), (n, 0), (0, n))
        if corner:
            continue
        if j == 0:
            edges["A-B"].append(nd)
        elif i == 0:
            edges["A-C"].append(nd)
        elif i + j == n:
            edges["B-C"].append(nd)
    return edges


def corner_nodes(nodes, n):
    by = {(nd["i"], nd["j"]): nd for nd in nodes}
    return {"A": by[(0, 0)], "B": by[(n, 0)], "C": by[(0, n)]}


def within(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def parse_number(text: str) -> float:
    """'0.25' or '1/14'."""
    text = text.strip()
    if "/" in text:
        a, b = text.split("/")
        return float(a) / float(b)
    return float(text)


def parse_fixed(text: str) -> dict[str, float]:
    """'LA:1/14' -> {'LA': 0.0714...} (not normalised)."""
    out = {}
    for part in text.split(";"):
        if part.strip():
            el, val = part.split(":")
            out[el.strip().upper()] = parse_number(val)
    return out


def parse_composition(text: str) -> dict[str, float]:
    """'FE:0.857;LA:1/14;SI:0.0714' -> {'FE': .857, ...} (normalised; ';' because the CSV uses ',')."""
    out = parse_fixed(text)
    s = sum(out.values())
    return {k: v / s for k, v in out.items()}


def single_phase_regions(xs, fracs, level=SINGLE_PHASE):
    """Contiguous index ranges [(k0, k1), ...] where fracs >= level. A gap of one point between
    two regions (one failed or deviating equilibrium) is bridged; returns (regions, bridged)."""
    inside = [f is not None and f >= level for f in fracs]
    regions = []
    k = 0
    while k < len(xs):
        if inside[k]:
            k0 = k
            while k + 1 < len(xs) and inside[k + 1]:
                k += 1
            regions.append([k0, k])
        k += 1
    bridged = 0
    merged = []
    for r in regions:
        if merged and r[0] - merged[-1][1] == 2:
            merged[-1][1] = r[1]
            bridged += 1
        else:
            merged.append(r)
    return [tuple(r) for r in merged], bridged


def pick_region(xs, regions, ref):
    """The region containing ref, else the one with the nearest edge."""
    for r in regions:
        if xs[r[0]] <= ref <= xs[r[1]]:
            return r
    return min(regions, key=lambda r: min(abs(xs[r[0]] - ref), abs(xs[r[1]] - ref)))


def phase_set(state: dict | None, min_fraction: float):
    """(counted phases, minor phases) of an equilibrium state."""
    if not state:
        return None, None
    major = sorted(p for p, f in state.items() if f >= min_fraction)
    minor = sorted(p for p, f in state.items() if f < min_fraction)
    return major, minor


# ---------------------------------------------------------------------------
# pycalphad: independent liquidus / solidus of a binary or unary composition
# ---------------------------------------------------------------------------
def _scan(db, comps, phases, conds_x, temps, liquids):
    from pycalphad import equilibrium, variables as v
    conds = {v.T: list(temps), v.P: 101325, v.N: 1}
    for el, x in conds_x.items():
        conds[v.X(el)] = x
    eq = equilibrium(db, comps + ["VA"], phases, conds)
    ph = np.asarray(eq.Phase.values).reshape(len(temps), -1)
    npf = np.asarray(eq.NP.values).reshape(len(temps), -1)
    gm = np.asarray(eq.GM.values).reshape(len(temps))
    fl, states = [], []
    gms = [float(g) if np.isfinite(g) else None for g in gm]
    bad = set(non_minimal_points(list(temps), gms))   # same filter as the export
    for k in range(len(temps)):
        if k in bad:
            fl.append(None)
            states.append(None)
            continue
        if not np.isfinite(gm[k]):
            fl.append(None)
            states.append(None)
            continue
        st: dict[str, float] = {}
        for p, f in zip(ph[k], npf[k]):
            if str(p) and np.isfinite(f) and f > 0:
                st[str(p)] = st.get(str(p), 0.0) + float(f)
        states.append(st)
        fl.append(sum(f for p, f in st.items() if p in liquids))
    return fl, states


def independent_point(args):
    """Liquidus, solidus and primary phase of one composition, two-stage scan."""
    tdb, comps, conds_x, tmin, tmax = args
    warnings.filterwarnings("ignore")
    from pycalphad import Database
    db = Database(tdb)
    phases = sorted(db.phases)
    liquids = {p for p in phases if "LIQ" in p.upper()}
    coarse = list(np.arange(tmin, tmax + COARSE_STEP / 2, COARSE_STEP))
    fl, _ = _scan(db, comps, phases, conds_x, coarse, liquids)
    t_liq_c = crossing_up(coarse, fl, LIQ_FULL)
    t_sol_c = crossing_down(coarse, fl, LIQ_NONE)

    def refine(t_c, finder, level):
        if t_c is None:
            return None, None
        lo, hi = max(tmin, t_c - 2 * COARSE_STEP), min(tmax, t_c + 2 * COARSE_STEP)
        fine = list(np.arange(lo, hi + FINE_STEP / 2, FINE_STEP))
        f2, st2 = _scan(db, comps, phases, conds_x, fine, liquids)
        return finder(fine, f2, level), (fine, st2)

    t_liq, liq_scan = refine(t_liq_c, crossing_up, LIQ_FULL)
    t_sol, _ = refine(t_sol_c, crossing_down, LIQ_NONE)
    primary = None
    if t_liq is not None and liq_scan:
        fine, st2 = liq_scan
        below = [k for k, t in enumerate(fine) if t < t_liq and st2[k]]
        if below:
            solids = {p: f for p, f in st2[below[-1]].items() if p not in liquids}
            primary = max(solids, key=solids.get) if solids else None
    return {"t_liquidus_K": t_liq, "t_solidus_K": t_sol, "primary_phase": primary}


# ---------------------------------------------------------------------------
# pycalphad: reference points evaluated directly at the given composition
# ---------------------------------------------------------------------------
_DB_CACHE: dict = {}


def _db(tdb):
    from pycalphad import Database
    if tdb not in _DB_CACHE:
        _DB_CACHE[tdb] = Database(tdb)
    return _DB_CACHE[tdb]


def equilibria_along(tdb, comps, fixed, axis, values):
    """Equilibria along one axis ('T' or an element), all other conditions fixed
    ({'T': ..., 'LA': x, ...}). Results that are not the minimum (same chord rule as the export,
    applied along the axis) and failed points are None. Returns (states, n_failed, n_rejected)."""
    from pycalphad import equilibrium, variables as v
    db = _db(tdb)
    phases = sorted(db.phases)
    conds = {v.P: 101325, v.N: 1}
    for k, val in fixed.items():
        conds[v.T if k == "T" else v.X(k)] = val
    conds[v.T if axis == "T" else v.X(axis)] = [float(x) for x in values]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eq = equilibrium(db, list(comps) + ["VA"], phases, conds)
    n = len(values)
    ph = np.asarray(eq.Phase.values).reshape(n, -1)
    npf = np.asarray(eq.NP.values).reshape(n, -1)
    gm = np.asarray(eq.GM.values).reshape(n)
    gms = [float(g) if np.isfinite(g) else None for g in gm]
    bad = set(non_minimal_points([float(x) for x in values], gms))
    states, failed = [], 0
    for k in range(n):
        if gms[k] is None:
            failed += 1
            states.append(None)
            continue
        if k in bad:
            states.append(None)
            continue
        st: dict[str, float] = {}
        for p, f in zip(ph[k], npf[k]):
            if str(p) and np.isfinite(f) and f > 0:
                st[str(p)] = st.get(str(p), 0.0) + float(f)
        states.append(st)
    return states, failed, len(bad)


def _comps_and_fixed(comp: dict[str, float]):
    """Elements present, and the X conditions (all but the first)."""
    comps = sorted(e for e, x in comp.items() if x > 0)
    return comps, {e: comp[e] for e in comps[1:]}


def eval_phases_at_T(tdb, comp, T, min_fraction):
    comps, fixed = _comps_and_fixed(comp)
    temps = [T - 10.0, T, T + 10.0]        # neighbours only for the non-minimum check
    states, failed, rejected = equilibria_along(tdb, comps, fixed, "T", temps)
    st = states[1]
    major, minor = phase_set(st, min_fraction)
    return {"model": None if major is None else "+".join(major),
            "minor_phases": minor, "fractions": None if st is None else {p: round(f, 4) for p, f in st.items()},
            "failed": st is None}


def eval_upper_stability(tdb, comp, phase, tmin, tmax):
    comps, fixed = _comps_and_fixed(comp)
    coarse = list(np.arange(tmin, tmax + UPPER_COARSE_K / 2, UPPER_COARSE_K))
    states, failed, rejected = equilibria_along(tdb, comps, fixed, "T", coarse)
    present = [k for k, st in enumerate(states) if st and st.get(phase, 0) >= PRESENT]
    info = {"failed_points": failed, "rejected_points": rejected}
    if not present:
        return {"model": None, "detail": f"{phase} not present between {tmin:.0f} and {tmax:.0f} K", **info}
    k = present[-1]
    if k == len(coarse) - 1:
        return {"model": None, "detail": f"{phase} still present at {tmax:.0f} K (above range)", **info}
    fine = list(np.arange(coarse[k], coarse[k + 1] + 0.5, 1.0))
    st2, f2, r2 = equilibria_along(tdb, comps, fixed, "T", fine)
    pres2 = [fine[j] for j, st in enumerate(st2) if st and st.get(phase, 0) >= PRESENT]
    t_up = max(pres2) if pres2 else coarse[k]
    above = st2[-1] if st2[-1] else states[k + 1]
    return {"model": float(t_up),
            "detail": "above: " + (" + ".join(f"{p} {f:.2f}" for p, f in sorted(above.items())) if above else "—"),
            "failed_points": failed + f2, "rejected_points": rejected + r2}


def solubility_scan(tdb, fixed, vary, balance, T):
    """Coarse scan of x(vary) at fixed T and fixed elements; the balance element takes the rest."""
    fixed = {e: x for e, x in fixed.items() if x > 0}
    comps = sorted([balance, vary, *fixed])
    top = 1.0 - sum(fixed.values())
    xs = [round(x, 6) for x in np.arange(X_STEP, top - X_STEP / 2, X_STEP)]
    states, failed, rejected = equilibria_along(tdb, comps, {"T": T, **fixed}, vary, xs)
    return {"comps": comps, "fixed": fixed, "xs": xs, "states": states, "failed": failed, "rejected": rejected}


def eval_solubility_limit(tdb, scan, vary, T, phase, side, ref):
    xs, states = scan["xs"], scan["states"]
    fr = [None if st is None else st.get(phase, 0.0) for st in states]
    regions, bridged = single_phase_regions(xs, fr)
    info = {"failed_points": scan["failed"], "rejected_points": scan["rejected"], "bridged_gaps": bridged,
            "single_phase_regions": [[xs[a], xs[b]] for a, b in regions]}
    if not regions:
        return {"model": None, "detail": f"{phase} never single phase (max fraction "
                f"{max((f for f in fr if f is not None), default=0):.3f})", **info}
    r = pick_region(xs, regions, ref)
    k = r[0] if side == "low" else r[1]
    nxt = k - 1 if side == "low" else k + 1
    if nxt < 0 or nxt >= len(xs):
        return {"model": float(xs[k]), "detail": "edge at the end of the scan", **info}
    lo, hi = sorted((xs[nxt], xs[k]))
    fine = [round(x, 7) for x in np.linspace(lo, hi, 21)]
    st2, f2, r2 = equilibria_along(tdb, scan["comps"], {"T": T, **scan["fixed"]}, vary, fine)
    inside = [x for x, st in zip(fine, st2) if st and st.get(phase, 0) >= SINGLE_PHASE]
    edge = (min(inside) if side == "low" else max(inside)) if inside else xs[k]
    info["failed_points"] += f2
    info["rejected_points"] += r2
    return {"model": round(float(edge), 5),
            "detail": f"single-phase {phase} {xs[r[0]]:.3f}–{xs[r[1]]:.3f} (coarse)", **info}


def _ref_job(args):
    """One group of reference rows (rows sharing a solubility scan are evaluated together)."""
    tdb, elements, rows, tmin, tmax, min_fraction = args
    warnings.filterwarnings("ignore")
    out = []
    scan = None
    for r in rows:
        q = r["quantity"]
        e = {}
        try:
            if q in ("t_liquidus_K", "t_solidus_K"):
                comp = parse_composition(r["composition"])
                comps, conds_x = _comps_and_fixed(comp)
                res = independent_point((tdb, comps, conds_x, tmin, tmax))
                e["model"] = res[q]
                if res[q] is None:
                    e["detail"] = "outside the temperature range"
            elif q == "phases_at_T":
                e = eval_phases_at_T(tdb, parse_composition(r["composition"]), parse_number(r["T_K"]), min_fraction)
            elif q == "t_upper_stability_K":
                e = eval_upper_stability(tdb, parse_composition(r["composition"]), r["phase"], tmin, tmax)
            elif q == "solubility_limit":
                T = parse_number(r["T_K"])
                fixed = parse_fixed(r["composition"])
                vary = r["vary"]
                balance = [x for x in elements if x != vary and x not in fixed]
                if len(balance) != 1:
                    raise ValueError("composition must fix all elements except 'vary' and one balance element")
                if scan is None:
                    scan = solubility_scan(tdb, fixed, vary, balance[0], T)
                e = eval_solubility_limit(tdb, scan, vary, T, r["phase"], r["side"], parse_number(r["value"]))
                e["balance"] = balance[0]
            else:
                e = {"error": f"unknown quantity {q!r}"}
        except Exception as exc:  # report the row, keep the others
            e = {"error": f"{type(exc).__name__}: {exc}"}
        out.append((r["_index"], e))
    return out


def read_reference_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(row for row in f if row.strip() and not row.lstrip().startswith("#")))
    clean = []
    for k, r in enumerate(rows):
        c = {key.strip(): (val or "").strip() for key, val in r.items() if key}
        c["quantity"] = c.get("quantity", "")
        c["phase"] = c.get("phase", "").upper()
        c["vary"] = c.get("vary", "").upper()
        c["side"] = c.get("side", "").lower()
        c["class"] = c.get("class", "").lower() or "unclassified"
        c["_index"] = k
        clean.append(c)
    return clean


def compare(r: dict, e: dict) -> dict:
    """Adds reference, difference and within_tolerance to an evaluated row."""
    q = r["quantity"]
    entry = {"id": r["id"], "class": r["class"], "quantity": q, "composition": r["composition"],
             "T_K": r.get("T_K") or None, "phase": r["phase"] or None, "vary": r["vary"] or None,
             "side": r["side"] or None, "reference": r.get("value"), "tolerance": r.get("tolerance") or None,
             "source": r.get("source", ""), "note": r.get("note", ""), **e}
    if "error" in e:
        entry["within_tolerance"] = None
        return entry
    model = e.get("model")
    if q == "phases_at_T":
        ref = "+".join(sorted(p.strip().upper() for p in r["value"].split("+")))
        entry["reference"] = ref
        entry["within_tolerance"] = model == ref
    else:
        ref = parse_number(r["value"])
        tol = parse_number(r["tolerance"])
        entry["difference"] = None if model is None else round(model - ref, 5 if q == "solubility_limit" else 1)
        entry["within_tolerance"] = model is not None and abs(model - ref) <= tol
    return entry


def run_reference_points(tdb: Path, elements, refs: Path, tmin, tmax, workers=1,
                         min_fraction=MIN_FRACTION) -> dict:
    rows = read_reference_rows(refs)
    elements = [e.upper() for e in elements]
    groups: dict = {}
    for r in rows:
        if r["quantity"] == "solubility_limit":
            key = ("sol", r["composition"], r["T_K"], r["vary"])
        else:
            key = ("row", r["_index"])
        groups.setdefault(key, []).append(r)
    jobs = [(str(tdb), elements, g, float(tmin), float(tmax), min_fraction) for g in groups.values()]
    if workers > 1 and len(jobs) > 1:
        with Pool(min(workers, len(jobs))) as pool:
            results = pool.map(_ref_job, jobs)
    else:
        results = [_ref_job(j) for j in jobs]
    evaluated = dict(item for res in results for item in res)
    entries = [compare(r, evaluated[r["_index"]]) for r in rows]
    summary = {}
    for e in entries:
        s = summary.setdefault(e["class"], {"rows": 0, "within": 0, "errors": 0})
        s["rows"] += 1
        s["within"] += bool(e.get("within_tolerance"))
        s["errors"] += "error" in e
    return {"tdb_file": Path(tdb).name, "tdb_sha256": sha256_file(Path(tdb)), "elements": elements,
            "settings": {"min_fraction_phases_at_T": min_fraction, "single_phase_fraction": SINGLE_PHASE,
                         "present_fraction": PRESENT, "composition_step": X_STEP,
                         "upper_stability_scan_K": [float(tmin), float(tmax), UPPER_COARSE_K, 1.0]},
            "points": entries, "summary": summary}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def run_checks(ds: dict, tdb: Path, refs: Path | None, workers: int,
               min_fraction: float = MIN_FRACTION) -> dict:
    elements = ds["system"]["elements"]
    A, B, C = elements
    n = ds["grid"]["subdivisions"]
    temps = ds["grid"]["temperatures_K"]
    dt = ds["grid"]["temperature_step_K"]
    tol = dt + 2.0
    tmin, tmax = temps[0], temps[-1]
    out = {"elements": elements, "tolerance_K": tol, "dataset_step_K": dt}

    # A1 hash
    sha = sha256_file(tdb)
    out["A1_tdb_hash"] = {"pass": sha == ds["system"]["source"]["tdb_sha256"],
                          "dataset": ds["system"]["source"]["tdb_sha256"], "file": sha}

    # A2 + A3: build all independent jobs
    jobs, keys = [], []
    corners = corner_nodes(ds["nodes"], n)
    for name, el in zip("ABC", elements):
        jobs.append((str(tdb), [el], {}, tmin, tmax))
        keys.append(("corner", name, el, corners[name]))
    edge_pairs = {"A-B": (A, B, lambda nd: nd["i"] / n),
                  "A-C": (A, C, lambda nd: nd["j"] / n),
                  "B-C": (B, C, lambda nd: nd["j"] / n)}
    for edge, nds in edge_nodes(ds["nodes"], n).items():
        e1, e2, x2 = edge_pairs[edge]
        for nd in nds:
            x = min(1 - EDGE_EPS, max(EDGE_EPS, x2(nd)))
            jobs.append((str(tdb), [e1, e2], {e2: x}, tmin, tmax))
            keys.append(("edge", edge, f"{e1}-{e2} x({e2})={x:.4f}", nd))
    if workers > 1:
        with Pool(workers) as pool:
            results = pool.map(independent_point, jobs)
    else:
        results = [independent_point(j) for j in jobs]

    corner_rows, edge_rows = [], []
    for (kind, group, label, nd), res in zip(keys, results):
        row = {"group": group, "point": label,
               "dataset": {k: nd[k] for k in ("t_liquidus_K", "t_solidus_K", "primary_phase")},
               "independent": res}
        row["liquidus_ok"] = within(nd["t_liquidus_K"], res["t_liquidus_K"], tol)
        row["solidus_ok"] = within(nd["t_solidus_K"], res["t_solidus_K"], tol)
        row["primary_ok"] = nd["primary_phase"] == res["primary_phase"]
        (corner_rows if kind == "corner" else edge_rows).append(row)
    out["A2_corners"] = corner_rows
    out["A3_edges"] = edge_rows
    out["A_summary"] = {
        "corners_liquidus_ok": sum(r["liquidus_ok"] for r in corner_rows), "corners": len(corner_rows),
        "edges_liquidus_ok": sum(r["liquidus_ok"] for r in edge_rows),
        "edges_solidus_ok": sum(r["solidus_ok"] for r in edge_rows),
        "edges_primary_ok": sum(r["primary_ok"] for r in edge_rows), "edge_points": len(edge_rows),
    }

    # B1 SGTE melting points (model vs reference)
    out["B1_melting_points"] = [
        {"element": el, "model_K": r["independent"]["t_liquidus_K"], "sgte_K": SGTE_MELTING_K.get(el)}
        for el, r in zip(elements, corner_rows)
    ]

    # B2 reference points (computed directly from the TDB, not read from the grid)
    out["B2"] = run_reference_points(tdb, elements, refs, tmin, tmax, workers, min_fraction) if refs else None

    s = out["A_summary"]
    out["A_pass"] = bool(out["A1_tdb_hash"]["pass"] and s["corners_liquidus_ok"] == s["corners"]
                         and s["edges_liquidus_ok"] == s["edge_points"])
    return out


def fmt(t):
    return "—" if t is None else f"{t:.0f}"


def markdown(res: dict, ds: dict) -> str:
    s = res["A_summary"]
    L = [f"# Dataset check: {ds['system']['label']}", "",
         f"TDB `{ds['system']['source']['tdb_file']}`; dataset step {res['dataset_step_K']} K; "
         f"tolerance {res['tolerance_K']} K.", "",
         "## A. Does the dataset reproduce the model? (pipeline)", "",
         f"- A1 TDB hash matches the dataset: **{'yes' if res['A1_tdb_hash']['pass'] else 'NO'}**",
         f"- A2 corners, liquidus within tolerance: **{s['corners_liquidus_ok']}/{s['corners']}**",
         f"- A3 edges: liquidus **{s['edges_liquidus_ok']}/{s['edge_points']}**, "
         f"solidus {s['edges_solidus_ok']}/{s['edge_points']}, "
         f"primary phase {s['edges_primary_ok']}/{s['edge_points']}",
         f"- Overall (A1, A2, A3 liquidus): **{'PASS' if res['A_pass'] else 'FAIL'}**", ""]
    bad = [r for r in res["A2_corners"] + res["A3_edges"]
           if not (r["liquidus_ok"] and r["solidus_ok"] and r["primary_ok"])]
    if bad:
        L += ["Points that differ (dataset vs independent binary/unary calculation):", "",
              "| Point | T_liq dataset / indep. | T_sol dataset / indep. | Primary dataset / indep. |",
              "|---|---|---|---|"]
        for r in bad:
            d, i = r["dataset"], r["independent"]
            L.append(f"| {r['point']} | {fmt(d['t_liquidus_K'])} / {fmt(i['t_liquidus_K'])}"
                     f"{'' if r['liquidus_ok'] else ' ✗'} | {fmt(d['t_solidus_K'])} / {fmt(i['t_solidus_K'])}"
                     f"{'' if r['solidus_ok'] else ' ✗'} | {d['primary_phase']} / {i['primary_phase']}"
                     f"{'' if r['primary_ok'] else ' ✗'} |")
        L.append("")
    L += ["## B. Does the model agree with reference data? (comparison, not a test of the code)", "",
          "B1 melting points of the pure elements:", "", "| Element | Model (K) | SGTE unary (K) | Difference (K) |",
          "|---|---|---|---|"]
    for m in res["B1_melting_points"]:
        diff = "—" if m["model_K"] is None or m["sgte_K"] is None else f"{m['model_K'] - m['sgte_K']:+.1f}"
        L.append(f"| {m['element']} | {fmt(m['model_K'])} | {m['sgte_K'] if m['sgte_K'] else '—'} | {diff} |")
    L.append("")
    if res.get("B2"):
        L += markdown_b2(res["B2"])
    else:
        L.append("B2 reference points: none given (see reference_points_TEMPLATE.csv).")
    return "\n".join(L) + "\n"


def _fmt_value(q, v):
    if v is None:
        return "—"
    if q == "solubility_limit":
        return f"{v:.4f}"
    if q in ("t_liquidus_K", "t_solidus_K", "t_upper_stability_K"):
        return f"{v:.0f}"
    return str(v)


def markdown_b2(b2: dict) -> list[str]:
    st = b2["settings"]
    L = [f"B2 reference points, computed directly with pycalphad from `{b2['tdb_file']}` "
         f"(sha256 `{b2['tdb_sha256'][:16]}…`) at the given compositions. Settings (defaults unless changed): "
         f"phases_at_T counts phases ≥ {st['min_fraction_phases_at_T']} (smaller ones listed in brackets); "
         f"single phase = fraction ≥ {st['single_phase_fraction']}; present = fraction ≥ {st['present_fraction']}; "
         f"composition step {st['composition_step']} (edge refined to {st['composition_step'] / 20:g}); "
         f"upper stability searched {st['upper_stability_scan_K'][0]:.0f}–{st['upper_stability_scan_K'][1]:.0f} K.", ""]
    order = ["hard", "soft"] + sorted(c for c in b2["summary"] if c not in ("hard", "soft"))
    for cls in order:
        rows = [p for p in b2["points"] if p["class"] == cls]
        if not rows:
            continue
        s = b2["summary"][cls]
        L += [f"**{cls.capitalize()}** ({s['within']}/{s['rows']} within tolerance"
              + (f", {s['errors']} errors" if s["errors"] else "") + "):", "",
              "| Id | Quantity | Phase | Composition | T (K) | Reference | Model | Difference | Tolerance | Within | Detail | Source |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in rows:
            q = p["quantity"]
            if "error" in p:
                model, within, detail = "—", "error", p["error"]
            else:
                model = _fmt_value(q, p.get("model"))
                within = "yes" if p.get("within_tolerance") else "no"
                detail = p.get("detail", "")
                if q == "phases_at_T":
                    fr = p.get("fractions") or {}
                    detail = " + ".join(f"{k} {v:.3f}" for k, v in sorted(fr.items())) or "not converged"
                    if p.get("minor_phases"):
                        model += " (" + "+".join(p["minor_phases"]) + ")"
                if q == "solubility_limit":
                    detail = f"{p.get('side')} edge in x({p.get('vary')}), balance {p.get('balance')}; " + detail
                    if p.get("bridged_gaps"):
                        detail += f"; {p['bridged_gaps']} one-point gap(s) bridged"
                if p.get("failed_points") or p.get("rejected_points"):
                    detail += f"; failed {p.get('failed_points', 0)}, rejected {p.get('rejected_points', 0)}"
            diff = p.get("difference")
            L.append(f"| {p['id']} | {q} | {p['phase'] or '—'} | {p['composition']} | {p['T_K'] or '—'} | "
                     f"{p['reference']} | {model} | {'—' if diff is None else f'{diff:+g}'} | "
                     f"{p['tolerance'] or '—'} | {within} | {detail} | {p['source']} |")
        L.append("")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, help="dataset JSON; without it only the B2 reference points are run")
    ap.add_argument("--tdb", type=Path, required=True)
    ap.add_argument("--refs", type=Path)
    ap.add_argument("--elements", nargs=3, help="without --dataset: the three elements")
    ap.add_argument("--tmin", type=float, help="without --dataset: lower T for liquidus / upper-stability searches")
    ap.add_argument("--tmax", type=float, help="without --dataset: upper T for liquidus / upper-stability searches")
    ap.add_argument("--min-fraction", type=float, default=MIN_FRACTION,
                    help=f"phases_at_T: smallest phase fraction counted (default {MIN_FRACTION})")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, help="writes <out>.md and <out>.json")
    a = ap.parse_args(argv)
    if a.dataset:
        ds = json.loads(a.dataset.read_text())
        res = run_checks(ds, a.tdb, a.refs, a.workers, a.min_fraction)
        md = markdown(res, ds)
        code = 0 if res["A_pass"] else 1
    else:
        if not (a.refs and a.elements and a.tmin is not None and a.tmax is not None):
            ap.error("without --dataset, give --refs, --elements, --tmin and --tmax")
        res = run_reference_points(a.tdb, a.elements, a.refs, a.tmin, a.tmax, a.workers, a.min_fraction)
        md = "\n".join([f"# Reference points: {'–'.join(res['elements'])}", ""] + markdown_b2(res)) + "\n"
        code = 0
    print(md)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.with_suffix(".md").write_text(md, encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
