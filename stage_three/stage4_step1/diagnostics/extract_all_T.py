"""Ensemble thresholds of the 78 survivors at all eight temperatures -> results_v2/ensemble_all_T.csv"""
import json, csv
from _common import RESULTS
rows = []
for f in sorted((RESULTS / "detail").glob("*.json")):
    d = json.load(open(f))
    if not d.get("survived"): continue
    row = {"combo_id": d["combo_id"]}
    row.update({f"T{int(t)}": v for t, v in zip(d["temperatures_K"], d["threshold_kJ_mol_atom"])})
    rows.append(row)
out = RESULTS / "ensemble_all_T.csv"
with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), "survivors ->", out)
