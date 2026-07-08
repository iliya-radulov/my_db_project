"""
aflow_lookup.py

Standalone AFLOW lookup, using the official `aflow` python package (AFLUX
query language under the hood). Mirrors the tier structure of
mp_lookup.py / oqmd_lookup.py so results from all three can eventually
sit in the same literature_checks table.

Install: pip install aflow
No API key needed -- AFLOW's search API is fully open.

*** VERIFICATION STATUS: LOWER CONFIDENCE THAN mp_lookup.py / oqmd_lookup.py ***
Unlike those two, this script could not be checked against the live AFLOW
server at all (aflowlib.duke.edu isn't reachable from the sandbox this was
written in -- not even far enough to get a clean HTTP rejection confirming
the request shape, which is what happened when testing oqmd_lookup.py).
On top of that, this python package's keyword objects turned out to be
mutable singletons: calling .filter() more than once on the same keyword
(e.g. K.species) silently corrupts earlier filter values instead of
raising an error -- an easy trap that wasn't obvious until tested locally.
The code below works around this by building one combined expression per
keyword (chained with `&`) before calling .filter() a single time, which
matches how the library's internal self-combination logic appears to be
designed to be used.

What's still genuinely uncertain: whether a comma-separated list inside
one keyword's own clause (e.g. species(*'Fe'*,*'Al'*,*'Ni'*)) means
"must contain ALL of these" or "must contain ANY of these" in AFLUX. This
script assumes ALL (that's the intent, matching MP/OQMD's exact-set
queries) but that assumption is UNVERIFIED.

RECOMMENDED FIRST STEP: before trusting a ternary/quaternary result,
sanity-check this script on a simple, well-known binary system first (e.g.
Fe-Ni) and confirm the returned compounds match what you already expect,
to rule out an ANY-of instead of ALL-of interpretation.

IMPORTANT DIFFERENCE FROM MP/OQMD: this data source has no hull-distance
/ stability field. The closest available number is enthalpy_formation_atom
(eV/atom, formation enthalpy relative to the pure elements) -- NOT directly
comparable to MP's energy_above_hull or OQMD's _oqmd_stability. A very
negative formation enthalpy means "favorable to form at all", not
"most stable phase in this particular chemical system". Don't average or
directly compare this number against the other two databases' stability
values.

"Experimentally known" here comes from which AFLOW catalog an entry lives
in: 'icsd' = real, experimentally-determined structures; 'lib1'/'lib2'/
'lib3' = computed prototypes for unary/binary/ternary systems. This script
queries both and tags results accordingly.
"""

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional

import aflow
from aflow import K

TIER_LABELS = {
    1: "info available (near-exact match)",
    2: "similar (same elements, different ratio)",
    3: "partial match (subsystem known, not full system)",
    4: "no information found",
}


@dataclass
class AFLOWMatchResult:
    tier: int
    tier_label: str
    auid: Optional[str]
    formula: str
    elements: List[str]
    formation_enthalpy: Optional[float]  # eV/atom -- NOT a hull distance, see module docstring
    experimentally_known: bool           # True if found in the 'icsd' catalog
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


def _build_element_set_query(elements: List[str], catalog):
    """Builds a query for an EXACT element-set match (not a superset).
    Resets the shared keyword singletons first, and builds the species
    condition as one chained expression before calling .filter() once --
    calling .filter() repeatedly on the same keyword object silently
    corrupts earlier values instead of erroring (discovered during local
    testing, see module docstring)."""
    aflow.keywords.reset()
    query = aflow.search(catalog=catalog).select(
        K.compound, K.species, K.stoichiometry, K.enthalpy_formation_atom, K.auid
    )
    species_expr = K.species % elements[0]
    for el in elements[1:]:
        species_expr = species_expr & (K.species % el)
    query = query.filter(K.nspecies == len(elements))
    query = query.filter(species_expr)
    return query


def _run_catalog_query(elements: List[str], catalog) -> List:
    results = []
    try:
        query = _build_element_set_query(elements, catalog)
        for entry in query:
            try:
                species = list(entry.species)
                stoich = list(entry.stoichiometry)
                candidate_comp = dict(zip(species, stoich))
                results.append((entry, candidate_comp))
            except Exception as e:
                print(f"  [warning] Skipped one AFLOW entry due to a parsing "
                      f"issue: {e}")
    except Exception as e:
        print(f"  [warning] AFLOW query failed (catalog={catalog}): {e}")
    return results


def lookup(
    target_composition: Dict[str, float],
    near_match_threshold: float = 0.05,
) -> List[AFLOWMatchResult]:
    """
    target_composition: e.g. {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    Same input shape as mp_lookup.lookup() / oqmd_lookup.lookup().
    """
    target_elements = sorted(target_composition.keys())
    results: List[AFLOWMatchResult] = []

    # --- exact element-set match (tiers 1 & 2), across both catalogs ---
    raw_matches = (
        [(e, c, True) for e, c in _run_catalog_query(target_elements, "icsd")] +
        [(e, c, False) for e, c in _run_catalog_query(target_elements, ["lib1", "lib2", "lib3"])]
    )
    for entry, candidate_comp, exp_known in raw_matches:
        dist = _composition_distance(target_composition, candidate_comp)
        tier = 1 if dist <= near_match_threshold else 2
        results.append(AFLOWMatchResult(
            tier=tier, tier_label=TIER_LABELS[tier],
            auid=getattr(entry, "auid", None),
            formula=getattr(entry, "compound", "?"),
            elements=list(getattr(entry, "species", [])),
            formation_enthalpy=getattr(entry, "enthalpy_formation_atom", None),
            experimentally_known=exp_known,
            composition_distance=dist,
        ))

    # --- subsystem match: drop one element at a time (tier 3) ---
    if not any(r.tier in (1, 2) for r in results) and len(target_elements) > 1:
        for subset in itertools.combinations(target_elements, len(target_elements) - 1):
            subset = list(subset)
            sub_matches = (
                [(e, c, True) for e, c in _run_catalog_query(subset, "icsd")] +
                [(e, c, False) for e, c in _run_catalog_query(subset, ["lib1", "lib2", "lib3"])]
            )
            for entry, candidate_comp, exp_known in sub_matches:
                results.append(AFLOWMatchResult(
                    tier=3, tier_label=TIER_LABELS[3],
                    auid=getattr(entry, "auid", None),
                    formula=getattr(entry, "compound", "?"),
                    elements=list(getattr(entry, "species", [])),
                    formation_enthalpy=getattr(entry, "enthalpy_formation_atom", None),
                    experimentally_known=exp_known,
                    composition_distance=None,
                ))

    if not results:
        results.append(AFLOWMatchResult(
            tier=4, tier_label=TIER_LABELS[4], auid=None, formula="",
            elements=target_elements, formation_enthalpy=None,
            experimentally_known=False, composition_distance=None,
        ))

    results.sort(key=lambda r: (
        r.tier,
        r.composition_distance if r.composition_distance is not None else 1.0,
        r.formation_enthalpy if r.formation_enthalpy is not None else 999,
    ))
    return results


def print_report(target_composition: Dict[str, float], results: List[AFLOWMatchResult]) -> None:
    print(f"Target composition: {target_composition}\n")
    seen_tiers = set()
    for r in results:
        if r.tier not in seen_tiers:
            print(f"--- Tier {r.tier}: {r.tier_label} ---")
            seen_tiers.add(r.tier)
        if r.tier == 4:
            print("  (nothing found in any subsystem either)")
            continue
        enthalpy = "unknown" if r.formation_enthalpy is None else f"{r.formation_enthalpy:.3f} eV/atom (formation enthalpy, not hull distance)"
        origin = "experimentally known (ICSD)" if r.experimentally_known else "computed/hypothetical only"
        dist_str = f", distance={r.composition_distance:.3f}" if r.composition_distance is not None else ""
        print(f"  aflow-{r.auid}  {r.formula:<15}  {enthalpy}  ({origin}){dist_str}")
    print()


if __name__ == "__main__":
    # Example: your Fe70 Al15 Ni15 alloy -- same composition tested against MP and OQMD
    target = {"Fe": 0.70, "Al": 0.15, "Ni": 0.15}
    results = lookup(target)
    print_report(target, results)
