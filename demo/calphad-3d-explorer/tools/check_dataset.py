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
       reference_points_TEMPLATE.csv): liquidus/solidus at a composition, or the phase set at
       a composition and temperature. Each row carries its own tolerance and source.

Usage (repository root):
    python demo/calphad-3d-explorer/tools/check_dataset.py \
        --dataset demo/calphad-3d-explorer/datasets/lafesi_paperbuild.json \
        --tdb stage_four/calphad_lafesi/refit_tau12/results_addD/paperbuild_FeLa-23Su_LaSi-10Zho_FeSi-12Ohn.tdb \
        [--refs my_reference_points.csv] --workers 4 --out demo/calphad-3d-explorer/datasets/lafesi_paperbuild_check
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


def parse_composition(text: str) -> dict[str, float]:
    """'FE:0.857;LA:0.0714;SI:0.0714' -> {'FE': .857, ...} (normalised; ';' because the CSV uses ',')."""
    out = {}
    for part in text.split(";"):
        el, val = part.split(":")
        out[el.strip().upper()] = float(val)
    s = sum(out.values())
    return {k: v / s for k, v in out.items()}


def nearest_node(nodes, elements, comp: dict[str, float]):
    a, b, c = elements
    return min(nodes, key=lambda nd: (nd["xA"] - comp.get(a, 0)) ** 2
               + (nd["xB"] - comp.get(b, 0)) ** 2 + (nd["xC"] - comp.get(c, 0)) ** 2)


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
# Checks
# ---------------------------------------------------------------------------
def run_checks(ds: dict, tdb: Path, refs: Path | None, workers: int) -> dict:
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

    # B2 reference points
    out["B2_reference_points"] = []
    if refs:
        with open(refs, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(row for row in f if not row.lstrip().startswith("#")):
                comp = parse_composition(r["composition"])
                nd = nearest_node(ds["nodes"], elements, comp)
                q = r["quantity"].strip()
                entry = {"id": r["id"], "quantity": q, "composition": r["composition"],
                         "source": r["source"], "reference": r["value"],
                         "grid_point": [round(nd["xA"], 4), round(nd["xB"], 4), round(nd["xC"], 4)]}
                if q in ("t_liquidus_K", "t_solidus_K"):
                    model = nd[q]
                    ref = float(r["value"])
                    t = float(r["tolerance"])
                    entry.update(model=model, difference_K=None if model is None else round(model - ref, 1),
                                 within_tolerance=model is not None and abs(model - ref) <= t)
                elif q == "phases_at_T":
                    k = int(np.argmin([abs(tt - float(r["T_K"])) for tt in temps]))
                    st = nd["states"][k]
                    model = "+".join(sorted(st)) if st else None
                    ref = "+".join(sorted(p.strip() for p in r["value"].split("+")))
                    entry.update(T_K=temps[k], model=model, within_tolerance=model == ref)
                else:
                    entry.update(error=f"unknown quantity {q!r}")
                out["B2_reference_points"].append(entry)

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
    if res["B2_reference_points"]:
        L += ["B2 reference points:", "", "| Id | Quantity | Composition | Reference | Model | Within tolerance | Source |",
              "|---|---|---|---|---|---|---|"]
        for r in res["B2_reference_points"]:
            L.append(f"| {r['id']} | {r['quantity']} | {r['composition']} | {r['reference']} | {r.get('model')} | "
                     f"{'yes' if r.get('within_tolerance') else 'no'} | {r['source']} |")
    else:
        L.append("B2 reference points: none given (see reference_points_TEMPLATE.csv).")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--tdb", type=Path, required=True)
    ap.add_argument("--refs", type=Path)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, help="writes <out>.md and <out>.json")
    a = ap.parse_args(argv)
    ds = json.loads(a.dataset.read_text())
    res = run_checks(ds, a.tdb, a.refs, a.workers)
    md = markdown(res, ds)
    print(md)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.with_suffix(".md").write_text(md, encoding="utf-8")
        a.out.with_suffix(".json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0 if res["A_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
