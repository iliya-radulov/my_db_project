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
