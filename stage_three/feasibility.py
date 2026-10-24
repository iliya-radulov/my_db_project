"""
feasibility.py — Fast stability screen for a hypothetical target phase.

Given a ternary system and the composition of a target compound, scan a grid
of temperatures and hypothetical formation enthalpies and report:
  - is the target phase stable at (T, ΔH_f)?
  - the driving force: how far its Gibbs energy sits above/below the
    competing equilibrium assemblage built from the binary phases;
  - the threshold ΔH_f below which the target is stable, and the competing phases.

Usage:
    python feasibility.py FE ND B 0.8235 0.1176 0.0588
        #                          ^ x_FE   x_ND   x_B   (same order as elements)
        # Nd2Fe14B: Fe=14/17≈0.8235, Nd=2/17≈0.1176, B=1/17≈0.0588
    Results are also written to feasibility_<SYSTEM>.json (for the paper's figure).

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
    threshold = −dG at ΔH_f = 0 = G_competing − Σ x_i GHSER_i

Changes 24 Oct 2026 (paper 3, Section 6):
  - merge with tdb_merge.py (the text merge lost Fe from LIQUID/BCC/FCC and doubled
    shared parameters) and check the merged description against its binaries;
  - SER function names are looked up in the database. The old version built them as
    GHSER + element symbol, i.e. GHSERB for boron; the SGTE files call it GHSERBB, and
    pycalphad sets an UNDEFINED function to zero without a warning, so the target lacked
    its boron term (x_B * G_B; 0.55 kJ/mol-atom at 800 K);
  - independent check: the target at ΔH_f = 0 must equal Σ x_i GHSER_i at 800 K;
  - threshold column, competing phases, JSON output.
"""

import json
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
from tdb_merge import merged_text, check_edges

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
def binary_paths(elements):
    index = build_index(TDB_DIR)
    cand  = find_binaries(elements, index)
    if len(cand) < 3:
        raise RuntimeError(
            f"Need 3 binary TDBs for {elements}; found {len(cand)}: {list(cand)}"
        )
    selected = {p: select_preferred(f) for p, f in cand.items()}
    return sorted(selected.values(), key=lambda p: p.name)


def load_tdb_text(text, tag):
    """Write TDB text to a temp file next to this script and load it.
    pycalphad's Database is immutable once loaded, so the text must be final."""
    path = THIS_DIR / f"_feas_{tag}.tdb"
    path.write_text(text, encoding="utf-8")
    return Database(str(path)), path


def ser_function(db, el):
    """Name of the SER Gibbs-energy function of *el* in *db* (GHSERFE, GHSERB, GHSERBB ...).
    Raises if there is none: pycalphad would silently set an undefined function to zero."""
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return name
    raise KeyError(f"no SER function for {el} in the merged database "
                   f"(tried GHSER{el}, GHSER{el}{el})")


def target_phase_block(elements, sites, dHf_atom, ser, phase_name=PHASE_NAME):
    """
    TDB block for a stoichiometric target phase.
    Uses the % (default) model letter — the old ':FENDB:' form was parsed by
    pycalphad as unknown type characters F, E, N, D, B and crashed.
    *ser* maps each element to its SER function name in the database.
    """
    el1, el2, el3 = elements
    n_total = sum(sites)
    terms   = "+".join(f"{n}*{ser[el]}" for el, n in zip(elements, sites))
    return f"""
PHASE {phase_name} % 3 {sites[0]} {sites[1]} {sites[2]} !
CONSTITUENT {phase_name} :{el1}:{el2}:{el3}: !
PARAMETER G({phase_name},{el1}:{el2}:{el3};0)  298.15
   {terms}+({n_total * dHf_atom})  ;  6000  N !
"""


# ── thermodynamics ───────────────────────────────────────────────────────────
def conditions(elements, x, T):
    el1, el2, _ = elements
    return {v.X(el1): x[0], v.X(el2): x[1], v.T: float(T), v.P: 101325, v.N: 1}


def species_for(db, elements):
    return [e for e in elements + ["VA"] if e in db.elements]


def competing(db_bin, elements, x, T):
    """Equilibrium GM (J/mol-atom) and phase fractions of the binary-phase assemblage at x."""
    res = equilibrium(db_bin, species_for(db_bin, elements),
                      list(db_bin.phases.keys()), conditions(elements, x, T))
    phases = {str(p): round(float(f), 3)
              for p, f in zip(res["Phase"].values.ravel(), res["NP"].values.ravel())
              if p and np.isfinite(f) and f > 1e-3}
    return float(np.nanmean(res["GM"].values)), phases


def target_gm(db_full, elements, T, phase_name=PHASE_NAME):
    """GM of the target phase alone (J/mol-atom); a line compound has one point."""
    res = calculate(db_full, species_for(db_full, elements), phase_name,
                    T=float(T), P=101325, N=1)
    return float(np.nanmin(res["GM"].values))


def target_fraction(db_full, elements, x, T, phase_name=PHASE_NAME):
    """Phase fraction of the target in the full equilibrium (0 if absent)."""
    res = equilibrium(db_full, species_for(db_full, elements),
                      list(db_full.phases.keys()), conditions(elements, x, T))
    phases = res["Phase"].values.flatten()
    fracs  = res["NP"].values.flatten()
    return float(sum(n for p, n in zip(phases, fracs)
                     if p == phase_name and np.isfinite(n)))


def check_reference(db_full0, elements, x, ser, T=800.0):
    """Independent check: at ΔH_f = 0 the target must equal Σ x_i GHSER_i(T)."""
    g_target = target_gm(db_full0, elements, T)
    g_ref = sum(xi * float(db_full0.symbols[ser[el]].subs({v.T: float(T)}))
                for el, xi in zip(elements, x))
    print(f"Reference check at {T:.0f} K: target(ΔH=0) {g_target:.1f}, "
          f"Σ x·GHSER {g_ref:.1f} J/mol-atom")
    if abs(g_target - g_ref) > 1.0:
        raise RuntimeError("the target's reference energy is wrong — stop")


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    elements, x_in = parse_args()
    sites   = composition_to_sites(x_in)
    n_total = sum(sites)
    x       = [s / n_total for s in sites]     # snap to exact stoichiometry
    system  = "".join(elements)

    print(f"System:        {'-'.join(elements)}")
    print(f"Input x:       {x_in}   (sum {sum(x_in):.4f})")
    print(f"Stoichiometry: " + " ".join(f"{e}{n}" for e, n in zip(elements, sites))
          + f"   → exact x = [{', '.join(f'{xi:.4f}' for xi in x)}]\n")

    # Build every database once, up front.
    paths = binary_paths(elements)
    print("Binary files:", ", ".join(p.name for p in paths))
    base_text = merged_text(paths)
    tmp_files = []
    db_bin, p = load_tdb_text(base_text, f"{system}_binary")
    tmp_files.append(p)
    try:
        print("Edge check of the merged description:")
        if not check_edges(db_bin, paths):
            raise RuntimeError("merged description does not reproduce its binaries — stop")
        ser = {el: ser_function(db_bin, el) for el in elements}
        print("SER functions:", ", ".join(f"{el}: {name}" for el, name in ser.items()), "\n")

        db_full = {}
        for dHf in DHF_GRID:
            text = base_text + "\n" + target_phase_block(elements, sites, dHf, ser)
            db_full[dHf], p = load_tdb_text(text, f"{system}_{int(dHf)}")
            tmp_files.append(p)
        check_reference(db_full[0.0], elements, x, ser)

        head = " | ".join(f"ΔH={d/1000:>4.0f}k" for d in DHF_GRID)
        print(f"\n{'T (K)':>7} | {head} | thresh. | competing phases")
        print("-" * (32 + 11 * len(DHF_GRID)))

        rows, first_err = [], True
        for T in T_GRID:
            row, rec = [], {"T": float(T), "dG": {}, "stable": {}}
            try:
                g_comp, mix = competing(db_bin, elements, x, T)
            except Exception:
                g_comp, mix = np.nan, {}
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
                    rec["dG"][f"{dHf/1000:.0f}"] = dG / 1000
                    rec["stable"][f"{dHf/1000:.0f}"] = bool(np_t > 1e-3)
                except Exception:
                    row.append("   ERR    ")
                    if first_err:
                        print(f"\n--- first error (T={T:.0f} K, ΔH={dHf/1000:.0f} kJ/mol-atom) ---")
                        traceback.print_exc()
                        print("---\n")
                        first_err = False
            thr = -rec["dG"].get("0", np.nan)
            rec["threshold"], rec["mix"] = thr, mix
            rows.append(rec)
            mix_s = " + ".join(f"{k} {f:.3f}" for k, f in mix.items())
            print(f"{T:>7.0f} | " + "|".join(row) + f"| {thr:>+7.2f} | {mix_s}")
    finally:
        for f in tmp_files:
            f.unlink(missing_ok=True)

    out = THIS_DIR / f"feasibility_{system}.json"
    out.write_text(json.dumps({"elements": elements, "sites": sites, "x": x,
                               "binaries": [p.name for p in paths], "ser": ser,
                               "rows": rows}, indent=1), encoding="utf-8")
    print("\nLegend:  ✓ target stable   ~ trace   · not stable")
    print("         ΔH = formation enthalpy of target, kJ/mol-atom (vs SER)")
    print("         number = dG = G_target − G_competing, kJ/mol-atom  (<0 target wins)")
    print("         thresh. = ΔH_f below which the target is stable (= −dG at ΔH = 0)")
    print(f"Written: {out.name}")


if __name__ == "__main__":
    main()
