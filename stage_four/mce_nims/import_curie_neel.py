"""
import_curie_neel.py

Roadmap priority 5 (broader magnetic databases), used here only for the
La(Fe,Si/Al)13 family: the Curie/Néel temperature dataset of Kelly and
Cole, Sci. Data (2025), doi:10.1038/s41597-025-06244-6; data
doi:10.6084/m9.figshare.29559686; code github.com/C-R-Kelly/Curie-Neel-temperature-dataset.
Licence CC BY 4.0 -- cite the paper and the dataset.

56,037 records text-mined with ChemDataExtractor 2 + Snowball v2;
estimated precision 72 %, recall 61 % (paper). quality_flag
'literature_mined'.

Put curie_neel_database_data_processed.json (figshare) in
stage_four/mce_nims/data/curie_neel/ (gitignored).

Pitfalls of the file, handled here:
  - 'value' is NOT converted to kelvin: a "Tc = 250 °C" record has
    value [250] with units 'Celsius^(1.0)'. Converted here.
  - Bounds and approximations lose their qualifier: raw '>580' gives
    value [580]. Records whose raw value has '>', '<', '~'/'∼', '±', a
    range or two values are rejected, not taken at face value.
  - 'Tc' / 'TC' also means ferroelectric or superconducting transitions;
    for this family only Curie specifiers are kept, Néel ('TN') rejected.
  - 'names' can hold several compounds; a record is used only when
    exactly one of them is a La(Fe,Si/Al)13 formula.
  - Plausibility for La(Fe,Si/Al)13: T_C outside 100-500 K is rejected
    (values such as 6.9 K or 15 K are ΔT_ad or hysteresis widths picked
    up as T_C). The window is a stated choice (PLAUSIBLE_TC_K).

  python import_curie_neel.py --dry-run
  python import_curie_neel.py
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
from import_mcedb import family_of, nims_comparison
from literature_db import upsert_records
from mcedb_dataset import FormulaError, in_lafesi_family, parse_formula

DEFAULT_PATH = Path(__file__).resolve().parent / 'data' / 'curie_neel' / 'curie_neel_database_data_processed.json'
SOURCE = 'curie_neel_kelly_cole_2025'
LICENCE = 'CC BY 4.0 (Kelly & Cole, Sci. Data 2025, doi:10.6084/m9.figshare.29559686)'
QUALITY_FLAG = 'literature_mined'
PLAUSIBLE_TC_K = (100.0, 500.0)
CURIE_SPECIFIERS = {'tc', 'curie temperature', 'tcurie', 'curie point', 't_c', 'curie'}


def to_kelvin(value, units):
    """Value in the dataset's normalised unit -> kelvin; None if the unit is not recognised."""
    m = re.fullmatch(r'(?:\(10\^(-?\d+(?:\.\d+)?)\) \* )?(Kelvin|Celsius|Fahrenheit)\^\(1\.0\)', str(units))
    if not m:
        return None
    v = float(value) * (10 ** float(m.group(1)) if m.group(1) else 1.0)
    return {'Kelvin': v, 'Celsius': v + 273.15, 'Fahrenheit': (v - 32) * 5 / 9 + 273.15}[m.group(2)]


def classify(rec):
    """(status, formula, composition, T_C in K)."""
    names = rec.get('names') or []
    hits = []
    for n in names:
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
    if str(rec.get('specifier', '')).strip().lower() not in CURIE_SPECIFIERS:
        return f"specifier '{rec.get('specifier')}' is not a Curie temperature", name, comp, None
    raw = str(rec.get('raw_value', '')).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?', raw) or len(rec.get('value') or []) != 1:
        return 'raw value not a plain number (bound, approximation, range)', name, comp, None
    t = to_kelvin(rec['value'][0], rec.get('units'))
    if t is None:
        return f"unit not recognised ({rec.get('units')})", name, comp, None
    if not PLAUSIBLE_TC_K[0] <= t <= PLAUSIBLE_TC_K[1]:
        return f'T_C outside {PLAUSIBLE_TC_K[0]:.0f}-{PLAUSIBLE_TC_K[1]:.0f} K (implausible for this family)', name, comp, t
    return 'accepted', name, comp, t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-nims', action='store_true')
    args = ap.parse_args()

    path = Path(args.data)
    if not path.exists():
        sys.exit(f"{path} not found: download curie_neel_database_data_processed.json from "
                 f"https://doi.org/10.6084/m9.figshare.29559686 into {path.parent}/")
    data = json.loads(path.read_text(encoding='utf-8'))

    rows = []
    for rid, rec in data.items():
        status, name, comp, t = classify(rec)
        rows.append({'external_id': str(rec.get('_id', rid)), 'status': status, 'formula': name,
                     'composition': comp, 'Tc': t,
                     'doi': re.sub(r'^https?://(dx\.)?doi\.org/', '', str(rec.get('doi', ''))).strip().lower() or None,
                     'raw_value': rec.get('raw_value'), 'raw_units': rec.get('raw_units'),
                     'specifier': rec.get('specifier'), 'confidence': rec.get('confidence'),
                     'sentence': rec.get('sentence')})
    df = pd.DataFrame(rows)
    acc = df[df['status'] == 'accepted'].copy()
    acc['composition_key'] = [composition_key(c) for c in acc['composition']]
    acc['dS'] = float('nan')
    acc['field_T'] = float('nan')

    print(f"Curie/Néel dataset: {len(df)} records")
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
        records.append({
            'source': SOURCE, 'external_id': r['external_id'], 'doi': r['doi'], 'licence': LICENCE,
            'quality_flag': QUALITY_FLAG,
            'metal_at_pct': Json({e: round(v, 4) for e, v in metal.items()}),
            'interstitial_at_pct': Json({e: round(v, 4) for e, v in inter.items()}) if inter else None,
            'composition_key': r['composition_key'], 'family': family_of(metal),
            'composition_text': r['formula'], 't_tr_k': r['Tc'], 't_tr_source': 'reported',
            'comments': (f"specifier '{r['specifier']}', raw '{r['raw_value']} {r['raw_units']}', "
                         f"confidence {r['confidence']:.2f}; sentence: {r['sentence']}"),
        })
    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    try:
        ids = upsert_records(db.cursor, records)
        db.commit()
        print(f"\nImported {len(ids)} records (source '{SOURCE}', no points: this dataset has T_C only)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
