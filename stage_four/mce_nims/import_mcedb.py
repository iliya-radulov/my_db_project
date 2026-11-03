"""
import_mcedb.py

Roadmap priority 3: the LLM-extracted magnetocaloric database
(github.com/RunqingYang1996/MCEdatabase; see mcedb_dataset.py) into the
literature tables of 007_mce_literature.sql, filtered to the
La(Fe,Si/Al)13 family (roadmap §5: "filter to compositions that match our
target systems").

PERMISSION: the source repository has no licence file; B. Liao (corresponding
author) agreed by email on 2 Nov 2026 to its use with citation of the paper
(Yuan, Yang, Patra, Liao, AIP Advances 14, 085125 (2024)). The data are not
redistributed: they are read from a local clone of the authors' repository.

  python import_mcedb.py --dry-run     # parse, filter, report; no database
  python import_mcedb.py               # write (same tables as NIMS, source 'mcedb_github')
  python import_mcedb.py --all-families --dry-run

The report (roadmap §4 step C and §5 day 7):
  - every row accepted or rejected, with the reason;
  - overlap with NIMS by paper (DOI) and by paper + composition key;
  - accuracy of the LLM extraction where both sources have the same
    paper and composition: T_c against NIMS T_tr (reported values only)
    and |ΔS| against NIMS at the same field.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg2.extras import Json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from composition_key import composition_key, split_composition
from literature_db import replace_points, upsert_records
from mcedb_dataset import DEFAULT_REPO, load_mcedb
from nims_dataset import DEFAULT_PATH as NIMS_PATH
from nims_dataset import INTERSTITIALS, METAL_ELEMENTS, expand_points, load_nims

SOURCE = 'mcedb_github'
LICENCE = ('no licence file; use with citation permitted by B. Liao, email 2 Nov 2026 '
           '(cite Yuan et al., AIP Advances 14, 085125 (2024))')


def repo_commit(repo):
    """Commit hash of the cloned repository, read from .git without running git."""
    head = Path(repo) / '.git' / 'HEAD'
    try:
        ref = head.read_text().strip()
        if ref.startswith('ref: '):
            return (Path(repo) / '.git' / ref[5:]).read_text().strip()[:7]
        return ref[:7]
    except OSError:
        return 'unknown'


def family_of(metal_pct):
    order = [e for e in METAL_ELEMENTS if e not in ('Fe', 'La')]
    subs = [e for e in order if e in metal_pct] + sorted(e for e in metal_pct if e not in order + ['Fe', 'La'])
    return '+'.join(subs) if subs else 'none'


def classify(df, all_families):
    """Adds 'status': 'accepted' or the first reason the row is rejected."""
    status = []
    for _, r in df.iterrows():
        if r['covered_by_corrected']:
            status.append('raw row of a paper in the corrected file (corrected rows used)')
        elif r['source_index_problem']:
            status.append('source index unreadable (e.g. "948(1)")')
        elif r['composition'] is None:
            status.append(f"formula rejected ({r['formula_problem'].split(' at ')[0].replace('formula: ', '')})")
        elif not all_families and not r['lafesi_family']:
            status.append('not La(Fe,Si/Al)13 family')
        elif pd.isna(r['Tc']) and (pd.isna(r['dS']) or pd.isna(r['field_T'])):
            status.append('no usable value (T_c, or |ΔS| with field)')
        else:
            status.append('accepted')
    out = df.copy()
    out['status'] = status
    return out


def nims_comparison(acc):
    """Compare accepted rows with NIMS records of the same paper and composition key."""
    nims = load_nims(NIMS_PATH)
    nims_keys = {}
    for nid, r in nims.iterrows():
        key = composition_key({e: r[e] for e in METAL_ELEMENTS if r[e] > 0},
                              {k: r[k] for k in INTERSTITIALS.values() if r[k] > 0})
        for d in r['doi_list']:
            nims_keys.setdefault((d, key), []).append(nid)
    nims_dois = {d for (d, _) in nims_keys}
    pts = expand_points(nims, 'dS')

    in_paper = acc['doi'].isin(nims_dois)
    print(f"\nOverlap with NIMS: {int(in_paper.sum())} of {len(acc)} accepted rows from papers NIMS also has "
          f"({acc.loc[in_paper, 'doi'].nunique()} papers); {acc.loc[~in_paper, 'doi'].nunique()} papers only here")

    tc_pairs, ds_pairs, n_key = [], [], 0
    for _, r in acc[in_paper].iterrows():
        ids = nims_keys.get((r['doi'], r['composition_key']))
        if not ids:
            continue
        n_key += 1
        if pd.notna(r['Tc']):
            ref = [nims.at[i, 'T_tr_K'] for i in ids if pd.notna(nims.at[i, 'T_tr_K'])]
            if ref:
                tc_pairs.append((r['Tc'], min(ref, key=lambda v: abs(v - r['Tc']))))
        if pd.notna(r['dS']) and pd.notna(r['field_T']):
            ref = pts[pts['nims_id'].isin(ids) & np.isclose(pts['field_T'], r['field_T'])]['dS_max'].dropna()
            if len(ref):
                ds_pairs.append((r['dS'], min(ref, key=lambda v: abs(v - r['dS']))))
    print(f"  same paper and same composition key: {n_key} rows")
    for name, pairs, tol, unit in (('T_c vs NIMS T_tr', tc_pairs, 2.0, 'K'),
                                   ('|ΔS| vs NIMS, same field', ds_pairs, 0.5, 'J/kg K')):
        if not pairs:
            print(f"  {name}: no comparable pairs"); continue
        a = np.array(pairs)
        diff = np.abs(a[:, 0] - a[:, 1])
        print(f"  {name}: {len(a)} pairs, within {tol} {unit}: {np.mean(diff <= tol):.0%}, "
              f"median |difference| {np.median(diff):.2f} {unit}, worst {diff.max():.1f} {unit}")
    print("  (NIMS is closest-match per pair: where a paper reports several values for one composition,\n"
          "   the nearest NIMS value is used -- an optimistic comparison.)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default=str(DEFAULT_REPO))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--all-families', action='store_true', help='do not filter to La(Fe,Si/Al)13')
    ap.add_argument('--no-nims', action='store_true', help='skip the comparison with NIMS')
    args = ap.parse_args()

    commit = repo_commit(args.repo)
    df = classify(load_mcedb(args.repo), args.all_families)
    acc = df[df['status'] == 'accepted'].copy()
    acc['composition_key'] = [composition_key(c) for c in acc['composition']]

    print(f"MCEdatabase (commit {commit}): {len(df)} rows "
          f"({(df['file'] == '725_updated.csv').sum()} corrected, {(df['file'] == 'modified6125.csv').sum()} raw)")
    for reason, n in df['status'].value_counts().items():
        print(f"  {n:5d}  {reason}")
    print(f"Accepted: {len(acc)} rows from {acc['doi'].nunique()} papers; quality_flag "
          f"{acc['quality_flag'].value_counts().to_dict()}; T_c {int(acc['Tc'].notna().sum())}, "
          f"|ΔS| with field {int((acc['dS'].notna() & acc['field_T'].notna()).sum())}; "
          f"{acc['composition_key'].nunique()} composition keys")
    if not args.no_nims:
        nims_comparison(acc)
    if args.dry_run:
        return

    records, points = [], []
    for _, r in acc.iterrows():
        metal, inter = split_composition(r['composition'])
        records.append({
            'source': SOURCE, 'external_id': r['external_id'], 'doi': r['doi'],
            'article_ref': str(int(r['paper_index'])), 'licence': LICENCE,
            'quality_flag': r['quality_flag'],
            'metal_at_pct': Json({e: round(v, 4) for e, v in metal.items()}),
            'interstitial_at_pct': Json({e: round(v, 4) for e, v in inter.items()}) if inter else None,
            'composition_key': r['composition_key'], 'family': family_of(metal),
            'composition_text': r['Material'],
            't_tr_k': r['Tc'], 't_tr_source': 'reported' if pd.notna(r['Tc']) else None,
            'comments': (f"MCEdatabase {commit}, {r['file']}; as extracted: dS='{r['Magnetic Entropy Change']}', "
                         f"field='{r['Magnetic Field']}', Tc='{r['Curie Temperature']}'"),
        })
        points.append((r['external_id'], 'dS_max', r['field_T'], r['dS'], None, None))

    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()
    try:
        ids = upsert_records(db.cursor, records)
        n_points = replace_points(db.cursor, ids, points)
        db.commit()
        print(f"\nImported {len(ids)} records and {n_points} points (source '{SOURCE}')")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
