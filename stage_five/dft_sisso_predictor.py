#!/usr/bin/env python3
"""
stage_five/dft_sisso_predictor.py

Finite-temperature formation Gibbs energy predictor using Materials Project DFT
entries + pymatgen's GibbsComputedStructureEntry (Bartel et al., Nat. Commun. 2018
SISSO vibrational/electronic free-energy descriptor).

Converts eV/atom -> kJ/mol-atom so values sit directly on the same energy axis as
CALPHAD binary-ensemble thresholds ΔG_f*(T).

Usage:
    export MP_API_KEY=...
    python stage_five/dft_sisso_predictor.py --formula Nd2Fe14B --temps 800 1000 1300 1375
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pymatgen.analysis.phase_diagram import PhaseDiagram
from pymatgen.core import Composition
from pymatgen.entries.computed_entries import GibbsComputedStructureEntry

# Exact CODATA 2019 conversion: 1 eV/particle = 96.48533212331002 kJ/mol
EV_PER_ATOM_TO_KJ_PER_MOL = 96.48533212331002
SISSO_T_MIN = 300.0
SISSO_T_MAX = 2000.0


def _resolve_mp_api_key(explicit_key: str | None = None) -> str:
    if explicit_key:
        return explicit_key.strip()
    env_key = os.environ.get("MP_API_KEY", "").strip()
    if env_key:
        return env_key
    fallback = Path(__file__).resolve().parents[2] / "back_up" / "API" / "MP_API_KEY.txt"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8").strip()
    raise RuntimeError("MP_API_KEY not found in environment or fallback file.")


def predict_sisso_formation_gibbs(
    formula: str,
    temperatures: list[float],
    api_key: str | None = None,
    include_subsystems: bool = False,
) -> dict:
    """
    Query Materials Project for `formula` (and its chemical system's elemental
    references), compute Bartel SISSO finite-T formation Gibbs energies (kJ/mol-atom)
    via pymatgen's GibbsComputedStructureEntry + PhaseDiagram.
    """
    from mp_api.client import MPRester

    key = _resolve_mp_api_key(api_key)
    target_comp = Composition(formula)
    target_reduced = target_comp.reduced_composition
    elements = sorted(str(el) for el in target_comp.elements)

    with MPRester(key) as mpr:
        chemsys_entries = mpr.get_entries_in_chemsys(
            elements,
            additional_criteria={"thermo_types": ["GGA_GGA+U"]},
        )

    if not chemsys_entries:
        return {
            "formula": formula,
            "reduced_formula": target_reduced.reduced_formula,
            "elements": elements,
            "candidates": [],
            "error": f"No Materials Project entries found for chemical system {'-'.join(elements)}",
        }

    # Index target entries by entry_id (GibbsComputedStructureEntry.from_entries
    # may drop entries without structures, so never index by raw list position).
    candidates: dict[str, dict] = {}
    for entry in chemsys_entries:
        is_exact = entry.composition.reduced_composition == target_reduced
        is_ternary = include_subsystems and len(entry.composition.elements) == len(elements)
        if is_exact or is_ternary:
            eid = str(entry.entry_id)
            e_hull_0k = entry.data.get("e_above_hull") if hasattr(entry, "data") else None
            candidates[eid] = {
                "material_id": eid,
                "formula": entry.composition.reduced_formula,
                "composition_fractions": {
                    str(el): round(amt, 6)
                    for el, amt in entry.composition.fractional_composition.get_el_amt_dict().items()
                },
                "e_above_hull_0K_eV_atom": round(float(e_hull_0k), 5) if e_hull_0k is not None else None,
                "dGf_sisso_kJ_mol_atom": {},
            }

    if not candidates:
        return {
            "formula": formula,
            "reduced_formula": target_reduced.reduced_formula,
            "elements": elements,
            "candidates": [],
            "note": "Exact formula not present in Materials Project (novel composition).",
        }

    # Convert full chemical system once per temperature and evaluate formation Gibbs
    # energy against the temperature-dependent GibbsComputedStructureEntry hull.
    for T in temperatures:
        T_float = float(T)
        t_key = str(T_float)
        if not (SISSO_T_MIN <= T_float <= SISSO_T_MAX):
            for c in candidates.values():
                c["dGf_sisso_kJ_mol_atom"][t_key] = None
            continue

        gibbs_entries = GibbsComputedStructureEntry.from_entries(chemsys_entries, temp=T_float)
        pd_T = PhaseDiagram(gibbs_entries)
        gibbs_by_id = {str(ge.entry_id): ge for ge in gibbs_entries}

        for eid, c in candidates.items():
            ge = gibbs_by_id.get(eid)
            if ge is None:
                c["dGf_sisso_kJ_mol_atom"][t_key] = None
                continue
            dgf_ev_per_atom = float(pd_T.get_form_energy_per_atom(ge))
            c["dGf_sisso_kJ_mol_atom"][t_key] = round(
                dgf_ev_per_atom * EV_PER_ATOM_TO_KJ_PER_MOL, 4
            )

    sorted_candidates = sorted(
        candidates.values(),
        key=lambda c: (
            c["e_above_hull_0K_eV_atom"] if c["e_above_hull_0K_eV_atom"] is not None else 999.0,
            next((v for v in c["dGf_sisso_kJ_mol_atom"].values() if v is not None), 999.0),
        ),
    )

    return {
        "formula": formula,
        "reduced_formula": target_reduced.reduced_formula,
        "elements": elements,
        "method": "Bartel_2018_SISSO_pymatgen",
        "units": "kJ/mol-atom",
        "candidates": sorted_candidates,
    }


def compare_with_calphad_ensemble(sisso_report: dict, ensemble_report: dict) -> list[dict]:
    """
    Combine Bartel SISSO ΔG_f(T) with the CALPHAD binary-ensemble threshold ΔG_f*(T).
    Negative margin (ΔG_f_SISSO - ΔG_f*_median < 0) indicates the candidate phase is
    thermodynamically stable against the competing binary assemblage.
    """
    if not ensemble_report.get("gates", {}).get("gate_passed"):
        return []

    rows = []
    dist_by_T = ensemble_report.get("threshold_distribution", {})
    for cand in sisso_report.get("candidates", []):
        for t_key, dgf_sisso in cand["dGf_sisso_kJ_mol_atom"].items():
            t_stats = dist_by_T.get(t_key)
            if dgf_sisso is None or t_stats is None:
                continue
            med = t_stats["median_kJ"]
            margin = round(dgf_sisso - med, 4)
            if dgf_sisso < t_stats["p05_kJ"]:
                verdict = "stable_across_band"
            elif dgf_sisso <= t_stats["p95_kJ"]:
                verdict = "borderline_within_band"
            else:
                verdict = "metastable_above_band"

            rows.append({
                "material_id": cand["material_id"],
                "formula": cand["formula"],
                "T_K": float(t_key),
                "dGf_sisso_kJ": dgf_sisso,
                "threshold_median_kJ": med,
                "threshold_p05_kJ": t_stats["p05_kJ"],
                "threshold_p95_kJ": t_stats["p95_kJ"],
                "stability_margin_kJ": margin,
                "verdict": verdict,
                "competing_assemblage": t_stats["dominant_competing_assemblage"],
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formula", required=True, help="Target formula, e.g. Nd2Fe14B")
    ap.add_argument("--temps", nargs="+", type=float, default=[800.0, 1000.0, 1200.0, 1300.0, 1375.0, 1450.0])
    ap.add_argument("--include-subsystems", action="store_true", help="Also score other ternary phases in MP")
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = ap.parse_args()

    res = predict_sisso_formation_gibbs(
        formula=args.formula,
        temperatures=args.temps,
        include_subsystems=args.include_subsystems,
    )

    print(f"\n=== Bartel SISSO Finite-T Formation Energy: {res['reduced_formula']} ===")
    if not res["candidates"]:
        print(res.get("error") or res.get("note"))
        return

    for c in res["candidates"]:
        print(f"\nMP ID: {c['material_id']}  (0K E_hull = {c['e_above_hull_0K_eV_atom']} eV/atom)")
        for t_key, val in c["dGf_sisso_kJ_mol_atom"].items():
            print(f"  T = {float(t_key):6.1f} K : ΔG_f(SISSO) = {val:+8.3f} kJ/mol-atom")

    if args.out:
        args.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
