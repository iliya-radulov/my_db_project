"""
consistency_report.py

Roadmap §5, day 7: a consistency report over everything in the
magnetocaloric literature tables, after one or more sources have been
imported:

  - records, papers, composition keys and quality flags per source;
  - new compositions: keys found in only one source, per source;
  - collisions: keys shared between sources, and the same paper in
    several sources;
  - agreement where two sources have the same paper and key (T_tr, and
    |ΔS| at the same field);
  - the lab's own samples: how many have exact matches, per source.

Read-only. Run after import_nims.py / import_mcedb.py / link_samples.py.

  python consistency_report.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

QUERIES = {
    'Per source': """
        SELECT source, quality_flag, count(*) AS records, count(DISTINCT doi) AS papers,
               count(DISTINCT composition_key) AS keys,
               count(t_tr_k) AS with_t_tr
        FROM mce_literature_records GROUP BY 1, 2 ORDER BY 1, 2""",
    'Points per source': """
        SELECT r.source, p.quantity, count(*) AS points, count(DISTINCT p.record_id) AS records
        FROM mce_literature_points p JOIN mce_literature_records r ON r.id = p.record_id
        GROUP BY 1, 2 ORDER BY 1, 2""",
    'New compositions (keys found in only this source)': """
        WITH k AS (SELECT composition_key, array_agg(DISTINCT source) AS sources
                   FROM mce_literature_records GROUP BY 1)
        SELECT sources[1] AS source, count(*) AS keys_only_here
        FROM k WHERE cardinality(sources) = 1 GROUP BY 1 ORDER BY 1""",
    'Collisions between sources': """
        WITH k AS (SELECT composition_key, count(DISTINCT source) AS n FROM mce_literature_records GROUP BY 1),
             d AS (SELECT lower(doi) AS doi, count(DISTINCT source) AS n FROM mce_literature_records
                   WHERE doi IS NOT NULL GROUP BY 1)
        SELECT (SELECT count(*) FROM k WHERE n > 1) AS keys_in_several_sources,
               (SELECT count(*) FROM d WHERE n > 1) AS papers_in_several_sources""",
    'Agreement where two sources have the same paper and composition key': """
        WITH pairs AS (
            SELECT a.source AS source_a, b.source AS source_b, a.id AS id_a, b.id AS id_b,
                   a.t_tr_k AS t_a, b.t_tr_k AS t_b
            FROM mce_literature_records a
            JOIN mce_literature_records b
              ON a.composition_key = b.composition_key AND a.source < b.source
             AND position(lower(a.doi) IN lower(b.doi)) + position(lower(b.doi) IN lower(a.doi)) > 0),
        t AS (
            SELECT source_a, source_b, count(*) AS record_pairs,
                   count(*) FILTER (WHERE t_a IS NOT NULL AND t_b IS NOT NULL) AS t_tr_pairs,
                   round(avg(CASE WHEN abs(t_a - t_b) <= 2 THEN 1.0 ELSE 0 END)
                         FILTER (WHERE t_a IS NOT NULL AND t_b IS NOT NULL), 2) AS t_tr_share_within_2k
            FROM pairs GROUP BY 1, 2),
        d AS (
            SELECT q.source_a, q.source_b, count(*) AS ds_pairs_same_field
            FROM pairs q
            JOIN mce_literature_points pa ON pa.record_id = q.id_a AND pa.quantity = 'dS_max'
            JOIN mce_literature_points pb ON pb.record_id = q.id_b AND pb.quantity = 'dS_max'
             AND abs(pa.field_t - pb.field_t) < 1e-6
            GROUP BY 1, 2)
        SELECT t.*, coalesce(d.ds_pairs_same_field, 0) AS ds_pairs_same_field
        FROM t LEFT JOIN d USING (source_a, source_b) ORDER BY 1, 2""",
    "Own samples with exact matches": """
        SELECT source, quality_flag, count(DISTINCT sample_db_id) AS samples, count(*) AS matched_records
        FROM mce_literature_matches GROUP BY 1, 2 ORDER BY 1, 2""",
}


def main():
    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    try:
        for title, sql in QUERIES.items():
            db.cursor.execute(sql)
            rows = db.cursor.fetchall()
            print(f"\n{title}")
            if not rows:
                print("  (none)")
                continue
            cols = list(rows[0].keys())
            widths = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
            print('  ' + '  '.join(c.ljust(w) for c, w in zip(cols, widths)))
            for r in rows:
                print('  ' + '  '.join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
    finally:
        db.close()


if __name__ == '__main__':
    main()
