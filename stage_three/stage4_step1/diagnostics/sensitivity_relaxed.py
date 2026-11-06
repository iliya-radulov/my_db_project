"""Tolerance sensitivity for the six edge-check failures.
Run from anywhere:   python3 sensitivity_relaxed.py
Reads the six merged TDBs already written by the batch run (results_v2/merged_tdbs/), measures per-edge worst |dG|
and phase-set mismatches (same grid as check_edges), then computes the feasibility threshold at all 8 T with the
unchanged v2 kernel. Writes results_v2/sensitivity_relaxed.csv and prints each threshold's percentile in the ensemble.
"""
import sys, csv, warnings
warnings.filterwarnings("ignore")
from _common import BIN_DIR, RESULTS, S4
from pathlib import Path
import numpy as np, pandas as pd
from pycalphad import Database, equilibrium, variables as v
import run_batch_v2 as rb
from tdb_merge import _phase_set

HERE = S4
mdir = HERE / "results_v2" / "merged_tdbs"
FEND = ["FeNd-16Che", "FeNd-16Wan", "FeNd-95Hal-LB"]
FEB, NDB = "FeB-19Wit", ["NdB-16Zho-corrected", "NdB-19Che"]
TEMPS = (800.0, 1200.0, 1600.0)

def edge_stats(db_m, path):
    db_b = Database(str(path))
    a, b = sorted(e for e in db_b.elements if e not in ("VA", "/-"))
    comps = [a, b, "VA"]; worst = 0.0; n_phase = 0; n = 0; where = None
    for T in TEMPS:
        for x in np.round(np.arange(0.05, 0.96, 0.1), 2):
            cond = {v.X(b): float(x), v.T: T, v.P: 101325, v.N: 1}
            r1 = equilibrium(db_b, comps, list(db_b.phases), cond)
            r2 = equilibrium(db_m, comps, list(db_m.phases), cond)
            d = abs(float(r1.GM.values.squeeze()) - float(r2.GM.values.squeeze()))
            n += 1
            if _phase_set(r1) != _phase_set(r2): n_phase += 1
            if d > worst: worst, where = d, (T, x)
    return a, b, worst, n_phase, n, where

ens = pd.read_csv(RESULTS / "ensemble_all_T.csv")
rows = []
for fe in FEND:
    for nb in NDB:
        cid = f"{fe}___{FEB}___{nb}"
        m = mdir / f"FENDB_merged_v4__{cid}.tdb"
        dbm = Database(str(m))
        paths = [rb.TDB_DIR / f"{fe}.tdb", rb.TDB_DIR / f"{FEB}.tdb", rb.TDB_DIR / f"{nb}.tdb"]
        row = {"combo_id": cid}
        for p in paths:
            a, b, worst, nph, n, wh = edge_stats(dbm, p)
            row[f"{a}-{b}_maxdG_Jmol"] = round(worst, 2); row[f"{a}-{b}_phase_mismatch"] = f"{nph}/{n}"
            row[f"{a}-{b}_worst_at"] = str(wh)
        res = rb.run_feasibility(m, rb.TEMPERATURES, rb.X_TARGET["FE"], rb.X_TARGET["ND"], rb.X_TARGET["B"])
        res = res[0] if isinstance(res, tuple) else res
        for T, thr, _ in res: row[f"T{int(T)}"] = thr
        rows.append(row); print(cid, {k: v_ for k, v_ in row.items() if "maxdG" in k or "phase_mismatch" in k})
df = pd.DataFrame(rows); out = HERE / "results_v2" / "sensitivity_relaxed.csv"; df.to_csv(out, index=False)
print("\nPercentile of each relaxed member within the 78-member ensemble (fraction of ensemble more negative):")
for _, r in df.iterrows():
    print(r.combo_id[:44].ljust(46), " ".join(f"{T}:{(ens[f'T{T}'] < r[f'T{T}']).mean()*100:3.0f}" for T in (800, 1000, 1200, 1600)))
print("\nwritten", out)
