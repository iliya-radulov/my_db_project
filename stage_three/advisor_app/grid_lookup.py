"""
grid_lookup.py — Fast nearest-neighbour lookup over pre-computed ternary grids.

Loads the pkl files produced by phase_diagram_ternary_v3.py (one per temperature)
and builds a scipy KD-tree for each.  Given a composition and a temperature, it
returns the phase fractions at the nearest converged grid point in O(log N).

Coordinate convention (matches the pkl files — CHECKED AGAINST THE GENERATOR):
    phase_diagram_ternary_v3.py FE ND B  sets  v.X(FE) = x1, v.X(ND) = x2
    so:   x1 = x_Fe    x2 = x_Nd    x_B = 1 - x_Fe - x_Nd
    (cache files are named FENDB_*, i.e. element order FE, ND, B)

    History: on 2026-09-28 this was changed to (x_Fe, x_B), which swapped Nd and
    B for every grid-backed result.  Restored to (x_Fe, x_Nd) on 2026-10-04.
    Self-check: _check_convention() below asserts that the Nd-rich corner of
    each grid contains DHCP (Nd) and not the B-rich borides.

Fallback behaviour:
  - Returns None when the requested temperature has no pkl file.
  - Returns None when the nearest converged grid point is farther than MAX_DIST
    (composition units), so the caller can fall back to live pycalphad.
  - Points whose original equilibrium did not converge are excluded from the tree.

Usage (standalone test):
    python stage_three/advisor_app/grid_lookup.py
"""

from __future__ import annotations
import pickle
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).resolve().parent          # advisor_app/
STAGE3    = THIS_DIR.parent                          # stage_three/
CACHE_DIR = STAGE3 / "cache"

# Temperatures with existing N=200 pkl files
AVAILABLE_T = [800, 1000, 1100, 1200, 1300, 1375, 1450, 1600]

# Distance threshold in (x_Fe, x_Nd) composition units.
# Grid spacing at N=200 is 0.005; 0.025 ≈ 5 spacings.
# NOTE: widened from 0.015 on 2026-09-28 while the Nd/B swap was present —
# re-check whether 0.015 is enough now (see __main__ test output).
MAX_DIST = 0.025


# ── Internal grid store (loaded once per process) ─────────────────────────────
_grids: dict[int, tuple[cKDTree, list[dict]]] = {}
_loaded = False


def _check_convention(T: int, x1: np.ndarray, x2: np.ndarray, results: list) -> None:
    """Fail loudly if x2 is not x_Nd: the most Nd-rich converged point must contain DHCP."""
    ok = [i for i, r in enumerate(results) if r and r.get("stable")]
    if not ok:
        return
    i_nd = max(ok, key=lambda i: x2[i])            # largest x2 → should be Nd corner
    phases = results[i_nd]["phases"]
    if "DHCP" not in phases and "LIQUID" not in phases:
        raise RuntimeError(
            f"[grid_lookup] {T} K: most x2-rich point (x1={x1[i_nd]:.3f}, x2={x2[i_nd]:.3f}) "
            f"has phases {phases} — expected DHCP or LIQUID (Nd corner). "
            "The pkl coordinate convention is not (x_Fe, x_Nd)."
        )


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

        x1      = np.asarray(data["x1"])   # x_Fe
        x2      = np.asarray(data["x2"])   # x_Nd
        results = data["results"]

        _check_convention(T, x1, x2, results)

        # Keep only converged points that have at least one phase
        mask = np.array([
            bool(r and r.get("stable")) and len(r.get("phases", ())) > 0
            for r in results
        ])

        pts = np.column_stack([x1[mask], x2[mask]])
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
    Return phase fractions at the nearest converged grid point for the
    composition at T.

    Parameters
    ----------
    x_nd, x_fe, x_b : mole fractions (normalised by the caller; x_b is not
                      needed for the query because the grid is indexed by
                      (x_Fe, x_Nd))
    T               : temperature in K (must be in AVAILABLE_T)

    Returns
    -------
    list of (phase_name, mole_fraction) sorted by fraction descending,
    or None if the lookup cannot be satisfied (unknown T, or no converged
    point within MAX_DIST).
    """
    _load_all(cache_dir)

    if T not in _grids:
        return None

    tree, results = _grids[T]
    dist, idx = tree.query([x_fe, x_nd])   # grid coords: (x_Fe, x_Nd)

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
    print("Lever-rule expectation for Nd2Fe14B stoich in DHCP+FE17ND2+M2B_C16:")
    print("    FE17ND2 ≈ 0.789   M2B_C16 ≈ 0.176   DHCP ≈ 0.035   (800–1100 K)\n")

    # (x_nd, x_fe, x_b, T, label)
    test_cases = [
        (0.1176, 0.8235, 0.0588,  800, "Nd2Fe14B stoich 800K"),
        (0.1176, 0.8235, 0.0588, 1375, "Nd2Fe14B stoich 1375K"),
        (0.15,   0.79,   0.06,    800, "Nd-rich 800K"),     # expect ≈ 0.749 / 0.180 / 0.071
        (0.10,   0.83,   0.07,    800, "Fe-rich 800K"),     # expect ≈ 0.771 / 0.210 / 0.019
    ]

    for x_nd, x_fe, x_b, T, label in test_cases:
        tree, _ = _grids.get(T, (None, None))
        result = lookup(x_nd, x_fe, x_b, T)
        if result is None:
            print(f"  {label:25s} → MISS (fallback needed)")
            continue
        d, _ = tree.query([x_fe, x_nd])
        phases_str = "  ".join(f"{p}={f:.3f}" for p, f in result)
        print(f"  {label:25s} → {phases_str}   (nearest point at d={d:.4f})")
