"""
link_samples.py

Links the lab's own samples to the literature records (decision 2 Nov
2026, option B) through the composition key:

  1. computes composition_key() for every row of samples (from
     samples.composition) and upserts it into sample_composition_keys;
  2. reports exact matches (the view mce_literature_matches) and near
     matches: literature records within --near at.% of a sample in every
     element (composition_distance), e.g. EDX vs nominal compositions.

Samples whose composition cannot be keyed (empty, placeholder, no metal
element) are skipped and listed, never guessed.

Usage:
  python link_samples.py               # update keys, print the report
  python link_samples.py --near 1.0    # near-match tolerance in at.% (default 0.5)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from composition_key import composition_distance, composition_key


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--near', type=float, default=0.5, help='near-match tolerance, at.%% per element')
    args = ap.parse_args()

    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    cur = db.cursor
    try:
        cur.execute("SELECT id, sample_id, composition FROM samples ORDER BY id")
        samples = cur.fetchall()
        keyed, skipped = [], []
        for s in samples:
            try:
                key = composition_key(s['composition'] or {})
            except (ValueError, TypeError, AttributeError) as e:
                skipped.append((s['sample_id'], str(e)))
                continue
            keyed.append((s, key))
            cur.execute("""INSERT INTO sample_composition_keys (sample_id, composition_key, computed_at)
                           VALUES (%s, %s, NOW())
                           ON CONFLICT (sample_id) DO UPDATE
                           SET composition_key = EXCLUDED.composition_key, computed_at = NOW()""",
                        (s['id'], key))
        db.commit()
        print(f"{len(samples)} samples: {len(keyed)} keyed, {len(skipped)} skipped")
        for sid, why in skipped:
            print(f"  skipped {sid}: {why}")

        cur.execute("SELECT sample_id, composition_key, count(*) AS n, count(DISTINCT doi) AS papers "
                    "FROM mce_literature_matches GROUP BY 1, 2 ORDER BY 1")
        exact = cur.fetchall()
        print(f"\nExact matches: {len(exact)} samples")
        for m in exact:
            print(f"  {m['sample_id']:30s} {m['composition_key']:32s} {m['n']} records from {m['papers']} papers")

        cur.execute("SELECT id, source, external_id, doi, metal_at_pct, interstitial_at_pct, composition_key "
                    "FROM mce_literature_records")
        records = cur.fetchall()
        print(f"\nNear matches (every element within {args.near} at.%, excluding exact matches):")
        n_near = 0
        for s, key in keyed:
            near = []
            for r in records:
                if r['composition_key'] == key:
                    continue
                # metal at.% sum to 100 and interstitials are relative to that total,
                # so together they form one amount mapping on the same basis
                lit = {**r['metal_at_pct'], **(r['interstitial_at_pct'] or {})}
                d = composition_distance(s['composition'], lit)
                if d <= args.near:
                    near.append((d, r))
            if near:
                n_near += 1
                near.sort(key=lambda t: t[0])
                best = ', '.join(f"{r['source']}:{r['external_id']} ({d:.2f})" for d, r in near[:5])
                print(f"  {s['sample_id']:30s} {key:32s} {len(near)} records; closest: {best}")
        if not n_near:
            print("  none")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
