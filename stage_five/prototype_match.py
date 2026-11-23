"""
stage_five/prototype_match.py

Simplex-safe nearest-prototype selection for the SISSO side of the screening.

When the target composition has no exact Materials Project entry (for example
La7.1Fe82.1Si10.8 ~ La(Fe,Si)13), the closest chemically meaningful entry is used as an
INDICATIVE prototype, with its provenance (match type, prototype formula, composition distance)
attached to every row. No network access and no structure data are needed here, so the rules
can be tested offline.

Rules
-----
exact_match        fractional distance <= exact_tol (5e-4: absorbs rounded at.% input).
nearest_prototype  all of
                     1. anchor guard: every anchor element is present in the candidate and
                        |x_cand - x_target| <= anchor_tol (default 0.03) for each anchor. The
                        anchor is the minority element of the target (La in La7.1Fe82.1Si10.8),
                        so a La-free Fe-Si entry can never pass, however close in Euclidean
                        distance (the nearest Fe-Si composition is 0.087 away, LaFe13 0.152);
                     2. distance <= max_dx (default 0.16) in atomic-fraction space.
Optional `site_groups` (e.g. [("FE", "SI")]) treats elements that substitute on one site as one
coordinate: LaFe13 vs La(Fe,Si)13 then differs by 0.0004 instead of 0.15, so the same prototype
is found for the whole composition series (with plain Euclidean distance, LaFe13 leaves the 0.16
cutoff for Si > 0.113, i.e. x >= 1.6 in LaFe13-xSix). The Euclidean distance is always reported
too (`delta_x_euclid`).

Ranking (rank_candidates): exact_match before nearest_prototype; then 0 K energy above hull
(differences below 0.01 eV/atom count as ties) and the lowest-temperature SISSO formation
Gibbs energy; then the composition distance.

A nearest prototype is NOT at the target composition, so its energy is not compared with the
CALPHAD threshold at the target composition as a stability verdict (see
dft_sisso_predictor.compare_with_calphad_ensemble): the row is marked
"prototype_indicative_only" and `comparable=False`.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from pymatgen.core import Composition

EXACT_MATCH = "exact_match"
NEAREST_PROTOTYPE = "nearest_prototype"
LISTED_OTHER_TERNARY = "listed_other_ternary"   # include_subsystems: listed, never compared
NO_DFT_ENTRY = "no_dft_entry"

E_HULL_TIE_EV = 0.01      # eV/atom: ranking treats smaller hull differences as ties


@dataclass(frozen=True)
class PrototypeFilter:
    max_dx: float = 0.16
    anchor_tol: float = 0.03
    anchors: tuple[str, ...] | None = None          # None -> minority element(s) of the target
    site_groups: tuple[tuple[str, ...], ...] = ()   # elements that substitute on one site
    max_prototypes: int = 3
    exact_tol: float = 5e-4

    def as_dict(self) -> dict:
        d = asdict(self)
        d["anchors"] = list(self.anchors) if self.anchors else None
        d["site_groups"] = [list(g) for g in self.site_groups]
        return d


def fractions(comp: Composition) -> dict[str, float]:
    return {str(el).upper(): float(a) for el, a in comp.fractional_composition.get_el_amt_dict().items()}


def default_anchors(target: dict[str, float], tol: float = 1e-9) -> list[str]:
    """Minority element(s) of the target (smallest positive fraction)."""
    pos = {e: x for e, x in target.items() if x > 0}
    m = min(pos.values())
    return sorted(e for e, x in pos.items() if x - m <= tol)


def _label_map(elements, groups) -> dict[str, str]:
    mapping = {e: e for e in elements}
    for g in groups:
        label = "+".join(sorted(x.upper() for x in g))
        for e in g:
            mapping[e.upper()] = label
    return mapping


def _distance(a: dict[str, float], b: dict[str, float], groups=()) -> float:
    elements = set(a) | set(b)
    mapping = _label_map(elements, groups)
    tot_a: dict[str, float] = {}
    tot_b: dict[str, float] = {}
    for e in elements:
        tot_a[mapping[e]] = tot_a.get(mapping[e], 0.0) + a.get(e, 0.0)
        tot_b[mapping[e]] = tot_b.get(mapping[e], 0.0) + b.get(e, 0.0)
    return math.sqrt(sum((tot_a.get(k, 0.0) - tot_b.get(k, 0.0)) ** 2 for k in set(tot_a) | set(tot_b)))


def classify(target: Composition, cand: Composition, flt: PrototypeFilter | None = None) -> dict | None:
    """Return the provenance dict of `cand` against `target`, or None when it is rejected."""
    flt = flt or PrototypeFilter()
    t, c = fractions(target), fractions(cand)
    euclid = _distance(t, c)
    if euclid <= flt.exact_tol:
        return {"match_type": EXACT_MATCH, "delta_x": 0.0, "delta_x_euclid": round(euclid, 6),
                "anchor_delta": 0.0}
    anchors = [a.upper() for a in (flt.anchors or default_anchors(t))]
    for a in anchors:
        if c.get(a, 0.0) <= 0.0 or abs(c[a] - t.get(a, 0.0)) > flt.anchor_tol:
            return None
    dx = _distance(t, c, flt.site_groups)
    if dx > flt.max_dx:
        return None
    return {"match_type": NEAREST_PROTOTYPE, "delta_x": round(dx, 6), "delta_x_euclid": round(euclid, 6),
            "anchor_delta": round(max(abs(c[a] - t.get(a, 0.0)) for a in anchors), 6)}


def _lowest_t_dgf(cand: dict) -> float:
    vals = [(float(k), v) for k, v in cand.get("dGf_sisso_kJ_mol_atom", {}).items() if v is not None]
    return min(vals)[1] if vals else math.inf


def rank_candidates(cands: list[dict]) -> list[dict]:
    """exact before nearest; then low-temperature stability; then composition distance."""
    def key(c):
        tier = 0 if c["match_type"] == EXACT_MATCH else 1
        e_hull = c.get("e_above_hull_0K_eV_atom")
        bucket = math.floor(e_hull / E_HULL_TIE_EV) if e_hull is not None else math.inf
        return (tier, bucket, _lowest_t_dgf(c), c.get("delta_x", 0.0))
    return sorted(cands, key=key)


def cap_prototypes(ranked: list[dict], max_prototypes: int) -> list[dict]:
    """Keep every exact match and the best `max_prototypes` nearest prototypes."""
    out, n = [], 0
    for c in ranked:
        if c["match_type"] == NEAREST_PROTOTYPE:
            n += 1
            if n > max_prototypes:
                continue
        out.append(c)
    return out


def provenance_label(row: dict) -> str:
    """'mp-123 (LaFe13, nearest_prototype Δx=0.152)'; exact: 'mp-1 (Nd2Fe14B, exact_match)'."""
    mt = row.get("match_type") or EXACT_MATCH
    mid = row.get("material_id", "")
    if mt == NO_DFT_ENTRY or mid == "NO_MP_ENTRY":
        return "no_dft_entry"
    formula = row.get("prototype_formula") or row.get("formula") or ""
    if mt == NEAREST_PROTOTYPE:
        dx = row.get("delta_x")
        return f"{mid} ({formula}, {mt} Δx={dx:.3f})" if dx is not None else f"{mid} ({formula}, {mt})"
    return f"{mid} ({formula}, {mt})"
