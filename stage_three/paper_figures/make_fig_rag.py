"""make_fig_rag.py — Figure 2 of the Stage 3 paper: retrieval hit@5 by subgroup, MiniLM vs bge-m3 (same chunks).
Numbers: rebuilt index (_v2 collections), runs v2_minilm and v2_bge of 24 Oct 2026, 39 scored questions;
computed from the retrieval ranks in the grading files; bge-m3 values agree with the run's own summary."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = [  # label, n, MiniLM, bge-m3
    ("All questions", 39, 0.10, 0.51),
    ("Russian-language source", 7, 0.00, 0.71),
    ("English-language source", 32, 0.12, 0.47),
    ("phase_stability", 8, 0.00, 0.62),
    ("synthesis", 11, 0.09, 0.55),
    ("magnetic", 20, 0.15, 0.45),
]
LIGHT, DARK = "#6da7ec", "#184f95"      # one hue, two validated shades (ordinal check passed)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
plt.rcParams.update({"font.family": "serif", "font.size": 9.5, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK})
fig, ax = plt.subplots(figsize=(6.4, 3.1))
ys = [0, 1.4, 2.4, 3.8, 4.8, 5.8]           # gaps separate overall / language / collection
for (lab, n, a, b), y in zip(rows, ys):
    ax.plot([a, b], [y, y], color=GRID, lw=2.2, solid_capstyle="round", zorder=1)
    ax.scatter([a], [y], s=46, facecolor="white", edgecolor=LIGHT, linewidth=1.8, zorder=3)
    ax.scatter([b], [y], s=46, color=DARK, edgecolor="white", linewidth=0.8, zorder=3)
    ax.text(a - 0.025, y, f"{a:.2f}", ha="right", va="center", fontsize=8.5, color=MUTED)
    ax.text(b + 0.025, y, f"{b:.2f}", ha="left", va="center", fontsize=8.5, color=INK)
ax.set_yticks(ys)
ax.set_yticklabels([f"{lab} ({n})" for lab, n, *_ in rows])
ax.get_yticklabels()[0].set_fontweight("bold")
ax.invert_yaxis()
ax.set_xlim(-0.12, 1.0)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xlabel("hit@5: share of questions with the gold passage among the top 5")
ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
from matplotlib.lines import Line2D
handles = [Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=LIGHT, markeredgewidth=1.8, markersize=7, label="all-MiniLM-L6-v2"),
           Line2D([], [], marker="o", ls="", color=DARK, markersize=7, label="bge-m3")]
fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.62, 1.0), ncol=2, frameon=False, fontsize=8.5)
fig.tight_layout(rect=(0, 0, 1, 0.92))
HERE = Path(__file__).resolve().parent
fig.savefig(HERE / "rag_benchmark.pdf"); fig.savefig(HERE / "rag_benchmark.png", dpi=200)
