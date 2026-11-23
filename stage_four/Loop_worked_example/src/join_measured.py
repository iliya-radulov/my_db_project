#!/usr/bin/env python3
"""Unblinding step: join measured values to the frozen predictions.

Refuses to run if the prediction files no longer match the sha256 in
manifest.json. Measured file: Heldout_12_measured_values_20261123.csv
(columns nims_id, Tc_K_NIMS, abs_dS_NIMS_J_kg_K). Prints MAE per model and the
flag against the thresholds in the manifest.
"""
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='blind_out'); ap.add_argument('--measured', required=True)
a = ap.parse_args(); out = Path(a.out)
man = json.loads((out / 'manifest.json').read_text())
for name, h in man['outputs'].items():
    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == h, f'{name} changed since freeze'
meas = pd.read_csv(a.measured)
col = {'T_tr': 'Tc_K_NIMS', 'dS': 'abs_dS_NIMS_J_kg_K'}
for target in ('T_tr', 'dS'):
    p = pd.read_csv(out / f'predictions_{target}.csv').merge(meas[['nims_id', col[target]]], on='nims_id')
    assert len(p) == 12
    res = {m: float((p[f'pred_{m}'] - p[col[target]]).abs().mean()) for m in ('mean', 'ridge', 'gbr')}
    prim = man['primary_model'][target]; thr = man['criterion_MAE'][target]
    print(target, {k: round(v, 2) for k, v in res.items()}, 'primary', prim,
          'PASS' if res[prim] <= thr else 'FAIL', f'(threshold {thr})')
