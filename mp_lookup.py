"""
mp_lookup.py

Given a target alloy composition, checks the Materials Project for known
phases and classifies the result into four tiers:

  1. info available     -- same elements, near-identical composition
  2. similar             -- same elements, different ratio
  3. partial match       -- a subsystem (one fewer element) is known
  4. no information      -- nothing found in any subsystem

Requires a free API key: register at https://materialsproject.org,
then set it as an environment variable:

    export MP_API_KEY="your_key_here"

Install: pip install mp-api

NOTE: Materials Project data is DFT-computed (0 K, no entropy/temperature
effects). A "stable" result here means thermodynamically plausible, not
"confirmed to form under your furnace conditions" -- treat tier 1/2 hits
as a strong lead to chase in the literature, not a guarantee.
"""

import itertools
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
from mp_api.client import MPRester


@dataclass
class MatchResult:
    tier: int
    tier_label: str
    material_id: str
    formula: str
    elements: List[str]
    energy_above_hull: Optional[float]  # eV/atom; 0 = stable, higher = less stable
    theoretical: bool                   # True = never experimentally observed in MP
    composition_distance: Optional[float]  # 0-1, only meaningful within same element set


TIER_LABELS = {
    1: "info available (near-exact match)",
    2: "similar (same elements, different ratio)",
    3: "partial match (subsystem known, not full system)",
    4: "no information found",
}


def _normalize(comp: Dict[str, float]) -> Dict[str, float]:
    total = sum(comp.values())
    return {el: amt / total for el, amt in comp.items()}


def _composition_distance(target: Dict[str, float], candidate: Dict[str, float]) -> float:
    """0 = identical, 1 = completely disjoint. Only meaningful when target
    and candidate share the same element set -- otherwise it will always
    show a large distance, which is expected (that's what makes it a
    different tier)."""
    target = _normalize(target)
    candidate = _normalize(candidate)
    elements = set(target) | set(candidate)
    diff = sum(abs(target.get(el, 0.0) - candidate.get(el, 0.0)) for el in elements)
    return diff / 2  # L1 distance over probability-simplex-like vectors, capped at 1


def lookup(
    target_composition: Dict[str, float],
    api_key: Optional[str] = None,
    near_match_threshold: float = 0.05,
) -> List[MatchResult]:
    """
    target_composition: e.g. {"Fe": 0.70, "Al": 0.15, "Ni": 0.15} (atomic
    fractions -- this is exactly the shape produced by
    CalculationResult.as_composition_dict() in alloy_calculator.py)
    """
    api_key = api_key or os.environ.get("MP_API_KEY")
    if not api_key:
        raise ValueError(
            "No API key found. Pass api_key=... or set the MP_API_KEY "
            "environment variable. Register free at materialsproject.org"
        )

    target_elements = sorted(target_composition.keys())
    fields = [
        "material_id", "formula_pretty", "elements",
        "energy_above_hull", "theoretical", "composition",
    ]

    results: List[MatchResult] = []

    with MPRester(api_key) as mpr:
        # --- exact element-set match (tiers 1 & 2) ---
        exact_chemsys = "-".join(target_elements)
        exact_docs = mpr.materials.summary.search(chemsys=exact_chemsys, fields=fields)

        for doc in exact_docs:
            candidate_comp = {str(el): amt for el, amt in doc.composition.items()}
            dist = _composition_distance(target_composition, candidate_comp)
            tier = 1 if dist <= near_match_threshold else 2
            results.append(MatchResult(
                tier=tier, tier_label=TIER_LABELS[tier],
                material_id=str(doc.material_id), formula=doc.formula_pretty,
                elements=[str(e) for e in doc.elements],
                energy_above_hull=doc.energy_above_hull,
                theoretical=doc.theoretical, composition_distance=dist,
            ))

        # --- subsystem match: drop one element at a time (tier 3) ---
        if not any(r.tier in (1, 2) for r in results) and len(target_elements) > 1:
            for subset in itertools.combinations(target_elements, len(target_elements) - 1):
                sub_chemsys = "-".join(sorted(subset))
                sub_docs = mpr.materials.summary.search(chemsys=sub_chemsys, fields=fields)
                for doc in sub_docs:
                    results.append(MatchResult(
                        tier=3, tier_label=TIER_LABELS[3],
                        material_id=str(doc.material_id), formula=doc.formula_pretty,
                        elements=[str(e) for e in doc.elements],
                        energy_above_hull=doc.energy_above_hull,
                        theoretical=doc.theoretical, composition_distance=None,
                    ))

    if not results:
        results.append(MatchResult(
            tier=4, tier_label=TIER_LABELS[4],
            material_id="", formula="", elements=target_elements,
            energy_above_hull=None, theoretical=False, composition_distance=None,
        ))

    # best matches first: lower tier, then closer composition, then more stable
    results.sort(key=lambda r: (
        r.tier,
        r.composition_distance if r.composition_distance is not None else 1.0,
        r.energy_above_hull if r.energy_above_hull is not None else 999,
    ))
    return results


def print_report(target_composition: Dict[str, float], results: List[MatchResult]) -> None:
    print(f"Target composition: {target_composition}\n")
    seen_tiers = set()
    for r in results:
        if r.tier not in seen_tiers:
            print(f"--- Tier {r.tier}: {r.tier_label} ---")
            seen_tiers.add(r.tier)
        if r.tier == 4:
            print("  (nothing found in any subsystem either)")
            continue
        stability = "unknown" if r.energy_above_hull is None else (
            "stable" if r.energy_above_hull == 0 else f"{r.energy_above_hull:.3f} eV/atom above hull"
        )
        origin = "theoretical only" if r.theoretical else "experimentally known"
        dist_str = f", distance={r.composition_distance:.3f}" if r.composition_distance is not None else ""
        print(f"  {r.material_id}  {r.formula:<15}  {stability}  ({origin}){dist_str}")
    print()


@dataclass
class SynthesisRecipe:
    target_formula: str
    synthesis_type: str
    precursors: List[str]
    operations: List[str]   # human-readable one-liners, e.g. "Heating at 800 C for 6.0 h under Ar"
    doi: str
    paragraph: str


def _format_operation(op) -> str:
    conditions = op.conditions
    parts = [op.type]
    heating_temp = getattr(conditions, "heating_temperature", None)
    heating_time = getattr(conditions, "heating_time", None)
    atmosphere = getattr(conditions, "heating_atmosphere", None)
    if heating_temp:
        # heating_temperature is a list of value objects (min/max ranges are text-mined,
        # so can contain more than one step) -- just report the first for a quick read
        try:
            parts.append(f"at {heating_temp[0].values[0]:.0f} C")
        except (IndexError, AttributeError, TypeError):
            pass
    if heating_time:
        try:
            parts.append(f"for {heating_time[0].values[0]:.1f} h")
        except (IndexError, AttributeError, TypeError):
            pass
    if atmosphere:
        parts.append(f"under {', '.join(atmosphere)}")
    return " ".join(parts)


def lookup_synthesis(
    formula: str,
    api_key: Optional[str] = None,
    max_results: int = 5,
) -> List[SynthesisRecipe]:
    """
    Text-mined synthesis recipes for a given target formula (e.g. "AlFe2Ni"),
    from the Materials Project's literature-mined synthesis dataset.
    Coverage is oxide-heavy (that's what most of the source literature was
    mined from) -- for metallic alloys, don't be surprised if this comes
    back empty even when the summary search finds a real phase. An empty
    result here means "not text-mined," not "no such synthesis exists."
    """
    api_key = api_key or os.environ.get("MP_API_KEY")
    if not api_key:
        raise ValueError("No API key found. Pass api_key=... or set MP_API_KEY.")

    recipes: List[SynthesisRecipe] = []
    with MPRester(api_key) as mpr:
        docs = mpr.materials.synthesis.search(
            target_formula=formula, chunk_size=max_results
        )
        for doc in docs[:max_results]:
            ops = []
            for op in doc.operations or []:
                try:
                    ops.append(_format_operation(op))
                except Exception:
                    ops.append(op.type)
            recipes.append(SynthesisRecipe(
                target_formula=doc.targets_formula_s[0] if doc.targets_formula_s else formula,
                synthesis_type=str(doc.synthesis_type),
                precursors=doc.precursors_formula_s or [],
                operations=ops,
                doi=doc.doi or "",
                paragraph=doc.paragraph_string or "",
            ))
    return recipes


def print_synthesis_report(recipes: List[SynthesisRecipe]) -> None:
    if not recipes:
        print("No text-mined synthesis recipes found for this formula.\n"
              "(Coverage is oxide-heavy -- absence here doesn't mean no "
              "synthesis route exists, just that it wasn't in the mined corpus.)\n")
        return
    for i, r in enumerate(recipes, 1):
        print(f"[{i}] {r.target_formula}  ({r.synthesis_type})")
        print(f"    precursors: {', '.join(r.precursors) or 'unknown'}")
        for op in r.operations:
            print(f"    - {op}")
        print(f"    source: https://doi.org/{r.doi}" if r.doi else "    source: (no DOI on record)")
        print()


if __name__ == "__main__":
    # Example: your Fe70 Al15 Ni15 alloy
    target = {"Nd": 0.2, "Fe": 0.75, "B": 0.15}
    
    # Read API key from a separate file, e.g. secrets/MP_API_KEY.txt
    key_file = Path("../../back_up/API") / "MP_API_KEY.txt"    
    # Option A: set MP_API_KEY as an environment variable (recommended --
    # keeps the key out of any file you might later share or commit).
    #api_key = os.environ.get("MP_API_KEY")

    # Option B: paste your key directly here instead, e.g.:
    try:
        api_key = key_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        api_key = None
        print(f"API key file not found: {key_file}")

    if not api_key:
        print("Set MP_API_KEY environment variable first (free key from "
              "materialsproject.org), then re-run this script.")
    else:
        results = lookup(target, api_key=api_key)
        print_report(target, results)

        # Chain into synthesis lookup using the best real (non-theoretical)
        # match found above.
        best_real = next((r for r in results if r.tier in (1, 2) and not r.theoretical), None)
        if best_real:
            print(f"Checking text-mined synthesis recipes for {best_real.formula}...\n")
            recipes = lookup_synthesis(best_real.formula, api_key=api_key)
            print_synthesis_report(recipes)

        # Ready to log into your DB, e.g.:
        # db.add_literature_check(
        #     sample_composition=target,
        #     tier=results[0].tier,
        #     best_match_id=results[0].material_id,
        #     best_match_formula=results[0].formula,
        # )
