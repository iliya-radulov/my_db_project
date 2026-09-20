"""
feasibility.py — Fast stability screen for a target phase.
target-phase stability scan
Given a ternary system, a target composition, and a range of hypothetical
formation enthalpies for the target phase, determine:
  - is the target phase stable at (T, ΔH_f)?
  - if not, what is the driving force for its formation?

Usage:
    python feasibility.py FE ND B 0.1176 0.8235 0.0588
        # ^ composition of Nd2Fe14B
"""

import sys
from pathlib import Path
import numpy as np
from pycalphad import Database, equilibrium, variables as v

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
from tdb_lookup import build_index, find_binaries, select_preferred

# Reuse merge from your existing script
from phase_diagram_ternary import merge_tdb_files

TDB_DIR = THIS_DIR.parent / "data" / "tdb" / "sgte_binary"


def parse_args():
    a = sys.argv[1:]
    if len(a) < 6:
        print("Usage: feasibility.py EL1 EL2 EL3 x1 x2 x3")
        sys.exit(1)
    els = [x.upper() for x in a[:3]]
    xs  = [float(x) for x in a[3:6]]
    return els, xs


def build_merged_db(elements):
    index = build_index(TDB_DIR)
    cand  = find_binaries(elements, index)
    if len(cand) < 3:
        raise RuntimeError("missing binary TDB")
    selected = {p: select_preferred(f) for p, f in cand.items()}
    paths = sorted(selected.values(), key=lambda p: p.name)
    merged = THIS_DIR / f"{''.join(elements)}_merged.tdb"
    merged.write_text(merge_tdb_files(paths), encoding="utf-8")
    return Database(str(merged)), merged


def add_hypothetical_phase(db, phase_name, elements, dHf):
    """
    Inject a simple stoichiometric line compound with formation enthalpy dHf
    (J/mol of formula unit) on top of the SER reference.

    For a proper screen, replace this with the real sublattice model of your
    candidate. Here we assume a 1:1:1 formula for illustration.
    """
    el1, el2, el3 = elements
    # Use SER Gibbs energies of the pure elements — pycalphad exposes these
    # via the DB; simplest is to reference GHSERxx symbols if present.
    # Fallback: build from the pure-element G functions in the DB.
    # For brevity we assume the DB has GHSER{el} symbols (SGTE convention).
    ghs = [f"GHSER{e}" for e in elements]
    expr = " + ".join(ghs) + f" + {dHf}"
    block = f"""
PHASE {phase_name} :{el1}{el2}{el3}: 1 1 1 !
CONSTITUENT {phase_name} :{el1}:{el2}:{el3}: !
PARAMETER G({phase_name},{el1}:{el2}:{el3};0)  298.15  {expr}  ;  6000  N !
"""
    tmp = THIS_DIR / f"_tmp_{phase_name}.tdb"
    tmp.write_text(block, encoding="utf-8")
    db2 = Database(str(tmp), fmt="tdb")
    # Merge into existing DB by concatenation — pycalphad doesn't have a
    # public "merge" but you can write both to one file. Simpler: append.
    # For robustness, write combined TDB:
    combined = THIS_DIR / f"_combined_{phase_name}.tdb"
    combined.write_text(
        open(db._filename if hasattr(db, "_filename") else "").read()
        if False else "",  # placeholder — see note below
        encoding="utf-8",
    )
    # NOTE: pycalphad's Database is immutable post-load. The clean way is to
    # append the block to the merged TDB text *before* loading. See
    # build_db_with_phase() below — that's the recommended path.
    tmp.unlink(missing_ok=True)
    return db2


def build_db_with_phase(elements, dHf, phase_name="TARGET"):
    """Merge binaries, then append the hypothetical phase, then load."""
    index = build_index(TDB_DIR)
    cand  = find_binaries(elements, index)
    selected = {p: select_preferred(f) for p, f in cand.items()}
    paths = sorted(selected.values(), key=lambda p: p.name)
    text = merge_tdb_files(paths)

    el1, el2, el3 = elements
    block = f"""
PHASE {phase_name} :{el1}{el2}{el3}: 1 1 1 !
CONSTITUENT {phase_name} :{el1}:{el2}:{el3}: !
PARAMETER G({phase_name},{el1}:{el2}:{el3};0)  298.15
   GHSER{el1}+GHSER{el2}+GHSER{el3}+({dHf})  ;  6000  N !
"""
    combined = THIS_DIR / f"_combined_{''.join(elements)}_{int(dHf)}.tdb"
    combined.write_text(text + "\n" + block, encoding="utf-8")
    db = Database(str(combined))
    return db, combined


def stability_at(db, elements, phases, x, T, phase_name="TARGET"):
    """Return (stable?, NP_target, driving_force_J_per_mol)."""
    el1, el2, el3 = elements
    species = [e for e in elements + ["VA"] if e in db.elements]
    res = equilibrium(
        db, species, phases,
        {v.X(el1): x[0], v.X(el2): x[1], v.T: T, v.P: 101325},
    )
    ph_arr = res["Phase"].values.flatten()
    np_arr = res["NP"].values.flatten()
    gm     = float(res["GM"].values.flatten()[0])

    target_np = 0.0
    for p, n in zip(ph_arr, np_arr):
        if p == phase_name and np.isfinite(n):
            target_np = float(n)

    # Driving force: compare equilibrium GM to hypothetical pure target GM.
    # For a rough signal, use the difference between the equilibrium GM and
    # the GM of the target phase evaluated at x. pycalphad can give you the
    # latter via a single-phase equilibrium with the phase restricted.
    try:
        res_target = equilibrium(
            db, species, [phase_name],
            {v.X(el1): x[0], v.X(el2): x[1], v.T: T, v.P: 101325},
        )
        gm_target = float(res_target["GM"].values.flatten()[0])
        dG = gm - gm_target   # >0 means target is metastable/unstable
    except Exception:
        dG = np.nan

    return target_np > 1e-3, target_np, dG


def main():
    elements, x = parse_args()
    print(f"Target: {'-'.join(elements)}  x = {x}")
    print(f"Sum check: {sum(x):.4f}  (should be ~1.0)\n")

    T_grid   = np.linspace(800, 1800, 15)
    dHf_grid = np.array([0, -10, -25, -50, -75, -100]) * 1000  # J/mol

    print(f"{'T (K)':>7} | " + " | ".join(f"ΔH={d/1000:>5.0f}k" for d in dHf_grid))
    print("-" * (9 + 12 * len(dHf_grid)))

    for T in T_grid:
        row = []
        for dHf in dHf_grid:
            db, combined = build_db_with_phase(elements, dHf)
            phases = list(db.phases.keys())
            try:
                stable, np_t, dG = stability_at(db, elements, phases, x, T)
                mark = "✓" if stable else ("~" if np_t > 0 else "·")
                row.append(f"{mark} {dG/1000:>+6.1f}")
            except Exception as e:
                row.append(f"  ERR   ")
            finally:
                combined.unlink(missing_ok=True)
        print(f"{T:>7.0f} | " + " | ".join(row))

    print("\nLegend:  ✓ = target stable (NP>0)   · = not stable")
    print("         numbers = driving force ΔG (kJ/mol), >0 means metastable")


if __name__ == "__main__":
    main()