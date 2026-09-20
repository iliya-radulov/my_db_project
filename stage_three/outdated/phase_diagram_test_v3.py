"""
CALPHAD phase diagram test using SGTE binary datasets.
Tests Fe-Si binary system first — relevant to LaFeSi alloy research.

Run from project root with venv active:
    python stage_three/phase_diagram_test.py
"""

from pycalphad import Database, binplot, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

TDB_DIR = "/Users/r/Documents/Projects/my_db_project/data/tdb"
UNARY   = f"{TDB_DIR}/unary50_bengt.tdb"
BINARY  = f"{TDB_DIR}/sgte_binary/FeSi-91Lac-LB.tdb"

# ── 1. Merge TDB files (pycalphad Database() takes exactly one string/path) ──
print("Merging TDB files...")
with open(UNARY,  "r", encoding="utf-8", errors="replace") as f:
    unary_text = f.read()
with open(BINARY, "r", encoding="utf-8", errors="replace") as f:
    binary_text = f.read()

merged = unary_text + "\n" + binary_text

merged_path = "/tmp/FeSi_merged.tdb"
with open(merged_path, "w", encoding="utf-8") as f:
    f.write(merged)
print(f"  ✓ Written to {merged_path}")

# ── 2. Load merged database ───────────────────────────────────────────────────
print("Loading database...")
db = Database(merged_path)
phases = list(db.phases.keys())
print(f"  ✓ Phases found: {phases}")
print(f"  Elements: {sorted(db.elements)}\n")

# ── 3. Binary phase diagram (Fe-Si, 400–1873 K) ───────────────────────────────
print("Calculating Fe-Si phase diagram (30–120 s)...")

fig, ax = plt.subplots(figsize=(10, 7))

binplot(
    db,
    ["FE", "SI", "VA"],
    phases,
    {v.X("SI"): (0, 1, 0.01),
     v.T: (400, 1873, 10),
     v.P: 101325},
    ax=ax,
)

ax.set_title("Fe-Si binary phase diagram (SGTE / pycalphad)")
ax.set_xlabel("Si mole fraction")
ax.set_ylabel("Temperature (K)")

out = "stage_three/FeSi_phase_diagram.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"\n  ✓ Saved → {out}")
plt.close(fig)
