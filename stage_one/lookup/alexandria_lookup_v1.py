"""
alexandria_lookup.py

Standalone Alexandria (ICAMS, Ruhr-University Bochum) lookup, using the
same OPTIMADE standard and the same `optimade` python client as
oqmd_lookup.py -- this is nearly a copy of that file with the provider
URL and provider-specific field names swapped, which is exactly the
point of OPTIMADE: one client, many databases.

Install: pip install "optimade[http-client]"  (same package as oqmd_lookup.py)
No API key needed.

Unlike OQMD, Alexandria has a genuine hull-distance field
(_alexandria_hull_distance, eV/atom) with the same 0=stable convention as
MP's energy_above_hull and OQMD's _oqmd_stability -- directly comparable,
unlike AFLOW's formation-enthalpy-only data.

KNOWN LIMITATION: Alexandria is a purely computational database (2.5M+
DFT-calculated materials). There's no ICSD-style linkage field found in
its OPTIMADE schema, so there's no clean "experimentally known" signal
here -- every result is marked experimentally_known=False. Treat
Alexandria as a third independent DFT stability check, not a source of
"has this actually been made" information.
"""

import itertools
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dataclasses import dataclass
from typing import Dict, List, Optional

from optimade.client import OptimadeClient

ALEXANDRIA_BASE_URL = "https://alexandria.icams.rub.de/pbe"

RESPONSE_FIELDS = [
    "chemical_formula_reduced", "elements", "elements_ratios", "nelements",
    "_alexandria_hull_distance", "_alexandria_formation_energy_per_atom",
]

TIER_LABELS = {
    1: "info available (near-exact match)",
    2: "similar (same elements, different ratio)",
    3: "partial match (subsystem known, not full system)",
    4: "no information found",
}


@dataclass
class AlexandriaMatchResult:
    tier: int
    tier_label: str
    entry_id: Optional[str]
    formula: str
    elements: List[str]
    hull_distance: Optional[float]     # eV/atom; 0 = stable, same convention as MP/OQMD
    formation_energy: Optional[float]  # eV/atom
    experimentally_known: bool         # always False -- see module docstring
    composition_distance: Optional[float]


def _normalize(comp: Dict[str, float]) -> Dict[str, float]:
    total = sum(comp.values())
    return {el: amt / total for el, amt in comp.items()}


def _composition_distance(target: Dict[str, float], candidate: Dict[str, float]) -> float:
    target = _normalize(target)
    candidate = _normalize(candidate)
    elements = set(target) | set(candidate)
    diff = sum(abs(target.get(el, 0.0) - candidate.get(el, 0.0)) for el in elements)
    return diff / 2


def _quote_elements(elements: List[str]) -> str:
    return ",".join(f'"{el}"' for el in elements)


def _extract_results(raw: dict, filter_str: str) -> List[dict]:
    try:
        provider_result = raw["structures"][filter_str][ALEXANDRIA_BASE_URL]
    except (KeyError, TypeError):
        return []
    errors = provider_result.get("errors") or []
    if errors:
        print(f"  [warning] Alexandria query returned an error, not just zero "
              f"results -- treat any tier-4 result with suspicion: {errors[0]}")
    return provider_result.get("data") or []


def lookup(
    target_composition: Dict[str, float],
    near_match_threshold: float = 0.05,
) -> List[AlexandriaMatchResult]:
    """
    target_composition: e.g. {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    Same input shape as mp_lookup.lookup() / oqmd_lookup.lookup().
    """
    target_elements = sorted(target_composition.keys())
    client = OptimadeClient(base_urls=[ALEXANDRIA_BASE_URL], use_async=False, silent=True)

    results: List[AlexandriaMatchResult] = []

    # --- exact element-set match (tiers 1 & 2) ---
    exact_filter = (
        f'elements HAS ALL {_quote_elements(target_elements)} '
        f'AND nelements={len(target_elements)}'
    )
    raw = client.get(filter=exact_filter, response_fields=RESPONSE_FIELDS)
    for entry in _extract_results(raw, exact_filter):
        attrs = entry.get("attributes", {})
        candidate_comp = dict(zip(attrs.get("elements", []), attrs.get("elements_ratios", [])))
        dist = _composition_distance(target_composition, candidate_comp)
        tier = 1 if dist <= near_match_threshold else 2
        results.append(AlexandriaMatchResult(
            tier=tier, tier_label=TIER_LABELS[tier],
            entry_id=entry.get("id"),
            formula=attrs.get("chemical_formula_reduced", "?"),
            elements=attrs.get("elements", []),
            hull_distance=attrs.get("_alexandria_hull_distance"),
            formation_energy=attrs.get("_alexandria_formation_energy_per_atom"),
            experimentally_known=False,
            composition_distance=dist,
        ))

    # --- subsystem match: drop one element at a time (tier 3) ---
    if not any(r.tier in (1, 2) for r in results) and len(target_elements) > 1:
        for subset in itertools.combinations(target_elements, len(target_elements) - 1):
            sub_filter = (
                f'elements HAS ALL {_quote_elements(list(subset))} '
                f'AND nelements={len(subset)}'
            )
            raw = client.get(filter=sub_filter, response_fields=RESPONSE_FIELDS)
            for entry in _extract_results(raw, sub_filter):
                attrs = entry.get("attributes", {})
                results.append(AlexandriaMatchResult(
                    tier=3, tier_label=TIER_LABELS[3],
                    entry_id=entry.get("id"),
                    formula=attrs.get("chemical_formula_reduced", "?"),
                    elements=attrs.get("elements", []),
                    hull_distance=attrs.get("_alexandria_hull_distance"),
                    formation_energy=attrs.get("_alexandria_formation_energy_per_atom"),
                    experimentally_known=False,
                    composition_distance=None,
                ))

    if not results:
        results.append(AlexandriaMatchResult(
            tier=4, tier_label=TIER_LABELS[4], entry_id=None, formula="",
            elements=target_elements, hull_distance=None, formation_energy=None,
            experimentally_known=False, composition_distance=None,
        ))

    results.sort(key=lambda r: (
        r.tier,
        r.composition_distance if r.composition_distance is not None else 1.0,
        r.hull_distance if r.hull_distance is not None else 999,
    ))
    return results


def print_report(target_composition: Dict[str, float], results: List[AlexandriaMatchResult]) -> None:
    print(f"Target composition: {target_composition}\n")
    seen_tiers = set()
    for r in results:
        if r.tier not in seen_tiers:
            print(f"--- Tier {r.tier}: {r.tier_label} ---")
            seen_tiers.add(r.tier)
        if r.tier == 4:
            print("  (nothing found in any subsystem either)")
            continue
        stability = "unknown" if r.hull_distance is None else (
            "stable" if r.hull_distance == 0 else f"{r.hull_distance:.3f} eV/atom above hull"
        )
        dist_str = f", distance={r.composition_distance:.3f}" if r.composition_distance is not None else ""
        print(f"  {r.entry_id}  {r.formula:<15}  {stability}  (computed only){dist_str}")
    print()


if __name__ == "__main__":
    # Example: your Fe70 Al15 Ni15 alloy -- same composition tested against MP and OQMD
    target = {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    results = lookup(target)
    print_report(target, results)
