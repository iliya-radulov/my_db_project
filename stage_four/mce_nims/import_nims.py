"""
import_nims.py

Loads the NIMS La(Fe,Si)13 dataset into the staging tables of
007_mce_literature.sql (run that migration first).

  python import_nims.py --dry-run     # validate and count, no database
  python import_nims.py               # upsert into mce_literature_records/_points

Re-running is safe: records are upserted on (source, external_id) and
each record's points are replaced, so the tables always match the file.
The whole import is one transaction; on any error nothing is written.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from composition_key import composition_key
from literature_db import clean, replace_points, upsert_records
from nims_dataset import (DATASET_DOI, DEFAULT_PATH, INTERSTITIALS, METAL_ELEMENTS,
                          expand_points, load_nims, restore_T_tr)

SOURCE = 'nims_lafesi_1_13'
LICENCE = f'CC BY 4.0 (NIMS MDR, doi:{DATASET_DOI})'
QUALITY_FLAG = 'experimental_literature'   # measured values, curated from papers by NIMS

RECORD_COLUMNS = {
    # table column: dataframe column
    'doi': 'doi', 'article_ref': 'article_id', 'family': 'family',
    'composition_text': 'composition_text', 'composition_details': 'composition_details',
    'method': 'method', 'anneal_time_h': 'anneal_time_h', 'anneal_temp_k': 'anneal_temp_K',
    'phase_1_13_pct': 'phase_1_13_pct', 'phase_alpha_fe_pct': 'phase_alpha_fe_pct',
    'lattice_a_pm_angstrom': 'a_pm_A', 'density_g_cm3': 'density_g_cm3',
    't_tr_k': 'T_tr_restored_K', 't_tr_source': 'T_tr_source', 't_hys_k': 'T_hys_K',
    'h_tr_t': 'H_tr_T', 'comments': 'comments',
}


def record_rows(df):
    for nims_id, r in df.iterrows():
        metal_raw = {e: float(r[e]) for e in METAL_ELEMENTS if r[e] > 0}
        inter_raw = {k: float(r[k]) for k in INTERSTITIALS.values() if r[k] > 0}
        key = composition_key(metal_raw, inter_raw)          # from unrounded values
        metal = {e: round(v, 4) for e, v in metal_raw.items()}
        inter = {e: round(v, 4) for e, v in inter_raw.items()}
        row = {col: clean(r[src]) for col, src in RECORD_COLUMNS.items()}
        iso = clean(r['isothermal_protocol'])
        row.update(source=SOURCE, external_id=str(nims_id), licence=LICENCE, quality_flag=QUALITY_FLAG,
                   composition_key=key,
                   metal_at_pct=Json(metal), interstitial_at_pct=Json(inter) if inter else None,
                   isothermal_protocol=None if iso is None else bool(iso))
        yield int(nims_id), row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--dry-run', action='store_true', help='validate and count only')
    args = ap.parse_args()

    df = restore_T_tr(load_nims(args.data))
    dS = expand_points(df, 'dS')
    dT = expand_points(df, 'dTad')

    print(f"{len(df)} records from {df['doi'].nunique()} papers")
    print(f"  T_tr: {df['T_tr_source'].value_counts().to_dict()}, missing {int(df['T_tr_restored_K'].isna().sum())}")
    print(f"  dS_max points: {int(dS['dS_max'].notna().sum())}, dT_ad_max points: {int(dT['dT_ad_max_K'].notna().sum())}")
    # same code path as the database rows, so the counts match what is stored
    keys = pd.Series({nims_id: row['composition_key'] for nims_id, row in record_rows(df)})
    per_key = df.assign(key=keys).groupby('key')['doi'].nunique()
    print(f"  composition keys: {keys.nunique()} distinct; {int((per_key > 1).sum())} keys appear in more "
          f"than one paper (kept as separate records, see the duplicates rule in 007_mce_literature.sql)")
    print(f"  quality_flag: '{QUALITY_FLAG}' for all {len(df)} records")
    for kind, pts in (('dS', dS), ('dTad', dT)):
        if pts.attrs['length_mismatch']:
            print(f"  {kind}: list lengths differ from the field list, values left empty: {pts.attrs['length_mismatch']}")
    if args.dry_run:
        return

    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    cur = db.cursor
    try:
        ids = upsert_records(cur, (row for _, row in record_rows(df)))
        points = [(str(int(p['nims_id'])), 'dS_max', p['field_T'], p['dS_max'], p['T_peak_K'], p['dS_fwhm_K'])
                  for _, p in dS.iterrows()]
        points += [(str(int(p['nims_id'])), 'dT_ad_max', p['field_T'], p['dT_ad_max_K'], p['T_peak_K'], None)
                   for _, p in dT.iterrows()]
        n_points = replace_points(cur, ids, points)
        db.commit()
        print(f"Imported {len(ids)} records and {n_points} points (source '{SOURCE}')")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
