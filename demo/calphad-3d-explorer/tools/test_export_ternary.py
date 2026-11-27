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
