"""
oqmd_lookup.py

Standalone OQMD lookup, using the shared OPTIMADE standard rather than
OQMD's own bespoke REST API. Mirrors the tier structure from mp_lookup.py
so results from both can eventually sit in the same DB table.

Install: pip install "optimade[http-client]"
No API key needed -- OQMD's OPTIMADE endpoint is fully open.

Test this file standalone first. Only fold it into alloy_entry_full.py
once you've confirmed it returns sensible results on a real composition.
"""

import itertools
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dataclasses import dataclass
from typing import Dict, List, Optional

from optimade.client import OptimadeClient

OQMD_BASE_URL = "https://oqmd.org/optimade"
RETRY_WAIT_SECONDS = 45
MAX_RETRIES = 1

RESPONSE_FIELDS = [
    "chemical_formula_reduced", "elements", "elements_ratios", "nelements",
    "_oqmd_stability", "_oqmd_delta_e", "_oqmd_entry_id",
    "_oqmd_icsd_id", "_oqmd_spacegroup",
]

TIER_LABELS = {
    1: "info available (near-exact match)",
    2: "similar (same elements, different ratio)",
    3: "partial match (subsystem known, not full system)",
    4: "no information found",
}


@dataclass
class OQMDMatchResult:
    tier: int
    tier_label: str
    entry_id: Optional[int]
    formula: str
    elements: List[str]
    stability: Optional[float]     # eV/atom above hull; 0 = stable
    formation_energy: Optional[float]  # eV/atom
    experimentally_known: bool     # True if linked to an ICSD structure
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


def _is_transient_error(errors: List) -> bool:
    """502/503/504 are transient server-side issues worth retrying.
    The optimade client's own built-in retry (max_attempts=5) only ever
    applies to HTTP 429 (rate-limiting) -- a 502 raises a plain
    RuntimeError internally that the library does NOT retry on its own,
    it just reports it in the result's 'errors' list. This is why OQMD's
    occasional 502s needed handling here rather than relying on the
    client's own retry count."""
    return any(any(code in str(e) for code in ("502", "503", "504")) for e in errors)


def _query_with_retry(client: OptimadeClient, filter_str: str) -> dict:
    """Runs client.get() and retries once (after a wait) if OQMD returned
    a transient server error, before giving up and returning the (still
    possibly erroring) result for _extract_results to report."""
    raw = client.get(filter=filter_str, response_fields=RESPONSE_FIELDS)
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            errors = raw["structures"][filter_str][OQMD_BASE_URL].get("errors") or []
        except (KeyError, TypeError):
            errors = []
        if not _is_transient_error(errors):
            break
        attempt += 1
        print(f"  [retry] OQMD returned a transient server error "
              f"({errors[0]}) -- waiting {RETRY_WAIT_SECONDS}s before "
              f"retry {attempt}/{MAX_RETRIES}...")
        time.sleep(RETRY_WAIT_SECONDS)
        raw = client.get(filter=filter_str, response_fields=RESPONSE_FIELDS)
    return raw


def _extract_results(raw: dict, filter_str: str) -> List[dict]:
    try:
        provider_result = raw["structures"][filter_str][OQMD_BASE_URL]
    except (KeyError, TypeError):
        return []
    errors = provider_result.get("errors") or []
    if errors:
        print(f"  [warning] OQMD query returned an error, not just zero "
              f"results -- treat any tier-4 result with suspicion: {errors[0]}")
    return provider_result.get("data") or []


def lookup(
    target_composition: Dict[str, float],
    near_match_threshold: float = 0.05,
) -> List[OQMDMatchResult]:
    """
    target_composition: e.g. {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    Same shape as CalculationResult.as_composition_dict() from
    alloy_calculator.py, and the same input shape used by mp_lookup.lookup().
    """
    target_elements = sorted(target_composition.keys())
    client = OptimadeClient(base_urls=[OQMD_BASE_URL], use_async=False, silent=True)

    results: List[OQMDMatchResult] = []

    # --- exact element-set match (tiers 1 & 2) ---
    exact_filter = (
        f'elements HAS ALL {_quote_elements(target_elements)} '
        f'AND nelements={len(target_elements)}'
    )
    raw = _query_with_retry(client, exact_filter)
    for entry in _extract_results(raw, exact_filter):
        attrs = entry.get("attributes", {})
        candidate_comp = dict(zip(attrs.get("elements", []), attrs.get("elements_ratios", [])))
        dist = _composition_distance(target_composition, candidate_comp)
        tier = 1 if dist <= near_match_threshold else 2
        results.append(OQMDMatchResult(
            tier=tier, tier_label=TIER_LABELS[tier],
            entry_id=attrs.get("_oqmd_entry_id"),
            formula=attrs.get("chemical_formula_reduced", "?"),
            elements=attrs.get("elements", []),
            stability=attrs.get("_oqmd_stability"),
            formation_energy=attrs.get("_oqmd_delta_e"),
            experimentally_known=attrs.get("_oqmd_icsd_id") is not None,
            composition_distance=dist,
        ))

    # --- subsystem match: drop one element at a time (tier 3) ---
    if not any(r.tier in (1, 2) for r in results) and len(target_elements) > 1:
        for subset in itertools.combinations(target_elements, len(target_elements) - 1):
            sub_filter = (
                f'elements HAS ALL {_quote_elements(list(subset))} '
                f'AND nelements={len(subset)}'
            )
            raw = _query_with_retry(client, sub_filter)
            for entry in _extract_results(raw, sub_filter):
                attrs = entry.get("attributes", {})
                results.append(OQMDMatchResult(
                    tier=3, tier_label=TIER_LABELS[3],
                    entry_id=attrs.get("_oqmd_entry_id"),
                    formula=attrs.get("chemical_formula_reduced", "?"),
                    elements=attrs.get("elements", []),
                    stability=attrs.get("_oqmd_stability"),
                    formation_energy=attrs.get("_oqmd_delta_e"),
                    experimentally_known=attrs.get("_oqmd_icsd_id") is not None,
                    composition_distance=None,
                ))

    if not results:
        results.append(OQMDMatchResult(
            tier=4, tier_label=TIER_LABELS[4], entry_id=None, formula="",
            elements=target_elements, stability=None, formation_energy=None,
            experimentally_known=False, composition_distance=None,
        ))

    results.sort(key=lambda r: (
        r.tier,
        r.composition_distance if r.composition_distance is not None else 1.0,
        r.stability if r.stability is not None else 999,
    ))
    return results


def print_report(target_composition: Dict[str, float], results: List[OQMDMatchResult]) -> None:
    print(f"Target composition: {target_composition}\n")
    seen_tiers = set()
    for r in results:
        if r.tier not in seen_tiers:
            print(f"--- Tier {r.tier}: {r.tier_label} ---")
            seen_tiers.add(r.tier)
        if r.tier == 4:
            print("  (nothing found in any subsystem either)")
            continue
        stability = "unknown" if r.stability is None else (
            "stable" if r.stability == 0 else f"{r.stability:.3f} eV/atom above hull"
        )
        origin = "experimentally known (ICSD)" if r.experimentally_known else "computed/hypothetical only"
        dist_str = f", distance={r.composition_distance:.3f}" if r.composition_distance is not None else ""
        print(f"  oqmd-{r.entry_id}  {r.formula:<15}  {stability}  ({origin}){dist_str}")
    print()


if __name__ == "__main__":
    # Example: your Fe70 Al15 Ni15 alloy -- same composition used to test mp_lookup.py
    target = {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    results = lookup(target)
    print_report(target, results)
