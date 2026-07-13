"""
lookup_common.py

Shared logic for combining mp_lookup.py and oqmd_lookup.py results:
normalizes both into one shape, then collapses raw entries down to one
row per distinct formula (the dedup rule agreed on after seeing OQMD
return 33 near-duplicate rows for a single Fe-Al-Ni query).

Dedup ranking, per formula:
  1. prefer experimentally_known = True over theoretical/hypothetical-only
  2. among those, lowest stability (most stable / lowest energy above hull)
  3. then closest composition_distance to the target
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DedupCandidate:
    formula: str
    match_id: str
    tier: int
    stability: Optional[float]
    experimentally_known: bool
    composition_distance: Optional[float]


def from_mp_results(results: List) -> List[DedupCandidate]:
    """Adapts mp_lookup.MatchResult objects. Skips tier-4 (nothing found)
    placeholders, since there's nothing to store."""
    return [
        DedupCandidate(
            formula=r.formula,
            match_id=r.material_id,
            tier=r.tier,
            stability=r.energy_above_hull,
            experimentally_known=not r.theoretical,
            composition_distance=r.composition_distance,
        )
        for r in results if r.tier != 4
    ]


def from_oqmd_results(results: List) -> List[DedupCandidate]:
    """Adapts oqmd_lookup.OQMDMatchResult objects. Skips tier-4 placeholders."""
    return [
        DedupCandidate(
            formula=r.formula,
            match_id=f"oqmd-{r.entry_id}",
            tier=r.tier,
            stability=r.stability,
            experimentally_known=r.experimentally_known,
            composition_distance=r.composition_distance,
        )
        for r in results if r.tier != 4
    ]


def from_alexandria_results(results: List) -> List[DedupCandidate]:
    """Adapts alexandria_lookup.AlexandriaMatchResult objects. Skips tier-4
    (nothing found) placeholders. experimentally_known is always False --
    Alexandria is a purely computational database, see its module
    docstring."""
    return [
        DedupCandidate(
            formula=r.formula,
            match_id=str(r.entry_id),
            tier=r.tier,
            stability=r.hull_distance,
            experimentally_known=r.experimentally_known,
            composition_distance=r.composition_distance,
        )
        for r in results if r.tier != 4
    ]


def filter_by_distance(candidates: List[DedupCandidate], max_distance: float) -> List[DedupCandidate]:
    """Drops tier-2 (and tier-1, though its 0.05 near-match threshold
    means this rarely matters) candidates whose composition_distance
    exceeds max_distance. Tier-3 and tier-4 candidates have no
    composition_distance (they're subsystem/no-info matches, a different
    kind of result) and are never filtered by this -- the cutoff is only
    about "how different is the ratio", which doesn't apply to them."""
    return [
        c for c in candidates
        if c.composition_distance is None or c.composition_distance <= max_distance
    ]


def _is_better(candidate: DedupCandidate, current: DedupCandidate) -> bool:
    if candidate.experimentally_known != current.experimentally_known:
        return candidate.experimentally_known  # True beats False
    c_stab = candidate.stability if candidate.stability is not None else float('inf')
    cur_stab = current.stability if current.stability is not None else float('inf')
    if c_stab != cur_stab:
        return c_stab < cur_stab
    c_dist = candidate.composition_distance if candidate.composition_distance is not None else 1.0
    cur_dist = current.composition_distance if current.composition_distance is not None else 1.0
    return c_dist < cur_dist


def dedup_by_formula(candidates: List[DedupCandidate]) -> List[DedupCandidate]:
    """Collapses a list of raw candidates down to one entry per distinct
    formula, keeping the best one by the ranking above."""
    best: Dict[str, DedupCandidate] = {}
    for c in candidates:
        current = best.get(c.formula)
        if current is None or _is_better(c, current):
            best[c.formula] = c
    return sorted(best.values(), key=lambda c: (
        c.tier,
        c.composition_distance if c.composition_distance is not None else 1.0,
        c.stability if c.stability is not None else 999,
    ))
