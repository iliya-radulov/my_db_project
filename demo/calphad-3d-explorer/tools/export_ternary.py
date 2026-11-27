#!/usr/bin/env python3
"""
demo/calphad-3d-explorer/tools/export_ternary.py

Computes a ternary phase-diagram dataset with pycalphad from a real TDB file and writes it as one
JSON file for the 3D explorer ("Load computed dataset"). Replaces the explorer's qualitative toy
solver by full equilibrium calculations.

For every point of a triangular composition grid (A, B, C = the three elements, in this order)
and every temperature of a temperature grid, the equilibrium phases and their fractions are
stored. From the liquid fraction along temperature, per composition:

    T_liquidus  lowest temperature at which the system is all liquid (liquid fraction >= LIQ_FULL)
    T_solidus   highest temperature at which no liquid is present (liquid fraction <= LIQ_NONE)
    primary phase       the solid with the largest fraction just below T_liquidus
    solid assemblage    the phases just below T_solidus

Both temperatures are linearly interpolated between grid temperatures; their resolution is the
temperature step, recorded in the file. Values outside the grid range are stored as null
(e.g. "not fully liquid even at T_max").

Provenance in the file: TDB file name, path and SHA-256, this script's SHA-256, package versions,
the full command line and the grid. The dataset carries no claim beyond the model in the file.

Usage (repository root):
    python demo/calphad-3d-explorer/tools/export_ternary.py \
        --tdb stage_four/calphad_lafesi/refit_tau12/results_addD/paperbuild_FeLa-23Su_LaSi-10Zho_FeSi-12Ohn.tdb \
        --elements FE LA SI --tmin 800 --tmax 2000 --dt 10 --grid 30 --workers 4 \
        --out demo/calphad-3d-explorer/datasets/lafesi_paperbuild.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import warnings
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

SCHEMA = "calphad-ternary-dataset/1"
VERTEX_EPS = 1e-4      # compositions are kept this far from 0 (pycalphad needs X > 0)
LIQ_FULL = 0.999       # liquid fraction counted as "all liquid"
LIQ_NONE = 0.001       # liquid fraction counted as "no liquid"
FRACTION_DIGITS = 4


# ---------------------------------------------------------------------------
# Pure helpers (tested without pycalphad)
# ---------------------------------------------------------------------------
def triangle_grid(n: int, eps: float = VERTEX_EPS):
    """(i, j, xA, xB, xC) for i + j <= n, with xB = i/n, xC = j/n, kept eps away from 0."""
    pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            xb, xc = i / n, j / n
            xa = 1.0 - xb - xc
            xa, xb, xc = (max(eps, x) for x in (xa, xb, xc))
            s = xa + xb + xc
            pts.append((i, j, xa / s, xb / s, xc / s))
    return pts


def crossing_up(temps, values, level):
    """Lowest T at which values (assumed to rise with T) reach `level`, interpolated.
    None if never reached; temps[0] if already reached at the lowest T."""
    for k, val in enumerate(values):
        if val is None or not np.isfinite(val):
            continue
        if val >= level:
            if k == 0:
                return float(temps[0])
            prev = values[k - 1]
            if prev is None or not np.isfinite(prev) or val == prev:
                return float(temps[k])
            t0, t1 = temps[k - 1], temps[k]
            return float(t0 + (level - prev) / (val - prev) * (t1 - t0))
    return None


def crossing_down(temps, values, level):
    """Highest T at which values are still <= `level` (scanning from high T), interpolated.
    None if values exceed `level` everywhere; temps[-1] if they never exceed it."""
    n = len(values)
    for k in range(n - 1, -1, -1):
        val = values[k]
        if val is None or not np.isfinite(val):
            continue
        if val <= level:
            if k == n - 1:
                return float(temps[-1])
            nxt = values[k + 1]
            if nxt is None or not np.isfinite(nxt) or nxt == val:
                return float(temps[k])
            t0, t1 = temps[k], temps[k + 1]
            return float(t0 + (level - val) / (nxt - val) * (t1 - t0))
    return None


def liquid_names(phases) -> set[str]:
    return {p for p in phases if "LIQ" in p.upper()}


def node_summary(temps, states, liquids: set[str]) -> dict:
    """Liquidus/solidus, primary phase and solid assemblage from the per-T states
    (each state: {phase: fraction} or None)."""
    f_liq = [None if s is None else sum(f for p, f in s.items() if p in liquids) for s in states]
    t_liq = crossing_up(temps, f_liq, LIQ_FULL)
    t_sol = crossing_down(temps, f_liq, LIQ_NONE)
    primary, assemblage = None, None
    if t_liq is not None:
        below = [k for k, t in enumerate(temps) if t < t_liq and states[k] is not None]
        if below:
            s = states[below[-1]]
            solids = {p: f for p, f in s.items() if p not in liquids}
            if solids:
                primary = max(solids, key=solids.get)
    if t_sol is not None:
        below = [k for k, t in enumerate(temps) if t <= t_sol and states[k] is not None]
        if below:
            assemblage = sorted(p for p in states[below[-1]] if p not in liquids)
    return {"t_liquidus_K": t_liq, "t_solidus_K": t_sol, "primary_phase": primary,
            "solid_assemblage": assemblage, "liquid_fraction": f_liq}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# pycalphad part
# ---------------------------------------------------------------------------
def _states_from_arrays(phase, frac, gm):
    """{phase: fraction} per (composition, T) from arrays shaped (T, comp, vertex) / (T, comp)."""
    n_t, n_c = gm.shape
    out = [[None] * n_t for _ in range(n_c)]
    gms = [[None] * n_t for _ in range(n_c)]
    for t in range(n_t):
        for c in range(n_c):
            if not np.isfinite(gm[t, c]):
                continue
            s: dict[str, float] = {}
            for p, f in zip(phase[t, c], frac[t, c]):
                p = str(p)
                if p and np.isfinite(f) and f > 0:
                    s[p] = s.get(p, 0.0) + float(f)   # merge composition sets (#1, #2) by name
            out[c][t] = {p: round(f, FRACTION_DIGITS) for p, f in s.items()}
            gms[c][t] = round(float(gm[t, c]), 2)
    return out, gms


def compute_row(args):
    """One grid row: fixed x_B, all x_C of that row, all temperatures. Runs in a worker."""
    tdb, elements, phases, temps, row = args
    warnings.filterwarnings("ignore")
    from pycalphad import Database, equilibrium, variables as v
    db = Database(tdb)
    A, B, C = elements
    xb = row[0][3]
    xcs = [p[4] for p in row]
    eq = equilibrium(db, [A, B, C, "VA"], phases,
                     {v.X(B): xb, v.X(C): xcs, v.T: list(temps), v.P: 101325, v.N: 1})
    # arrays in (T, X_C[, vertex]) order, whatever order pycalphad chose
    keep = ["T", f"X_{C}"]

    def arr(name):
        da = eq[name]
        da = da.isel({d: 0 for d in da.dims if d not in keep and d != "vertex"})
        return np.asarray(da.transpose(*keep, *[d for d in da.dims if d not in keep]).values)

    return _states_from_arrays(arr("Phase"), arr("NP"), arr("GM"))


def build_dataset(tdb: Path, elements, tmin, tmax, dt, grid, workers, exclude, argv) -> dict:
    from pycalphad import Database
    import pycalphad
    elements = [e.upper() for e in elements]
    db = Database(str(tdb))
    db_elements = sorted(e for e in db.elements if e not in ("VA", "/-"))
    missing = [e for e in elements if e not in db_elements]
    if missing:
        raise SystemExit(f"{tdb.name}: elements {missing} not in the file ({db_elements})")
    phases = sorted(p for p in db.phases if p not in set(exclude))
    temps = [float(t) for t in np.arange(tmin, tmax + dt / 2, dt)]
    pts = triangle_grid(grid)
    rows: dict[int, list] = {}
    for p in pts:
        rows.setdefault(p[0], []).append(p)
    row_keys = sorted(rows)
    t0 = time.time()
    jobs = [(str(tdb), elements, phases, temps, rows[i]) for i in row_keys]
    if workers > 1:
        with Pool(workers) as pool:
            results = pool.map(compute_row, jobs)
    else:
        results = [compute_row(j) for j in jobs]
    liquids = liquid_names(phases)
    nodes, seen = [], set()
    for i, (states_rows, gm_rows) in zip(row_keys, results):
        for p, states, gms in zip(rows[i], states_rows, gm_rows):
            summ = node_summary(temps, states, liquids)
            for s in states:
                if s:
                    seen.update(s)
            nodes.append({"i": p[0], "j": p[1], "xA": p[2], "xB": p[3], "xC": p[4],
                          **{k: summ[k] for k in ("t_liquidus_K", "t_solidus_K", "primary_phase",
                                                  "solid_assemblage")},
                          "states": states, "gm_J": gms})
    failed = sum(1 for n in nodes for s in n["states"] if s is None)
    script = Path(__file__).resolve()
    return {
        "schema": SCHEMA,
        "system": {
            "elements": elements,
            "label": f"{'–'.join(e.capitalize() for e in elements)} · {tdb.stem}",
            "source": {"tdb_file": tdb.name, "tdb_path": str(tdb), "tdb_sha256": sha256_file(tdb)},
        },
        "grid": {"subdivisions": grid, "vertex_eps": VERTEX_EPS, "temperatures_K": temps,
                 "temperature_step_K": dt, "liquid_full": LIQ_FULL, "liquid_none": LIQ_NONE},
        "phases": {"considered": phases, "appearing": sorted(seen), "liquid": sorted(liquids),
                   "excluded": sorted(exclude)},
        "provenance": {
            "script": "demo/calphad-3d-explorer/tools/export_ternary.py",
            "script_sha256": sha256_file(script),
            "command": " ".join(argv),
            "pycalphad": pycalphad.__version__, "numpy": np.__version__,
            "python": platform.python_version(),
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runtime_s": round(time.time() - t0, 1),
            "failed_points": failed,
        },
        "nodes": nodes,
    }


def main(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tdb", type=Path, required=True)
    ap.add_argument("--elements", nargs=3, required=True, metavar=("A", "B", "C"),
                    help="the three elements; A, B, C = triangle corners in this order")
    ap.add_argument("--tmin", type=float, default=800.0)
    ap.add_argument("--tmax", type=float, default=2000.0)
    ap.add_argument("--dt", type=float, default=10.0, help="temperature step (K); also the resolution of T_liquidus / T_solidus")
    ap.add_argument("--grid", type=int, default=20, help="composition subdivisions per edge")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--exclude-phase", nargs="*", default=[], help="phases left out (recorded)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv[1:])
    data = build_dataset(a.tdb, a.elements, a.tmin, a.tmax, a.dt, a.grid, a.workers,
                         a.exclude_phase, argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, separators=(",", ":")))
    p = data["provenance"]
    print(f"{a.out}: {len(data['nodes'])} compositions x {len(data['grid']['temperatures_K'])} temperatures, "
          f"{p['runtime_s']} s, failed points {p['failed_points']}, phases {data['phases']['appearing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
