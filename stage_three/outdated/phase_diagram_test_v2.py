"""
CALPHAD phase diagram test using SGTE binary datasets.
Tests Fe-Si binary system first — relevant to LaFeSi alloy research.

Requirements:
    pip install pycalphad matplotlib --break-system-packages
    (or activate venv: source venv/bin/activate)

Run from project root:
    python stage_three/phase_diagram_test.py
"""

from pycalphad import Database, binplot, variables as v
import matplotlib
matplotlib.use("Agg")   # headless — saves PNG, no display needed
import matplotlib.pyplot as plt

TDB_DIR = "/Users/r/Documents/Projects/my_db_project/data/tdb"
UNARY   = f"{TDB_DIR}/unary50_bengt.tdb"
BINARY  = f"{TDB_DIR}/sgte_binary/FeSi-91Lac-LB.tdb"

# ── 1. Load database ──────────────────────────────────────────────────────────
print("Loading TDB files...")
try:
    db = Database(UNARY, BINARY)
except Exception as e:
    print(f"  ✗ Failed: {e}")
    raise

phases = list(db.phases.keys())
print(f"  ✓ Loaded.  Phases found: {phases}\n")

# ── 2. Quick component check ──────────────────────────────────────────────────
comps = list(db.elements)
print(f"  Elements in DB: {comps}")
# pycalphad always needs 'VA' (vacancy) in component list
if "VA" not in comps:
    comps.append("VA")

# ── 3. Binary phase diagram  (Fe-Si, 0–1600 °C) ──────────────────────────────
print("\nCalculating Fe-Si phase diagram (this may take 30–120 s)...")

fig, ax = plt.subplots(figsize=(10, 7))

try:
    binplot(
        db,
        ["FE", "SI", "VA"],   # component list — must include VA
        phases,
        {v.X("SI"): (0, 1, 0.01),          # Si mole fraction 0→1, step 0.01
         v.T: (400, 1873, 10),              # 400–1600 °C in Kelvin
         v.P: 101325},
        ax=ax,
    )
except Exception as e:
    print(f"  ✗ binplot failed: {e}")
    print("  Tip: check that both UNARY and BINARY files cover FE and SI.")
    raise

ax.set_title("Fe-Si binary phase diagram (SGTE / pycalphad)")
ax.set_xlabel("Si mole fraction")
ax.set_ylabel("Temperature (K)")

out = "stage_three/FeSi_phase_diagram.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"\n  ✓ Saved → {out}")
plt.close(fig)
