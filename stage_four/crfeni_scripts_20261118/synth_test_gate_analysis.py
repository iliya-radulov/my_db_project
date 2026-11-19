"""Synthetic tests of crfeni_gate.py / crfeni_analysis.py. No real data; random, planted structure."""
import csv, json, itertools, random, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import crfeni_defs as D

CF = sorted(D.LINEAGE["CrFe"]); CN = sorted(D.LINEAGE["CrNi"]); FN = sorted(D.LINEAGE["FeNi"])
COMBOS = [(a, b, c) for a in CF for b in CN for c in FN]

def make(root, surv_fn, s_fn, break_rows=False, fail_frac=0.0, seed=0):
    rng = random.Random(seed); nrng = np.random.default_rng(seed)
    root = Path(root); shutil.rmtree(root, ignore_errors=True); (root / "sigma").mkdir(parents=True)
    ec, sg = [], []
    for i, (a, b, c) in enumerate(COMBOS):
        cid = f"c{i:03d}"
        ok = surv_fn(a, b, c, rng)
        ec.append({"combo": cid, "CrFe": a, "CrNi": b, "FeNi": c, "pass": str(ok)})
        if ok:
            for T in (900.0, 800.0, 1000.0):
                failed = rng.random() < fail_frac
                S = s_fn(a, b, c, T, nrng)
                sg.append({"combo": cid, "CrFe": a, "CrNi": b, "FeNi": c, "T": T,
                           "S": "" if failed else S, "status": "failed" if failed else "direct"})
    if break_rows:
        ec = ec[:-5]
    for name, rows in (("edge_check.csv", ec), ("sigma/sigma_S.csv", sg)):
        with open(root / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return root

def run(script, root):
    p = subprocess.run([sys.executable, script, "--run-dir", str(root)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def surv_all(a, b, c, r): return r.random() < 0.5
S_flat = lambda a, b, c, T, n: abs(n.normal(0.5, 0.15))
def S_plant(a, b, c, T, n): return {"A": 0.5, "B": 1.5, "C": 0.9}[D.CLASS[a]] + n.normal(0, 0.1)
def S_null(a, b, c, T, n): return 0.8 + n.normal(0, 0.3)
def S_tiny(a, b, c, T, n): return 0.01 + abs(n.normal(0, 0.01))

T = {}
def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, info); T[name] = cond

# 1 planted class effect -> gate pass, MATTERS
r = make("s1", surv_all, S_plant)
rc, out = run("crfeni_gate.py", r); g = json.load(open(r/"sigma/gate.json"))
check("1 gate pass", rc == 0 and not g["failed_gates"], g["failed_gates"])
rc, out = run("crfeni_analysis.py", r); a = json.load(open(r/"sigma/analysis.json"))
check("1 planted -> MATTERS", a["primary"]["verdict"] == "MATTERS", a["primary"]["class_median"])
check("1 eta2 CrFe dominant", a["primary"]["eta2"]["CrFe"] > 0.8, a["primary"]["eta2"])
# 2 null -> DOES NOT MATTER or INCONCLUSIVE, never MATTERS
r = make("s2", surv_all, S_null)
run("crfeni_gate.py", r); rc, out = run("crfeni_analysis.py", r); a = json.load(open(r/"sigma/analysis.json"))
check("2 null never MATTERS", a["primary"]["verdict"] != "MATTERS", (a["primary"]["verdict"], a["primary"]["C"], a["primary"]["N_eff"]))
# 3 flat tiny S -> G3 fail, analysis refuses
r = make("s3", surv_all, S_tiny)
rc, out = run("crfeni_gate.py", r); g = json.load(open(r/"sigma/gate.json"))
check("3 G3 fail", rc == 0 and g["failed_gates"] == ["G3"], g["failed_gates"])
rc, out = run("crfeni_analysis.py", r); check("3 analysis refuses", rc != 0 and not (r/"sigma/analysis.json").exists())
# 4 low survival -> G1 fail
r = make("s4", lambda a, b, c, rng: rng.random() < 0.1, S_plant)
rc, out = run("crfeni_gate.py", r); g = json.load(open(r/"sigma/gate.json"))
check("4 G1 fail", "G1" in g["failed_gates"], (g["G1"]["surviving"], g["failed_gates"]))
# 5 class B has no file with >=5 survivors -> G2 fail
r = make("s5", lambda a, b, c, rng: (a != "CrFe-21Laf" or rng.random() < 0.02) and rng.random() < 0.7, S_plant)
rc, out = run("crfeni_gate.py", r); g = json.load(open(r/"sigma/gate.json"))
check("5 G2 fail (class B)", "G2" in g["failed_gates"] and not g["G2"]["per_class"]["B"]["pass"], g["failed_gates"])
# 6 invalid run: too many failed S
r = make("s6", surv_all, S_plant, fail_frac=0.4)
rc, out = run("crfeni_gate.py", r); g = json.load(open(r/"sigma/gate.json"))
check("6 invalid run exit 3", rc == 3 and g["run_valid"] is False)
rc, out = run("crfeni_analysis.py", r); check("6 analysis refuses", rc != 0)
# 7 truncated edge_check -> invalid
r = make("s7", surv_all, S_plant, break_rows=True)
rc, out = run("crfeni_gate.py", r); check("7 truncated edge_check exit 3", rc == 3)
# 8 analysis without gate.json
r = make("s8", surv_all, S_plant); (r/"sigma/gate.json").unlink(missing_ok=True)
rc, out = run("crfeni_analysis.py", r); check("8 no gate.json refuses", rc != 0)
# 9 boundary: C exactly between -> INCONCLUSIVE
r = make("s9", surv_all, lambda a, b, c, T, n: {"A": 0.6, "B": 0.8, "C": 0.7}[D.CLASS[a]] + n.normal(0, 0.05))
run("crfeni_gate.py", r); rc, out = run("crfeni_analysis.py", r); a = json.load(open(r/"sigma/analysis.json"))
check("9 C~0.2, N_eff 0.1 area -> not DOES NOT MATTER if C>N_eff", a["primary"]["verdict"] in ("INCONCLUSIVE", "MATTERS"), (a["primary"]["verdict"], a["primary"]["C"], a["primary"]["N_eff"]))
print("\nALL PASS" if all(T.values()) else "\nSOME FAILED")
