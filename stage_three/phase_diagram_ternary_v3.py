"""
phase_diagram_ternary_v3.py — Ternary isothermal section with multiprocessing.

Uses Python multiprocessing to parallelize equilibrium calculations across all
available CPU cores. ~10x faster than v2 on a 12-core machine (N=80 in ~7 min).

Each worker process loads the merged TDB once (via Pool initializer) and then
processes individual composition points — correct and fast.

Usage:
    python stage_three/phase_diagram_ternary_v3.py FE ND B 1375
    python stage_three/phase_diagram_ternary_v3.py FE ND B 1375 80
    python stage_three/phase_diagram_ternary_v3.py FE ND B 1375 80 --force
    python stage_three/phase_diagram_ternary_v3.py LA FE SI 1375 60
"""

import sys
import pickle
import argparse
from pathlib import Path
from multiprocessing import Pool, cpu_count
import numpy as np

from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Path setup ────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
TDB_DIR   = PROJ_ROOT / "data" / "tdb" / "sgte_binary"
CACHE_DIR = THIS_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(THIS_DIR))
from tdb_lookup import build_index, find_binaries, select_preferred

SQRT3_2 = np.sqrt(3) / 2


# ── TDB merge (same dedup logic as v1/v2) ────────────────────────────────────
def merge_tdb_files(paths):
    seen, out = set(), []
    DEDUP = {"FUNCTION", "ELEMENT", "PHASE", "CONSTITUENT"}
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        skip = False
        for line in lines:
            u = line.strip().upper()
            if skip:
                if "!" in line:
                    skip = False
                continue
            tok = u.split()[0] if u.split() else ""
            if tok in DEDUP:
                toks = u.split()
                name = toks[1].rstrip(":") if len(toks) > 1 else ""
                key  = f"{tok}_{name}"
                if key in seen:
                    if "!" not in line:
                        skip = True
                    continue
                seen.add(key)
            out.append(line)
        out.append("\n")
    return "".join(out)


# ── Ternary <-> Cartesian ─────────────────────────────────────────────────────
def tern2cart(x1, x2):
    """el1=top, el2=bottom-right, el3=bottom-left."""
    return np.asarray(x2) + 0.5 * np.asarray(x1), SQRT3_2 * np.asarray(x1)


# ── Composition grid ──────────────────────────────────────────────────────────
def make_grid(N, eps=1e-3):
    g = np.linspace(0, 1, N + 1)
    X1, X2 = np.meshgrid(g, g, indexing="ij")
    X3 = 1.0 - X1 - X2
    mask = (X3 > eps) & (X1 > eps) & (X2 > eps)
    return X1[mask], X2[mask], X3[mask]


# ── Worker (module-level so multiprocessing can pickle it) ────────────────────
_worker_db     = None
_worker_phases = None
_worker_els    = None


def _init_worker(tdb_path, phases, elements):
    """Load the database once per worker process."""
    global _worker_db, _worker_phases, _worker_els
    _worker_db     = Database(str(tdb_path))
    _worker_phases = phases
    _worker_els    = elements


def _compute_one(args):
    """Compute equilibrium for a single composition point."""
    x1, x2, T = args
    el1, el2, el3 = _worker_els
    try:
        species = [e for e in _worker_els + ["VA"] if e in _worker_db.elements]
        res = equilibrium(
            _worker_db, species, _worker_phases,
            {v.X(el1): x1, v.X(el2): x2, v.T: T, v.P: 101325},
        )
        phase_arr = np.asarray(res["Phase"].values).flatten()
        np_arr    = np.asarray(res["NP"].values).flatten()

        ph_list, np_list = [], []
        for p, n in zip(phase_arr, np_arr):
            if p == "" or p is None:
                continue
            if not np.isfinite(float(n)) or float(n) < 1e-3:
                continue
            ph_list.append(str(p))
            np_list.append(float(n))

        return {
            "phases": tuple(ph_list),
            "nps":    np_list,
            "stable": len(ph_list) > 0,
        }
    except Exception:
        return None


# ── Plotting ──────────────────────────────────────────────────────────────────
def classify(r):
    if r is None or not r["stable"]:
        return "UNKNOWN"
    return "+".join(sorted(r["phases"]))


def plot_section(elements, T, x1, x2, results, out_png):
    el1, el2, el3 = elements
    labels = [classify(r) for r in results]
    unique = sorted(set(labels) - {"UNKNOWN"})

    cmap  = plt.get_cmap("tab20", max(len(unique), 1))
    color = {lab: cmap(i) for i, lab in enumerate(unique)}
    cx, cy = tern2cart(x1, x2)

    fig, ax = plt.subplots(figsize=(11, 10))
    for lab in unique:
        m = np.array([l == lab for l in labels])
        ax.scatter(cx[m], cy[m], s=14, c=[color[lab]],
                   marker="s", linewidths=0, label=lab)
    m_unk = np.array([l == "UNKNOWN" for l in labels])
    if m_unk.any():
        ax.scatter(cx[m_unk], cy[m_unk], s=14, c="lightgray",
                   marker="x", linewidths=0.4)

    ax.plot([0, 1, 0.5, 0], [0, 0, SQRT3_2, 0], "k-", lw=1.5)

    off = 0.04
    ax.text(-off, -off, el3, ha="right",  va="top",    fontsize=14, fontweight="bold")
    ax.text(1+off, -off, el2, ha="left",   va="top",    fontsize=14, fontweight="bold")
    ax.text(0.5, SQRT3_2+off, el1, ha="center", va="bottom", fontsize=14, fontweight="bold")

    # Stoichiometric marker for Nd2Fe14B
    if set(elements) == {"ND", "FE", "B"}:
        stoich = {"ND": 2/17, "FE": 14/17, "B": 1/17}
        scx, scy = tern2cart(stoich[el1], stoich[el2])
        ax.plot(scx, scy, "k*", markersize=14, zorder=5)
        ax.text(scx - 0.03, scy - 0.03, "Nd₂Fe₁₄B\nstoich.",
                ha="right", va="top", fontsize=8)

    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left",
              fontsize=7, framealpha=0.9, ncol=1)
    ax.set_title(f"{el1}-{el2}-{el3} isothermal section at {T} K  "
                 f"(pycalphad, SGTE binaries)", fontsize=12)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    print(f"  ✓ Saved → {out_png}")
    plt.close(fig)


def plot_phase_fraction(elements, T, x1, x2, results, target_phase, out_png):
    el1, el2, el3 = elements
    cx, cy = tern2cart(x1, x2)
    frac = np.full(len(results), np.nan)
    for i, r in enumerate(results):
        if r is None or not r["stable"]:
            continue
        for ph, npv in zip(r["phases"], r["nps"]):
            if ph == target_phase:
                frac[i] = npv
                break

    valid = ~np.isnan(frac)
    fig, ax = plt.subplots(figsize=(9, 8))
    sc = ax.scatter(cx[valid], cy[valid], c=frac[valid], s=18,
                    cmap="viridis", vmin=0, vmax=1, marker="s")
    ax.plot([0, 1, 0.5, 0], [0, 0, SQRT3_2, 0], "k-", lw=1.5)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.8)
    cbar.set_label(f"NP({target_phase})")
    ax.set_title(f"{target_phase} fraction at {T} K")
    ax.set_aspect("equal")
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(out_png, dpi=160, bbox_inches="tight")
    print(f"  ✓ Saved → {out_png}")
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("elements", nargs=3)
    parser.add_argument("T",   type=float, nargs="?", default=1375.0)
    parser.add_argument("N",   type=int,   nargs="?", default=80)
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache and recompute")
    parser.add_argument("--cores", type=int, default=0,
                        help="Number of cores (0 = all available)")
    args = parser.parse_args()

    elements = [e.upper() for e in args.elements]
    el1, el2, el3 = elements
    T, N = args.T, args.N
    ncores = args.cores or cpu_count()

    print(f"System : {el1}-{el2}-{el3}")
    print(f"Temp   : {T} K  ({T - 273.15:.0f} °C)")
    print(f"Grid   : N={N}  (~{N*N//2} points)")
    print(f"Cores  : {ncores} / {cpu_count()}")

    cache = CACHE_DIR / f"{''.join(elements)}_{int(T)}K_N{N}_v3.pkl"

    if cache.exists() and not args.force:
        print(f"\n  Loading cache: {cache.name}")
        with open(cache, "rb") as f:
            payload = pickle.load(f)
        x1, x2, results = payload["x1"], payload["x2"], payload["results"]
    else:
        # 1. Find + merge TDBs
        print("\n  Looking up binary TDB files...")
        index = build_index(TDB_DIR)
        cand  = find_binaries(elements, index)
        if len(cand) < 3:
            print("ERROR: missing binary TDB files")
            sys.exit(1)
        selected = {p: select_preferred(f) for p, f in cand.items()}
        for pair, path in selected.items():
            a, b = sorted(pair)
            print(f"    {a}-{b}: {path.name}")

        tdb_paths  = sorted(selected.values(), key=lambda p: p.name)
        merged_path = THIS_DIR / f"{''.join(elements)}_merged_v3.tdb"
        merged_path.write_text(merge_tdb_files(tdb_paths), encoding="utf-8")

        # Load once in main process just to get phase list
        db_main = Database(str(merged_path))
        phases  = list(db_main.phases.keys())
        print(f"  Phases: {phases}\n")

        # 2. Build grid
        x1, x2, _ = make_grid(N)
        n = len(x1)
        print(f"  Computing {n} equilibria at {T} K using {ncores} cores...")

        # 3. Parallel equilibrium
        import time
        t0   = time.time()
        tasks = [(float(x1[i]), float(x2[i]), T) for i in range(n)]

        with Pool(
            processes=ncores,
            initializer=_init_worker,
            initargs=(merged_path, phases, elements),
        ) as pool:
            results = pool.map(_compute_one, tasks, chunksize=10)

        elapsed = time.time() - t0
        print(f"  ✓ Done in {elapsed/60:.1f} min  ({elapsed/n:.2f} s/point)\n")

        # 4. Cache
        with open(cache, "wb") as f:
            pickle.dump({"x1": x1, "x2": x2, "results": results}, f)
        merged_path.unlink(missing_ok=True)

    # 5. Diagnostics
    from collections import Counter
    failed = sum(1 for r in results if r is None or not r["stable"])
    print(f"  Failed/empty : {failed} / {len(results)}")
    cnts = Counter(len(r["phases"]) for r in results if r and r["stable"])
    print(f"  Phase counts : {dict(sorted(cnts.items()))}")
    asm = Counter(classify(r) for r in results if r and r["stable"])
    print("  Top assemblages:")
    for k, val in asm.most_common(10):
        print(f"    {val:5d}  {k}")

    # 6. Plots
    tag  = "".join(elements)
    out1 = THIS_DIR / f"{tag}_ternary_{int(T)}K_v3.png"
    plot_section(elements, T, x1, x2, results, out1)

    for target in ("LIQUID", "FE17ND2", "FE17ND5"):
        if any(r and target in r["phases"] for r in results):
            out2 = THIS_DIR / f"{tag}_{target}_{int(T)}K_v3.png"
            plot_phase_fraction(elements, T, x1, x2, results, target, out2)


if __name__ == "__main__":
    main()
