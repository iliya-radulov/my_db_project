"""Nearest-prototype fallback and methods table (offline: synthetic Materials Project entries)."""
import json
import math

import pytest

pytest.importorskip("pymatgen")
from pymatgen.core import Composition, Lattice, Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry

import prototype_match as P
from dft_sisso_predictor import compare_with_calphad_ensemble, sisso_report_from_entries
from methods_table import build_table

TARGET = Composition("La7.1Fe82.1Si10.8")


def C(f):
    return Composition(f)


# ------------------------------------------------------------------ filter rules

def test_plan_numbers():
    t = P.fractions(TARGET)
    assert t == pytest.approx({"LA": 0.071, "FE": 0.821, "SI": 0.108}, abs=1e-9)
    lafe13 = P.classify(TARGET, C("LaFe13"))
    assert lafe13["match_type"] == P.NEAREST_PROTOTYPE
    assert lafe13["delta_x"] == pytest.approx(0.152, abs=0.001)
    # the figure sqrt(0.071^2 + 0.108^2) = 0.129 ignores the Fe component: the nearest Fe-Si
    # composition is 0.087 away, so a plain Euclidean ranking would prefer a La-free Fe-Si entry
    best = min(math.dist((0.071, 0.821, 0.108), (0.0, 1 - s, s)) for s in [i / 1000 for i in range(1001)])
    assert best == pytest.approx(0.087, abs=0.001) and best < lafe13["delta_x"]


def test_anchor_guard_rejects_la_free_entries():
    for f in ("Fe9Si", "Fe3Si", "Fe", "FeSi", "Fe7Si"):            # close in distance, no La
        assert P.classify(TARGET, C(f)) is None
    assert P.classify(TARGET, C("La")) is None
    assert P.classify(TARGET, C("LaFe11Si2"))["match_type"] == P.NEAREST_PROTOTYPE
    # anchor present but far: La fraction off by more than anchor_tol
    assert P.classify(TARGET, C("La2Fe13Si")) is None


def test_exact_match_and_tolerance():
    assert P.classify(C("Nd2Fe14B"), C("Nd2Fe14B"))["match_type"] == P.EXACT_MATCH
    assert P.classify(C("Nd11.76Fe82.35B5.88"), C("Nd2Fe14B"))["match_type"] == P.EXACT_MATCH
    assert P.classify(C("LaFe11.5Si1.5"), C("LaFe11.5Si1.5"))["delta_x"] == 0.0


def test_cutoff_is_fragile_and_site_group_fixes_it():
    """Plain Euclid keeps LaFe13 only for x <= 1.5 in La(Fe13-xSix); site groups keep it throughout."""
    plain, grouped = [], []
    flt_group = P.PrototypeFilter(site_groups=(("FE", "SI"),))
    for x in (1.2, 1.4, 1.5, 1.6, 1.8, 2.0):
        target = C(f"LaFe{13 - x}Si{x}")
        plain.append(P.classify(target, C("LaFe13")) is not None)
        g = P.classify(target, C("LaFe13"), flt_group)
        grouped.append(g is not None)
        assert g["delta_x"] < 0.002 and g["delta_x_euclid"] > 0.12        # both distances reported
    assert plain == [True, True, True, False, False, False]
    assert all(grouped)


def test_tied_minority_elements_are_all_anchors():
    t = P.fractions(C("LaFe12Si"))                     # La and Si both 1/14
    assert P.default_anchors(t) == ["LA", "SI"]
    assert P.classify(C("LaFe12Si"), C("LaFe13")) is None   # no Si: rejected by the anchor guard


def test_anchor_override_and_max_dx():
    t = C("Nd2Fe14B")
    assert P.default_anchors(P.fractions(t)) == ["B"]
    assert P.classify(t, C("Nd2Fe14B0.2")) is None                      # B 0.012 vs 0.059: off by 0.046 > 0.03
    assert P.classify(t, C("Nd2Fe14B0.2"), P.PrototypeFilter(anchor_tol=0.06)) is not None
    assert P.classify(t, C("Nd2Fe14B0.2"), P.PrototypeFilter(anchors=("ND",))) is not None   # anchor = Nd instead
    assert P.classify(C("LaFe11.5Si1.5"), C("LaFe13"), P.PrototypeFilter(max_dx=0.1)) is None


# ------------------------------------------------------------------ ranking and labels

def _cand(mt, e_hull, dgf, dx, mid="mp-x"):
    return {"material_id": mid, "match_type": mt, "e_above_hull_0K_eV_atom": e_hull,
            "dGf_sisso_kJ_mol_atom": {"800.0": dgf}, "delta_x": dx}


def test_ranking_tiers_stability_then_distance():
    ranked = P.rank_candidates([
        _cand(P.NEAREST_PROTOTYPE, 0.000, -20.0, 0.15, "near-stable"),
        _cand(P.NEAREST_PROTOTYPE, 0.030, -25.0, 0.02, "near-unstable"),
        _cand(P.EXACT_MATCH, 0.050, -5.0, 0.0, "exact-unstable"),
        _cand(P.NEAREST_PROTOTYPE, 0.004, -22.0, 0.05, "tie-bucket-closer"),
        _cand(P.NEAREST_PROTOTYPE, 0.001, -21.0, 0.10, "tie-bucket"),
    ])
    ids = [c["material_id"] for c in ranked]
    assert ids[0] == "exact-unstable"                      # exact tier first, whatever its stability
    # same hull bucket (< 0.01 eV): the lower low-T energy first, not the distance
    assert ids[1:4] == ["tie-bucket-closer", "tie-bucket", "near-stable"]
    assert ids[-1] == "near-unstable"
    assert [c["material_id"] for c in P.cap_prototypes(ranked, 2)] == ids[:3]


def test_provenance_label():
    assert P.provenance_label({"material_id": "mp-1", "formula": "Nd2Fe14B", "match_type": "exact_match"}) == \
        "mp-1 (Nd2Fe14B, exact_match)"
    assert P.provenance_label({"material_id": "mp-9", "formula": "LaFe13", "match_type": "nearest_prototype",
                               "delta_x": 0.152}) == "mp-9 (LaFe13, nearest_prototype Δx=0.152)"
    assert P.provenance_label({"material_id": "NO_MP_ENTRY"}) == "no_dft_entry"


# ------------------------------------------------------------------ offline SISSO pipeline

def _entry(formula, e_per_atom, mid, a=5.0):
    comp = Composition(formula)
    n = int(round(comp.num_atoms))
    species = [str(el) for el, amt in comp.items() for _ in range(int(round(amt)))]
    coords = [[(i * 0.37) % 1, (i * 0.61) % 1, (i * 0.83) % 1] for i in range(n)]
    s = Structure(Lattice.cubic(a * (n / 4) ** (1 / 3)), species, coords)
    return ComputedStructureEntry(s, e_per_atom * n, entry_id=mid)


def _entries():
    return [
        _entry("Fe", -8.30, "mp-fe", 2.9), _entry("La", -4.90, "mp-la", 5.3), _entry("Si", -5.42, "mp-si", 5.4),
        _entry("LaFe13", -7.50, "mp-lafe13"),             # hypothetical binary prototype
        _entry("LaFe11Si2", -7.62, "mp-lafe11si2"),       # ternary, closer in composition
        _entry("Fe3Si", -7.40, "mp-fe3si"), _entry("FeSi", -6.90, "mp-fesi"),
        _entry("LaFe2Si2", -6.80, "mp-lafe2si2"),
    ]


def test_fallback_report_has_provenance_and_skips_la_free_entries():
    rep = sisso_report_from_entries("La7.1Fe82.1Si10.8", _entries(), [800.0, 1300.0], prototype_filter=P.PrototypeFilter())
    ids = [c["material_id"] for c in rep["candidates"]]
    assert set(ids) == {"mp-lafe11si2", "mp-lafe13"}                    # no Fe3Si, FeSi, LaFe2Si2
    assert rep["match_type"] == P.NEAREST_PROTOTYPE and rep["fallback_used"] is True
    for c in rep["candidates"]:
        assert c["match_type"] == P.NEAREST_PROTOTYPE and c["delta_x"] > 0 and c["prototype_formula"]
        assert all(v is not None and math.isfinite(v) for v in c["dGf_sisso_kJ_mol_atom"].values())
    assert rep["candidates"][0]["material_id"] == "mp-lafe11si2"        # more stable prototype first
    assert rep["prototype_filter"]["max_dx"] == 0.16


def test_exact_match_beats_prototypes_and_prototype_rows_are_not_verdicts():
    entries = _entries() + [_entry("La2Fe23Si3", -7.58, "mp-exact")]
    rep = sisso_report_from_entries("La2Fe23Si3", entries, [800.0], prototype_filter=P.PrototypeFilter())
    assert rep["candidates"][0]["material_id"] == "mp-exact" and rep["candidates"][0]["match_type"] == P.EXACT_MATCH
    assert rep["fallback_used"] is False
    ens = {"gates": {"gate_passed": True}, "threshold_distribution": {"800.0": {
        "median_kJ": -8.5, "p05_kJ": -9.0, "p95_kJ": -8.0, "q25_kJ": -8.7, "q75_kJ": -8.3, "iqr_kJ": 0.4,
        "dominant_competing_assemblage": "A+B", "eta2_by_edge": {}}}}
    rows = compare_with_calphad_ensemble(rep, ens)
    by_id = {r["material_id"]: r for r in rows}
    assert by_id["mp-exact"]["comparable"] is True and by_id["mp-exact"]["verdict"] in (
        "stable_across_band", "borderline_within_band", "metastable_above_band")
    protos = [r for r in rows if r["match_type"] == P.NEAREST_PROTOTYPE]
    assert protos and all(r["verdict"] == "prototype_indicative_only" and r["comparable"] is False for r in protos)


def test_no_dft_entry_when_nothing_passes_the_filter():
    only_binaries = [e for e in _entries() if e.entry_id in ("mp-fe", "mp-la", "mp-si", "mp-fe3si", "mp-fesi")]
    rep = sisso_report_from_entries("La7.1Fe82.1Si10.8", only_binaries, [800.0], prototype_filter=P.PrototypeFilter())
    assert rep["candidates"] == [] and rep["match_type"] == P.NO_DFT_ENTRY
    off = sisso_report_from_entries("La7.1Fe82.1Si10.8", _entries(), [800.0], prototype_filter=None)
    assert off["candidates"] == [] and off["match_type"] == P.NO_DFT_ENTRY      # fallback disabled


# ------------------------------------------------------------------ methods table

def _ensemble(label="B-Fe-Nd", passed=True):
    return {"system": label, "edge_priority": ["FE-ND", "B-FE", "B-ND"],
            "target_composition": {"FE": 0.8235, "ND": 0.1176, "B": 0.0588},
            "gates": {"gate_passed": passed, "parameters": {"preregistered": False},
                      "G1_survival": {"survived": 78, "total": 84, "min_required": 21, "pass": True},
                      "G2_lineage_coverage": {"pass": True, "min_required": 2, "surviving_lineages_per_edge": {
                          "FE-ND": ["a", "b", "c"], "B-FE": ["a"] * 7, "B-ND": ["a"] * 4}}},
            "threshold_distribution": {"800.0": {"median_kJ": -8.79, "p05_kJ": -9.20, "p95_kJ": -8.40,
                                                  "q25_kJ": -9.0, "q75_kJ": -8.6, "iqr_kJ": 0.4,
                                                  "dominant_competing_assemblage": "FE17ND2+ND2B5+NDB4_D1E",
                                                  "eta2_by_edge": {}}}}


def test_methods_table_three_systems():
    rep = sisso_report_from_entries("La7.1Fe82.1Si10.8", _entries(), [800.0], prototype_filter=P.PrototypeFilter())
    md, rows = build_table([("B-Fe-Nd", _ensemble(), None),
                            ("Al-Fe-Mn", _ensemble("Al-Fe-Mn"), None),
                            ("Fe-La-Si", _ensemble("Fe-La-Si"), rep)], T=800.0)
    assert len(rows) == 3 and "78/84 (93 %)" in md and "FE-ND > B-FE > B-ND" in md
    assert rows[0]["SISSO entry (provenance)"].startswith("not run")           # never guessed
    assert "nearest_prototype Δx=" in rows[2]["SISSO entry (provenance)"]
    assert rows[2]["Margin kJ/mol-atom"].endswith("†") and "prototype_indicative_only" == rows[2]["Verdict"]
    assert "indicative, not a stability verdict" in md and "preregistered=False" in md
    failed, _ = build_table([("X", _ensemble(passed=False), None)])
    assert "FAIL" in failed
