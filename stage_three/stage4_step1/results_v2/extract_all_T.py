import json, glob, csv
from pathlib import Path
here = Path(__file__).resolve().parent
rows = []
for f in sorted(here.glob("detail/*.json")) or sorted(here.glob("*.json")):
    d = json.load(open(f))
    if not d.get("survived"):
        continue
    row = {"combo_id": d["combo_id"]}
    row.update({f"T{int(t)}": v for t, v in zip(d["temperatures_K"], d["threshold_kJ_mol_atom"])})
    rows.append(row)
out = here / "ensemble_all_T.csv"
with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), "survivors ->", out)