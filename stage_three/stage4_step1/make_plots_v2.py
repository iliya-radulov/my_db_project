"""
Figures 1-3 of the Track A paper (ensemble of binary CALPHAD assessments, Nd2Fe14B threshold).
Run from anywhere:  python make_plots_v2.py   (reads results_v2/batch_results.csv, writes figures/).
The two ternary reference curves are the thresholds printed by ternary_threshold.py
(stored in ternary_results/hallemans_1995_threshold.json and pycalphad_examples_threshold.json).

Panel A: histogram of threshold at 1000 K, Stage 3 single-point + both ternary refs.
Panel B: box plot by Fe-Nd assessment at 800, 1375, 1600 K with ternary refs.
Panel C: box plot by Fe-B assessment at 1000 K with ternary refs.
"""
import csv
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.dpi": 120,
})

HERE = Path(__file__).resolve().parent
CSV = HERE / "results_v2" / "batch_results.csv"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)

# Ternary reference thresholds, from ternary_threshold.py (ternary_results/*.json); kJ/mol per mole of atoms
HAL = {800: -8.7757, 1000: -7.9198, 1100: -7.5095, 1200: -7.1176,
       1300: -6.7547, 1375: -6.7297, 1450: -7.1982, 1600: -8.5728}
CHE = {800: -9.0981, 1000: -8.0514, 1100: -7.5349, 1200: -7.0368,
       1300: -6.5573, 1375: -6.4054, 1450: -6.7543, 1600: -8.0143}

with open(CSV) as f:
    rows = [r for r in csv.DictReader(f) if r["survived"] == "True"]

def strip_tdb(s): return s.replace(".tdb", "")

HAL_COLOR = "#7a2e2b"   # dark red (Hallemans)
CHE_COLOR = "#2b5a7a"   # dark blue (Chen candidate)
STAGE3_COLOR = "#8c2f2f"

# =========================================================================
# Panel A — histogram at 1000 K with Stage 3 + both ternaries
# =========================================================================
fig, ax = plt.subplots(figsize=(7.0, 4.3))
vals = np.array([float(r["threshold_at_1000K"]) for r in rows])

ax.hist(vals, bins=np.arange(-8.4, -7.3, 0.08),
        color="#4a3e75", edgecolor="white", linewidth=0.8, alpha=0.75,
        label=f"Ensemble (n={len(vals)})")

# the three reference lines
ax.axvline(HAL[1000], color=HAL_COLOR, lw=2.0, linestyle="-",
           label=f"Hallemans 1995 ternary: {HAL[1000]:+.2f}")
ax.axvline(CHE[1000], color=CHE_COLOR, lw=2.0, linestyle="-",
           label=f"Chen 2019 ternary: {CHE[1000]:+.2f}")
ax.axvline(-8.2, color=STAGE3_COLOR, lw=1.5, linestyle="--",
           label="Stage 3 single value: −8.20")
ax.axvline(np.median(vals), color="#1c1712", lw=1.0, linestyle=":",
           label=f"Ensemble median: {np.median(vals):+.2f}")

ax.set_xlabel(r"Feasibility threshold at 1000 K  (kJ mol$^{-1}$, per mole of atoms)")
ax.set_ylabel("Number of combinations")
ax.set_ylim(top=ax.get_ylim()[1]*1.38)
ax.legend(loc="upper left", fontsize=8.5)

plt.tight_layout()
plt.savefig(f"{OUT}/panel_A_v2_histogram_1000K_with_ternary.pdf")
plt.savefig(f"{OUT}/panel_A_v2_histogram_1000K_with_ternary.png", dpi=180)
plt.close()
print("Panel A v2 done")

# =========================================================================
# Panel B — box plot by Fe-Nd at 800, 1375, 1600 K with ternary refs
# =========================================================================
fe_nd_order = ["FeNd-16Che.tdb", "FeNd-16Wan.tdb", "FeNd-95Hal-LB.tdb"]
T_cols = [("800K", "threshold_at_800K", 800),
          ("1375K", "threshold_at_1375K", 1375),
          ("1600K", "threshold_at_1600K", 1600)]

fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.4), sharey=False)
for i, (T_label, col, T) in enumerate(T_cols):
    ax = axes[i]
    data = []
    for fnd in fe_nd_order:
        sub = [float(r[col]) for r in rows if r["binary_FeNd"] == fnd]
        data.append(sub)

    bp = ax.boxplot(data, tick_labels=[strip_tdb(f).replace("FeNd-", "") for f in fe_nd_order],
                    widths=0.55, patch_artist=True,
                    medianprops=dict(color="#1c1712", linewidth=1.5),
                    boxprops=dict(facecolor="#b9822b", edgecolor="#4d4436", alpha=0.7),
                    whiskerprops=dict(color="#4d4436"),
                    capprops=dict(color="#4d4436"),
                    flierprops=dict(marker="o", markersize=3,
                                    markerfacecolor="#4d4436", markeredgecolor="none"))

    # overlay ternary references as horizontal lines
    ax.axhline(HAL[T], color=HAL_COLOR, lw=1.8, linestyle="-",
               label=f"Hallemans: {HAL[T]:+.2f}")
    ax.axhline(CHE[T], color=CHE_COLOR, lw=1.8, linestyle="-",
               label=f"Chen: {CHE[T]:+.2f}")

    ax.set_title(f"{T_label}")
    ax.set_xlabel("Fe–Nd assessment")
    if i == 0:
        ax.set_ylabel(r"Threshold  (kJ mol$^{-1}$, per mole of atoms)")
    lo, hi = ax.get_ylim(); ax.set_ylim(lo, hi + 0.30*(hi-lo))
    ax.legend(loc="upper right", fontsize=7.5)
    for lab in ax.get_xticklabels():
        lab.set_rotation(15)
        lab.set_ha("right")

plt.tight_layout()
plt.savefig(f"{OUT}/panel_B_v2_boxplot_FeNd_with_ternary.pdf")
plt.savefig(f"{OUT}/panel_B_v2_boxplot_FeNd_with_ternary.png", dpi=180)
plt.close()
print("Panel B v2 done")

# =========================================================================
# Panel C — box plot by Fe-B at 1000 K with ternary refs
# =========================================================================
fe_b_order = ["FeB-01Pal.tdb", "FeB-02Rom.tdb", "FeB-08Yos.tdb",
              "FeB-19Wit.tdb", "FeB-20Tak.tdb", "FeB-91Pan.tdb", "FeB-94Hal-LB.tdb"]

fig, ax = plt.subplots(figsize=(8.0, 4.6))
data, labels, ns = [], [], []
for fb in fe_b_order:
    sub = [float(r["threshold_at_1000K"]) for r in rows if r["binary_FeB"] == fb]
    data.append(sub)
    labels.append(strip_tdb(fb).replace("FeB-", ""))
    ns.append(len(sub))

colors = ["#8c5a3a"] * len(fe_b_order)
tak_idx = fe_b_order.index("FeB-20Tak.tdb")
colors[tak_idx] = "#5c6a45"

bp = ax.boxplot(data, tick_labels=labels, widths=0.55, patch_artist=True,
                medianprops=dict(color="#1c1712", linewidth=1.5),
                whiskerprops=dict(color="#4d4436"),
                capprops=dict(color="#4d4436"),
                flierprops=dict(marker="o", markersize=3,
                                markerfacecolor="#4d4436", markeredgecolor="none"))
for patch, col in zip(bp["boxes"], colors):
    patch.set_facecolor(col)
    patch.set_edgecolor("#4d4436")
    patch.set_alpha(0.75)

ax.axhline(HAL[1000], color=HAL_COLOR, lw=1.8, linestyle="-",
           label=f"Hallemans ternary: {HAL[1000]:+.2f}")
ax.axhline(CHE[1000], color=CHE_COLOR, lw=1.8, linestyle="-",
           label=f"Chen 2019 ternary: {CHE[1000]:+.2f}")

ax.set_xlabel("Fe–B assessment")
ax.set_ylabel(r"Threshold at 1000 K  (kJ mol$^{-1}$, per mole of atoms)")
y_min = min(min(d) for d in data) - 0.15
for i, n in enumerate(ns, start=1):
    ax.text(i, y_min, f"n={n}", ha="center", va="top", fontsize=8, color="#4d4436")
ax.set_ylim(bottom=y_min - 0.05, top=ax.get_ylim()[1] + 0.22)

ax.legend(loc="upper right", fontsize=8)
for lab in ax.get_xticklabels():
    lab.set_rotation(20)
    lab.set_ha("right")

plt.tight_layout()
plt.savefig(f"{OUT}/panel_C_v2_boxplot_FeB_1000K_with_ternary.pdf")
plt.savefig(f"{OUT}/panel_C_v2_boxplot_FeB_1000K_with_ternary.png", dpi=180)
plt.close()
print("Panel C v2 done")

print("\nAll three panels written.")
