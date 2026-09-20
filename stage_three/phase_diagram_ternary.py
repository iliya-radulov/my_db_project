"""
phase_diagram_ternary.py — Generic CALPHAD ternary isothermal section.

Automatically finds and merges the three binary TDB files from the SGTE
collection using tdb_lookup.py.

Usage (from project root with venv active):
    python stage_three/phase_diagram_ternary.py FE ND B 1375
    python stage_three/phase_diagram_ternary.py LA FE SI 1375
    python stage_three/phase_diagram_ternary.py FE CO NI 1200
"""

import sys
import os
from pathlib import Path

from pycalphad import Database, equilibrium, variables as v
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────
# Works whether run from project root or from stage_three/
THIS_DIR   = Path(__file__).resolve().parent
PROJ_ROOT  = THIS_DIR.parent
TDB_DIR    = PROJ_ROOT / "data" / "tdb" / "sgte_binary"

sys.path.insert(0, str(THIS_DIR))
from tdb_lookup import get_tdb_paths, build_index, find_binaries, select_preferred

# ── CLI arguments ─────────────────────────────────────────────────────────────
def parse_args():
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage: python phase_diagram_ternary.py EL1 EL2 EL3 [TEMP_K]")
        print("Example: python phase_diagram_ternary.py FE ND B 1375")
        sys.exit(1)
    elements = [a.upper() for a in args[:3]]
    temp_k   = float(args[3]) if len(args) > 3 else 1375.0
    return elements, temp_k


# ── TDB merge (reused from original script) ───────────────────────────────────
def merge_tdb_files(paths):
    """
    Merge multiple TDB files, deduplicating FUNCTION/ELEMENT/PHASE/CONSTITUENT
    blocks. Works by scanning line-by-line and tracking which named blocks have
    already been written.
    """
    seen = set()
    out_lines = []
    DEDUP_KEYWORDS = {"FUNCTION", "ELEMENT", "PHASE", "CONSTITUENT"}

    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        skip_until_bang = False

        for line in lines:
            upper = line.strip().upper()

            if skip_until_bang:
                if "!" in line:
                    skip_until_bang = False
                continue

            first_token = upper.split()[0] if upper.split() else ""
            if first_token in DEDUP_KEYWORDS:
                tokens = upper.split()
                name = tokens[1].rstrip(":") if len(tokens) > 1 else ""
                block_key = f"{first_token}_{name}"
                if block_key in seen:
                    if "!" not in line:
                        skip_until_bang = True
                    continue
                seen.add(block_key)

            out_lines.append(line)

        out_lines.append("\n")

    return "".join(out_lines)


# ── Ternary coordinate conversion ─────────────────────────────────────────────
def ternary_to_cart(x1, x2):
    """Convert ternary fractions to 2D Cartesian. x3 = 1 - x1 - x2."""
    x = x2 + x1 * 0.5
    y = x1 * (3 ** 0.5 / 2)
    return x, y


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    elements, T_K = parse_args()
    el1, el2, el3 = elements

    print(f"System  : {el1}-{el2}-{el3}")
    print(f"Temp    : {T_K} K  ({T_K - 273.15:.0f} °C)")
    print(f"TDB dir : {TDB_DIR}")
    print()

    # ── 1. Find TDB files ─────────────────────────────────────────────────────
    print("Looking up binary TDB files...")
    index = build_index(TDB_DIR)
    candidates = find_binaries(elements, index)

    if len(candidates) < 3:
        missing = []
        from itertools import combinations
        for a, b in combinations(elements, 2):
            from builtins import frozenset
            if frozenset([a, b]) not in candidates:
                missing.append(f"{a}-{b}")
        print(f"ERROR: missing TDB files for: {', '.join(missing)}")
        sys.exit(1)

    selected = {}
    for pair, files in candidates.items():
        best = select_preferred(files)
        selected[pair] = best
        a, b = sorted(pair)
        print(f"  {a}-{b}: {best.name}")

    print()

    # ── 2. Merge TDB files ────────────────────────────────────────────────────
    # Sort alphabetically so merge order is the SAME regardless of CLI element order.
    # Without this, combinations(["ND","FE","B"]) vs combinations(["FE","ND","B"])
    # produce different insertion orders → different dedup winners → broken TDB.
    tdb_paths = sorted(selected.values(), key=lambda p: p.name)
    merged_path = THIS_DIR / f"{''.join(elements)}_merged.tdb"
    print(f"Merging {len(tdb_paths)} TDB files → {merged_path.name} ...")
    merged_text = merge_tdb_files(tdb_paths)
    merged_path.write_text(merged_text, encoding="utf-8")
    print("  ✓ Done\n")

    # ── 3. Load database ──────────────────────────────────────────────────────
    print("Loading merged database...")
    db     = Database(str(merged_path))
    phases = list(db.phases.keys())
    print(f"  ✓ Phases   : {phases}")
    print(f"  ✓ Elements : {sorted(db.elements)}\n")

    # ── 4. Build composition grid (Gibbs triangle) ────────────────────────────
    N = 30   # grid resolution — increase for publication quality (slower)
    compositions = []
    for i in range(N + 1):
        for j in range(N + 1 - i):
            x1 = i / N
            x2 = j / N
            x3 = 1.0 - x1 - x2
            if x3 < 0 or x1 < 0.001 or x2 < 0.001 or x3 < 0.001:
                continue
            compositions.append((x1, x2, x3))

    print(f"Running equilibrium at {T_K} K for {len(compositions)} compositions...")
    print("(This may take several minutes on CPU...)\n")

    # ── 5. Equilibrium calculations ───────────────────────────────────────────
    results_phase = []
    for idx, (x1, x2, x3) in enumerate(compositions):
        if idx % 50 == 0:
            print(f"  {idx}/{len(compositions)}...", flush=True)
        try:
            result = equilibrium(
                db,
                elements + ["VA"],
                phases,
                {v.X(el2): x2,
                 v.X(el1): x1,
                 v.T: T_K,
                 v.P: 101325,
                 v.N: 1},
            )
            phase_data = result["Phase"].values.flatten()
            np_data    = result["NP"].values.flatten()
            valid = [
                (np_data[i], phase_data[i])
                for i in range(len(phase_data))
                if phase_data[i] != "" and not np.isnan(np_data[i])
            ]
            dominant = max(valid, key=lambda x: x[0])[1] if valid else "UNKNOWN"
        except Exception as e:
            if idx < 5:
                print(f"    [warn] ({x1:.3f},{x2:.3f}): {e}")
            dominant = "UNKNOWN"
        results_phase.append(dominant)

    print("\n  ✓ Calculations done\n")

    # ── 6. Plot ───────────────────────────────────────────────────────────────
    all_phases = sorted(set(results_phase) - {"UNKNOWN"})
    print(f"Phases present at {T_K} K: {all_phases}")

    cmap = plt.get_cmap("tab20", len(all_phases) + 1)
    phase_color = {p: cmap(i) for i, p in enumerate(all_phases)}
    phase_color["UNKNOWN"] = (0.85, 0.85, 0.85)

    fig, ax = plt.subplots(figsize=(10, 9))

    for idx, (x1, x2, x3) in enumerate(compositions):
        cx, cy = ternary_to_cart(x1, x2)
        ph     = results_phase[idx]
        ax.plot(cx, cy, "s",
                color=phase_color.get(ph, (0.85, 0.85, 0.85)),
                markersize=6, markeredgewidth=0)

    # Triangle border
    tri_x = [0, 1, 0.5, 0]
    tri_y = [0, 0, 3 ** 0.5 / 2, 0]
    ax.plot(tri_x, tri_y, "k-", linewidth=1.5)

    # Corner labels
    off = 0.04
    ax.text(0 - off, 0 - off, el3, ha="right",  va="top",    fontsize=13, fontweight="bold")
    ax.text(1 + off, 0 - off, el2, ha="left",   va="top",    fontsize=13, fontweight="bold")
    ax.text(0.5,  3**0.5/2 + off, el1, ha="center", va="bottom", fontsize=13, fontweight="bold")

    # Stoichiometric marker for Nd2Fe14B if relevant
    if set(elements) == {"ND", "FE", "B"}:
        # Nd2Fe14B: x_Nd=2/17, x_Fe=14/17, x_B=1/17
        stoich = {"ND": 2/17, "FE": 14/17, "B": 1/17}
        # Map mole fractions to the correct ternary axes (el1=top, el2=bottom-right)
        cx, cy = ternary_to_cart(stoich[el1], stoich[el2])
        ax.plot(cx, cy, "k*", markersize=14, zorder=5)
        ax.text(cx - 0.03, cy - 0.03, "Nd₂Fe₁₄B\nstoich.",
                ha="right", va="top", fontsize=8)

    # Legend
    legend_elements = [Patch(facecolor=phase_color[p], label=p) for p in all_phases]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1),
              loc="upper left", fontsize=8, framealpha=0.8)

    title = f"{el1}-{el2}-{el3} ternary phase diagram at {T_K} K (pycalphad)"
    ax.set_title(title, fontsize=12)
    ax.set_aspect("equal")
    ax.axis("off")

    plt.tight_layout()
    out = THIS_DIR / f"{''.join(elements)}_ternary_{int(T_K)}K.png"
    fig.savefig(str(out), dpi=150, bbox_inches="tight")
    print(f"\n  ✓ Saved → {out}")
    plt.close(fig)

    # Clean up merged TDB
    merged_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
