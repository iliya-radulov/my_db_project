"""
stage_five/stability_window.py

Temperature-window logic of the screening contract (pure functions, no dependencies).

For one candidate (an exact match) over the temperature grid:
  * T_best_K        temperature of the most negative margin ΔΔG = ΔG_f^SISSO - ΔG*_median
  * below_upper     continuous temperature runs on the grid where ΔG_f^SISSO <= p95 of the band
                    (the candidate is not clearly above the competing binaries)
  * stable_runs     runs where ΔG_f^SISSO < p05 (clearly below)
  * class_changes   whether the CALPHAD-band class changes with temperature, and where

Only rows with a stability verdict enter (exact matches whose ensemble passed its gates);
nearest-prototype rows and `ensemble_unreliable` rows are left out.
"""
from __future__ import annotations

from itertools import groupby

VERDICT_CLASSES = ("stable_across_band", "borderline_within_band", "metastable_above_band")


def _runs(temps: list[float], flags: list[bool]) -> list[tuple[float, float]]:
    out, i = [], 0
    while i < len(temps):
        if flags[i]:
            j = i
            while j + 1 < len(temps) and flags[j + 1]:
                j += 1
            out.append((temps[i], temps[j]))
            i = j + 1
        else:
            i += 1
    return out


def stability_window(rows: list[dict]) -> dict | None:
    """rows: comparison rows of ONE candidate (keys T_K, dGf_sisso_kJ, stability_margin_kJ,
    threshold_p05_kJ, threshold_p95_kJ, verdict). Returns None if no row has a stability verdict."""
    use = sorted((r for r in rows if r.get("verdict") in VERDICT_CLASSES and r.get("stability_margin_kJ") is not None),
                 key=lambda r: r["T_K"])
    if not use:
        return None
    temps = [float(r["T_K"]) for r in use]
    best = min(use, key=lambda r: r["stability_margin_kJ"])
    below_upper = _runs(temps, [r["dGf_sisso_kJ"] <= r["threshold_p95_kJ"] for r in use])
    stable = _runs(temps, [r["dGf_sisso_kJ"] < r["threshold_p05_kJ"] for r in use])
    classes = [(float(r["T_K"]), r["verdict"]) for r in use]
    transitions = [(a[0], b[0], a[1], b[1]) for a, b in zip(classes, classes[1:]) if a[1] != b[1]]
    return {
        "T_best_K": float(best["T_K"]),
        "margin_best_kJ": float(best["stability_margin_kJ"]),
        "below_upper_edge": below_upper,
        "longest_below_upper_edge": max(below_upper, key=lambda r: r[1] - r[0]) if below_upper else None,
        "clearly_stable": stable,
        "classes": classes,
        "class_changes": bool(transitions),
        "transitions": transitions,
        "n_temperatures": len(use),
    }


def windows_from_rows(rows: list[dict]) -> dict[str, dict]:
    """{material_id: window} for the exact-match rows of a comparison table."""
    out = {}
    exact = [r for r in rows if r.get("match_type", "exact_match") == "exact_match"]
    for mid, grp in groupby(sorted(exact, key=lambda r: str(r["material_id"])), key=lambda r: r["material_id"]):
        w = stability_window(list(grp))
        if w:
            out[mid] = w
    return out


def format_windows(windows: dict[str, dict]) -> list[str]:
    """Plain-text lines for the CLI and the desktop preview."""
    lines = []
    for mid, w in windows.items():
        def rng(r):
            return f"{r[0]:.0f}-{r[1]:.0f} K" if r[0] != r[1] else f"{r[0]:.0f} K"
        lines.append(f"Stability window of {mid} (grid of {w['n_temperatures']} temperatures):")
        lines.append(f"  most negative margin {w['margin_best_kJ']:+.2f} kJ/mol-atom at {w['T_best_K']:.0f} K")
        lines.append("  not above the band (ΔG_f ≤ p95): "
                     + (", ".join(rng(r) for r in w["below_upper_edge"]) or "nowhere on the grid"))
        lines.append("  clearly below the band (ΔG_f < p05): "
                     + (", ".join(rng(r) for r in w["clearly_stable"]) or "nowhere on the grid"))
        if w["class_changes"]:
            lines.append("  class changes: " + "; ".join(f"{a:.0f}→{b:.0f} K: {x} → {y}" for a, b, x, y in w["transitions"]))
        else:
            lines.append(f"  class does not change with temperature ({w['classes'][0][1]})")
    return lines
