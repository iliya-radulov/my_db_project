"""Real-window smoke test of the split New Entry tab. Skipped without tkinter and a display
(run it with xvfb-run on a headless machine)."""
import os
import sys
import types
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")
pytest.importorskip("matplotlib")
if not os.environ.get("DISPLAY"):
    pytest.skip("needs a display (xvfb-run)", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def _stub(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


@pytest.fixture()
def app(monkeypatch):
    for pkg in ("stage_two", "stage_two.alloy", "stage_two.lookup", "stage_two.tools"):
        _stub(pkg).__path__ = []

    class _DB:
        def __getattr__(self, n):
            return lambda *a, **k: []

    _stub("stage_two.alloy.alloy_db_v2", get_db=lambda *a, **k: _DB())
    _stub("stage_two.alloy.alloy_screening_v2", screen_composition=lambda *a, **k: {})
    _stub("stage_two.alloy.alloy_calculator_v2", ATOMIC_WEIGHTS={"Fe": 55.8})
    _stub("stage_two.lookup.lookup_common_v2", **{n: (lambda *a, **k: []) for n in (
        "from_mp_results", "from_oqmd_results", "from_alexandria_results", "dedup_by_formula", "filter_by_distance")})
    _stub("stage_two.tools.plot_v2", plot_xrd=None, plot_vsm=None, plot_sem=None)
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("alloy_desktop_v2", None)
    import alloy_desktop_v2 as A
    a = A.AlloyLabApp()
    a.update()
    yield a
    a.destroy()


def test_inputs_and_results_are_side_by_side(app):
    app.update()
    paned = app.new_entry_paned
    assert len(paned.panes()) == 2
    left, right = (app.nametowidget(p) for p in paned.panes())
    assert left.winfo_rootx() < right.winfo_rootx()
    assert right.winfo_height() > 400                      # the result area now has the height of the tab
    # every input and the result box are children of the new tab
    for w in (app.formula_entry, app.calc_btn, app.stage5_btn, app.stage5_force_var and app.stage5_site_groups_entry):
        assert str(w).startswith(str(app.tab_new))
    assert str(app.result_text).startswith(str(right))


def test_wrap_toggle_and_copy(app):
    app.result_text.insert("end", "x" * 300)
    assert str(app.result_text.cget("wrap")) == "none"
    app.result_wrap_var.set(True)
    app.on_result_wrap_toggle()
    assert str(app.result_text.cget("wrap")) == "word" and not app.result_hscroll.winfo_ismapped()
    app.copy_results()
    assert app.clipboard_get() == "x" * 300


def test_divider_can_be_moved(app):
    app.update()
    before = app.new_entry_paned.sash_coord(0)[0]
    app.new_entry_paned.sash_place(0, before + 80, 0)
    app.update()
    assert app.new_entry_paned.sash_coord(0)[0] != before
