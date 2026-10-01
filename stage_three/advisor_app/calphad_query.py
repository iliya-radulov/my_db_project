"""
calphad_query.py — Single-point pycalphad equilibrium for the advisor app.

Loads and caches the merged FE-ND-B database in memory on first call,
then runs individual equilibrium points quickly (~2-4 s each).
"""

import sys
from pathlib import Path

THIS_DIR  = Path(__file__).resolve().parent   # advisor_app/
STAGE3    = THIS_DIR.parent                   # stage_three/
PROJ_ROOT = STAGE3.parent                     # my_db_project/
TDB_DIR   = PROJ_ROOT / "data" / "tdb" / "sgte_binary"

sys.path.insert(0, str(STAGE3))
from tdb_lookup import build_index, find_binaries, select_preferred

from pycalphad import Database, equilibrium, variables as v
import numpy as np
from grid_lookup import lookup as _grid_lookup, AVAILABLE_T as _GRID_T

# ── In-process DB cache (loaded once, reused for every request) ───────────────
_DB_CACHE: dict = {}


def _merge_tdb(paths):
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


def _get_db(elements: list[str]):
    """Load and cache merged TDB for the given element set."""
    key = tuple(sorted(elements))
    if key in _DB_CACHE:
        return _DB_CACHE[key]

    index = build_index(TDB_DIR)
    cand  = find_binaries(elements, index)
    if len(cand) < 3:
        raise RuntimeError(f"Missing binary TDB files — found only {len(cand)} pairs for {elements}")

    selected  = {p: select_preferred(f) for p, f in cand.items()}
    tdb_paths = sorted(selected.values(), key=lambda p: p.name)
    merged    = _merge_tdb(tdb_paths)

    # Write temp file so pycalphad can parse it, then delete
    tmp = STAGE3 / f"{''.join(sorted(elements))}_advisor_tmp.tdb"
    tmp.write_text(merged, encoding="utf-8")
    db = Database(str(tmp))
    tmp.unlink(missing_ok=True)

    phases = list(db.phases.keys())
    _DB_CACHE[key] = (db, phases)
    print(f"[calphad_query] DB loaded: {len(phases)} phases for {elements}")
    return db, phases


# ── Assessment logic ──────────────────────────────────────────────────────────
def _assess(phase_fracs: list[tuple[str, float]]) -> str:
    names = [p for p, _ in phase_fracs]
    has_target  = "FE17ND2" in names
    has_liquid  = "LIQUID"  in names

    if not has_target:
        return "no_target"
    if not has_liquid:
        return "solid"
    liquid_frac = next((f for p, f in phase_fracs if p == "LIQUID"), 0.0)
    if liquid_frac > 0.5:
        return "warning"
    return "good"


# ── Public API ────────────────────────────────────────────────────────────────
# Default temperatures: grid-backed ones first, 800K falls back to live calc
DEFAULT_TEMPS = [800, 1000, 1100, 1300, 1375, 1450, 1600]


def run_equilibrium(x_nd: float, x_fe: float, x_b: float,
                    temperatures: list[int] | None = None) -> dict:
    """
    Run single-point equilibrium for FE-ND-B at each temperature.

    Returns:
        {
          "composition": {x_nd, x_fe, x_b},   # normalized
          "results": [
              {"T": 1375, "T_C": 1101.85, "phases": [{"name":..,"fraction":..}],
               "status": "good"|"warning"|"solid"|"no_target"|"error"},
              ...
          ],
          "error": str | None
        }
    """
    if temperatures is None:
        temperatures = DEFAULT_TEMPS

    # Normalize composition
    total = x_nd + x_fe + x_b
    if total <= 0:
        return {"error": "All fractions are zero.", "results": []}
    x_nd /= total
    x_fe /= total
    x_b  /= total

    # Load DB only if we'll need live calculations
    _db_loaded = False
    db = phases = species = None

    def _ensure_db():
        nonlocal _db_loaded, db, phases, species
        if _db_loaded:
            return True
        try:
            db, phases = _get_db(["FE", "ND", "B"])
            species = [e for e in ["FE", "ND", "B", "VA"] if e in db.elements]
            _db_loaded = True
            return True
        except Exception as e:
            return str(e)

    results = []

    for T in temperatures:
        # ── Try grid lookup first (instant) ──────────────────────────────────
        grid_pf = _grid_lookup(x_nd, x_fe, x_b, T)
        if grid_pf is not None:
            pf = [{"name": p, "fraction": round(f, 4)} for p, f in grid_pf]
            status = _assess([(d["name"], d["fraction"]) for d in pf])
            results.append({
                "T":      T,
                "T_C":    round(T - 273.15, 1),
                "phases": pf,
                "status": status,
                "source": "grid",
            })
            continue

        # ── Fall back to live pycalphad ───────────────────────────────────────
        err = _ensure_db()
        if err is not True:
            results.append({
                "T": T, "T_C": round(T - 273.15, 1),
                "phases": [], "status": "error", "error": str(err),
            })
            continue

        try:
            res = equilibrium(
                db, species, phases,
                {v.X("ND"): x_nd, v.X("B"): x_b, v.T: float(T), v.P: 101325},
            )
            phase_arr = np.asarray(res["Phase"].values).flatten()
            np_arr    = np.asarray(res["NP"].values).flatten()

            pf = []
            for p, n in zip(phase_arr, np_arr):
                if not p or p == "":
                    continue
                try:
                    n = float(n)
                except Exception:
                    continue
                if not np.isfinite(n) or n < 1e-3:
                    continue
                pf.append({"name": str(p), "fraction": round(n, 4)})

            pf.sort(key=lambda x: -x["fraction"])
            status = _assess([(d["name"], d["fraction"]) for d in pf])

            results.append({
                "T":      T,
                "T_C":    round(T - 273.15, 1),
                "phases": pf,
                "status": status,
                "source": "live",
            })

        except Exception as e:
            results.append({
                "T":      T,
                "T_C":    round(T - 273.15, 1),
                "phases": [],
                "status": "error",
                "error":  str(e),
            })

    return {
        "composition": {
            "x_nd": round(x_nd, 4),
            "x_fe": round(x_fe, 4),
            "x_b":  round(x_b,  4),
        },
        "results": results,
    }
