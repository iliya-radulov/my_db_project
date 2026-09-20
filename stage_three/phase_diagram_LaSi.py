"""
CALPHAD La-Si binary phase diagram using SGTE dataset.

Run from project root with venv active:
    python stage_three/phase_diagram_LaSi.py
"""

from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

TDB_DIR = "/Users/r/Documents/Projects/my_db_project/data/tdb"
BINARY  = f"{TDB_DIR}/sgte_binary/LaSi-20Xu.tdb"

print("Loading database...")
db = Database(BINARY)
phases = list(db.phases.keys())
print(f"  ✓ Phases: {phases}")
print(f"  Elements: {sorted(db.elements)}\n")

X_SI  = np.linspace(0.001, 0.999, 100)
TEMPS = np.linspace(400, 1873, 120)

print("Running equilibrium calculations...")
result = equilibrium(
    db, ["LA", "SI", "VA"], phases,
    {v.X("SI"): X_SI, v.T: TEMPS, v.P: 101325, v.N: 1},
)
print("  ✓ Done\n")

phase_data = result["Phase"].values.squeeze()
np_data    = result["NP"].values.squeeze()

all_phases = sorted(set(phase_data.flatten()) - {""})
print(f"Phases present: {all_phases}")

cmap = plt.get_cmap("tab20", len(all_phases))
phase_color = {p: cmap(i) for i, p in enumerate(all_phases)}

fig, ax = plt.subplots(figsize=(11, 8))

for ti, T in enumerate(TEMPS):
    for xi, X in enumerate(X_SI):
        fracs = np_data[ti, xi, :]
        names = phase_data[ti, xi, :]
        valid = [(fracs[vi], names[vi]) for vi in range(len(fracs))
                 if names[vi] != "" and not np.isnan(fracs[vi])]
        if not valid:
            continue
        dominant = max(valid, key=lambda x: x[0])[1]
        ax.plot(X, T, "s", color=phase_color[dominant],
                markersize=3, markeredgewidth=0, alpha=1.0)

legend_elements = [Patch(facecolor=phase_color[p], label=p) for p in all_phases]
ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1),
          loc="upper left", fontsize=8, framealpha=0.8)

ax.set_title("La-Si binary phase diagram (SGTE / pycalphad)", fontsize=13)
ax.set_xlabel("Si mole fraction", fontsize=11)
ax.set_ylabel("Temperature (K)", fontsize=11)
ax.set_xlim(0, 1)
ax.set_ylim(400, 1873)

plt.tight_layout()
out = "stage_three/LaSi_phase_diagram.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
print(f"  ✓ Saved → {out}")
plt.close(fig)
