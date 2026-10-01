"""
phase_diagram_ternary_v2.py — Ternary isothermal section with phase regions,
tie-lines, and caching. Uses vectorized pycalphad calls for speed.

Usage:
    python stage_three/phase_diagram_ternary_v2.py FE ND B 1375 80
    python stage_three/phase_diagram_ternary_v2.py LA FE SI 1375 60
"""

import sys
import pickle
from pathlib import Path
import os
os.environ["OMP_NUM_THREADS"] = "8"

import numpy as np
from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ── Path setup ────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
TDB_DIR   = PROJ_ROOT / "data" / "tdb" / "sgte_binary"
CACHE_DIR = THIS_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(THIS_DIR))
from tdb_lookup import build_index, find_binaries, select_preferred


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    a = sys.argv[1:]
    if len(a) < 3:
        print("Usage: python phase_diagram_ternary_v2.py EL1 EL2 EL3 [T_K] [N]")
        sys.exit(1)
    els = [x.upper() for x in a[:3]]
    T   = float(a[3]) if len(a) > 3 else 1375.0
    N   = int(a[4])   if len(a) > 4 else 80
    return els, T, N


# ── TDB merge ─────────────────────────────────────────────────────────────────
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
                key = f"{tok}_{name}"
                if key in seen:
                    if "!" not in line:
                        skip = True
                    continue
                seen.add(key)
            out.append(line)
        out.append("\n")
    return "".join(out)



# ── Ternary <-> Cartesian ─────────────────────────────────────────────────────
SQRT3_2 = np.sqrt(3) / 2

def tern2cart(x1, x2):
    """el1 top, el2 bottom-right, el3 bottom-left.  x1+x2+x3=1."""
    return x2 + 0.5 * x1, SQRT3_2 * x1


# ── Composition grid ──────────────────────────────────────────────────────────
def make_grid(N, eps=1e-3):
    g = np.linspace(0, 1, N + 1)
    X1, X2 = np.meshgrid(g, g, indexing="ij")
    X3 = 1.0 - X1 - X2
    mask = (X3 > eps) & (X1 > eps) & (X2 > eps)
    return X1[mask], X2[mask], X3[mask]


# ── Shape normalisation helpers ───────────────────────────────────────────────
def _flat2d(arr, npts):
    """
    Coerce whatever pycalphad returns into a 2D array of shape (npts, K).
    K is whatever the last axis happened to be — caller may need to align it.
    """
    arr = np.asarray(arr)
    # remove trailing singleton dims
    arr = np.squeeze(arr)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        if arr.shape[0] == npts:
            arr = arr.reshape(npts, 1)
        else:
            arr = arr.reshape(1, -1)
    elif arr.ndim > 2:
        arr = arr.reshape(-1, arr.shape[-1])

    # pad / truncate first axis to npts
    if arr.shape[0] < npts:
        pad = np.full((npts - arr.shape[0], arr.shape[1]),
                      np.nan, dtype=arr.dtype)
        arr = np.concatenate([arr, pad], axis=0)
    elif arr.shape[0] > npts:
        arr = arr[:npts]
    return arr


def _align_to_maxph(arr, npts, maxph):
    """Force arr into shape (npts, maxph) using NaN padding / truncation."""
    if arr is None:
        return None
    arr = np.asarray(arr)
    arr = np.squeeze(arr)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        if arr.size == npts * maxph:
            arr = arr.reshape(npts, maxph)
        elif arr.size == npts:
            arr = arr.reshape(npts, 1)
        elif arr.size == maxph:
            arr = arr.reshape(1, maxph)
        else:
            arr = arr.reshape(npts, -1)
    elif arr.ndim > 2:
        arr = arr.reshape(-1, arr.shape[-1])

    # pad / truncate last axis to maxph
    if arr.shape[1] < maxph:
        pad = np.full((arr.shape[0], maxph - arr.shape[1]),
                      np.nan, dtype=arr.dtype)
        arr = np.concatenate([arr, pad], axis=1)
    elif arr.shape[1] > maxph:
        arr = arr[:, :maxph]

    # pad / truncate first axis to npts
    if arr.shape[0] < npts:
        pad = np.full((npts - arr.shape[0], arr.shape[1]),
                      np.nan, dtype=arr.dtype)
        arr = np.concatenate([arr, pad], axis=0)
    elif arr.shape[0] > npts:
        arr = arr[:npts]
    return arr


# ── Equilibrium over the whole grid ───────────────────────────────────────────
def compute_equilibria(db, elements, phases, x1, x2, T, chunk=1):
    """
    Returns a list of per-point dicts:
        'phases'  : tuple of phase names with NP > threshold
        'nps'     : matching NP values
        'comps'   : list of dicts {el: mole fraction}
        'stable'  : bool
    """
    el1, el2, el3 = elements
    comps = sorted(set(db.elements))
    species = [e for e in (el1, el2, el3, "VA") if e in comps]

    out = []
    n = len(x1)
    for start in range(0, n, chunk):
        sl = slice(start, min(start + chunk, n))
        npts = sl.stop - sl.start

        conds = {
            v.X(el2): np.atleast_1d(x2[sl]),
            v.X(el1): np.atleast_1d(x1[sl]),
            v.T: T,
            v.P: 101325,
        }
        try:
            res = equilibrium(db, species, phases, conds)
        except Exception as e:
            print(f"  [warn] chunk {start}: {e}")
            out.extend([None] * npts)
            continue

        # ── Pull Phase and NP first to determine maxph ────────────────────
        phase_arr = _flat2d(res["Phase"].values, npts)   # (npts, K)
        np_arr    = _flat2d(res["NP"].values,    npts)   # (npts, K)

        maxph = phase_arr.shape[1]

        # align NP to (npts, maxph)
        np_arr = _align_to_maxph(np_arr, npts, maxph)

        # ── Align composition arrays to (npts, maxph) ─────────────────────
        comp_arrays = {}
        for el in (el1, el2, el3):
            key = f"X_{el}"
            if key in res:
                comp_arrays[el] = _align_to_maxph(res[key].values,
                                                  npts, maxph)

        # ── Extract per-point data ────────────────────────────────────────
        for i in range(npts):
            ph_list, np_list, comp_list = [], [], []
            for j in range(maxph):
                p  = phase_arr[i, j]
                n_ = np_arr[i, j]
                if p == "" or p is None:
                    continue
                if not np.isfinite(n_) or n_ < 1e-3:
                    continue
                ph_list.append(str(p))
                np_list.append(float(n_))

                entry = {}
                for el in (el1, el2, el3):
                    if el not in comp_arrays:
                        continue
                    v_ij = comp_arrays[el][i, j]
                    if np.isfinite(v_ij):
                        entry[el] = float(v_ij)
                comp_list.append(entry)

            out.append({
                "phases": tuple(ph_list),
                "nps":    np_list,
                "comps":  comp_list,
                "stable": len(ph_list) > 0,
            })

    assert len(out) == n, f"got {len(out)} results for {n} inputs"
    return out


# ── Plotting ──────────────────────────────────────────────────────────────────
def classify(entry):
    if entry is None or not entry["stable"]:
        return "UNKNOWN"
    return "+".join(sorted(entry["phases"]))


def plot_section(elements, T, x1, x2, results, out_png, draw_tielines=True):
    el1, el2, el3 = elements
    labels = [classify(r) for r in results]
    unique = sorted(set(labels) - {"UNKNOWN"})

    cmap = plt.get_cmap("tab20", max(len(unique), 1))
    color = {lab: cmap(i) for i, lab in enumerate(unique)}

    cx, cy = tern2cart(x1, x2)

    fig, ax = plt.subplots(figsize=(10, 9))

    for lab in unique:
        m = np.array([l == lab for l in labels])
        ax.scatter(cx[m], cy[m], s=18, c=[color[lab]],
                   marker="s", linewidths=0, label=lab)

    m_unk = np.array([l == "UNKNOWN" for l in labels])
    if m_unk.any():
        ax.scatter(cx[m_unk], cy[m_unk], s=18, c="lightgray",
                   marker="x", linewidths=0.5, label="UNKNOWN")

    if draw_tielines:
        for r, (px, py) in zip(results, zip(cx, cy)):
            if r is None or len(r["phases"]) != 2:
                continue
            if len(r["comps"]) != 2:
                continue
            try:
                c0, c1 = r["comps"]
                if not all(el in c0 for el in elements):
                    continue
                if not all(el in c1 for el in elements):
                    continue
                a0, b0 = tern2cart(c0[el1], c0[el2])
                a1, b1 = tern2cart(c1[el1], c1[el2])
                ax.plot([a0, a1], [b0, b1], "-",
                        color="k", alpha=0.15, linewidth=0.4, zorder=0)
            except Exception:
                pass

    ax.plot([0, 1, 0.5, 0], [0, 0, SQRT3_2, 0], "k-", linewidth=1.5)

    off = 0.04
    ax.text(-off, -off, el3, ha="right",  va="top",    fontsize=14, fontweight="bold")
    ax.text(1 + off, -off, el2, ha="left",   va="top",    fontsize=14, fontweight="bold")
    ax.text(0.5, SQRT3_2 + off, el1, ha="center", va="bottom", fontsize=14, fontweight="bold")

    # mole-fraction ticks along each edge
    for frac in np.linspace(0.1, 0.9, 9):
        xb, yb = frac, 0.0
        ax.plot([xb, xb], [yb, yb + 0.008], "k-", linewidth=0.6)
        xr, yr = tern2cart(frac, 1 - frac)
        ax.plot([xr, xr - 0.005], [yr, yr + 0.008], "k-", linewidth=0.6)
        xl, yl = tern2cart(1 - frac, 0)
        ax.plot([xl, xl + 0.005], [yl, yl + 0.008], "k-", linewidth=0.6)

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


# ── Phase fraction heatmap (bonus) ────────────────────────────────────────────
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

    fig, ax = plt.subplots(figsize=(9, 8))
    sc = ax.scatter(cx, cy, c=frac, s=22, cmap="viridis",
                    vmin=0, vmax=1, marker="s")
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
    elements, T, N = parse_args()
    el1, el2, el3 = elements
    print(f"System: {el1}-{el2}-{el3}   T = {T} K   grid N = {N}")

    cache = CACHE_DIR / f"{''.join(elements)}_{int(T)}K_N{N}.pkl"

    if cache.exists():
        print(f"  Loading cache {cache.name}")
        with open(cache, "rb") as f:
            payload = pickle.load(f)
        x1, x2, results = payload["x1"], payload["x2"], payload["results"]
    else:
        # 1. Find + merge TDBs
        index = build_index(TDB_DIR)
        cand  = find_binaries(elements, index)
        if len(cand) < 3:
            print("ERROR: missing binaries")
            sys.exit(1)
        selected = {p: select_preferred(f) for p, f in cand.items()}
        for pair, path in selected.items():
            a, b = sorted(pair)
            print(f"  {a}-{b}: {path.name}")

        tdb_paths = sorted(selected.values(), key=lambda p: p.name)
        merged = THIS_DIR / f"{''.join(elements)}_merged.tdb"
        merged.write_text(merge_tdb_files(tdb_paths), encoding="utf-8")

        db     = Database(str(merged))
        phases = list(db.phases.keys())
        print(f"  Phases: {phases}")

        # 2. Grid + equilibria
        x1, x2, _ = make_grid(N)
        print(f"  Computing {len(x1)} equilibria at {T} K...")
        results = compute_equilibria(db, elements, phases, x1, x2, T)
        print("  ✓ Done")

        with open(cache, "wb") as f:
            pickle.dump({"x1": x1, "x2": x2, "results": results}, f)
        merged.unlink(missing_ok=True)
        
        

    # 3. Diagnostic summary
    from collections import Counter
    failed = sum(1 for r in results if r is None or not r["stable"])
    print(f"  Failed/empty: {failed} / {len(results)}")
    cnts = Counter(len(r["phases"]) for r in results if r and r["stable"])
    print(f"  Phase count distribution: {dict(sorted(cnts.items()))}")
    asm = Counter(classify(r) for r in results if r and r["stable"])
    print("  Top assemblages:")
    for k, val in asm.most_common(8):
        print(f"    {val:5d}  {k}")

    # 4. Plots
    tag = "".join(elements)
    out1 = THIS_DIR / f"{tag}_ternary_{int(T)}K_v2.png"
    plot_section(elements, T, x1, x2, results, out1, draw_tielines=True)

    # Optional: phase-fraction heatmaps for a couple of common phases
    for target in ("LIQUID", "FE17ND2", "ND2FE14B"):
        if any(target in (r["phases"] if r else ()) for r in results):
            out2 = THIS_DIR / f"{tag}_{target}_{int(T)}K.png"
            plot_phase_fraction(elements, T, x1, x2, results, target, out2)


if __name__ == "__main__":
    main()