"""Merged 'Calculate & Preview' + Stage 5 flow of alloy_desktop_v2.py, tested without Tk.

The Stage 5 methods are extracted from the app's source and run on a stand-in object with fake
widgets, so the logic (final composition, ternary-only, running guard, stale results, wt% / pre-alloy
handling) is checked without a display. The widgets themselves are not exercised."""
import ast
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("pymatgen")
ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "alloy_desktop_v2.py"
NAMES = ["_preview_key", "_show_stage5", "_start_stage5", "_auto_stage5", "run_stage5_screen"]


class Var:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class Widget:
    def __init__(self, text=""):
        self.text, self.config = text, {}

    def get(self):
        return self.text

    def configure(self, **kw):
        self.config.update(kw)


class TextBox:
    def __init__(self):
        self.parts = []

    def insert(self, _pos, text):
        self.parts.append(text)

    def see(self, _pos):
        pass


class Msg:
    def __init__(self):
        self.calls = []

    def showinfo(self, *a):
        self.calls.append(("info", a))

    def showwarning(self, *a):
        self.calls.append(("warning", a))


def _load_methods(msg):
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    src = APP.read_text(encoding="utf-8")
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in NAMES:
            found[node.name] = textwrap.dedent(ast.get_source_segment(src, node))
    assert set(found) == set(NAMES), set(NAMES) - set(found)
    ns = {"messagebox": msg}
    for code in found.values():
        exec(compile(code, str(APP), "exec"), ns)
    return {n: ns[n] for n in NAMES}


@pytest.fixture
def app(monkeypatch):
    import stage_five.desktop_screening_hook as H

    msg = Msg()
    methods = _load_methods(msg)

    class Harness:
        pass

    for n, f in methods.items():
        setattr(Harness, n, f)
    a = Harness()
    a.formula_entry, a.unit_var = Widget("Nd2Fe14B"), Var("at%")
    a.excess_entry, a.prealloy_formula_entry = Widget(), Widget()
    a.prealloy_mass_entry, a.prealloy_atpct_entry = Widget(), Widget()
    a.sample_id_entry = Widget("S-1")
    a.stage5_proto_var, a.stage5_site_groups_entry = Var(True), Widget("")
    a.stage5_auto_var, a.stage5_force_var = Var(True), Var(False)
    a.stage5_btn, a.status_label, a.result_text = Widget(), Widget(), TextBox()
    a.last_calc_output = ["PREVIEW"]
    a.rendered = []
    a.render_lit_section = lambda: a.rendered.append(a.stage5_text)
    a.after = lambda ms, fn: fn()
    a.msg = msg
    a.calls = []

    def fake_run(**kw):
        a.calls.append(kw)

    monkeypatch.setattr(H, "run_screening_async", fake_run)
    return a


def _preview(a, comp, **inputs):
    a.last_at_composition = dict(comp)
    a.last_preview_key = a._preview_key()
    a.stage5_text = ""


def test_auto_run_uses_the_final_atomic_composition_not_the_typed_text(app):
    app.formula_entry.text, app.unit_var.v = "Fe65Nd30Co5", "wt%"
    _preview(app, {"Fe": 80.1, "Nd": 15.9, "Co": 4.0})
    app._auto_stage5()
    assert len(app.calls) == 1
    assert app.calls[0]["formula"] == "Fe80.1Nd15.9Co4"          # converted atomic %, not the wt% text
    assert app.stage5_running and app.stage5_btn.config["state"] == "disabled"
    assert "running in the background" in app.rendered[-1]
    app.calls[0]["on_complete"]("RESULT TABLE")                      # worker finishes
    assert app.stage5_running is False and app.stage5_btn.config["state"] == "normal"
    assert app.rendered[-1] == "RESULT TABLE" and "complete" in app.status_label.config["text"]


def test_not_ternary_is_skipped_with_a_message(app):
    _preview(app, {"Fe": 50, "Nd": 25, "Co": 15, "B": 10})
    app._auto_stage5()
    assert not app.calls and "ternary" in app.rendered[-1]


def test_option_off_does_nothing(app):
    app.stage5_auto_var.v = False
    _preview(app, {"Fe": 82.35, "Nd": 11.76, "B": 5.88})
    app._auto_stage5()
    assert not app.calls and not app.rendered


def test_second_preview_while_running_does_not_start_a_second_run(app):
    _preview(app, {"Fe": 82.35, "Nd": 11.76, "B": 5.88})
    app._auto_stage5()
    _preview(app, {"Fe": 70.0, "Nd": 20.0, "B": 10.0})
    app._auto_stage5()
    assert len(app.calls) == 1 and "still running" in app.rendered[-1]


def test_result_for_an_earlier_composition_is_not_shown_in_a_newer_preview(app):
    _preview(app, {"Fe": 82.35, "Nd": 11.76, "B": 5.88})
    app._auto_stage5()
    app.formula_entry.text = "Fe70Nd20B10"                              # user previews something else
    _preview(app, {"Fe": 70.0, "Nd": 20.0, "B": 10.0})
    before = list(app.rendered)
    app.calls[0]["on_complete"]("OLD RESULT")
    assert app.rendered == before and "earlier composition" in app.status_label.config["text"]
    assert app.stage5_running is False


def test_errors_and_failure_keep_the_app_usable(app):
    _preview(app, {"Fe": 82.35, "Nd": 11.76, "B": 5.88})
    app._auto_stage5()
    app.calls[0]["on_error"]("Stage 5 screening error: RuntimeError: boom")
    assert "boom" in app.rendered[-1] and app.stage5_running is False
    assert app.status_label.config["text"] == "Stage 5 screening failed"


def test_button_without_preview_wt_percent_or_prealloy_asks_for_a_preview(app):
    app.unit_var.v = "wt%"
    app.run_stage5_screen()
    assert not app.calls and app.msg.calls and "Calculate & Preview" in app.msg.calls[-1][1][1]
    app.msg.calls.clear()
    app.unit_var.v = "at%"
    app.prealloy_mass_entry.text = "13"
    app.run_stage5_screen()
    assert not app.calls and app.msg.calls


def test_button_without_preview_uses_a_plain_atomic_formula_as_typed(app):
    app.run_stage5_screen()
    assert app.calls and app.calls[0]["formula"] == "Nd2Fe14B"
    assert app.calls[0]["force_recompute"] is False
    assert app.result_text.parts                                      # legacy: text appended, not in the preview


def test_button_with_matching_preview_uses_the_preview_composition(app):
    app.formula_entry.text = "Fe65Nd30Co5"
    app.unit_var.v = "wt%"
    _preview(app, {"Fe": 80.1, "Nd": 15.9, "Co": 4.0})
    app.run_stage5_screen()
    assert app.calls[0]["formula"] == "Fe80.1Nd15.9Co4"
    app.stage5_running = False
    app.formula_entry.text = "Fe1Nd1Co1"                              # changed after the preview: stale
    app.run_stage5_screen()
    assert len(app.calls) == 1 and app.msg.calls                     # wt% + no matching preview -> asks for a preview


def test_button_blocked_while_running(app):
    app.stage5_running = True
    app.run_stage5_screen()
    assert not app.calls and app.msg.calls and app.msg.calls[-1][0] == "info"


def test_invalid_site_group_shows_a_warning_and_does_not_start(app):
    app.stage5_site_groups_entry.text = "FE"
    _preview(app, {"Fe": 82.35, "Nd": 11.76, "B": 5.88})
    app._auto_stage5()
    assert not app.calls and app.msg.calls and "site group" in app.msg.calls[-1][1][1].lower()
    assert getattr(app, "stage5_running", False) is False
