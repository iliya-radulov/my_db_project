"""
ternary_threshold.py — Compute the Nd₂Fe₁₄B feasibility threshold from a
full ternary Nd–Fe–B CALPHAD assessment (Chen 2019, Hallemans 1995,
NIMS Nd-mag-STAM, …) at the same temperatures as the Step 1 batch.

The ternary files already contain Nd₂Fe₁₄B as a modelled phase with its
own G function. To compare apples-to-apples with the batch (where
Nd₂Fe₁₄B is a hypothetical line compound), we SUPPRESS the Nd₂Fe₁₄B
phase in the ternary file, compute equilibrium at the Nd₂Fe₁₄B
composition (14/17, 2/17, 1/17), and read:

    threshold [kJ/mol-atom] = (G_competing − G_SER) / 1000
    with   G_SER = Σ xᵢ · GHSER_i(T)

The threshold is the ΔH_f at which Nd₂Fe₁₄B would become competitive
with the binary assemblage described by the ternary file. It is directly
on the axis of our 78-point ensemble.

Usage (from stage_three/, main venv):

    # first find the Nd₂Fe₁₄B phase name in your file:
    grep "PHASE " /path/to/Chen2019.tdb

    # then run with that phase name:
    python ternary_threshold.py /path/to/Chen2019.tdb --suppress FE14ND2B
    python ternary_threshold.py /path/to/Hallemans1995.tdb --suppress TAU

If --suppress is omitted the script lists all phases and exits so you
can pick the Nd₂Fe₁₄B name.
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ELEMENTS   = ["FE", "ND", "B"]
X_TARGET   = {"FE": 14/17, "ND": 2/17, "B": 1/17}
TEMPERATURES = [800, 1000, 1100, 1200, 1300, 1375, 1450, 1600]


def ser_function(db, el: str) -> str:
    """GHSER symbol name for *el*; raises KeyError if neither GHSER<EL>
    nor GHSER<EL><EL> is defined (SGTE uses GHSERBB for boron)."""
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return name
    raise KeyError(f"no SER function for {el} in {list(db.symbols)[:5]}…")


def g_ser_at(db, ser_names: dict, T_K: float, xs: dict) -> float:
    """Σ xᵢ · GHSERᵢ(T) in J/mol-atom, by symbolic substitution."""
    from pycalphad import variables as v
    total = 0.0
    for el, xi in xs.items():
        if xi < 1e-12:
            continue
        total += xi * float(db.symbols[ser_names[el]].subs({v.T: float(T_K)}))
    return total


def threshold_at_T(db, ser_names: dict, T_K: float,
                   phases_to_use: list[str]) -> tuple[float, dict]:
    """Compute (threshold_kJ, competing_phase_fractions) at T_K."""
    from pycalphad import equilibrium, variables as v

    comps = ["FE", "ND", "B", "VA"]
    conds = {v.X("ND"): X_TARGET["ND"], v.X("B"): X_TARGET["B"],
             v.T: T_K, v.P: 101325, v.N: 1}

    eq = equilibrium(db, comps, phases_to_use, conds, calc_opts={"pdens": 500})
    G_competing = float(eq.GM.squeeze().values)

    G_SER = g_ser_at(db, ser_names, T_K, X_TARGET)
    threshold_kJ = (G_competing - G_SER) / 1000.0

    phase_fracs = {}
    try:
        for ph in phases_to_use:
            nf = float(eq.NP.sel(Phase=ph).squeeze().values)
            if nf > 0.01:
                phase_fracs[ph] = round(nf, 3)
    except Exception:
        pass

    return threshold_kJ, phase_fracs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tdb", type=Path, help="path to the ternary TDB file")
    ap.add_argument("--suppress", type=str, default=None,
                    help="exact name of the Nd₂Fe₁₄B phase to drop from "
                         "the equilibrium; if omitted, phases are listed "
                         "and the script exits")
    ap.add_argument("--out", type=Path, default=None,
                    help="optional JSON output file")
    args = ap.parse_args()

    from pycalphad import Database
    db = Database(str(args.tdb))

    all_phases = sorted(db.phases.keys())
    print(f"File:   {args.tdb.name}")
    print(f"Phases: {len(all_phases)}")
    for p in all_phases:
        print(f"  {p}")

    if not args.suppress:
        print("\nNo --suppress given; rerun with the Nd₂Fe₁₄B phase name.")
        return

    if args.suppress not in db.phases:
        print(f"\nERROR: phase '{args.suppress}' not in this database.")
        print(f"Available phases are listed above.")
        return

    phases_to_use = [p for p in all_phases if p != args.suppress]

    try:
        ser_names = {el: ser_function(db, el) for el in ELEMENTS}
    except KeyError as e:
        print(f"ERROR: {e}")
        return

    print(f"\nSuppressing {args.suppress}; using {len(phases_to_use)} phases.")
    print(f"SER lookup: {ser_names}\n")

    print(f"{'T (K)':>7}  {'threshold (kJ/mol-atom)':>25}  competing phases")
    print("-" * 80)

    out_rows = []
    for T in TEMPERATURES:
        try:
            thr, phases = threshold_at_T(db, ser_names, T, phases_to_use)
            mix = " + ".join(f"{k} {v:.3f}" for k, v in phases.items())
            print(f"{T:>7.0f}  {thr:>+25.4f}  {mix}")
            out_rows.append({"T_K": T, "threshold_kJ_mol_atom": round(thr, 4),
                             "competing_phases": phases})
        except Exception as e:
            print(f"{T:>7.0f}  {'ERROR':>25}  {e}")
            out_rows.append({"T_K": T, "threshold_kJ_mol_atom": None,
                             "error": str(e)})

    if args.out:
        payload = {
            "tdb_file": args.tdb.name,
            "suppressed_phase": args.suppress,
            "composition_Fe_Nd_B": [X_TARGET["FE"], X_TARGET["ND"], X_TARGET["B"]],
            "ser_names": ser_names,
            "kernel_version": "ternary (direct), GHSER-based reference",
            "rows": out_rows,
        }
        args.out.write_text(json.dumps(payload, indent=2))
        print(f"\nWritten: {args.out}")


if __name__ == "__main__":
    main()
