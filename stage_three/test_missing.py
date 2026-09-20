import pickle
with open("cache/FENDB_1375K_N80.pkl", "rb") as f:
    p = pickle.load(f)
res = p["results"]
missing = [i for i, r in enumerate(res) if r is None or not r["stable"]]
print(f"missing: {len(missing)} / {len(res)}")