"""Tests for sisso_t_calibration.py: the decision logic offline, the CALPHAD path on a toy TDB."""
import json
import sys

import numpy as np
import pytest

import sisso_t_calibration as cal


def _linear(slope_J, offset_kJ, temps=cal.GRID):
    return {T: offset_kJ + slope_J / 1000.0 * (T - cal.T0) for T in temps}


def test_ols_slope_recovers_a_known_slope():
    pts = _linear(12.5, 3.0)
    assert cal.ols_slope_J(list(pts), list(pts.values())) == pytest.approx(12.5)


def test_alpha_is_the_unweighted_mean_of_compound_slopes():
    res = {"A": _linear(10, 0), "B": _linear(20, 0, cal.GRID[:5])}  # B has fewer points: same weight
    out = cal.evaluate(res)
    assert out["alpha_J_mol_atom_K"] == pytest.approx(15.0)


def test_common_slope_is_removed_and_correction_adopted():
    # residual zero at T0 and growing by 15 J/mol-atom/K: the correction removes it completely
    res = {c: _linear(15, 0) for c in "ABCDE"}
    out = cal.evaluate(res)
    assert out["mean_mae_after_kJ"] == pytest.approx(0.0, abs=1e-9)
    assert out["mean_gain_kJ"] > cal.MAE_GAIN_MIN
    assert out["correction_adopted"]


def test_no_slope_means_no_correction():
    res = {c: _linear(0, 5.0) for c in "ABC"}
    out = cal.evaluate(res)
    assert out["mean_gain_kJ"] == pytest.approx(0.0, abs=1e-9)
    assert not out["correction_adopted"]


def test_v14_rule_rejects_when_one_compound_is_worsened_more_than_the_mean_gain():
    # four compounds with +20, one with -20: alpha = +12, the -20 compound gets much worse
    res = {**{c: _linear(20, 0) for c in "ABCD"}, "E": _linear(-20, 0)}
    v14 = cal.evaluate(res, rule="v1.4")
    assert v14["condition_1"]["pass"]
    assert not v14["condition_2"]["pass"]
    assert not v14["correction_adopted"]
    # the v1.0 rule tolerates one such compound
    v10 = cal.evaluate(res, rule="v1.0")
    assert v10["correction_adopted"]


def test_unknown_rule_is_an_error():
    with pytest.raises(ValueError):
        cal.evaluate({"A": _linear(1, 0), "B": _linear(2, 0)}, rule="v9")


def test_leave_one_out_uses_the_other_compounds_only():
    res = {"A": _linear(10, 0), "B": _linear(20, 0), "C": _linear(30, 0)}
    loo = cal.leave_one_out(res)
    assert loo["A"]["alpha_without_J"] == pytest.approx(25.0)
    assert loo["C"]["alpha_without_J"] == pytest.approx(15.0)


def test_restrict_drops_compounds_with_too_few_points():
    res = {"A": _linear(10, 0), "B": {800.0: 0.0, 1375.0: 1.0, 1450.0: 2.0}}
    sub = cal.restrict(res, 1300.0)
    assert set(sub) == {"A"} and max(sub["A"]) == 1300.0


def test_phase_fraction_sums_vertices_of_the_wanted_phase_and_ignores_nan():
    names = ["B2_BCC", "B2_BCC", ""]
    fracs = [0.6, 0.3995, float("nan")]
    assert cal.phase_fraction(names, fracs, ["B2_BCC"]) == pytest.approx(0.9995)
    assert cal.phase_fraction(["LIQUID", "B2_BCC"], [0.5, 0.5], ["B2_BCC"]) == pytest.approx(0.5)


def test_sisso_candidate_matches_id_with_functional_suffix():
    rep = {"candidates": [{"material_id": "mp-21990-GGA"}, {"material_id": "mp-2199-GGA"}]}
    assert cal.pick_sisso_candidate(rep, "mp-2199")["material_id"] == "mp-2199-GGA"
    assert cal.pick_sisso_candidate(rep, "mp-1915") is None


def test_manifest_detects_a_changed_file(tmp_path):
    f = tmp_path / "a.tdb"
    f.write_text("x")
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"files": {"a": {"path": str(f), "sha256": cal.sha256_file(f)}}}))
    assert cal.verify_manifest(m) == []
    f.write_text("y")
    assert cal.verify_manifest(m) == ["a: changed since the freeze (%s)" % f]


def test_settings_are_consistent():
    assert cal.DECISION_RULE in ("v1.4", "v1.0")
    for c in cal.COMPOUNDS:
        assert sum(c["x"].values()) == pytest.approx(1.0)
        assert c["phase"] and c["tdb"].endswith(".tdb") and c["mp_id"].startswith("mp-")


TOY_TDB = """
ELEMENT /-   ELECTRON_GAS              0.0000E+00  0.0000E+00  0.0000E+00!
ELEMENT VA   VACUUM                    0.0000E+00  0.0000E+00  0.0000E+00!
ELEMENT B    BETA_RHOMBO_B             1.0811E+01  1.2220E+03  5.9000E+00!
ELEMENT FE   BCC_A2                    5.5847E+01  4.4890E+03  2.7280E+01!
FUNCTION GHSERFE 298.15 -8000-20*T; 6000 N !
FUNCTION GHSERBB 298.15 -2000-6*T; 6000 N !
TYPE_DEFINITION % SEQ *!
PHASE BCC_A2 % 1 1 !
CONSTITUENT BCC_A2 :FE,B: !
PARAMETER G(BCC_A2,FE;0) 298.15 +GHSERFE; 6000 N !
PARAMETER G(BCC_A2,B;0) 298.15 +GHSERBB+40000; 6000 N !
PHASE BETA_RHOMBO_B % 1 1 !
CONSTITUENT BETA_RHOMBO_B :B: !
PARAMETER G(BETA_RHOMBO_B,B;0) 298.15 +GHSERBB; 6000 N !
PHASE ALPHA_RHOMBO_B % 1 1 !
CONSTITUENT ALPHA_RHOMBO_B :B: !
PARAMETER G(ALPHA_RHOMBO_B,B;0) 298.15 +GHSERBB-500; 6000 N !
PHASE M2B_C16 % 2 2 1 !
CONSTITUENT M2B_C16 :FE:B: !
PARAMETER G(M2B_C16,FE:B;0) 298.15 +2*GHSERFE+GHSERBB-60000+3*T; 6000 N !
"""


def test_calphad_path_on_a_toy_fe_b_database():
    pycalphad = pytest.importorskip("pycalphad")
    db = pycalphad.Database(TOY_TDB)
    comp = {"name": "Fe2B", "x": {"Fe": 2 / 3, "B": 1 / 3}, "phase": ["M2B_C16"]}
    temps = [800.0, 1200.0, 1600.0]
    res = cal.compound_calphad(db, comp, temps)
    assert res["n_retained"] == 3
    for r in res["rows"]:
        # dG = (-60000 + 3 T) / 3 J/mol-atom against BETA boron (ALPHA is 500 J lower but must not be used)
        assert r["dG_calphad_kJ"] == pytest.approx((-60000 + 3 * r["T"]) / 3 / 1000, abs=1e-3)
        assert r["element_phase"]["B"] == "BETA_RHOMBO_B"
        assert r["phases"] == ["M2B_C16"]


def test_manifest_alone_is_a_valid_command_and_no_mode_is_an_error():
    args = cal.build_parser().parse_args(["--note", "n.md", "--manifest", "m.json"])
    assert args.manifest and not args.run and not args.check_calphad
    with pytest.raises(SystemExit):
        cal.main([])


def test_pycalphad_version_guard():
    assert cal.pycalphad_version_problem(cal.PYCALPHAD_OF_RECORD) is None
    assert "0.12.0" in cal.pycalphad_version_problem("0.12.0")


def test_a_failing_compound_is_reported_not_dropped(monkeypatch, tmp_path):
    pycalphad = pytest.importorskip("pycalphad")
    tdb = tmp_path / "FeB-02Rom.tdb"
    tdb.write_text(TOY_TDB)

    def boom(*a, **k):
        raise ValueError("no usable phase for B")

    monkeypatch.setattr(cal, "COMPOUNDS", [c for c in cal.COMPOUNDS if c["name"] == "Fe2B"])
    monkeypatch.setattr(cal, "find_file", lambda name, roots: tdb)
    monkeypatch.setattr(cal, "g_els_kJ", lambda els, temps: {e: [0.0] * len(temps) for e in els})
    monkeypatch.setattr(cal, "element_gm_kJ", lambda db, el, temps: ([0.0] * len(temps), [""] * len(temps)))
    monkeypatch.setattr(cal, "compound_calphad", boom)
    res = cal.check_calphad([tmp_path])
    assert res["compounds"]["Fe2B"]["error"].startswith("ValueError")
    assert res["compounds"]["Fe2B"]["dropped"] is True
    with pytest.raises(RuntimeError):
        cal.run_study([tmp_path])


def _fake_namespace_pymatgen(monkeypatch, tmp_path, contents):
    import sys
    import types
    mod = types.ModuleType("pymatgen")          # namespace-package style: no __file__
    mod.__path__ = [str(tmp_path)]
    monkeypatch.setitem(sys.modules, "pymatgen", mod)
    for i, text in enumerate(contents):
        d = tmp_path / f"sub{i}" / "data"
        d.mkdir(parents=True)
        (d / "g_els.json").write_text(text)


def test_g_els_path_works_without_a_file_attribute_and_accepts_identical_copies(monkeypatch, tmp_path):
    _fake_namespace_pymatgen(monkeypatch, tmp_path, ['{"300": {"Fe": 0.0}}', '{"300": {"Fe": 0.0}}'])
    assert cal.g_els_path().name == "g_els.json"


def test_g_els_path_refuses_copies_with_different_content(monkeypatch, tmp_path):
    _fake_namespace_pymatgen(monkeypatch, tmp_path, ['{"300": {"Fe": 0.0}}', '{"300": {"Fe": 1.0}}'])
    with pytest.raises(RuntimeError):
        cal.g_els_path()


# ---- provenance of the Materials Project query (offline, with a fake MPRester)
def _fake_mp(monkeypatch, entries, version="2099.01.01"):
    import sys
    import types
    calls = {}

    class FakeMPRester:
        def __init__(self, key=None):
            calls["key"] = key

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_entries_in_chemsys(self, elements, additional_criteria=None):
            calls["elements"], calls["criteria"] = list(elements), additional_criteria
            return list(entries)

        def get_database_version(self):
            if version is None:
                raise RuntimeError("offline")
            return version

    client = types.ModuleType("mp_api.client")
    client.MPRester = FakeMPRester
    monkeypatch.setitem(sys.modules, "mp_api.client", client)
    if "mp_api" not in sys.modules:
        monkeypatch.setitem(sys.modules, "mp_api", types.ModuleType("mp_api"))
    return calls


def _synthetic_entries():
    pytest.importorskip("pymatgen")
    from pymatgen.core import Composition, Lattice, Structure
    from pymatgen.entries.computed_entries import ComputedStructureEntry

    def entry(formula, e_per_atom, mid, a=5.0):
        comp = Composition(formula)
        n = int(round(comp.num_atoms))
        species = [str(el) for el, amt in comp.items() for _ in range(int(round(amt)))]
        coords = [[(i * 0.37) % 1, (i * 0.61) % 1, (i * 0.83) % 1] for i in range(n)]
        s = Structure(Lattice.cubic(a * (n / 4) ** (1 / 3)), species, coords)
        return ComputedStructureEntry(s, e_per_atom * n, entry_id=mid)
    return [entry("Fe", -8.30, "mp-fe", 2.9), entry("Si", -5.42, "mp-si", 5.4), entry("Fe3Si", -7.40, "mp-fe3si")]


def test_sisso_dgf_records_the_release_and_entries_and_matches_the_predictor(monkeypatch):
    entries = _synthetic_entries()
    calls = _fake_mp(monkeypatch, entries)
    sys.path.insert(0, str(cal.HERE))
    import dft_sisso_predictor as dsp
    monkeypatch.setattr(dsp, "_resolve_mp_api_key", lambda key=None: "dummy-key")
    comp = {"name": "Fe3Si", "formula": "Fe3Si", "mp_id": "mp-fe3si"}
    temps = [800.0, 1000.0]
    vals, eid, prov = cal.sisso_dgf(comp, temps)
    assert eid == "mp-fe3si" and set(vals) == set(temps) and all(v is not None for v in vals.values())
    assert prov["mp_database_version"] == "2099.01.01"
    assert prov["chemsys"] == ["Fe", "Si"] and prov["n_entries"] == 3
    assert calls["criteria"] == {"thermo_types": ["GGA_GGA+U"]} and calls["key"] == "dummy-key"
    assert {e["entry_id"] for e in prov["entries"]} == {"mp-fe", "mp-si", "mp-fe3si"}
    assert all(e["energy_per_atom_eV"] is not None for e in prov["entries"])
    # the recorded values are exactly what the Stage-5 predictor gives for the same entries
    rep = dsp.predict_sisso_formation_gibbs("Fe3Si", temps, api_key="dummy-key", nearest_prototype=False)
    ref = cal.pick_sisso_candidate(rep, "mp-fe3si")["dGf_sisso_kJ_mol_atom"]
    assert vals == {T: ref[str(T)] for T in temps}


def test_missing_database_version_is_recorded_not_fatal(monkeypatch):
    _fake_mp(monkeypatch, _synthetic_entries(), version=None)
    sys.path.insert(0, str(cal.HERE))
    import dft_sisso_predictor as dsp
    monkeypatch.setattr(dsp, "_resolve_mp_api_key", lambda key=None: "dummy-key")
    _, _, prov = cal.sisso_dgf({"name": "Fe3Si", "formula": "Fe3Si", "mp_id": "mp-fe3si"}, [800.0])
    assert prov["mp_database_version"].startswith("unavailable: RuntimeError")
