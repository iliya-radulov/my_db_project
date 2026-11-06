import json, glob, csv
rows = []
for f in sorted(glob.glob("*.json")):
    d = json.load(open(f))
    rows.append({"combo_id": f[:-5], "keys": list(d.keys())[:12], **{k: v for k, v in d.items() if "threshold" in k.lower()}})
print(json.dumps(rows[0], indent=1)[:1500])   # first check: what are the key names?