"""
evaluate.py

Baseline property models on the NIMS La(Fe,Si)13 dataset, evaluated the
way a small-data materials model has to be evaluated:

  random      random 80/20 splits -- reported only for comparison with the
              NIMS scripts; it puts the same paper (and often the same
              sample at another field) on both sides and flatters the model
  papers      GroupKFold over papers: every test paper is unseen
  families    leave-one-family-out for the families given by --families
  heldout     train on everything except the --test-dois papers, predict
              those papers; one line per test point is written to CSV

Every evaluation reports a predict-the-mean baseline and a ridge model
beside the gradient-boosting model, so a model is only credited with what
it adds over those.

Targets:
  T_tr   transition temperature, one value per sample (reported, or with
         --restore-T-tr also the peak temperature at the lowest field)
  dS     |ΔS_M|max, one value per (sample, field); field_T is a feature

Features: the 24 metal at.% columns, the H/C/N/B columns, annealing time
and temperature, and for dS the applied field. Missing annealing data
(as-cast, melt-spun or simply unreported) are kept as missing: the
gradient-boosting model handles them natively, ridge gets median
imputation plus a was-missing indicator. --drop-missing-anneal restores
the earlier behaviour of dropping those rows.

Usage:
  python evaluate.py --target T_tr --restore-T-tr
  python evaluate.py --target dS
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, ShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nims_dataset import (DEFAULT_PATH, INTERSTITIALS, METAL_ELEMENTS,
                          expand_points, load_nims, restore_T_tr)

# The two series co-authored by the project owner, measured in one lab:
# Moreno-Ramírez et al., Acta Mater. 160 (2018) 137 (Ni) and
# Acta Mater. 175 (2019) 406 (Cr).
DEFAULT_TEST_DOIS = ['10.1016/j.actamat.2018.08.054', '10.1016/j.actamat.2019.06.022']
DEFAULT_FAMILIES = ['Si+Cr', 'Si+Ni', 'Si+Mn', 'Si+Co', 'Si+Ce', 'Al']

# Hyperparameters translated from the NIMS scripts (ml_1_13.py: n_estimators,
# max_depth, learning_rate; min_samples_split=4 -> min_samples_leaf=2) to the
# histogram gradient-boosting model, which accepts missing values.
GBR_PARAMS = {
    'T_tr': dict(max_iter=200, max_depth=4, min_samples_leaf=2, learning_rate=0.1),
    'dS': dict(max_iter=400, max_depth=5, min_samples_leaf=2, learning_rate=0.15),
}


def build_table(df, target, use_restored, drop_missing_anneal=False):
    """Returns (table, feature_names, n_dropped_no_anneal). One row per
    sample (T_tr) or per (sample, field) (dS); 'y', 'paper', 'family' and
    'nims_id' columns are always present."""
    features = METAL_ELEMENTS + list(INTERSTITIALS.values()) + ['anneal_time_h', 'anneal_temp_K']
    base = df.copy()
    base['nims_id'] = base.index
    base['paper'] = base['doi'].str.lower()

    if target == 'T_tr':
        if use_restored:
            base = restore_T_tr(base)
            base['y'] = base['T_tr_restored_K']
        else:
            base['y'] = base['T_tr_K']
        table = base
    elif target == 'dS':
        points = expand_points(base, 'dS').rename(columns={'dS_max': 'y'})
        table = points.merge(base.drop(columns=['dS_max']), left_on='nims_id', right_index=True,
                             suffixes=('', '_sample'))
        table['nims_id'] = table['nims_id']
        features = features + ['field_T']
    else:
        raise ValueError("target must be 'T_tr' or 'dS'")

    table = table[table['y'].notna()]
    no_anneal = table[['anneal_time_h', 'anneal_temp_K']].isna().any(axis=1)
    if drop_missing_anneal:
        table = table[~no_anneal]
    return table.reset_index(drop=True), features, int(no_anneal.sum())


def models(target):
    return {
        'mean': None,
        'ridge': make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(),
                               RidgeCV(alphas=np.logspace(-3, 3, 13))),
        'gbr': HistGradientBoostingRegressor(random_state=0, **GBR_PARAMS[target]),
    }


def fit_predict(model, X_tr, y_tr, X_te):
    if model is None:
        return np.full(len(X_te), y_tr.mean())
    model.fit(X_tr, y_tr)
    return model.predict(X_te)


def cv_scores(table, features, target, splits):
    """Mean MAE per model over the given (train, test) index splits."""
    X, y = table[features].to_numpy(float), table['y'].to_numpy(float)
    out = {}
    for name, model in models(target).items():
        maes = [mean_absolute_error(y[te], fit_predict(model, X[tr], y[tr], X[te])) for tr, te in splits]
        out[name] = (float(np.mean(maes)), float(np.std(maes)))
    return out


def print_scores(label, n, scores, unit):
    parts = '   '.join(f"{m} {v[0]:6.2f}" for m, v in scores.items())
    print(f"  {label:34s} n={n:4d}   MAE ({unit}):  {parts}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--target', choices=['T_tr', 'dS'], default='T_tr')
    ap.add_argument('--restore-T-tr', action='store_true',
                    help='T_tr only: fill missing values from the lowest-field peak temperature')
    ap.add_argument('--test-dois', nargs='*', default=DEFAULT_TEST_DOIS)
    ap.add_argument('--families', nargs='*', default=DEFAULT_FAMILIES)
    ap.add_argument('--drop-missing-anneal', action='store_true',
                    help='drop rows without annealing data instead of keeping them as missing')
    ap.add_argument('--out', default=str(Path(__file__).resolve().parent / 'data' / 'results'))
    args = ap.parse_args()

    df = load_nims(args.data)
    table, features, n_missing = build_table(df, args.target, args.restore_T_tr, args.drop_missing_anneal)
    unit = 'K' if args.target == 'T_tr' else 'J/kg K'
    test_dois = [d.lower() for d in args.test_dois]
    is_test = table['paper'].map(lambda p: any(d in p for d in test_dois)).to_numpy()

    action = 'dropped' if args.drop_missing_anneal else 'kept as missing'
    print(f"Target {args.target}: {len(table)} rows from {table['paper'].nunique()} papers "
          f"({n_missing} without annealing data, {action}); {int(is_test.sum())} rows in the test papers")
    for d in test_dois:
        if not table['paper'].str.contains(d, regex=False).any():
            print(f"  WARNING: test DOI {d} not found in the table")

    # Cross-validation runs on the training part only, so the test papers
    # are never seen before the held-out step.
    train = table[~is_test].reset_index(drop=True)
    print("\nCross-validation on the training papers:")
    rs = list(ShuffleSplit(10, test_size=0.2, random_state=15).split(train))
    print_scores('random 80/20 (as NIMS scripts)', len(train), cv_scores(train, features, args.target, rs), unit)
    gk = list(GroupKFold(5).split(train, groups=train['paper']))
    print_scores('whole papers held out (5 folds)', len(train), cv_scores(train, features, args.target, gk), unit)

    print("\nLeave one family out (trained on all other training rows):")
    for fam in args.families:
        te = np.where(train['family'] == fam)[0]
        if len(te) == 0:
            print(f"  {fam}: no rows"); continue
        tr = np.where(train['family'] != fam)[0]
        print_scores(f"family {fam}", len(te), cv_scores(train, features, args.target, [(tr, te)]), unit)

    if is_test.any():
        print("\nHeld-out test papers (trained on all other papers):")
        X, y = table[features].to_numpy(float), table['y'].to_numpy(float)
        tr, te = np.where(~is_test)[0], np.where(is_test)[0]
        test = table.iloc[te][['nims_id', 'paper', 'family', 'composition_details', 'y']].copy()
        if 'field_T' in table:
            test.insert(4, 'field_T', table['field_T'].iloc[te].to_numpy())
        for name, model in models(args.target).items():
            test[f'pred_{name}'] = fit_predict(model, X[tr], y[tr], X[te])
        parent = (table.iloc[te][[e for e in METAL_ELEMENTS if e not in ('Fe', 'La', 'Si')]].sum(axis=1) == 0).to_numpy()
        for label, mask in (('all test rows', np.ones(len(te), bool)),
                            ('parent alloy (x = 0)', parent), ('substituted (x > 0)', ~parent)):
            if mask.any():
                scores = {m: (mean_absolute_error(test['y'][mask], test[f'pred_{m}'][mask]), 0.0)
                          for m in models(args.target)}
                print_scores(label, int(mask.sum()), scores, unit)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"heldout_{args.target}.csv"
        test.round(3).to_csv(path, index=False)
        print(f"\nPer-point predictions: {path}")


if __name__ == '__main__':
    main()
