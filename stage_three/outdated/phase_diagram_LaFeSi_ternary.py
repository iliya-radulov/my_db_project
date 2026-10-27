"""
CALPHAD La-Fe-Si ternary isothermal section at 1375 K.
This is the typical annealing temperature for single-phase LaFe13-xSix.

Requires all three binary TDB files — we merge them into one consistent database.
Run from project root with venv active:
    python stage_three/phase_diagram_LaFeSi_ternary.py
"""

from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import os

TDB_DIR = "/Users/r/Documents/Projects/my_db_project/data/tdb"
TDB_FeSi = f"{TDB_DIR}/sgte_binary/FeSi-91Lac-LB.tdb"
TDB_LaFe = f"{TDB_DIR}/sgte_binary/FeLa-23Su.tdb"
TDB_LaSi = f"{TDB_DIR}/sgte_binary/LaSi-20Xu.tdb"

T_ANNEAL = 1375  # K — typical single-phase LaFe13-xSix annealing temperature

# ── 1. Merge three binary TDBs into one ternary database ─────────────────────
# Strategy: load each, collect ELEMENT/PHASE/PARAMETER blocks, deduplicate
# functions (GHSERFE etc. appear in multiple files), keep first occurrence.

print("Merging three binary TDB files...")

def merge_tdb_files(paths):
    """
    Merge multiple TDB files, deduplicating FUNCTION/ELEMENT/PHASE/CONSTITUENT
    blocks. Works by scanning line-by-line and tracking which named blocks have
    already been written. A block runs from its keyword line until the next '!'
    terminator.
    """
    seen = set()          # "FUNCTION_GHSERFE", "ELEMENT_FE", etc.
    out_lines = []

    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        DEDUP_KEYWORDS = {"FUNCTION", "ELEMENT", "PHASE", "CONSTITUENT"}
        skip_until_bang = False
        block_key = None

        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()

            if skip_until_bang:
                if "!" in line:
                    skip_until_bang = False
                continue

            # Check if this line starts a dedup-able block
            first_token = upper.split()[0] if upper.split() else ""
            if first_token in DEDUP_KEYWORDS:
                tokens = upper.split()
                name = tokens[1].rstrip(":") if len(tokens) > 1 else ""
                block_key = f"{first_token}_{name}"
                if block_key in seen:
                    # Skip this block including continuation until '!'
                    if "!" not in line:
                        skip_until_bang = True
                    continue
                seen.add(block_key)

            out_lines.append(line)

        out_lines.append("\n")  # separator between files

    return "".join(out_lines)

merged_text = merge_tdb_files([TDB_FeSi, TDB_LaFe, TDB_LaSi])

merged_path = "/tmp/LaFeSi_ternary.tdb"
with open(merged_path, "w", encoding="utf-8") as f:
    f.write(merged_text)
print(f"  ✓ Written to {merged_path}\n")

# ── 2. Load ───────────────────────────────────────────────────────────────────
print("Loading ternary database...")
db = Database(merged_path)

phases = list(db.phases.keys())
print(f"  ✓ Phases: {phases}")
print(f"  Elements: {sorted(db.elements)}\n")

# ── 3. Ternary grid at 1375 K ─────────────────────────────────────────────────
# Sample the Gibbs triangle: X_La + X_Fe + X_Si = 1
# Step across X_La and X_Si, X_Fe = 1 - X_La - X_Si
N = 30  # grid points per axis — increase for higher resolution (slower)
compositions = []
for i in range(N + 1):
    for j in range(N + 1 - i):
        x_la = i / N
        x_si = j / N
        x_fe = 1.0 - x_la - x_si
        if x_fe < 0 or x_la < 0.001 or x_si < 0.001 or x_fe < 0.001:
            continue
        compositions.append((x_la, x_si, x_fe))

X_LA_vals = np.array([c[0] for c in compositions])
X_SI_vals = np.array([c[1] for c in compositions])

print(f"Running equilibrium at {T_ANNEAL} K for {len(compositions)} compositions...")
print("(This may take several minutes...)")

results_phase = []

for idx, (x_la, x_si, x_fe) in enumerate(compositions):
    if idx % 50 == 0:
        print(f"  {idx}/{len(compositions)}...", flush=True)
    try:
        result = equilibrium(
            db,
            ["FE", "LA", "SI", "VA"],
            phases,
            {v.X("LA"): x_la,
             v.X("SI"): x_si,
             v.T: T_ANNEAL,
             v.P: 101325,
             v.N: 1},
        )
        phase_data = result["Phase"].values.flatten()
        np_data    = result["NP"].values.flatten()
        valid = [(np_data[i], phase_data[i]) for i in range(len(phase_data))
                 if phase_data[i] != "" and not np.isnan(np_data[i])]
        dominant = max(valid, key=lambda x: x[0])[1] if valid else "UNKNOWN"
    except Exception:
        dominant = "UNKNOWN"
    results_phase.append(dominant)

print("  ✓ Done\n")

# ── 4. Plot ternary ───────────────────────────────────────────────────────────
all_phases = sorted(set(results_phase) - {"UNKNOWN"})
print(f"Phases present at {T_ANNEAL} K: {all_phases}")

cmap = plt.get_cmap("tab20", len(all_phases) + 1)
phase_color = {p: cmap(i) for i, p in enumerate(all_phases)}
phase_color["UNKNOWN"] = (0.8, 0.8, 0.8)

fig, ax = plt.subplots(figsize=(10, 9))

# Convert to 2D ternary coordinates (x_si → right, x_la → top)
# Standard ternary: bottom-left = Fe, bottom-right = Si, top = La
def ternary_to_cart(x_la, x_si):
    """Convert ternary (La, Si, Fe=1-La-Si) to Cartesian."""
    x = x_si + x_la * 0.5
    y = x_la * (3**0.5 / 2)
    return x, y

for idx, (x_la, x_si, x_fe) in enumerate(compositions):
    cx, cy = ternary_to_cart(x_la, x_si)
    ph = results_phase[idx]
    color = phase_color.get(ph, (0.8, 0.8, 0.8))
    ax.plot(cx, cy, "s", color=color, markersize=6, markeredgewidth=0)

# Triangle border
tri_x = [0, 1, 0.5, 0]
tri_y = [0, 0, 3**0.5/2, 0]
ax.plot(tri_x, tri_y, "k-", linewidth=1.5)

# Corner labels
offset = 0.03
ax.text(0 - offset, 0 - offset, "Fe", ha="right", va="top", fontsize=12, fontweight="bold")
ax.text(1 + offset, 0 - offset, "Si", ha="left",  va="top", fontsize=12, fontweight="bold")
ax.text(0.5,        3**0.5/2 + offset, "La", ha="center", va="bottom", fontsize=12, fontweight="bold")

# Legend
legend_elements = [Patch(facecolor=phase_color[p], label=p) for p in all_phases]
ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1),
          loc="upper left", fontsize=8, framealpha=0.8)

ax.set_title(f"La-Fe-Si ternary phase diagram at {T_ANNEAL} K (SGTE / pycalphad)", fontsize=12)
ax.set_aspect("equal")
ax.axis("off")

plt.tight_layout()
out = "stage_three/LaFeSi_ternary_1375K.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"\n  ✓ Saved → {out}")
plt.close(fig)
