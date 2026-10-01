"""
sweep_chart.py — Temperature-sweep phase-fraction chart.

Runs pycalphad equilibrium at a fixed set of temperatures and returns
a matplotlib PNG showing how each phase fraction evolves with temperature.

Highlights the sintering range (1300–1450 K) with a shaded band and
colour-codes the key phases (FE17ND2, LIQUID, FE2B) for quick reading.
"""

from __future__ import annotations
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — must come before pyplot
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from calphad_query import run_equilibrium

# Temperatures to evaluate (K) — matches the pre-computed grid files
SWEEP_T = [800, 1000, 1100, 1200, 1300, 1375, 1450, 1600]

# ── Colour map for well-known phases ─────────────────────────────────────────
PHASE_COLOURS = {
    "FE17ND2": "#c0392b",   # red   — target phase
    "LIQUID":  "#2980b9",   # blue
    "FE2B":    "#e67e22",   # orange
    "BCC_A2":  "#27ae60",   # green  (α-Fe)
    "FCC_A1":  "#8e44ad",   # purple (γ-Fe)
    "DHCP":    "#16a085",   # teal   (ε-Nd)
    "BCT_A5":  "#f39c12",   # yellow (β-Sn; appears at low T)
}
FALLBACK_COLOURS = ["#7f8c8d", "#bdc3c7", "#95a5a6", "#2c3e50", "#1abc9c"]


def make_sweep_chart(x_nd: float, x_fe: float, x_b: float) -> bytes:
    """
    Run equilibrium at SWEEP_T temperatures and return a PNG (bytes) showing
    phase fraction vs. temperature.

    Parameters
    ----------
    x_nd, x_fe, x_b : mole fractions (will be normalized automatically)
    """
    data = run_equilibrium(x_nd, x_fe, x_b, temperatures=SWEEP_T)

    if data.get("error"):
        raise RuntimeError(data["error"])

    # ── Collect per-phase data ────────────────────────────────────────────────
    T_vals: list[float] = []
    phase_data: dict[str, list[float]] = {}   # phase_name → [fraction at each T]

    for row in data["results"]:
        T_vals.append(row["T"])
        seen = {p["name"] for p in row["phases"]}
        for p in row["phases"]:
            phase_data.setdefault(p["name"], [np.nan] * len(T_vals))
            phase_data[p["name"]][-1] = p["fraction"]
        # Pad phases not present at this T with 0
        for name, arr in phase_data.items():
            if len(arr) < len(T_vals):
                arr.append(0.0)

    T_vals_arr = np.array(T_vals)

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)

    # Sintering range shading
    ax.axvspan(1300, 1450, alpha=0.10, color="#c0392b", label=None, zorder=0)
    ax.axvline(1300, color="#c0392b", linewidth=0.7, linestyle="--", alpha=0.5)
    ax.axvline(1450, color="#c0392b", linewidth=0.7, linestyle="--", alpha=0.5)
    ax.text(1375, 0.98, "sintering range", ha="center", va="top",
            fontsize=7, color="#c0392b", alpha=0.7,
            transform=ax.get_xaxis_transform())

    # Sort: target phase first, then by average fraction descending
    sorted_phases = sorted(
        phase_data.items(),
        key=lambda kv: (kv[0] != "FE17ND2", -np.nanmean(kv[1]))
    )

    fallback_idx = 0
    handles = []
    for name, fracs in sorted_phases:
        arr = np.array(fracs, dtype=float)
        colour = PHASE_COLOURS.get(name)
        if colour is None:
            colour = FALLBACK_COLOURS[fallback_idx % len(FALLBACK_COLOURS)]
            fallback_idx += 1
        lw = 2.2 if name == "FE17ND2" else 1.5
        ax.plot(T_vals_arr, arr, marker="o", markersize=4,
                linewidth=lw, color=colour, label=name)

    # Axis formatting
    ax.set_xlim(min(T_vals) - 50, max(T_vals) + 50)
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("Temperature (K)", fontsize=10)
    ax.set_ylabel("Mole fraction", fontsize=10)

    # Normalised composition string for title
    c = data["composition"]
    title = (f"Phase fractions vs. T   ·   "
             f"Nd={c['x_nd']}  Fe={c['x_fe']}  B={c['x_b']}")
    ax.set_title(title, fontsize=9, pad=8)

    # x-ticks at sweep temperatures
    ax.set_xticks(T_vals_arr)
    ax.set_xticklabels([str(int(t)) for t in T_vals_arr], fontsize=8)

    ax.legend(fontsize=8, loc="upper left", framealpha=0.85, ncol=2)
    ax.grid(axis="y", linewidth=0.4, alpha=0.5)
    ax.grid(axis="x", linewidth=0.3, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="PNG", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
