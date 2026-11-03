"""
augment.py

Does adding the text-mined / LLM-extracted literature sources to the NIMS
training data improve the model?

Sources added (accepted La(Fe,Si/Al)13 rows, same acceptance rules as
their import scripts):
  court2018  Court & Cole 2018 Curie/Néel database (T_C)      import_court_cole_2018.py
  kelly2025  Kelly & Cole 2025 Curie/Néel dataset (T_C)       import_curie_neel.py
  mcedb      GitHub MCE database (T_C; |ΔS| with field)       import_mcedb.py

The added rows have no annealing data: those features stay missing
(histogram gradient boosting handles them; ridge imputes). Rows with a
metal element outside the 24 NIMS columns are dropped and counted.

Leakage control:
  - papers are grouped across sources by DOI: an added row from a paper
    that is also in NIMS belongs to that NIMS paper's group, so when the
    NIMS paper is held out, its copies in the other sources are too;
  - the Ni and Cr test papers are removed from every source;
  - in leave-one-family-out, added rows of the held-out family are
    removed from training as well.
Scores are always computed on NIMS rows only (the reference quality).

SUCCESS CRITERION (written down before the first run, 3 Nov 2026): adding
all three sources counts as useful for a target if, for gradient boosting,
the MAE with whole papers held out drops by at least 5 %, and the MAE on
the Ni + Cr test papers rises by no more than 5 %.

Result of the first run (T_tr): NOT MET -- papers MAE +13.7 %, test MAE
+16.4 %. Cause: the mcedb T_c values were never checked for plausibility
(11 K, 60 K, 500-790 K among them); the two Cole sources were (100-500 K).
--plausible-mcedb applies the same range to mcedb. That variant was
added AFTER the first run, so it is reported as exploratory, not as a
test of the criterion.

  python augment.py --target T_tr
  python augment.py --target T_tr --plausible-mcedb    # exploratory
  python augment.py --target dS        # only mcedb carries |ΔS|
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold

from composition_key import split_composition
from evaluate import DEFAULT_FAMILIES, DEFAULT_TEST_DOIS, build_table, fit_predict, models
from nims_dataset import DEFAULT_PATH, INTERSTITIALS, METAL_ELEMENTS, load_nims

SUCCESS_PAPERS = 0.05
SUCCESS_TEST_TOLERANCE = 0.05


def family_from_metal(metal_pct):
    subs = [e for e in METAL_ELEMENTS if e not in ('Fe', 'La') and metal_pct.get(e, 0) > 0]
    return '+'.join(subs) if subs else 'none'


def extra_rows(target, plausible_mcedb=False):
    """Accepted La(Fe,Si/Al)13 rows of the added sources, as feature rows."""
    out, dropped = [], {}

    def add(source, comp, y, doi, field=None):
        metal, inter = split_composition(comp)
        unknown = [e for e in metal if e not in METAL_ELEMENTS]
        if unknown or [e for e in inter if e not in INTERSTITIALS.values()]:
            dropped[source] = dropped.get(source, 0) + 1
            return
        row = {e: metal.get(e, 0.0) for e in METAL_ELEMENTS}
        row.update({e: inter.get(e, 0.0) for e in INTERSTITIALS.values()})
        row.update(anneal_time_h=np.nan, anneal_temp_K=np.nan, y=y, doi=(doi or '').lower(),
                   family=family_from_metal(metal), source=source)
        if field is not None:
            row['field_T'] = field
        out.append(row)

    if target == 'T_tr':
        from import_court_cole_2018 import DEFAULT_PATH as P18, classify as c18, load_records
        for rec in load_records(P18):
            st, _, comp, t = c18(rec)
            if st == 'accepted':
                add('court2018', comp, t, str(rec.get('DOI') or ''))
        from import_curie_neel import DEFAULT_PATH as P25, classify as c25
        for rec in json.loads(Path(P25).read_text(encoding='utf-8')).values():
            st, _, comp, t = c25(rec)
            if st == 'accepted':
                add('kelly2025', comp, t, re.sub(r'^https?://(dx\.)?doi\.org/', '', str(rec.get('doi', ''))))
    from import_curie_neel import PLAUSIBLE_TC_K
    from import_mcedb import classify as cm
    from mcedb_dataset import load_mcedb
    m = cm(load_mcedb(), False)
    for _, r in m[m['status'] == 'accepted'].iterrows():
        if target == 'T_tr' and pd.notna(r['Tc']):
            if plausible_mcedb and not PLAUSIBLE_TC_K[0] <= r['Tc'] <= PLAUSIBLE_TC_K[1]:
                dropped['mcedb implausible T_c'] = dropped.get('mcedb implausible T_c', 0) + 1
                continue
            add('mcedb', r['composition'], r['Tc'], r['doi'] if pd.notna(r['doi']) else '')
        if target == 'dS' and pd.notna(r['dS']) and pd.notna(r['field_T']):
            add('mcedb', r['composition'], r['dS'], r['doi'] if pd.notna(r['doi']) else '', r['field_T'])
    return pd.DataFrame(out), dropped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', choices=['T_tr', 'dS'], default='T_tr')
    ap.add_argument('--plausible-mcedb', action='store_true',
                    help='exploratory: drop mcedb T_c outside PLAUSIBLE_TC_K (added after the first run)')
    args = ap.parse_args()
    unit = 'K' if args.target == 'T_tr' else 'J/kg K'

    nims, features, _ = build_table(load_nims(DEFAULT_PATH), args.target, use_restored=(args.target == 'T_tr'))
    nims['source'] = 'nims'
    extra, dropped = extra_rows(args.target, args.plausible_mcedb)

    # paper groups across sources: an added row whose DOI is one of a NIMS
    # paper's DOIs joins that paper's group
    doi_to_group = {}
    for g in nims['paper'].unique():
        for d in re.split(r'[\n;]', g):
            if d.strip():
                doi_to_group[d.strip()] = g
    extra['paper'] = [doi_to_group.get(d, d or f'nodoi-{i}') for i, d in enumerate(extra['doi'])]

    test_dois = [d.lower() for d in DEFAULT_TEST_DOIS]
    is_test_paper = lambda p: any(d in p for d in test_dois)
    nims_test = nims[nims['paper'].map(is_test_paper)]
    nims_train = nims[~nims['paper'].map(is_test_paper)].reset_index(drop=True)
    n_extra_test = int(extra['paper'].map(is_test_paper).sum())
    extra = extra[~extra['paper'].map(is_test_paper)].reset_index(drop=True)

    print(f"Target {args.target}: NIMS {len(nims_train)} training rows, {len(nims_test)} test rows")
    print(f"Added rows: {extra['source'].value_counts().to_dict()}; dropped: "
          f"{dropped or 0}; removed because from a test paper: {n_extra_test}")
    in_nims_paper = extra['paper'].isin(set(nims_train['paper']))
    print(f"  of the added rows, {int(in_nims_paper.sum())} come from papers also in NIMS, "
          f"{int((~in_nims_paper).sum())} from papers NIMS does not have")

    variants = {'NIMS only': []}
    for s in sorted(extra['source'].unique()):
        variants[f'+ {s}'] = [s]
    variants['+ all added'] = sorted(extra['source'].unique())

    def fit_eval(train_df, test_df, model_name):
        m = models(args.target)[model_name]
        X_tr, y_tr = train_df[features].to_numpy(float), train_df['y'].to_numpy(float)
        X_te = test_df[features].to_numpy(float)
        return mean_absolute_error(test_df['y'], fit_predict(m, X_tr, y_tr, X_te))

    groups = nims_train['paper'].to_numpy()
    folds = list(GroupKFold(5).split(nims_train, groups=groups))
    results = {}
    for vname, srcs in variants.items():
        add = extra[extra['source'].isin(srcs)]
        res = {}
        for mname in ('ridge', 'gbr'):
            maes = []
            for tr, te in folds:
                held = set(nims_train['paper'].iloc[te])
                train_df = pd.concat([nims_train.iloc[tr], add[~add['paper'].isin(held)]], ignore_index=True)
                maes.append(fit_eval(train_df, nims_train.iloc[te], mname))
            res[(mname, 'papers')] = np.mean(maes)
            res[(mname, 'test')] = fit_eval(pd.concat([nims_train, add], ignore_index=True), nims_test, mname)
            for fam in DEFAULT_FAMILIES:
                te_f = nims_train[nims_train['family'] == fam]
                if len(te_f) == 0:
                    continue
                train_df = pd.concat([nims_train[nims_train['family'] != fam], add[add['family'] != fam]],
                                     ignore_index=True)
                res[(mname, fam)] = fit_eval(train_df, te_f, mname)
        results[vname] = res

    cols = [('ridge', 'papers'), ('gbr', 'papers'), ('ridge', 'test'), ('gbr', 'test')]
    print(f"\nMAE ({unit}) on NIMS rows; papers = whole NIMS papers held out (5 folds), test = Ni + Cr papers")
    print(f"  {'variant':16s}" + ''.join(f"{m + ' ' + k:>14s}" for m, k in cols))
    for vname, res in results.items():
        print(f"  {vname:16s}" + ''.join(f"{res[c]:14.2f}" for c in cols))
    print(f"\nLeave one family out, gradient boosting (MAE, {unit}):")
    fams = [f for f in DEFAULT_FAMILIES if ('gbr', f) in results['NIMS only']]
    print(f"  {'variant':16s}" + ''.join(f"{f:>9s}" for f in fams))
    for vname, res in results.items():
        print(f"  {vname:16s}" + ''.join(f"{res[('gbr', f)]:9.2f}" for f in fams))

    base, full = results['NIMS only'], results['+ all added']
    d_papers = full[('gbr', 'papers')] / base[('gbr', 'papers')] - 1
    d_test = full[('gbr', 'test')] / base[('gbr', 'test')] - 1
    ok = d_papers <= -SUCCESS_PAPERS and d_test <= SUCCESS_TEST_TOLERANCE
    label = 'Exploratory (not the pre-registered test)' if args.plausible_mcedb else 'Criterion'
    print(f"\n{label}, gradient boosting, all added: papers MAE {d_papers:+.1%} (needs <= "
          f"-{SUCCESS_PAPERS:.0%}), test MAE {d_test:+.1%} (needs <= +{SUCCESS_TEST_TOLERANCE:.0%}) "
          f"-> {'MET' if ok else 'NOT MET'}")


if __name__ == '__main__':
    main()
