"""
import_court_cole_2018.py

Fourth literature source, La(Fe,Si/Al)13 Curie temperatures only: the
2018 Curie/Néel database of Court and Cole, Sci. Data 5, 180111 (2018),
doi:10.1038/sdata.2018.111; data doi:10.6084/m9.figshare.c.3954418.
Licence CC BY 4.0 (article; data on figshare) -- cite the paper.

39,822 records, ChemDataExtractor 1.3 + modified Snowball; estimated
precision 73 % (paper). The predecessor of the Kelly & Cole 2025 dataset
(import_curie_neel.py): papers present in both are kept as separate
records (duplicates rule) and show up as overlaps in consistency_report.py.
quality_flag 'literature_mined'.

Put phase_transitions.json (one JSON record per line) in
stage_four/mce_nims/data/court_cole_2018/ (gitignored).

Differences from the 2025 file, checked on the real data:
  - 'Normalised Value' really is in kelvin ('Normalised Units' 'K', or
    'K.' in 142 records); 355 records have no normalised value.
  - Fields: 'Names', 'Type' ('Curie' / 'Néel'), 'Extracted Value',
    'Extracted Units', 'DOI', 'Title', 'Confidence', '_id' {'$oid': …}.
Same acceptance rules as import_curie_neel.py: exactly one La(Fe,Si/Al)13
compound, Curie type, plain-number extracted value (no bound, range,
approximation), T_C within PLAUSIBLE_TC_K.

  python import_court_cole_2018.py --dry-run
  python import_court_cole_2018.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from composition_key import composition_key, split_composition
from import_curie_neel import PLAUSIBLE_TC_K
from import_mcedb import family_of, nims_comparison
from literature_db import upsert_records
from mcedb_dataset import FormulaError, in_lafesi_family, parse_formula

DEFAULT_PATH = Path(__file__).resolve().parent / 'data' / 'court_cole_2018' / 'phase_transitions.json'
SOURCE = 'curie_neel_court_cole_2018'
LICENCE = 'CC BY 4.0 (Court & Cole, Sci. Data 5, 180111 (2018), doi:10.6084/m9.figshare.c.3954418)'
QUALITY_FLAG = 'literature_mined'


def classify(rec):
    """(status, formula, composition, T_C in K)."""
    hits = []
    for n in rec.get('Names') or []:
        try:
            c = parse_formula(n)
        except FormulaError:
            continue
        if in_lafesi_family(c):
            hits.append((n, c))
    if not hits:
        return 'not La(Fe,Si/Al)13 family', None, None, None
    if len(hits) > 1:
        return 'several La(Fe,Si/Al)13 compounds in one record', None, None, None
    name, comp = hits[0]
    if rec.get('Type') != 'Curie':
        return f"type '{rec.get('Type')}' is not Curie", name, comp, None
    if not re.fullmatch(r'\d+(?:\.\d+)?', str(rec.get('Extracted Value', '')).strip()):
        return 'extracted value not a plain number (bound, approximation, range)', name, comp, None
    if str(rec.get('Normalised Units', '')).strip().rstrip('.') != 'K':
        return 'no value normalised to K', name, comp, None
    t = float(rec['Normalised Value'])
    if not PLAUSIBLE_TC_K[0] <= t <= PLAUSIBLE_TC_K[1]:
        return f'T_C outside {PLAUSIBLE_TC_K[0]:.0f}-{PLAUSIBLE_TC_K[1]:.0f} K (implausible for this family)', name, comp, t
    return 'accepted', name, comp, t


def load_records(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-nims', action='store_true')
    args = ap.parse_args()

    path = Path(args.data)
    if not path.exists():
        sys.exit(f"{path} not found: download phase_transitions.json from "
                 f"https://doi.org/10.6084/m9.figshare.c.3954418 into {path.parent}/")
    recs = load_records(path)

    rows = []
    for rec in recs:
        status, name, comp, t = classify(rec)
        oid = rec.get('_id')
        rows.append({'external_id': oid.get('$oid') if isinstance(oid, dict) else str(oid),
                     'status': status, 'formula': name, 'composition': comp, 'Tc': t,
                     'doi': str(rec.get('DOI') or '').strip().lower() or None,
                     'raw_value': rec.get('Extracted Value'), 'raw_units': rec.get('Extracted Units'),
                     'confidence': rec.get('Confidence'), 'title': rec.get('Title')})
    df = pd.DataFrame(rows)
    acc = df[df['status'] == 'accepted'].copy()
    acc['composition_key'] = [composition_key(c) for c in acc['composition']]
    acc['dS'] = float('nan')
    acc['field_T'] = float('nan')

    print(f"Court & Cole 2018: {len(df)} records")
    for reason, n in df['status'].value_counts().items():
        print(f"  {n:6d}  {reason}")
    print(f"Accepted: {len(acc)} records from {acc['doi'].nunique()} papers, "
          f"{acc['composition_key'].nunique()} composition keys; quality_flag '{QUALITY_FLAG}'")
    if not args.no_nims:
        nims_comparison(acc)
    if args.dry_run:
        return

    records = []
    for _, r in acc.iterrows():
        metal, inter = split_composition(r['composition'])
        conf = f"{r['confidence']:.2f}" if pd.notna(r['confidence']) else 'none (deterministic parser)'
        records.append({
            'source': SOURCE, 'external_id': r['external_id'], 'doi': r['doi'], 'licence': LICENCE,
            'quality_flag': QUALITY_FLAG,
            'metal_at_pct': Json({e: round(v, 4) for e, v in metal.items()}),
            'interstitial_at_pct': Json({e: round(v, 4) for e, v in inter.items()}) if inter else None,
            'composition_key': r['composition_key'], 'family': family_of(metal),
            'composition_text': r['formula'], 't_tr_k': r['Tc'], 't_tr_source': 'reported',
            'comments': f"extracted '{r['raw_value']} {r['raw_units']}', confidence {conf}; title: {r['title']}",
        })
    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    try:
        ids = upsert_records(db.cursor, records)
        db.commit()
        print(f"\nImported {len(ids)} records (source '{SOURCE}', no points: T_C only)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
