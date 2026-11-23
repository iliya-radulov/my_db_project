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

from prototype_match import (
    EXACT_MATCH,
    LISTED_OTHER_TERNARY,
    NEAREST_PROTOTYPE,
    NO_DFT_ENTRY,
    PrototypeFilter,
    cap_prototypes,
    classify,
    provenance_label,
    rank_candidates,
)

# Exact CODATA 2019 conversion: 1 eV/particle = 96.48533212331002 kJ/mol
EV_PER_ATOM_TO_KJ_PER_MOL = 96.48533212331002
SISSO_T_MIN = 300.0
SISSO_T_MAX = 2000.0


def mp_key_file_candidates() -> list[Path]:
    """Where a Materials Project key file is looked for, in order.

    1. ../../back_up/API/MP_API_KEY.txt relative to the working directory: the location the desktop app's
       literature search (stage_two.alloy.alloy_entry_full_v2.get_api_key) already uses, so that one key
       serves the literature check and the SISSO step;
    2. back_up/API/MP_API_KEY.txt two folders above the repository (relative to this file, as before).
    """
    return [
        Path("../../back_up/API") / "MP_API_KEY.txt",
        Path(__file__).resolve().parents[2] / "back_up" / "API" / "MP_API_KEY.txt",
    ]


def _resolve_mp_api_key(explicit_key: str | None = None) -> str:
    if explicit_key:
        return explicit_key.strip()
    env_key = os.environ.get("MP_API_KEY", "").strip()
    if env_key:
        return env_key
    for fallback in mp_key_file_candidates():
        if fallback.exists():
            key = fallback.read_text(encoding="utf-8").strip()
            if key:
                return key
    raise RuntimeError(
        "MP_API_KEY not found: set the MP_API_KEY environment variable or put the key in "
        + " or ".join(str(c) for c in mp_key_file_candidates())
    )


def _spacegroup(entry) -> str | None:
    """Space-group symbol of the entry's structure (provenance, e.g. Fm-3c for NaZn13-type)."""
    try:
        return str(entry.structure.get_space_group_info(symprec=0.1)[0])
    except Exception:
        return None


def build_candidates(
    chemsys_entries: list,
    target_comp: Composition,
    pd0: PhaseDiagram,
    prototype_filter: PrototypeFilter | None,
    include_subsystems: bool = False,
) -> dict[str, dict]:
    """Exact matches, simplex-safe nearest prototypes (if a filter is given) and, with
    include_subsystems, the other ternary phases (listed only), keyed by entry_id."""
    n_target = len(target_comp.elements)

    def _e_hull(entry):
        try:
            return float(pd0.get_e_above_hull(entry, allow_negative=True))
        except Exception:
            data = getattr(entry, "data", None) or {}
            val = data.get("e_above_hull", data.get("energy_above_hull"))
            return float(val) if val is not None else None

    candidates: dict[str, dict] = {}
    for entry in chemsys_entries:
        if entry.composition.is_element:
            continue
        info = classify(target_comp, entry.composition, prototype_filter) if prototype_filter else None
        if info is None and prototype_filter is None:
            # filter disabled: exact reduced formula only
            if entry.composition.reduced_composition == target_comp.reduced_composition:
                info = {"match_type": EXACT_MATCH, "delta_x": 0.0, "delta_x_euclid": 0.0, "anchor_delta": 0.0}
        if info is None and include_subsystems and len(entry.composition.elements) == n_target:
            info = {"match_type": LISTED_OTHER_TERNARY, "delta_x": None, "delta_x_euclid": None,
                    "anchor_delta": None}
        if info is None:
            continue
        eid = str(entry.entry_id)
        e_hull_0k = _e_hull(entry)
        candidates[eid] = {
            "material_id": eid,
            "formula": entry.composition.reduced_formula,
            "prototype_formula": entry.composition.reduced_formula,
            **info,
            # kept for older readers: True only for an entry at the target composition
            "matches_target_composition": info["match_type"] == EXACT_MATCH,
            "composition_fractions": {
                str(el): round(amt, 6)
                for el, amt in entry.composition.fractional_composition.get_el_amt_dict().items()
            },
            "e_above_hull_0K_eV_atom": round(e_hull_0k, 5) if e_hull_0k is not None else None,
            "dGf_sisso_kJ_mol_atom": {},
        }
    return candidates


def attach_sisso_energies(pd0: PhaseDiagram, candidates: dict[str, dict], temperatures: list[float]) -> None:
    """Bartel SISSO formation Gibbs energies (kJ/mol-atom) of every candidate, per temperature."""
    for T in temperatures:
        T_float = float(T)
        t_key = str(T_float)
        if not (SISSO_T_MIN <= T_float <= SISSO_T_MAX):
            for c in candidates.values():
                c["dGf_sisso_kJ_mol_atom"][t_key] = None
            continue
        gibbs_entries = GibbsComputedStructureEntry.from_pd(pd0, temp=T_float)
        pd_T = PhaseDiagram(gibbs_entries)
        gibbs_by_id = {str(ge.entry_id): ge for ge in gibbs_entries}
        for eid, c in candidates.items():
            ge = gibbs_by_id.get(eid)
            if ge is None:
                c["dGf_sisso_kJ_mol_atom"][t_key] = None
                continue
            c["dGf_sisso_kJ_mol_atom"][t_key] = round(
                float(pd_T.get_form_energy_per_atom(ge)) * EV_PER_ATOM_TO_KJ_PER_MOL, 4
            )


def sisso_report_from_entries(
    formula: str,
    chemsys_entries: list,
    temperatures: list[float],
    include_subsystems: bool = False,
    prototype_filter: PrototypeFilter | None = None,
) -> dict:
    """Core of predict_sisso_formation_gibbs without the network call (testable offline)."""
    target_comp = Composition(formula)
    elements = sorted(str(el) for el in target_comp.elements)
    base = {
        "formula": formula,
        "reduced_formula": target_comp.reduced_formula,
        "elements": elements,
        "prototype_filter": prototype_filter.as_dict() if prototype_filter else None,
    }
    if not chemsys_entries:
        return {**base, "candidates": [], "match_type": NO_DFT_ENTRY,
                "error": f"No Materials Project entries found for chemical system {'-'.join(elements)}"}

    # T = 0 K hull, built once: used for e_above_hull and (via from_pd) for every temperature.
    pd0 = PhaseDiagram(chemsys_entries)
    candidates = build_candidates(chemsys_entries, target_comp, pd0, prototype_filter, include_subsystems)
    if not candidates:
        return {**base, "candidates": [], "match_type": NO_DFT_ENTRY,
                "note": "No Materials Project entry at the target composition or within the "
                        "prototype filter (novel composition)."}

    attach_sisso_energies(pd0, candidates, temperatures)
    ranked = cap_prototypes(rank_candidates(list(candidates.values())),
                            prototype_filter.max_prototypes if prototype_filter else 0)
    by_id = {str(e.entry_id): e for e in chemsys_entries}
    for c in ranked:
        c["spacegroup"] = _spacegroup(by_id[c["material_id"]]) if c["material_id"] in by_id else None
    top = next((c for c in ranked if c["match_type"] in (EXACT_MATCH, NEAREST_PROTOTYPE)), None)
    return {
        **base,
        "method": "Bartel_2018_SISSO_pymatgen",
        "units": "kJ/mol-atom",
        "match_type": top["match_type"] if top else NO_DFT_ENTRY,
        "fallback_used": bool(top and top["match_type"] == NEAREST_PROTOTYPE),
        "candidates": ranked,
    }


def predict_sisso_formation_gibbs(
    formula: str,
    temperatures: list[float],
    api_key: str | None = None,
    include_subsystems: bool = False,
    nearest_prototype: bool = True,
    prototype_filter: PrototypeFilter | None = None,
) -> dict:
    """
    Query Materials Project for the chemical system of `formula` (all subsystems, so the elemental
    references are consistent) and compute Bartel SISSO finite-T formation Gibbs energies
    (kJ/mol-atom) via pymatgen's GibbsComputedStructureEntry + PhaseDiagram.

    Candidates: entries at the target composition (match_type "exact_match") and, with
    nearest_prototype=True (default), up to `prototype_filter.max_prototypes` simplex-safe nearest
    prototypes (match_type "nearest_prototype", see prototype_match.py). With nearest_prototype
    False only exact matches are used. With neither, the report has match_type "no_dft_entry".
    """
    from mp_api.client import MPRester

    key = _resolve_mp_api_key(api_key)
    elements = sorted(str(el) for el in Composition(formula).elements)
    with MPRester(key) as mpr:
        chemsys_entries = mpr.get_entries_in_chemsys(
            elements,
            additional_criteria={"thermo_types": ["GGA_GGA+U"]},
        )
    flt = (prototype_filter or PrototypeFilter()) if nearest_prototype else PrototypeFilter(max_dx=0.0, max_prototypes=0)
    return sisso_report_from_entries(formula, chemsys_entries, temperatures, include_subsystems, flt)


def compare_with_calphad_ensemble(
    sisso_report: dict, ensemble_report: dict, sisso_uncertainty_kJ: float = 0.0
) -> list[dict]:
    """
    Combine Bartel SISSO ΔG_f(T) with the CALPHAD binary-ensemble threshold ΔG_f*(T).

    exact_match         a stability verdict: margin = ΔG_f(SISSO) - median(ΔG_f*) < 0 means the
                        candidate is favoured over the competing binary assemblage.
    nearest_prototype   NOT at the target composition, so no stability verdict: the row carries
                        verdict "prototype_indicative_only", comparable=False, the prototype
                        formula and the composition distance. The margin is given for orientation
                        only (the threshold is at the target composition, the energy is not).
    listed_other_ternary (include_subsystems) is skipped.

    `sisso_uncertainty_kJ` (kJ/mol-atom, default 0.0) widens the verdict of exact matches:
    "stable" needs ΔG_f + u < p05, "metastable" needs ΔG_f - u > p95, anything else is
    "borderline". With the default 0.0 the verdict contains NO model error, and the CALPHAD band
    (about 1 kJ/mol-atom wide for Nd-Fe-B at 800 K) is much narrower than the error of a SISSO
    estimate, so "borderline" will rarely be reported. Set the value from the validation error of
    the descriptor (Bartel et al. 2018) before reading the verdicts.
    """
    if not ensemble_report.get("gates", {}).get("gate_passed"):
        return []

    u = abs(float(sisso_uncertainty_kJ))
    rows = []
    dist_by_T = ensemble_report.get("threshold_distribution", {})
    for cand in sisso_report.get("candidates", []):
        match_type = cand.get("match_type") or (
            EXACT_MATCH if cand.get("matches_target_composition", True) else LISTED_OTHER_TERNARY
        )
        if match_type not in (EXACT_MATCH, NEAREST_PROTOTYPE):
            continue
        for t_key, dgf_sisso in cand["dGf_sisso_kJ_mol_atom"].items():
            t_stats = dist_by_T.get(t_key)
            if dgf_sisso is None or t_stats is None:
                continue
            med = t_stats["median_kJ"]
            margin = round(dgf_sisso - med, 4)
            if match_type == NEAREST_PROTOTYPE:
                verdict = "prototype_indicative_only"
            elif dgf_sisso + u < t_stats["p05_kJ"]:
                verdict = "stable_across_band"
            elif dgf_sisso - u > t_stats["p95_kJ"]:
                verdict = "metastable_above_band"
            else:
                verdict = "borderline_within_band"

            rows.append({
                "material_id": cand["material_id"],
                "formula": cand["formula"],
                "match_type": match_type,
                "prototype_formula": cand.get("prototype_formula", cand["formula"]),
                "delta_x": cand.get("delta_x"),
                "spacegroup": cand.get("spacegroup"),
                "comparable": match_type == EXACT_MATCH,
                "T_K": float(t_key),
                "dGf_sisso_kJ": dgf_sisso,
                "threshold_median_kJ": med,
                "threshold_p05_kJ": t_stats["p05_kJ"],
                "threshold_p95_kJ": t_stats["p95_kJ"],
                "stability_margin_kJ": margin,
                "sisso_uncertainty_kJ": u,
                "verdict": verdict,
                "competing_assemblage": t_stats["dominant_competing_assemblage"],
            })
    return rows


def format_comparison_table(rows: list[dict]) -> list[str]:
    """Monospace table with provenance in the first column (CLI and desktop preview)."""
    labels = [provenance_label(r) for r in rows]
    w = max([len("MP entry (formula, match)")] + [len(x) for x in labels])
    lines = [
        f"{'MP entry (formula, match)':<{w}} | {'T (K)':>6} | {'ΔG_SISSO':>9} | {'ΔG* Med':>8} | "
        f"{'[5%, 95%] Band':>17} | {'Margin':>8} | Verdict",
        "-" * (w + 80),
    ]
    for r, lab in zip(rows, labels):
        lines.append(
            f"{lab:<{w}} | {r['T_K']:>6.0f} | {r['dGf_sisso_kJ']:>+9.3f} | "
            f"{r['threshold_median_kJ']:>+8.3f} | [{r['threshold_p05_kJ']:>+6.2f}, {r['threshold_p95_kJ']:>+6.2f}] | "
            f"{r['stability_margin_kJ']:>+8.3f} | {r['verdict']}"
        )
    if any(r.get("match_type") == NEAREST_PROTOTYPE for r in rows):
        lines.append("nearest_prototype rows: different composition from the target; energy and margin are "
                     "for orientation only, not a stability verdict.")
    return lines


def add_prototype_arguments(ap: argparse.ArgumentParser) -> None:
    """CLI options shared with screen_ternary.py."""
    d = PrototypeFilter()
    g = ap.add_argument_group("nearest-prototype fallback")
    g.add_argument("--no-prototype-fallback", action="store_true",
                   help="exact Materials Project matches only")
    g.add_argument("--max-dx", type=float, default=d.max_dx,
                   help="largest composition distance (atomic fractions) of a prototype [%(default)s]")
    g.add_argument("--anchor-tol", type=float, default=d.anchor_tol,
                   help="allowed |Δx| of the anchor (minority) element [%(default)s]")
    g.add_argument("--anchor", nargs="+", default=None,
                   help="anchor element(s) a prototype must contain (default: minority element of the target)")
    g.add_argument("--site-group", action="append", default=[], metavar="EL1,EL2",
                   help="elements that substitute on one site, e.g. FE,SI; repeatable")
    g.add_argument("--max-prototypes", type=int, default=d.max_prototypes,
                   help="how many nearest prototypes to keep [%(default)s]")


def prototype_filter_from_args(args) -> PrototypeFilter | None:
    if args.no_prototype_fallback:
        return None
    return PrototypeFilter(
        max_dx=args.max_dx,
        anchor_tol=args.anchor_tol,
        anchors=tuple(a.upper() for a in args.anchor) if args.anchor else None,
        site_groups=tuple(tuple(x.strip().upper() for x in g.split(",")) for g in args.site_group),
        max_prototypes=args.max_prototypes,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--formula", required=True, help="Target formula, e.g. Nd2Fe14B or La7.1Fe82.1Si10.8")
    ap.add_argument("--temps", nargs="+", type=float, default=[800.0, 1000.0, 1200.0, 1300.0, 1375.0, 1450.0])
    ap.add_argument("--include-subsystems", action="store_true", help="Also LIST other ternary phases of the system (not compared with the CALPHAD threshold, which is at the target composition only)")
    add_prototype_arguments(ap)
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = ap.parse_args()

    flt = prototype_filter_from_args(args)
    res = predict_sisso_formation_gibbs(
        formula=args.formula,
        temperatures=args.temps,
        include_subsystems=args.include_subsystems,
        nearest_prototype=flt is not None,
        prototype_filter=flt,
    )

    print(f"\n=== Bartel SISSO Finite-T Formation Energy: {res['reduced_formula']} ===")
    if not res["candidates"]:
        print(f"[{NO_DFT_ENTRY}] " + (res.get("error") or res.get("note") or ""))
        return
    if res.get("fallback_used"):
        print("No exact Materials Project entry: NEAREST PROTOTYPE(S) below, at a different composition "
              "(indicative only, not a stability verdict).")

    for c in res["candidates"]:
        print(f"\n{provenance_label(c)}  spacegroup={c.get('spacegroup')}  "
              f"(0K E_hull = {c['e_above_hull_0K_eV_atom']} eV/atom)")
        for t_key, val in c["dGf_sisso_kJ_mol_atom"].items():
            shown = "n/a" if val is None else f"{val:+8.3f}"
            print(f"  T = {float(t_key):6.1f} K : ΔG_f(SISSO) = {shown} kJ/mol-atom")

    if args.out:
        args.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
