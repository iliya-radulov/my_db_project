"""
literature_db.py

Shared writer for the magnetocaloric literature tables of
007_mce_literature.sql, used by every source's import script, so all
sources land the same way:

  - records are upserted on (source, external_id);
  - each record's points are replaced (the tables always match the source);
  - everything happens in the caller's transaction; the caller commits.
"""
import numpy as np
import pandas as pd


def clean(v):
    """NaN/None/pd.NA -> None; numpy scalars -> Python scalars (psycopg2
    cannot bind numpy or pandas missing-value types, and a leaked repr
    breaks the SQL -- see the Stage 1 'schema "np" does not exist' lesson)."""
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (float, np.floating)) and np.isnan(v):
        return None
    if isinstance(v, np.generic):
        return v.item()
    return v


def upsert_records(cur, records):
    """records: iterable of dicts with at least 'source', 'external_id' and
    the NOT NULL columns. Returns {external_id: record id}."""
    ids = {}
    for row in records:
        row = {k: clean(v) for k, v in row.items()}
        cols = list(row)
        updates = ', '.join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ('source', 'external_id'))
        cur.execute(
            f"INSERT INTO mce_literature_records ({', '.join(cols)}, retrieved_at) "
            f"VALUES ({', '.join(['%s'] * len(cols))}, NOW()) "
            f"ON CONFLICT (source, external_id) DO UPDATE SET {updates}, retrieved_at = NOW() "
            f"RETURNING id",
            [row[c] for c in cols])
        ids[row['external_id']] = cur.fetchone()['id']
    return ids


def replace_points(cur, ids, points):
    """points: iterable of (external_id, quantity, field_t, value, t_peak_k,
    fwhm_k). Deletes the existing points of every record in ids, then
    inserts. Points without a value or field are skipped. Returns the
    number inserted."""
    cur.execute("DELETE FROM mce_literature_points WHERE record_id = ANY(%s)", (list(ids.values()),))
    n = 0
    for ext_id, quantity, field_t, value, t_peak, fwhm in points:
        value, field_t = clean(value), clean(field_t)
        if value is None or field_t is None:
            continue
        cur.execute("INSERT INTO mce_literature_points (record_id, quantity, field_t, value, t_peak_k, fwhm_k) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (ids[ext_id], quantity, field_t, value, clean(t_peak), clean(fwhm)))
        n += cur.rowcount
    return n
