"""make_fig_feas.py — Figure 5 of paper 3: feasibility threshold vs temperature.

Data (24 Oct 2026):
  feasibility_sgte_fixed.json   — SGTE binaries, corrected merge (tdb_merge.py) and corrected target
                                  reference; parsed from the run of feasibility.py (log of 24 Oct 2026).
  thresholds_assessments.json   — Hallemans 1995 and Chen 2019: binary-phase assemblage of each full
                                  assessment (ternary phases removed) and Phi, both relative to
                                  sum x_i GHSER_i computed by pycalphad (thresholds_assessments.py).
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sg = json.loads((HERE / "feasibility_sgte_fixed.json").read_text())["rows"]
d = json.loads((HERE / "thresholds_assessments.json").read_text())
C = {"sgte": "#2a78d6", "hal": "#eb6834", "chen": "#1baf7a"}
TXT, GRID, MUTED = "#0b0b0b", "#e4e3df", "#52514e"

fig, ax = plt.subplots(figsize=(6.6, 4.4))
for key, c in (("Hallemans 1995", "hal"), ("Chen 2019", "chen")):
    t = [r["T"] for r in d[key]]
    ax.plot(t, [r["threshold"] for r in d[key]], color=C[c], lw=2,
            label=f"threshold, binaries of {key}")
    ax.plot(t, [r["phi"] for r in d[key]], color=C[c], lw=1.6, ls=(0, (4, 3)),
            label=f"$\\Phi$ in {key}")
ax.plot([r["T"] for r in sg], [r["threshold"] for r in sg], color=C["sgte"], lw=2.4,
        marker="o", ms=4.5, label="threshold, SGTE binaries (merged)")
ax.axvline(1453, color="#8a8984", lw=1, ls=":", zorder=0)
ax.text(1460, -4.75, "peritectic of $\\Phi$\n1453 K (exp.)", fontsize=7.5, color=MUTED, va="top")
ax.set_xlim(780, 1820)
ax.set_ylim(-11.3, -4.5)
ax.set_xlabel("Temperature (K)", color=TXT)
ax.set_ylabel(r"$\Delta H_f$ (kJ mol$^{-1}$ atom$^{-1}$)", color=TXT)
ax.grid(color=GRID, lw=0.8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
h, l = ax.get_legend_handles_labels()
order = [4, 0, 1, 2, 3]                       # SGTE first, then Hallemans, then Chen
ax.legend([h[i] for i in order], [l[i] for i in order], fontsize=7.5, frameon=False,
          loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
fig.tight_layout()
fig.savefig(HERE / "feasibility_threshold.pdf")
fig.savefig(HERE / "feasibility_threshold.png", dpi=150)
print("saved")
