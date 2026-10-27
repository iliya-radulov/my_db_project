"""
CALPHAD Nd-Fe-B ternary isothermal section at 1375 K.
Uses a dedicated ternary TDB with Nd2Fe14B properly parameterized.

Run from project root with venv active:
    python stage_three/phase_diagram_NdFeB_ternary.py
"""

from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

TDB_PATH = "/Users/r/Documents/Projects/my_db_project/data/other_tdb/Nd-Fe-B.TDB"
T_K      = 1375  # K

# ── 1. Load ───────────────────────────────────────────────────────────────────
print("Loading Nd-Fe-B ternary database...")
db = Database(TDB_PATH)
phases = list(db.phases.keys())
print(f"  ✓ Phases: {phases}")
print(f"  Elements: {sorted(db.elements)}\n")

# ── 2. Gibbs triangle grid ────────────────────────────────────────────────────
N = 30
compositions = []
for i in range(N + 1):
    for j in range(N + 1 - i):
        x_nd = i / N
        x_b  = j / N
        x_fe = 1.0 - x_nd - x_b
        if x_fe < 0.001 or x_nd < 0.001 or x_b < 0.001:
            continue
        compositions.append((x_nd, x_b, x_fe))

print(f"Running equilibrium at {T_K} K for {len(compositions)} compositions...")

results_phase = []
for idx, (x_nd, x_b, x_fe) in enumerate(compositions):
    if idx % 50 == 0:
        print(f"  {idx}/{len(compositions)}...", flush=True)
    try:
        result = equilibrium(
            db,
            ["FE", "ND", "B", "VA"],
            phases,
            {v.X("ND"): x_nd,
             v.X("B"):  x_b,
             v.T: T_K,
             v.P: 101325,
             v.N: 1},
        )
        phase_data = result["Phase"].values.flatten()
        np_data    = result["NP"].values.flatten()
        valid = [(np_data[i], phase_data[i]) for i in range(len(phase_data))
                 if phase_data[i] != "" and not np.isnan(np_data[i])]
        dominant = max(valid, key=lambda x: x[0])[1] if valid else "UNKNOWN"
    except Exception as e:
        dominant = "UNKNOWN"
    results_phase.append(dominant)

print("  ✓ Done\n")

# ── 3. Plot ───────────────────────────────────────────────────────────────────
all_phases = sorted(set(results_phase) - {"UNKNOWN"})
print(f"Phases present at {T_K} K: {all_phases}")

cmap = plt.get_cmap("tab20", len(all_phases) + 1)
phase_color = {p: cmap(i) for i, p in enumerate(all_phases)}
phase_color["UNKNOWN"] = (0.85, 0.85, 0.85)

def ternary_to_cart(x_nd, x_b):
    """Bottom-left = Fe, bottom-right = B, top = Nd"""
    x = x_b + x_nd * 0.5
    y = x_nd * (3**0.5 / 2)
    return x, y

fig, ax = plt.subplots(figsize=(10, 9))

for idx, (x_nd, x_b, x_fe) in enumerate(compositions):
    cx, cy = ternary_to_cart(x_nd, x_b)
    ph = results_phase[idx]
    ax.plot(cx, cy, "s", color=phase_color.get(ph, (0.85, 0.85, 0.85)),
            markersize=6, markeredgewidth=0)

# Triangle
tri_x = [0, 1, 0.5, 0]
tri_y = [0, 0, 3**0.5/2, 0]
ax.plot(tri_x, tri_y, "k-", linewidth=1.5)

# Mark the Nd2Fe14B stoichiometry: Nd=2/17, Fe=14/17, B=1/17
x_nd_target = 2/17
x_b_target  = 1/17
cx_t, cy_t = ternary_to_cart(x_nd_target, x_b_target)
ax.plot(cx_t, cy_t, "k*", markersize=14, zorder=5, label="Nd₂Fe₁₄B stoich.")

offset = 0.03
ax.text(0 - offset, 0 - offset, "Fe", ha="right", va="top", fontsize=12, fontweight="bold")
ax.text(1 + offset, 0 - offset, "B",  ha="left",  va="top", fontsize=12, fontweight="bold")
ax.text(0.5, 3**0.5/2 + offset, "Nd", ha="center", va="bottom", fontsize=12, fontweight="bold")

legend_elements = [Patch(facecolor=phase_color[p], label=p) for p in all_phases]
legend_elements.append(plt.Line2D([0], [0], marker="*", color="k",
                                   markersize=10, linestyle="None",
                                   label="Nd₂Fe₁₄B stoich."))
ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1),
          loc="upper left", fontsize=8, framealpha=0.8)

ax.set_title(f"Nd-Fe-B ternary phase diagram at {T_K} K (pycalphad)", fontsize=12)
ax.set_aspect("equal")
ax.axis("off")

plt.tight_layout()
out = "stage_three/NdFeB_ternary_1375K.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"  ✓ Saved → {out}")
plt.close(fig)
