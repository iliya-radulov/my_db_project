"""
grid_lookup.py — Fast nearest-neighbour lookup over pre-computed ternary grids.

Loads the pkl files produced by phase_diagram_ternary_v3.py (one per temperature)
and builds a scipy KD-tree for each.  Given a composition (x_fe, x_b) and a
temperature, it returns the phase fractions at the nearest grid point in O(log N).

Coordinate convention (matches the pkl files):
    x1 = x_Fe   x2 = x_B    x_Nd = 1 - x_Fe - x_B

Fallback behaviour:
  - Returns None when the requested temperature has no pkl file.
  - Returns None when the nearest grid point is farther than MAX_DIST
    (composition units), so the caller can fall back to live pycalphad.
  - Returns None when the nearest grid point is marked not-stable or has
    no phases (convergence failure in the original grid run).

Usage (standalone test):
    python stage_three/advisor_app/grid_lookup.py
"""

from __future__ import annotations
import pickle
from pathlib import Path
from functools import lru_cache

import numpy as np
from scipy.spatial import cKDTree

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).resolve().parent          # advisor_app/
STAGE3    = THIS_DIR.parent                          # stage_three/
CACHE_DIR = STAGE3 / "cache"

# Temperatures with existing N=200 pkl files
AVAILABLE_T = [800, 1000, 1100, 1200, 1300, 1375, 1450, 1600]

# Distance threshold: ~3-4× the grid spacing at N=200
# Grid spacing ≈ 1/sqrt(19700) ≈ 0.007; threshold = 0.025 bridges convergence holes
MAX_DIST = 0.025


# ── Internal grid store (loaded once per process) ─────────────────────────────
_grids: dict[int, tuple[cKDTree, list[dict]]] = {}
_loaded = False


def _load_all(cache_dir: Path = CACHE_DIR) -> None:
    """Load every available pkl file into _grids.  Called lazily on first use."""
    global _loaded
    if _loaded:
        return

    for T in AVAILABLE_T:
        pkl = cache_dir / f"FENDB_{T}K_N200_v3.pkl"
        if not pkl.exists():
            continue

        with open(pkl, "rb") as f:
            data = pickle.load(f)

        x1      = data["x1"]          # x_Nd
        x2      = data["x2"]          # x_B
        results = data["results"]

        # Keep only stable points that have at least one phase
        mask = [
            bool(r.get("stable")) and len(r.get("phases", ())) > 0
            for r in results
        ]
        mask_arr = np.array(mask)

        pts = np.column_stack([x1[mask_arr], x2[mask_arr]])
        good_results = [r for r, m in zip(results, mask) if m]

        _grids[T] = (cKDTree(pts), good_results)

    _loaded = True
    print(f"[grid_lookup] Loaded {len(_grids)} temperature grids from {cache_dir}")


# ── Public API ────────────────────────────────────────────────────────────────
def lookup(
    x_nd: float,
    x_fe: float,
    x_b:  float,
    T:    int,
    cache_dir: Path = CACHE_DIR,
) -> list[tuple[str, float]] | None:
    """
    Return phase fractions at the nearest grid point for (x_fe, x_b) at T.

    Parameters
    ----------
    x_nd, x_fe, x_b : mole fractions (x_nd is unused — kept for call-site
                       convenience; the grid is indexed by x_fe and x_b)
    T                : temperature in K (must be in AVAILABLE_T)

    Returns
    -------
    list of (phase_name, mole_fraction) sorted by fraction descending,
    or None if the lookup cannot be satisfied (unknown T, no stable point
    nearby, or grid not loaded).
    """
    _load_all(cache_dir)

    if T not in _grids:
        return None

    tree, results = _grids[T]
    dist, idx = tree.query([x_fe, x_b])  # grid coords: (x_Fe, x_B)

    if dist > MAX_DIST:
        return None

    r = results[idx]
    pf = list(zip(r["phases"], r["nps"]))
    pf.sort(key=lambda x: -x[1])
    return pf


def available_temperatures() -> list[int]:
    """Return the list of temperatures that have a loaded grid."""
    _load_all()
    return sorted(_grids.keys())


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Available temperatures:", available_temperatures())

    # (x_nd, x_fe, x_b, T, label)
    test_cases = [
        (0.118, 0.824, 0.059, 1375, "Nd2Fe14B stoich"),
        (0.15,  0.790, 0.06,  1375, "Nd-rich"),
        (0.10,  0.830, 0.07,  1375, "Fe-rich"),
        (0.118, 0.824, 0.059, 1100, "stoich 1100K"),
        (0.118, 0.824, 0.059, 1600, "stoich 1600K"),
    ]

    for x_nd, x_fe, x_b, T, label in test_cases:
        result = lookup(x_nd, x_fe, x_b, T)
        if result is None:
            print(f"  {label:25s} → MISS (fallback needed)")
        else:
            phases_str = "  ".join(f"{p}={f:.3f}" for p, f in result)
            print(f"  {label:25s} → {phases_str}")
