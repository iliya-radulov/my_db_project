"""Desktop hook: opt-in site groups, prototype options in the cache key (fake database)."""
import json

import pytest

pytest.importorskip("pymatgen")
import desktop_screening_hook as H
import screen_ternary as S
from prototype_match import PrototypeFilter


# ------------------------------------------------------------------ GUI field parsing

@pytest.mark.parametrize("text,expected", [
    ("", ()), (None, ()), ("   ", ()),
    ("FE,SI", (("FE", "SI"),)),
    ("fe, si", (("FE", "SI"),)),
    ("Fe Si", (("FE", "SI"),)),
    ("FE,SI; AL,GA", (("FE", "SI"), ("AL", "GA"))),
    ("FE,SI\nAL,GA,IN", (("FE", "SI"), ("AL", "GA", "IN"))),
])
def test_parse_site_groups(text, expected):
    assert H.parse_site_groups(text) == expected


@pytest.mark.parametrize("text", ["FE", "FE,FE", "F3,SI", "FE,SI;SI,AL", "FEE,SI", "FE,"])
def test_parse_site_groups_rejects_bad_input(text):
    with pytest.raises(ValueError):
        H.parse_site_groups(text)


def test_prototype_options_default_is_plain_composition_distance():
    assert H.prototype_options(True, "") == PrototypeFilter()
    assert H.prototype_options(True, "").site_groups == ()          # opt-in only
    assert H.prototype_options(False, "FE,SI") is None              # fallback off wins
    assert H.prototype_options(True, "FE,SI").site_groups == (("FE", "SI"),)


def test_describe_prototype_filter():
    assert H.describe_prototype_filter(None).startswith("off")
    txt = H.describe_prototype_filter(PrototypeFilter(site_groups=(("FE", "SI"),)))
    assert "site groups: FE+SI" in txt and "max Δx 0.16" in txt
    assert "site groups: none" in H.describe_prototype_filter(PrototypeFilter())


# ------------------------------------------------------------------ fake database

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.last = ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.last = sql
        self.conn.log.append((" ".join(sql.split()), params))

    def fetchone(self):
        if "information_schema" in self.last:
            col = self.conn.log[-1][1][1]
            return (1,) if col in self.conn.columns else None
        if "FROM calphad_ensemble_runs" in self.last:
            return self.conn.run_row
        if "RETURNING id" in self.last:
            return (42,)
        return None

    def fetchall(self):
        if "information_schema" in self.last:
            return [(c,) for c in sorted(self.conn.columns)]
        return []


class FakeConn:
    def __init__(self, columns=(), run_row=None):
        self.columns, self.run_row, self.log = set(columns), run_row, []

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def sql(self, needle):
        return [(s, p) for s, p in self.log if needle in s]


RUN_ROW = (7, "Nd2Fe14B", "B-FE-ND", 84, 78, True, {}, "2026-11-23")


def test_cache_lookup_includes_prototype_filter(monkeypatch):
    conn = FakeConn(columns={"prototype_filter", "match_type"}, run_row=None)
    monkeypatch.setattr(H, "_connect_db", lambda: conn)
    flt = PrototypeFilter(site_groups=(("FE", "SI"),))
    assert H.fetch_cached_screening("Nd2Fe14B", prototype_filter=flt) is None
    sql, params = conn.sql("FROM calphad_ensemble_runs")[0]
    assert "prototype_filter IS NOT DISTINCT FROM" in sql
    assert json.loads(params[1]) == flt.as_dict() and params[0] == H.compute_spec_sha256("Nd2Fe14B")
    # fallback off: matches runs stored with NULL
    H.fetch_cached_screening("Nd2Fe14B", prototype_filter=None)
    assert conn.sql("FROM calphad_ensemble_runs")[-1][1][1] is None


def test_cache_differs_with_site_groups_even_for_the_same_spec_hash():
    a = json.dumps(PrototypeFilter().as_dict())
    b = json.dumps(PrototypeFilter(site_groups=(("FE", "SI"),)).as_dict())
    assert a != b


def test_cache_before_migration_010(monkeypatch):
    conn = FakeConn(columns=set(), run_row=RUN_ROW)
    monkeypatch.setattr(H, "_connect_db", lambda: conn)
    # old table, fallback on: a stored run cannot contain prototype rows -> never served
    assert H.fetch_cached_screening("Nd2Fe14B") is None
    assert not conn.sql("FROM calphad_ensemble_runs")
    # old table, fallback off: served as before, without the filter clause
    out = H.fetch_cached_screening("Nd2Fe14B", prototype_filter=None)
    assert out is not None and out["run_id"] == 7 and out["prototype_filter_known"] is False
    assert "prototype_filter" not in conn.sql("FROM calphad_ensemble_runs")[0][0]
    assert "Nearest-prototype fallback" not in H.format_screening_summary({**out, "rows": []})


def test_summary_shows_the_options_of_the_run():
    base = {"run_id": 1, "formula": "X", "system": "A-B-C", "gate_passed": True, "n_survivors": 5, "n_total": 6,
            "rows": [], "prototype_filter": PrototypeFilter(site_groups=(("FE", "SI"),)).as_dict()}
    assert "site groups: FE+SI" in H.format_screening_summary(base)
    assert "off (exact" in H.format_screening_summary({**base, "prototype_filter": None})


def _report():
    return {"system": "B-FE-ND", "target_composition": {"FE": 0.8, "ND": 0.12, "B": 0.06}, "spec_sha256": "abc",
            "pycalphad_version": "0", "audit_log": [],
            "gates": {"gate_passed": False, "G1_survival": {"total": 84, "survived": 3}}}


def test_save_stores_the_filter_with_the_run(monkeypatch):
    flt = PrototypeFilter(site_groups=(("FE", "SI"),)).as_dict()
    conn = FakeConn(columns={"prototype_filter", "match_type"})
    monkeypatch.setattr(S, "_connect_db", lambda: conn)
    assert S.save_screening_to_db("Nd2Fe14B", _report(), {}, [], prototype_filter=flt) == 42
    sql, params = conn.sql("INSERT INTO calphad_ensemble_runs")[0]
    assert sql.count("prototype_filter") == 1 and json.loads(params[-1]) == flt

    old = FakeConn(columns=set())
    monkeypatch.setattr(S, "_connect_db", lambda: old)
    S.save_screening_to_db("Nd2Fe14B", _report(), {}, [], prototype_filter=flt)
    assert "prototype_filter" not in old.sql("INSERT INTO calphad_ensemble_runs")[0][0]


# ------------------------------------------------------------------ merged flow helpers

def test_composition_to_formula_and_applicability():
    assert H.composition_to_formula({"Nd": 11.76, "Fe": 82.35, "B": 5.88}) == "Nd11.76Fe82.35B5.88"
    assert H.composition_to_formula({"Fe": 80.1, "Nd": 15.9, "Co": 4.0, "B": 0}) == "Fe80.1Nd15.9Co4"
    f = H.composition_to_formula({"La": 7.1, "Fe": 82.1, "Si": 10.8})
    els, fr, _ = S.parse_ternary_formula(f)
    assert els == ["FE", "SI", "LA"] and fr == pytest.approx([0.821, 0.108, 0.071])
    assert H.stage5_applicable({"Fe": 1, "Nd": 1, "B": 1}) == (True, "")
    ok, why = H.stage5_applicable({"Fe": 1, "Nd": 1})
    assert not ok and "ternary" in why and "2 elements" in why
    assert not H.stage5_applicable({"Fe": 1, "Nd": 1, "B": 1, "Co": 1})[0]
    assert H.stage5_applicable({"Fe": 1, "Nd": 1, "B": 1, "Co": 0})[0]      # zero amounts do not count


def test_key_lookup_uses_env_then_the_apps_key_file(monkeypatch, tmp_path):
    import dft_sisso_predictor as D

    monkeypatch.delenv("MP_API_KEY", raising=False)
    kd = tmp_path / "work" / "sub"
    key_dir = tmp_path / "back_up" / "API"
    kd.mkdir(parents=True)
    key_dir.mkdir(parents=True)
    (key_dir / "MP_API_KEY.txt").write_text("  filekey \n")
    monkeypatch.chdir(kd)                                   # ../../back_up/API/MP_API_KEY.txt, as in the app
    assert D._resolve_mp_api_key() == "filekey"
    monkeypatch.setenv("MP_API_KEY", "envkey")
    assert D._resolve_mp_api_key() == "envkey"
    assert D._resolve_mp_api_key("explicit") == "explicit"
    monkeypatch.delenv("MP_API_KEY")
    (key_dir / "MP_API_KEY.txt").unlink()
    monkeypatch.setattr(D, "mp_key_file_candidates", lambda: [tmp_path / "nothing.txt"])
    with pytest.raises(RuntimeError, match="MP_API_KEY not found"):
        D._resolve_mp_api_key()


def _ensemble_for_screen():
    return {"system": "B-FE-ND", "target_composition": {"FE": 0.8, "ND": 0.12, "B": 0.06}, "spec_sha256": "abc",
            "pycalphad_version": "0", "audit_log": [], "edge_priority": ["FE-ND", "B-FE", "B-ND"],
            "gates": {"gate_passed": True, "parameters": {}, "G1_survival": {"total": 84, "survived": 78},
                      "G2_lineage_coverage": {"pass": True, "surviving_lineages_per_edge": {}}},
            "threshold_distribution": {"800.0": {"median_kJ": -8.79, "p05_kJ": -9.2, "p95_kJ": -8.4, "q25_kJ": -9.0,
                                                  "q75_kJ": -8.6, "iqr_kJ": 0.4, "eta2_by_edge": {},
                                                  "dominant_competing_assemblage": "A+B"}}}


def test_a_failing_materials_project_step_keeps_the_calphad_result(monkeypatch):
    ens = _ensemble_for_screen()
    monkeypatch.setattr(S, "run_binary_ensemble", lambda **kw: ens)

    def boom(**kw):
        raise RuntimeError("MP_API_KEY not found")

    monkeypatch.setattr(S, "predict_sisso_formation_gibbs", boom)
    bundle = S.screen_ternary("Nd2Fe14B", temperatures=[800.0], workers=1)
    assert bundle["ensemble"] is ens and bundle["comparison"] == []
    assert bundle["sisso"]["match_type"] == "sisso_unavailable" and "MP_API_KEY" in bundle["sisso"]["error"]

    conn = FakeConn(columns={"prototype_filter", "match_type", "verdict", "comparable", "mp_id", "run_id"})
    monkeypatch.setattr(S, "_connect_db", lambda: conn)
    S.save_screening_to_db("Nd2Fe14B", ens, bundle["sisso"], [], prototype_filter=PrototypeFilter().as_dict())
    sql, params = conn.sql("INSERT INTO calphad_dft_comparison")[0]
    assert "match_type" in sql and params.count("sisso_unavailable") == 2 and "NO_MP_ENTRY" in params
    assert params[0] == 42                                                         # the run row was saved first


def test_unavailable_rows_are_explained_in_the_preview():
    rows = [{"T_K": 800.0, "threshold_median_kJ": -8.79, "threshold_p05_kJ": -9.2, "threshold_p95_kJ": -8.4,
             "competing_assemblage": "A+B", "material_id": "NO_MP_ENTRY", "verdict": "sisso_unavailable"}]
    base = {"run_id": 1, "formula": "X", "system": "A-B-C", "gate_passed": True, "n_survivors": 5, "n_total": 6,
            "rows": rows, "prototype_filter": None, "sisso_error": "RuntimeError: MP_API_KEY not found"}
    txt = H.format_screening_summary(base)
    assert "[sisso_unavailable]" in txt and "MP_API_KEY not found" in txt and "Force recompute" in txt
    assert "-8.790" in txt                                                         # the CALPHAD band is still shown
    cached = {**base, "sisso_error": None}
    assert "[sisso_unavailable]" in H.format_screening_summary(cached)


# ------------------------------------------------------------ linking runs to samples (scripted fake database)

class ScriptCursor:
    """Answers by substring of the SQL; records every statement."""
    def __init__(self, conn):
        self.conn, self.out = conn, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        self.conn.log.append((sql, params))
        self.out = None
        for needle, result in self.conn.script:
            if needle in sql:
                self.out = result
                break

    def fetchone(self):
        return self.out[0] if self.out else None

    def fetchall(self):
        return list(self.out or [])


class ScriptConn:
    def __init__(self, script):
        self.script, self.log = script, []

    def cursor(self):
        return ScriptCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass


def _link(monkeypatch, script, run_id=7, code="S-1"):
    conn = ScriptConn(script)
    monkeypatch.setattr(H, "_connect_db", lambda: conn)
    return H.link_run_to_sample(run_id, code), conn


def test_link_with_the_link_table(monkeypatch):
    msg, conn = _link(monkeypatch, [("FROM samples", [(3,)]), ("SELECT sample_id FROM calphad_ensemble_runs", [(9,)]),
                                    ("information_schema.tables", [(1,)])])
    assert "linked to sample S-1" in msg
    assert any("INSERT INTO calphad_run_samples" in s for s, _ in conn.log)
    assert not any("UPDATE calphad_ensemble_runs" in s for s, _ in conn.log)   # run already has an old-column owner


def test_link_without_the_link_table_uses_the_old_column_once(monkeypatch):
    msg, conn = _link(monkeypatch, [("FROM samples", [(3,)]), ("SELECT sample_id FROM calphad_ensemble_runs", [(None,)])])
    assert "linked to sample" in msg and any("UPDATE calphad_ensemble_runs" in s for s, _ in conn.log)
    msg, _ = _link(monkeypatch, [("FROM samples", [(3,)]), ("SELECT sample_id FROM calphad_ensemble_runs", [(4,)])])
    assert "012" in msg and "not linked" in msg                                  # another sample owns it
    msg, _ = _link(monkeypatch, [("FROM samples", [(3,)]), ("SELECT sample_id FROM calphad_ensemble_runs", [(3,)])])
    assert "already linked" in msg


def test_link_unknown_sample_or_run(monkeypatch):
    assert "not found" in _link(monkeypatch, [("FROM samples", [])])[0]
    assert "run not found" in _link(monkeypatch, [("FROM samples", [(3,)]),
                                                  ("SELECT sample_id FROM calphad_ensemble_runs", [])])[0]


def test_runs_for_sample_are_listed_and_formatted(monkeypatch):
    import datetime
    row = (7, "La7.1Fe82.1Si10.8", "FE-LA-SI", True, 16, 20, datetime.datetime(2026, 11, 24, 9, 40))
    conn = ScriptConn([("FROM samples", [(3,)]), ("information_schema.tables", [(1,)]),
                       ("FROM calphad_ensemble_runs WHERE", [row])])
    monkeypatch.setattr(H, "_connect_db", lambda: conn)
    runs = H.fetch_runs_for_sample("S-1")
    assert runs[0]["run_id"] == 7 and runs[0]["system"] == "FE-LA-SI"
    assert any("calphad_run_samples" in s for s, _ in conn.log)
    text = "\n".join(H.format_sample_runs(runs))
    assert "run 7" in text and "16/20" in text and "PASS" in text
    assert H.format_sample_runs([]) == []
