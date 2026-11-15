# TDB reconstruction — results

Build: `build_tdb.py` → `LaFeSi_feng2023.tdb`. Validation + descriptor:
`audit.py`. Spec and acceptance test frozen beforehand in `FROZEN_SPEC.md`.

## Acceptance test (FROZEN_SPEC §4) — result: ACCEPTED

| # | test | result |
|---|---|---|
| A1 | parses & computes (17 phases, finite G) | **pass** |
| A2 | GHSERLA/FE/SI match SGTE numerically at 1000/1500 K | **pass** (exact) |
| A3 | τ1 single-phase at the frozen La(Fe11.5Si1.5), 1373 K | **pass** (NP = 1.000) |
| A4 | Feng Table 4 τ1-bearing alloys | τ1 correct in **5/5**; αFe correct where reported (#11, #17); τ3-alloys partial (τ3 deferred) |
| A5 | τ1/τ2 window vs literature | **pass** — τ1 single-phase x≈0.10–0.23, τ2 x≥0.27; lit. τ1 0.096–0.229, τ2 0.266+ |

A1–A3 full; A4/A5 strong with the one documented gap (τ3–τ6 deferred, so
the τ3-bearing alloys #10/#13/#21 substitute another phase for τ3). This
does not touch the τ1 corner or the descriptor.

## WP4 descriptor — ΔG_f(τ1) at La(Fe₁₁.₅Si₁.₅)

Formation Gibbs energy of τ1 relative to the SER elements (dhcp-La,
bcc-Fe, diamond-Si), from the equilibrium GM (τ1 single-phase throughout):

| T (K) | ΔG_f(τ1) [J/mol-atom] |
|---|---|
| 1173 | −20616 |
| 1273 | −20805 |
| **1373 (T_anneal)** | **−20993** |
| 1473 | −21181 |

Nearly linear, ≈ −1.9 J/mol-atom·K, smoothly more negative with T. This is
the Track B physics descriptor ΔG_f*(T_anneal) at the 1:13 composition.

Note: an earlier pass read +23 kJ via `calculate()` on a coarse internal
grid that missed τ1's ideal site occupancy — the equilibrium GM is the
correct source (negative, as a stable phase must be). Logged as a lesson.

## Scope and deferred

Built: LIQUID, FCC_A1, BCC_A2, DIAMOND_A4, the five Fe–Si line compounds,
the six La–Si(Fe) compounds, τ1 and τ2 = La(Fe,Si)₁₃. Deferred (do not
affect the Fe-rich τ1 descriptor): τ3–τ6 (need the three-sublattice site
ratios from a cleaner read of Feng's eq. 8) and the Fe–Si B2/D03 ordering.

## Faithfulness

Binary backbone = Feng's own Table 5 (so the ternary parameters sit on
exactly the binaries they were fitted on — Zhou/Cui/Su; no hybrid). Unaries
SGTE/Dinsdale 1991, verified identical across sources. The separate WP4
uncertainty band (swap Feng's binaries for the Track A collection's other
members) is the next layer and needs those external binary files.
