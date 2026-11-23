#!/usr/bin/env python3
"""Blinded held-out step for the loop worked example (WP6).

Runs the evaluate.py models (mean, ridge, GBR) for the 12 held-out compositions
of the Moreno-Ramirez Ni and Cr series WITHOUT using or writing their measured
values. Writes
  - predictions_<target>.csv   (composition columns + predictions, no 'y')
  - manifest.json              (sha256 of inputs, outputs, script; settings)
  - WP6_ledger_append_pending.csv (two pending ledger rows, L011 Tc and L012 dS)

Blinding is structural: the measured column of the test rows is set to NaN
before any model sees the table, and the script asserts that no NaN reaches a
training set. It is a procedural blind only: the values are in the public NIMS
file and were seen before (see the criteria note).

Usage:  python blinded_heldout_predict.py --out blind_out
Needs evaluate.py, nims_dataset.py, composition_key.py next to this file and
data/1-13_dataset.xlsx (NIMS, DOI 10.48505/nims.4909).
"""
import argparse, csv, hashlib, json, platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

import evaluate as ev
from nims_dataset import load_nims, DEFAULT_PATH

PRIMARY = {'T_tr': 'ridge', 'dS': 'gbr'}   # set after the 12 Nov baselines were known
CRITERION = {'T_tr': 10.0, 'dS': 4.0}      # MAE thresholds, K and J/(kg K)
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def predict(df, target):
    restore = target == 'T_tr'
    table, features, _ = ev.build_table(df, target, restore)
    dois = [d.lower() for d in ev.DEFAULT_TEST_DOIS]
    is_test = table['paper'].map(lambda p: any(d in p for d in dois)).to_numpy()
    assert is_test.sum() == 12, f'expected 12 test rows, found {int(is_test.sum())}'
    table.loc[is_test, 'y'] = np.nan           # blind: measured values hidden
    tr, te = np.where(~is_test)[0], np.where(is_test)[0]
    X, y = table[features].to_numpy(float), table['y'].to_numpy(float)
    assert not np.isnan(y[tr]).any(), 'NaN in training targets'
    keep = ['nims_id', 'paper', 'family', 'composition_details'] + (['field_T'] if 'field_T' in table else [])
    out = table.iloc[te][keep].copy()
    for name, model in ev.models(target).items():
        out[f'pred_{name}'] = ev.fit_predict(model, X[tr], y[tr], X[te])
    assert 'y' not in out.columns
    return out.round(3), int(len(tr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(DEFAULT_PATH))
    ap.add_argument('--out', default=str(HERE / 'blind_out'))
    ap.add_argument('--date', default='2026-11-23')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    df = load_nims(a.data)
    files, ntrain = {}, {}
    for target in ('T_tr', 'dS'):
        res, ntrain[target] = predict(df, target)
        p = out / f'predictions_{target}.csv'
        res.to_csv(p, index=False)
        files[p.name] = sha(p)
    manifest = dict(date=a.date, python=platform.python_version(), sklearn=sklearn.__version__,
                    numpy=np.__version__, pandas=pd.__version__, n_train=ntrain,
                    primary_model=PRIMARY, criterion_MAE=CRITERION,
                    gbr_params=ev.GBR_PARAMS,
                    inputs={'evaluate.py': sha(HERE / 'evaluate.py'),
                            'nims_dataset.py': sha(HERE / 'nims_dataset.py'),
                            'composition_key.py': sha(HERE / 'composition_key.py'),
                            'blinded_heldout_predict.py': sha(__file__),
                            'NIMS 1-13_dataset.xlsx': sha(a.data)},
                    outputs=files)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    mh = sha(out / 'manifest.json')

    cols = ['entry_id','date','kind','system_or_sample','composition','processing','model_id','target',
            'prediction','uncertainty','measured','metric_result','success_flag','success_criterion',
            'source_ref','notes']
    rows = []
    for eid, target, tname in (('L011','T_tr','Tc (K)'), ('L012','dS','|dS| (J/kg/K), 1.9 T')):
        m = PRIMARY[target]
        rows.append(dict(
            entry_id=eid, date=a.date, kind='test',
            system_or_sample='Held-out test: Moreno-Ramirez Ni + Cr series (n=12), blinded re-run',
            composition='La(Fe,Si)13 doped; Ni nominal 0.1-0.4, Cr x as EDX-based labels in NIMS (not nominal)',
            processing='as published',
            model_id=f'Snapshot v2 NIMS-only training; evaluate.py sha256 {manifest["inputs"]["evaluate.py"][:8]}; {m}; manifest sha256 {mh[:8]}',
            target=tname,
            prediction=f'12 per-point predictions in predictions_{target}.csv sha256 {files[f"predictions_{target}.csv"][:8]}...',
            uncertainty='', measured='', metric_result='',
            success_flag='pending',
            success_criterion=f'{"Tc" if target=="T_tr" else "|dS|"} MAE <= {CRITERION[target]:g} {"K" if target=="T_tr" else "J/kg/K"} ({m}) on 12 points; thresholds set AFTER 12 Nov baselines known, not blind',
            source_ref='claude/Heldout_Blinded_Criteria_20261123.md; L001/L002',
            notes='Predictions identical to L001/L002 (same model and data); retrospective re-run for the loop worked example, not an independent test.'))
    with open(out / 'WP6_ledger_append_pending.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(json.dumps(files, indent=2)); print('manifest sha256', mh)


if __name__ == '__main__':
    main()
