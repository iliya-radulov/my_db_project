"""
feasibility.py — Fast stability screen for a hypothetical target phase.

Given a ternary system and the composition of a target compound, scan a grid
of temperatures and hypothetical formation enthalpies and report:
  - is the target phase stable at (T, ΔH_f)?
  - the driving force: how far its Gibbs energy sits above/below the
    competing equilibrium assemblage built from the binary phases.

Usage:
    python feasibility.py FE ND B 0.8235 0.1176 0.0588
        #                          ^ x_FE   x_ND   x_B   (same order as elements)
        # Nd2Fe14B: Fe=14/17≈0.8235, Nd=2/17≈0.1176, B=1/17≈0.0588

Model of the target phase:
    Stoichiometric line compound, 3 sublattices, site ratios taken from the
    input composition (e.g. 14:2:1).  G per formula unit:
        G = n1*GHSER1 + n2*GHSER2 + n3*GHSER3 + n_total*ΔH_f
    so ΔH_f is in J per mole of ATOMS (the usual convention) relative to SER.

Conventions:
    pycalphad GM (from equilibrium and calculate) is per mole of atoms.
    dG = G_target − G_competing   (kJ/mol-atom)
         dG < 0  → target wins (stable)
         dG > 0  → target metastable
"""

import sys
import traceback
import warnings
from fractions import Fraction
from math import gcd
from functools import reduce
from pathlib import Path

import numpy as np
from pycalphad import Database, equilibrium, calculate, variables as v

# SGTE TDBs define magnetic TYPE_DEFINITIONs that pycalphad warns about on
# every load; they're harmless here and drown out the table.
warnings.filterwarnings("ignore", category=UserWarning, module="pycalphad.io.tdb")

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
from tdb_lookup import build_index, find_binaries, select_preferred
from phase_diagram_ternary_v3 import merge_tdb_files

TDB_DIR = THIS_DIR.parent / "data" / "tdb" / "sgte_binary"

PHASE_NAME = "TARGET"
T_GRID     = np.linspace(800, 1800, 15)                        # K
DHF_GRID   = np.array([0, -5, -10, -15, -20, -30]) * 1000.0    # J/mol-atom


# ── input ────────────────────────────────────────────────────────────────────
def parse_args():
    a = sys.argv[1:]
    if len(a) < 6:
        print("Usage: feasibility.py EL1 EL2 EL3 x1 x2 x3")
        print("       Fractions follow the element order and should sum to 1.")
        sys.exit(1)
    els = [s.upper() for s in a[:3]]
    xs  = [float(s) for s in a[3:6]]
    return els, xs


def composition_to_sites(x, max_denom=30):
    """Smallest integer site ratios for x, e.g. [0.8235, 0.1176, 0.0588] → [14, 2, 1]."""
    fracs  = [Fraction(xi).limit_denominator(max_denom) for xi in x]
    lcm_d  = reduce(lambda a, b: a * b // gcd(a, b), (f.denominator for f in fracs))
    nums   = [f.numerator * (lcm_d // f.denominator) for f in fracs]
    g      = reduce(gcd, nums)
    return [n // g for n in nums]


# ── database construction ────────────────────────────────────────────────────
def merged_binary_text(elements):
    """Text of the merged three binary TDBs for *elements*."""
    index = build_index(TDB_DIR)
    cand  = find_binaries(elements, index)
    if len(cand) < 3:
        raise RuntimeError(
            f"Need 3 binary TDBs for {elements}; found {len(cand)}: {list(cand)}"
        )
    selected = {p: select_preferred(f) for p, f in cand.items()}
    paths    = sorted(selected.values(), key=lambda p: p.name)
    return merge_tdb_files(paths)


def load_tdb_text(text, tag):
    """Write TDB text to a temp file next to this script and load it.
    pycalphad's Database is immutable once loaded, so the text must be final."""
    path = THIS_DIR / f"_feas_{tag}.tdb"
    path.write_text(text, encoding="utf-8")
    return Database(str(path)), path


def target_phase_block(elements, sites, dHf_atom, phase_name=PHASE_NAME):
    """
    TDB block for a stoichiometric target phase.
    Uses the % (default) model letter — the old ':FENDB:' form was parsed by
    pycalphad as unknown type characters F, E, N, D, B and crashed.
    """
    el1, el2, el3 = elements
    n1, n2, n3    = sites
    n_total       = sum(sites)
    return f"""
PHASE {phase_name} % 3 {n1} {n2} {n3} !
CONSTITUENT {phase_name} :{el1}:{el2}:{el3}: !
PARAMETER G({phase_name},{el1}:{el2}:{el3};0)  298.15
   {n1}*GHSER{el1}+{n2}*GHSER{el2}+{n3}*GHSER{el3}+({n_total * dHf_atom})  ;  6000  N !
"""


# ── thermodynamics ───────────────────────────────────────────────────────────
def conditions(elements, x, T):
    el1, el2, _ = elements
    return {v.X(el1): x[0], v.X(el2): x[1], v.T: T, v.P: 101325, v.N: 1}


def species_for(db, elements):
    return [e for e in elements + ["VA"] if e in db.elements]


def competing_gm(db_bin, elements, x, T):
    """Equilibrium GM (J/mol-atom) of the binary-phase assemblage at x, no target."""
    res = equilibrium(db_bin, species_for(db_bin, elements),
                      list(db_bin.phases.keys()), conditions(elements, x, T))
    return float(np.nanmean(res["GM"].values))


def target_gm(db_full, elements, T, phase_name=PHASE_NAME):
    """GM of the target phase alone (J/mol-atom); a line compound has one point."""
    res = calculate(db_full, species_for(db_full, elements), phase_name,
                    T=T, P=101325, N=1)
    return float(np.nanmin(res["GM"].values))


def target_fraction(db_full, elements, x, T, phase_name=PHASE_NAME):
    """Phase fraction of the target in the full equilibrium (0 if absent)."""
    res = equilibrium(db_full, species_for(db_full, elements),
                      list(db_full.phases.keys()), conditions(elements, x, T))
    phases = res["Phase"].values.flatten()
    fracs  = res["NP"].values.flatten()
    return float(sum(n for p, n in zip(phases, fracs)
                     if p == phase_name and np.isfinite(n)))


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    elements, x_in = parse_args()
    sites   = composition_to_sites(x_in)
    n_total = sum(sites)
    x       = [s / n_total for s in sites]     # snap to exact stoichiometry

    print(f"System:        {'-'.join(elements)}")
    print(f"Input x:       {x_in}   (sum {sum(x_in):.4f})")
    print(f"Stoichiometry: " + " ".join(f"{e}{n}" for e, n in zip(elements, sites))
          + f"   → exact x = [{', '.join(f'{xi:.4f}' for xi in x)}]\n")

    # Build every database once, up front.
    base_text = merged_binary_text(elements)
    tmp_files = []
    db_bin, p = load_tdb_text(base_text, f"{''.join(elements)}_binary")
    tmp_files.append(p)
    db_full = {}
    for dHf in DHF_GRID:
        text = base_text + "\n" + target_phase_block(elements, sites, dHf)
        db_full[dHf], p = load_tdb_text(text, f"{''.join(elements)}_{int(dHf)}")
        tmp_files.append(p)

    head = " | ".join(f"ΔH={d/1000:>4.0f}k" for d in DHF_GRID)
    print(f"{'T (K)':>7} | {head}")
    print("-" * (10 + 11 * len(DHF_GRID)))

    first_err = True
    try:
        for T in T_GRID:
            row = []
            try:
                g_comp = competing_gm(db_bin, elements, x, T)
            except Exception:
                g_comp = np.nan
                if first_err:
                    print(f"\n--- error in competing-phase equilibrium at T={T:.0f} K ---")
                    traceback.print_exc()
                    print("---\n")
                    first_err = False

            for dHf in DHF_GRID:
                try:
                    np_t = target_fraction(db_full[dHf], elements, x, T)
                    dG   = target_gm(db_full[dHf], elements, T) - g_comp
                    mark = "✓" if np_t > 1e-3 else ("~" if np_t > 1e-6 else "·")
                    val  = f"{dG/1000:>+6.1f}" if np.isfinite(dG) else "   nan"
                    row.append(f"{mark} {val} ")
                except Exception:
                    row.append("   ERR    ")
                    if first_err:
                        print(f"\n--- first error (T={T:.0f} K, ΔH={dHf/1000:.0f} kJ/mol-atom) ---")
                        traceback.print_exc()
                        print("---\n")
                        first_err = False
            print(f"{T:>7.0f} | " + "|".join(row))
    finally:
        for f in tmp_files:
            f.unlink(missing_ok=True)

    print("\nLegend:  ✓ target stable   ~ trace   · not stable")
    print("         ΔH = formation enthalpy of target, kJ/mol-atom (vs SER)")
    print("         number = dG = G_target − G_competing, kJ/mol-atom  (<0 target wins)")


if __name__ == "__main__":
    main()
