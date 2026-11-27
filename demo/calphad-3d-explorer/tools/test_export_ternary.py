"""Tests for export_ternary.py: helpers offline, the pycalphad path on a toy ternary.

Run: python -m pytest demo/calphad-3d-explorer/tools/test_export_ternary.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_ternary as ex  # noqa: E402


def test_triangle_grid_covers_the_triangle_and_stays_off_zero():
    pts = ex.triangle_grid(4)
    assert len(pts) == 15  # (n+1)(n+2)/2
    for _, _, xa, xb, xc in pts:
        assert xa + xb + xc == pytest.approx(1.0)
        assert min(xa, xb, xc) >= ex.VERTEX_EPS * 0.99


def test_crossings_interpolate_and_handle_out_of_range():
    temps = [1000, 1100, 1200, 1300]
    assert ex.crossing_up(temps, [0.0, 0.2, 0.8, 1.0], 0.999) == pytest.approx(1299.5, abs=0.1)
    assert ex.crossing_up(temps, [0.0, 0.1, 0.2, 0.3], 0.999) is None          # never all liquid
    assert ex.crossing_up(temps, [1.0, 1.0, 1.0, 1.0], 0.999) == 1000.0         # liquid already at T_min
    assert ex.crossing_down(temps, [0.0, 0.0, 0.5, 1.0], 0.001) == pytest.approx(1100.2, abs=0.1)
    assert ex.crossing_down(temps, [0.0, 0.0, 0.0, 0.0], 0.001) == 1300.0       # never liquid in range
    assert ex.crossing_down(temps, [0.5, 0.6, 0.9, 1.0], 0.001) is None         # liquid even at T_min
    assert ex.crossing_up(temps, [0.0, None, 0.5, 1.0], 0.999) == pytest.approx(1299.8, abs=0.1)


def test_node_summary_reads_primary_phase_and_assemblage():
    temps = [900, 1000, 1100, 1200]
    states = [{"FCC_A1": 0.7, "BCC_A2": 0.3}, {"FCC_A1": 0.6, "LIQUID": 0.4},
              {"FCC_A1": 0.2, "LIQUID": 0.8}, {"LIQUID": 1.0}]
    s = ex.node_summary(temps, states, {"LIQUID"})
    assert s["primary_phase"] == "FCC_A1"
    assert s["solid_assemblage"] == ["BCC_A2", "FCC_A1"]
    assert 1100 < s["t_liquidus_K"] <= 1200
    assert 900 <= s["t_solidus_K"] < 1000


TOY = """
ELEMENT VA VACUUM 0 0 0 !
ELEMENT AL FCC_A1 27 0 0 !
ELEMENT CU FCC_A1 63.5 0 0 !
ELEMENT NI FCC_A1 58.7 0 0 !
FUNCTION GHSERAL 298.15 -1000-20*T; 4000 N !
FUNCTION GHSERCU 298.15 -2000-22*T; 4000 N !
FUNCTION GHSERNI 298.15 -3000-24*T; 4000 N !
TYPE_DEFINITION % SEQ * !
PHASE LIQUID % 1 1 !
CONSTITUENT LIQUID :AL,CU,NI: !
PARAMETER G(LIQUID,AL;0) 298.15 +GHSERAL+10000-10*T; 4000 N !
PARAMETER G(LIQUID,CU;0) 298.15 +GHSERCU+12000-10*T; 4000 N !
PARAMETER G(LIQUID,NI;0) 298.15 +GHSERNI+14000-10*T; 4000 N !
PHASE FCC_A1 % 1 1 !
CONSTITUENT FCC_A1 :AL,CU,NI: !
PARAMETER G(FCC_A1,AL;0) 298.15 +GHSERAL; 4000 N !
PARAMETER G(FCC_A1,CU;0) 298.15 +GHSERCU; 4000 N !
PARAMETER G(FCC_A1,NI;0) 298.15 +GHSERNI; 4000 N !
"""
# Melting points by construction: dH / dS = 10000/10 = 1000 K (Al), 1200 K (Cu), 1400 K (Ni)


def test_toy_ternary_reproduces_the_constructed_melting_points(tmp_path):
    pytest.importorskip("pycalphad")
    tdb = tmp_path / "toy.tdb"
    tdb.write_text(TOY)
    data = ex.build_dataset(tdb, ["AL", "CU", "NI"], 900, 1500, 10, 4, 1, [], ["test"])
    assert data["schema"] == ex.SCHEMA
    assert data["system"]["source"]["tdb_sha256"] == ex.sha256_file(tdb)
    assert data["provenance"]["failed_points"] == 0
    corners = {(0, 0): 1000.0, (4, 0): 1200.0, (0, 4): 1400.0}   # A=Al, B=Cu (i), C=Ni (j)
    for n in data["nodes"]:
        if (n["i"], n["j"]) in corners:
            assert n["t_liquidus_K"] == pytest.approx(corners[(n["i"], n["j"])], abs=10)
            assert n["t_solidus_K"] == pytest.approx(corners[(n["i"], n["j"])], abs=10)
            assert n["primary_phase"] == "FCC_A1"
        if n["t_liquidus_K"] is not None and n["t_solidus_K"] is not None:
            assert n["t_solidus_K"] <= n["t_liquidus_K"] + 1e-6
    json.dumps(data)  # serialisable


# --- check_dataset.py -------------------------------------------------------
import check_dataset as chk  # noqa: E402


def _toy_dataset(tmp_path):
    tdb = tmp_path / "toy.tdb"
    tdb.write_text(TOY)
    return tdb, ex.build_dataset(tdb, ["AL", "CU", "NI"], 900, 1500, 10, 4, 1, [], ["test"])


def test_check_passes_on_a_correct_dataset_and_catches_a_wrong_liquidus(tmp_path):
    pytest.importorskip("pycalphad")
    tdb, ds = _toy_dataset(tmp_path)
    res = chk.run_checks(ds, tdb, None, 1)
    assert res["A1_tdb_hash"]["pass"]
    assert res["A_summary"]["edges_liquidus_ok"] == res["A_summary"]["edge_points"] == 9
    assert res["A_pass"]
    sgte_al = [m for m in res["B1_melting_points"] if m["element"] == "AL"][0]
    assert sgte_al["model_K"] == pytest.approx(1000, abs=2)   # toy model, not the real Al (933 K)
    # corrupt one edge liquidus by 50 K: the check must fail
    edge = [n for n in ds["nodes"] if n["j"] == 0 and 0 < n["i"] < 4][0]
    edge["t_liquidus_K"] += 50
    assert not chk.run_checks(ds, tdb, None, 1)["A_pass"]


def test_check_reads_reference_points(tmp_path):
    pytest.importorskip("pycalphad")
    tdb, ds = _toy_dataset(tmp_path)
    refs = tmp_path / "refs.csv"
    refs.write_text(
        "# comment\n"
        "id,quantity,composition,T_K,value,tolerance,source,note\n"
        "al_melt,t_liquidus_K,AL:1;CU:0;NI:0,,1000,15,toy construction,\n"
        "al_wrong,t_liquidus_K,AL:1;CU:0;NI:0,,1100,15,deliberately wrong,\n"
        "ni_solid,phases_at_T,AL:0;CU:0;NI:1,1300,FCC_A1,,toy construction,\n")
    rows = {r["id"]: r for r in chk.run_checks(ds, tdb, refs, 1)["B2_reference_points"]}
    assert rows["al_melt"]["within_tolerance"]
    assert not rows["al_wrong"]["within_tolerance"]
    assert rows["ni_solid"]["within_tolerance"] and rows["ni_solid"]["model"] == "FCC_A1"


def test_non_minimal_points_flags_a_point_far_above_the_chord():
    temps = [1040, 1050, 1060, 1070, 1080, 1090]
    # La-Fe x=0.1 from the paper-build file: 1070 K came back "all liquid", 5.6 kJ/mol too high
    gms = [-48030.3, -48751.8, -49478.1, -44617.4, -50955.6, -51706.6]
    assert ex.non_minimal_points(temps, gms) == [3]
    states = [{"A": 1.0}] * 6
    states = list(states)
    assert ex.reject_non_minimal(temps, states, gms) == 1 and states[3] is None and gms[3] is None
    # a smooth concave G (with a small kink, like a phase transition) is kept
    smooth = [-1000 - 50 * t - 0.001 * t * t for t in temps]
    smooth[3] += 20
    assert ex.non_minimal_points(temps, smooth) == []
