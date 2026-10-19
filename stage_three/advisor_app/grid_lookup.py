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
    Self-check: _check_convention() verifies at load time, by boron mass balance,
    that the stored coordinates are (x_Fe, x_Nd).
    (2026-10-19: two earlier checks based on corner phases failed on real grids —
    Nd is BCC between 1136 and 1297 K, and the last grid points near the boron
    corner do not converge. The mass balance depends on neither.)

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
MAX_DIST = 0.015

# Boron mole fraction of each phase of the merged Fe-Nd-B description (line compounds
# and boron-free phases). LIQUID and unlisted phases are skipped by the check below.
B_CONTENT = {
    "BETA_RHOMBO_B": 1.0, "NDB66": 66 / 67, "NDB6_D21": 6 / 7, "NDB4_D1E": 4 / 5,
    "ND2B5": 5 / 7, "MB_B27": 1 / 2, "M2B_C16": 1 / 3,
    "FE17ND2": 0.0, "FE17ND5": 0.0, "DHCP": 0.0, "BCC_A2": 0.0, "FCC_A1": 0.0, "HCP_A3": 0.0,
}


# ── Internal grid store (loaded once per process) ─────────────────────────────
_grids: dict[int, tuple[cKDTree, list[dict]]] = {}
_convention_stats: dict[int, tuple[int, float, float] | None] = {}
_loaded = False


def _check_convention(T: int, x1: np.ndarray, x2: np.ndarray, results: list):
    """Fail loudly unless x2 is x_Nd — by boron mass balance.

    For every converged point whose phases all have a fixed boron content, the phase
    fractions predict the point's boron content exactly. That prediction must equal
    x_B = 1 - x1 - x2 (convention x2 = x_Nd), not x_B = x2 (the swapped reading).
    Unlike a test on corner phases, this does not depend on Nd's allotropes or on
    which points converged. Returns (points used, mean error, mean error if swapped).
    """
    err_ok, err_swap = [], []
    for i, r in enumerate(results):
        if not (r and r.get("stable")) or any(p not in B_CONTENT for p in r["phases"]):
            continue
        total = sum(r["nps"]) or 1.0
        xb = sum(B_CONTENT[p] * n for p, n in zip(r["phases"], r["nps"])) / total
        err_ok.append(abs(xb - (1.0 - x1[i] - x2[i])))
        err_swap.append(abs(xb - x2[i]))
    if len(err_ok) < 50:
        print(f"[grid_lookup] {T} K: only {len(err_ok)} points usable for the convention check — skipped")
        return None
    e_ok, e_swap = float(np.mean(err_ok)), float(np.mean(err_swap))
    if e_ok > e_swap or e_ok > 0.02:
        raise RuntimeError(
            f"[grid_lookup] {T} K: boron mass balance fails for (x_Fe, x_Nd): mean error "
            f"{e_ok:.4f} vs {e_swap:.4f} for the swapped reading ({len(err_ok)} points). "
            "The pkl coordinate convention is not (x_Fe, x_Nd)."
        )
    return len(err_ok), e_ok, e_swap


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

        _convention_stats[T] = _check_convention(T, x1, x2, results)

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
    print("Convention check (boron mass balance, mean |error|):")
    for T, s in sorted(_convention_stats.items()):
        if s:
            print(f"    {T:5d} K: {s[0]:6d} points  error {s[1]:.5f}   (swapped reading: {s[2]:.3f})")
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
