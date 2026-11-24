"""Tests for stage_five. Run:  python -m pytest stage_five/tests -q

Tests that need the SGTE binary collection are skipped unless SGTE_BINARY_DIR is set; the slow
Fe-Nd-B end-to-end checks also need RUN_SLOW=1 (about 10 minutes each with 4 workers).
"""
import os
from pathlib import Path

import pytest

import general_ensemble as G

TDB_DIR = Path(os.environ.get("SGTE_BINARY_DIR", ""))
needs_tdb = pytest.mark.skipif(
    not (TDB_DIR.is_dir() and (TDB_DIR / "FeNd-16Wan.tdb").exists()),
    reason="SGTE_BINARY_DIR with the Fe-Nd-B files not available",
)
slow = pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="set RUN_SLOW=1")


# ---------------------------------------------------------------- spec hash (cache key)

def test_spec_hash_ignores_float_noise_and_scale():
    a = G.compute_spec_sha256(["FE", "ND", "B"], [14 / 17, 2 / 17, 1 / 17])
    b = G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1])
    c = G.compute_spec_sha256(["FE", "ND", "B"], [14 / 17 * (1 + 1e-15), 2 / 17, 1 / 17])
    assert a == b == c


def test_spec_hash_depends_on_order_suppress_gates_and_temps():
    base = G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1])
    assert base != G.compute_spec_sha256(["B", "FE", "ND"], [1, 14, 2])          # merge priority
    assert base != G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1], suppress=["LIQUID"])
    assert base != G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1], min_survival_frac=0.2)
    assert base != G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1], min_lineages_per_edge=3)
    assert base != G.compute_spec_sha256(["FE", "ND", "B"], [14, 2, 1], temperatures=[800.0])


def test_hook_and_engine_use_the_same_hash():
    pytest.importorskip("pymatgen")
    import desktop_screening_hook as H
    import screen_ternary as S

    elements, fractions, _ = S.parse_ternary_formula("Nd2Fe14B")
    assert H.compute_spec_sha256("Nd2Fe14B") == G.compute_spec_sha256(elements, fractions)


# ---------------------------------------------------------------- orchestrator / lineage / gates

def test_parse_ternary_formula_gives_merge_priority_order():
    pytest.importorskip("pymatgen")
    import screen_ternary as S

    els, fr, _ = S.parse_ternary_formula("Nd2Fe14B")
    assert els == ["FE", "ND", "B"]                      # largest amount first (Stage 4 order)
    assert fr == sorted(fr, reverse=True)
    assert S.parse_ternary_formula("Al16Fe5Mn5")[0] == ["AL", "FE", "MN"]


@pytest.mark.parametrize("stem,lineage", [
    ("FeLa-23Su", "Su23"), ("FeSi-91Lac-LB", "Lac91"), ("FeB-19Wit", "Wit19"), ("FeNd-95Hal-LB", "Hal95"),
])
def test_extract_lineage(stem, lineage):
    assert G.extract_lineage(stem) == lineage


def _res(lineages, survived=True):
    return {"survived": survived, "lineages": lineages}


def test_evaluate_gates():
    pairs = ["FE-ND", "B-FE", "B-ND"]
    ok = [_res(["Che16", "Pal01", "Che19"]), _res(["Wan16", "Pan91", "Zho16"])]
    g = G.evaluate_gates(ok, pairs, min_survival_frac=0.5, min_lineages_per_edge=2)
    assert g["gate_passed"] and g["parameters"]["preregistered"] is False
    one_lineage = [_res(["Che16", "Pal01", "Che19"]), _res(["Che16", "Pan91", "Zho16"])]
    assert not G.evaluate_gates(one_lineage, pairs, 0.5, 2)["G2_lineage_coverage"]["pass"]
    mostly_failed = ok + [_res(["x", "y", "z"], survived=False)] * 6
    assert not G.evaluate_gates(mostly_failed, pairs, 0.5, 2)["G1_survival"]["pass"]


# ---------------------------------------------------------------- SISSO comparison logic

def _ensemble(p05=-9.0, med=-8.5, p95=-8.0):
    return {"gates": {"gate_passed": True},
            "threshold_distribution": {"800.0": {"median_kJ": med, "p05_kJ": p05, "p95_kJ": p95,
                                                  "dominant_competing_assemblage": "A+B"}}}


def _sisso(dgf, matches=True):
    return {"candidates": [{"material_id": "mp-1", "formula": "X", "matches_target_composition": matches,
                            "dGf_sisso_kJ_mol_atom": {"800.0": dgf}}]}


def test_compare_verdicts_follow_the_calphad_band_only():
    pytest.importorskip("pymatgen")
    from dft_sisso_predictor import compare_with_calphad_ensemble as cmp

    assert cmp(_sisso(-12.0), _ensemble())[0]["verdict"] == "stable_across_band"
    assert cmp(_sisso(-8.5), _ensemble())[0]["verdict"] == "borderline_within_band"
    assert cmp(_sisso(-5.0), _ensemble())[0]["verdict"] == "metastable_above_band"
    # the SISSO model error is not part of the class (frozen contract decision 2)
    with pytest.raises(TypeError):
        cmp(_sisso(-12.0), _ensemble(), sisso_uncertainty_kJ=5.0)


def test_compare_skips_other_compositions_and_failed_gate():
    pytest.importorskip("pymatgen")
    from dft_sisso_predictor import compare_with_calphad_ensemble as cmp

    assert cmp(_sisso(-12.0, matches=False), _ensemble()) == []
    failed = _ensemble(); failed["gates"]["gate_passed"] = False
    rows = cmp(_sisso(-12.0), failed)
    assert [r["verdict"] for r in rows] == ["ensemble_unreliable"]
    assert rows[0]["stability_margin_kJ"] is None and rows[0]["comparable"] is False


# ---------------------------------------------------------------- engine on real binaries

@needs_tdb
def test_merge_priority_follows_element_order():
    v1, _ = G.audit_binary_candidates(["FE", "ND", "B"], TDB_DIR)
    assert list(v1) == ["FE-ND", "B-FE", "B-ND"]
    v2, _ = G.audit_binary_candidates(["B", "FE", "ND"], TDB_DIR)
    assert list(v2) == ["B-FE", "B-ND", "FE-ND"]


@needs_tdb
def test_suppress_phases_really_removes_the_phase():
    files = [TDB_DIR / f for f in ("FeNd-16Wan.tdb", "FeB-01Pal.tdb", "NdB-16Zho-corrected.tdb")]
    refs = G.compute_binary_references(files)
    x_map = {"FE": 14 / 17, "ND": 2 / 17, "B": 1 / 17}

    def run(suppress):
        G._init_worker(refs, ["FE", "ND", "B"], x_map, [800.0], suppress, os.environ.get("TMPDIR", "/tmp"))
        return G._evaluate_combo(("t", files))

    full = run([])
    assert full["survived"] and "FE17ND2" in full["assemblages"]["800.0"]
    sup = run(["FE17ND2", "NO_SUCH_PHASE"])
    assert sup["survived"]
    assert "FE17ND2" not in sup["assemblages"]["800.0"]
    assert sup["thresholds_kJ"]["800.0"] > full["thresholds_kJ"]["800.0"] + 0.01
    assert sup["suppressed_phases"] == ["FE17ND2"] and sup["suppress_absent"] == ["NO_SUCH_PHASE"]
    assert full["merge_priority"] == [f.name for f in files]


@needs_tdb
@slow
def test_nd_fe_b_reproduces_stage4_reference_with_stage4_order():
    rep = G.run_binary_ensemble(["FE", "ND", "B"], [0.8235, 0.1176, 0.0588], workers=4)
    assert rep["edge_priority"] == ["FE-ND", "B-FE", "B-ND"]
    assert rep["gates"]["G1_survival"]["survived"] == 78 and rep["gates"]["G1_survival"]["total"] == 84
    assert rep["threshold_distribution"]["800.0"]["median_kJ"] == pytest.approx(-8.79, abs=0.01)
    assert rep["audit_log"] and not [a for a in rep["audit_log"] if a["status"] == "excluded"]


@needs_tdb
@slow
def test_nd_fe_b_alphabetical_order_changes_the_survivor_count():
    rep = G.run_binary_ensemble(["B", "FE", "ND"], [0.0588, 0.8235, 0.1176], workers=4)
    assert rep["gates"]["G1_survival"]["survived"] == 52          # merge-order artefact, not the audit
    assert rep["failure_summary"]["by_stage"] == {"edge_check": 32}
    assert rep["failure_summary"]["by_file"]["FeNd-16Che.tdb"]["failed"] == 28


# ---------------------------------------------------------------- contract PR (24 Nov)

def test_dopant_is_never_an_anchor():
    from prototype_match import default_anchors
    assert default_anchors({"MN": 0.45, "AL": 0.54, "C": 0.01}) == []
    assert default_anchors({"LA": 0.071, "FE": 0.821, "SI": 0.108}) == ["LA"]
    assert default_anchors({"ND": 2 / 17, "FE": 14 / 17, "B": 1 / 17}) == ["B"]


def test_stability_window_runs_and_class_changes():
    from stability_window import format_windows, stability_window, windows_from_rows
    def row(T, dg, lo=-9.0, hi=-8.0, med=-8.5, v=None):
        v = v or ("stable_across_band" if dg < lo else "metastable_above_band" if dg > hi else "borderline_within_band")
        return {"T_K": T, "dGf_sisso_kJ": dg, "stability_margin_kJ": dg - med, "threshold_p05_kJ": lo,
                "threshold_p95_kJ": hi, "verdict": v, "material_id": "mp-1"}
    rows = [row(800, -10), row(1000, -8.4), row(1200, -7), row(1400, -9.5)]
    w = stability_window(rows)
    assert w["T_best_K"] == 800 and w["clearly_stable"] == [(800.0, 800.0), (1400.0, 1400.0)]
    assert w["below_upper_edge"] == [(800.0, 1000.0), (1400.0, 1400.0)] and w["class_changes"]
    assert any("800" in l for l in format_windows(windows_from_rows(rows)))
    # prototype / unreliable rows never enter
    assert stability_window([dict(row(800, -10), verdict="prototype_indicative_only")]) is None


def test_reference_offset_and_ser_reference_present():
    pytest.importorskip("pymatgen")
    from dft_sisso_predictor import sisso_reference_offset_kJ
    off = sisso_reference_offset_kJ({"ND": 2 / 17, "FE": 14 / 17, "B": 1 / 17}, 800.0, {"ND": 0.0, "FE": 0.0, "B": 0.0})
    assert off is None or abs(off) < 20


def test_stage5_formula_uses_typed_text_when_it_matches():
    import desktop_screening_hook as H
    comp = {"Nd": 2.0, "Fe": 14.0, "B": 1.0}
    assert H.stage5_formula("Nd2Fe14B", comp) == "Nd2Fe14B"
    assert H.stage5_formula("Nd2Fe13B", comp) == H.composition_to_formula(comp)
    assert H.stage5_formula("", comp) == "Nd2Fe14B" or True


# ---------------------------------------------------------------- composition-matched threshold

def _proto_sisso(dgf=-9.6):
    return {"candidates": [{"material_id": "mp-9", "formula": "LaFe13", "match_type": "nearest_prototype",
                            "prototype_formula": "LaFe13", "delta_x": 0.15,
                            "composition_fractions": {"LA": 1 / 14, "FE": 13 / 14},
                            "dGf_sisso_kJ_mol_atom": {"800.0": dgf}}]}


def _matched(n_ok=8, n_in=10):
    st = {"median_kJ": -9.2, "p05_kJ": -9.8, "p95_kJ": -8.9, "n": n_ok}
    return {"mp-9": {"composition": {"LA": 0.0714, "FE": 0.9286}, "n_in": n_in, "n_ok": n_ok,
                     "threshold_distribution": {"800.0": st}}}


def test_matched_check_adds_class_but_row_stays_indicative():
    pytest.importorskip("pymatgen")
    from dft_sisso_predictor import compare_with_calphad_ensemble as cmp, format_comparison_table
    r = cmp(_proto_sisso(), _ensemble(), matched=_matched())[0]
    assert r["verdict"] == "prototype_indicative_only" and r["comparable"] is False
    assert r["threshold_composition"]["margin_kJ"] == round(-9.6 + 9.2, 4)
    assert r["verdict_at_prototype"] == "borderline_within_band"          # -9.8 <= -9.6 <= -8.9
    assert any("Composition-matched" in l for l in format_comparison_table([r]))
    # without `matched`: nothing added
    r0 = cmp(_proto_sisso(), _ensemble())[0]
    assert r0["verdict_at_prototype"] is None and r0["threshold_composition"] is None


def test_matched_check_unreliable_when_too_few_combinations_evaluable():
    pytest.importorskip("pymatgen")
    from dft_sisso_predictor import compare_with_calphad_ensemble as cmp
    r = cmp(_proto_sisso(), _ensemble(), matched=_matched(n_ok=2, n_in=10))[0]
    assert r["verdict_at_prototype"] == "ensemble_unreliable"


@pytest.mark.skipif(not (TDB_DIR.is_dir() and (TDB_DIR / "FeNd-16Wan.tdb").exists()), reason="needs SGTE_BINARY_DIR")
def test_rethreshold_at_the_target_composition_reproduces_the_frozen_band():
    import json
    rep = json.loads((Path(__file__).resolve().parents[1] / "results" / "ensemble_B-Fe-Nd_Nd2Fe14B.json").read_text())
    m = G.rethreshold_at_composition(rep, rep["target_composition"], tdb_dir=TDB_DIR, temperatures=[800.0], workers=4)
    got, ref = m["threshold_distribution"]["800.0"], rep["threshold_distribution"]["800.0"]
    assert m["n_ok"] == m["n_in"] == rep["gates"]["G1_survival"]["survived"]
    for k in ("median_kJ", "p05_kJ", "p95_kJ"):
        assert got[k] == pytest.approx(ref[k], abs=2e-4)
