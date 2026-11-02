"""
correct.py

Step 5: correct the NIMS-trained model with the small, consistently
measured test series, instead of training on them.

The base model (ridge or gradient boosting from evaluate.py) is trained on
NIMS without the test papers. Its residuals on the consistent series are
then modelled by one of these corrections, each evaluated leave-one-out
(every consistent point is predicted from the base model plus a
correction fitted on the other consistent points only):

  none           base model alone
  offset         + mean residual of all other consistent points
  series_offset  + mean residual of the other points of the same series
  gp             + Gaussian process on the residuals (inputs: substituent
                   content, Si content, and the field for dS)

plus two references that do not use NIMS at all:
  series_mean    mean of the other points of the same series
  series_linear  linear fit of the other points of the same series
                 against the substituent content

Success criterion (written down before the first run, 2 Nov 2026):
a correction counts as useful if it lowers the leave-one-out MAE of the
base model by at least 20 % for both T_tr and dS, and also beats
series_mean.

--curve adds the more realistic question: at the start of a new series
only k of its samples are measured. For each series and k = 0, 1, 2, ...
the remaining samples are predicted from those k (all choices of k
samples, averaged); the other series is not used. With k = 0 only the
base model is available; series_mean needs k >= 1, series_linear k >= 2.

Usage:
  python correct.py --target T_tr --restore-T-tr
  python correct.py --target dS
  python correct.py --target T_tr --base ridge
  python correct.py --target T_tr --restore-T-tr --base ridge --curve
"""
import argparse
from itertools import combinations

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler

from evaluate import DEFAULT_TEST_DOIS, build_table, fit_predict, models
from nims_dataset import DEFAULT_PATH, load_nims

SUBSTITUENTS = ['Cr', 'Ni']           # the substituent of each test series
SUCCESS_REDUCTION = 0.20


def gp_correction(Z_tr, r_tr, Z_te):
    scaler = StandardScaler().fit(Z_tr)
    kernel = ConstantKernel(1.0) * RBF(length_scale=np.ones(Z_tr.shape[1])) + WhiteKernel(1.0)
    gp = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=0, n_restarts_optimizer=3)
    gp.fit(scaler.transform(Z_tr), r_tr)
    return gp.predict(scaler.transform(Z_te))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--target', choices=['T_tr', 'dS'], default='T_tr')
    ap.add_argument('--restore-T-tr', action='store_true')
    ap.add_argument('--base', choices=['gbr', 'ridge'], default='gbr')
    ap.add_argument('--test-dois', nargs='*', default=DEFAULT_TEST_DOIS)
    ap.add_argument('--curve', action='store_true', help='error vs number of known samples per series')
    args = ap.parse_args()

    table, features, _ = build_table(load_nims(args.data), args.target, args.restore_T_tr)
    test_dois = [d.lower() for d in args.test_dois]
    series = table['paper'].map(lambda p: next((d for d in test_dois if d in p), None))
    is_test = series.notna().to_numpy()

    X, y = table[features].to_numpy(float), table['y'].to_numpy(float)
    base = models(args.target)[args.base]
    base_pred = fit_predict(base, X[~is_test], y[~is_test], X[is_test])

    t = table[is_test].reset_index(drop=True)
    y_t, s_t = t['y'].to_numpy(float), series[is_test].to_numpy()
    resid = y_t - base_pred
    subst = t[SUBSTITUENTS].sum(axis=1).to_numpy(float)       # at.% of Cr or Ni
    z_cols = [subst, t['Si'].to_numpy(float)] + ([t['field_T'].to_numpy(float)] if 'field_T' in t else [])
    Z = np.column_stack(z_cols)

    n = len(t)
    preds = {k: np.full(n, np.nan) for k in
             ['none', 'offset', 'series_offset', 'gp', 'series_mean', 'series_linear']}
    for i in range(n):
        other = np.arange(n) != i
        same = other & (s_t == s_t[i])
        preds['none'][i] = base_pred[i]
        preds['offset'][i] = base_pred[i] + resid[other].mean()
        preds['series_offset'][i] = base_pred[i] + (resid[same].mean() if same.any() else 0.0)
        preds['gp'][i] = base_pred[i] + gp_correction(Z[other], resid[other], Z[i:i + 1])[0]
        preds['series_mean'][i] = y_t[same].mean()
        coef = np.polyfit(subst[same], y_t[same], 1)
        preds['series_linear'][i] = np.polyval(coef, subst[i])

    unit = 'K' if args.target == 'T_tr' else 'J/kg K'
    mae = {k: mean_absolute_error(y_t, v) for k, v in preds.items()}
    print(f"Target {args.target}, base model {args.base}, {n} consistent points "
          f"({', '.join(f'{(s_t == d).sum()} from {d}' for d in test_dois)})")
    print(f"Leave-one-out MAE ({unit}):")
    for k, v in mae.items():
        per = '  '.join(f"{d.split('/')[-1]}: {mean_absolute_error(y_t[s_t == d], preds[k][s_t == d]):.2f}"
                        for d in test_dois)
        print(f"  {k:14s} {v:6.2f}    ({per})")

    print("\nAgainst the success criterion (>= 20 % below 'none' and below 'series_mean'):")
    for k in ['offset', 'series_offset', 'gp']:
        red = 1 - mae[k] / mae['none']
        ok = red >= SUCCESS_REDUCTION and mae[k] < mae['series_mean']
        print(f"  {k:14s} reduction {red:+.0%}, {'meets' if ok else 'does not meet'} the criterion")

    if args.curve:
        print(f"\nNew-series curve: MAE ({unit}) on the unknown samples of a series, "
              f"from k known samples of that series")
        methods = ['base', 'base+offset', 'base+gp', 'series_mean', 'series_linear']
        print(f"  {'series':24s} k  " + ''.join(f"{m:>15s}" for m in methods))
        for d in test_dois:
            idx = np.where(s_t == d)[0]
            for k in range(0, len(idx) - 1):
                errs = {m: [] for m in methods}
                for known in combinations(idx, k):
                    known = np.array(known, dtype=int)
                    unknown = np.setdiff1d(idx, known)
                    b = base_pred[unknown]
                    errs['base'].append(np.abs(y_t[unknown] - b).mean())
                    if k >= 1:
                        errs['base+offset'].append(np.abs(y_t[unknown] - (b + resid[known].mean())).mean())
                        errs['series_mean'].append(np.abs(y_t[unknown] - y_t[known].mean()).mean())
                    if k >= 2:
                        corr = gp_correction(Z[known], resid[known], Z[unknown])
                        errs['base+gp'].append(np.abs(y_t[unknown] - (b + corr)).mean())
                        coef = np.polyfit(subst[known], y_t[known], 1)
                        errs['series_linear'].append(np.abs(y_t[unknown] - np.polyval(coef, subst[unknown])).mean())
                cells = ''.join(f"{np.mean(errs[m]):15.2f}" if errs[m] else f"{'-':>15s}" for m in methods)
                print(f"  {d.split('/')[-1]:24s} {k}  {cells}")


if __name__ == '__main__':
    main()
