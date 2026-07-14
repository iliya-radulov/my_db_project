# Composition Screening (`alloy_screening.py`)

A cheap, offline, composition-only first filter for synthesis feasibility
— no network calls, no external dependencies, just arithmetic over a
per-element property table.

## The three metrics

- **VEC (Valence Electron Concentration)**: composition-weighted average
  of each element's valence electron count. Used as a rough predictor of
  solid-solution crystal structure (BCC vs. FCC) in multi-element alloys.
- **δ (atomic size mismatch)**: composition-weighted RMS deviation of
  atomic radius from the composition's average radius. Small δ suggests a
  solid solution is more likely; large δ suggests intermetallic phase
  formation is more likely.
- **ΔH_mix (mixing enthalpy)**: pairwise Miedema-style mixing enthalpy
  parameters, summed over all element pairs weighted by their atomic
  fractions. Strongly negative suggests compound formation; near zero
  suggests weak interaction.

Together, these three are the standard cheap empirical screen used ahead
of any actual melting — the same logic behind high-entropy-alloy phase
prediction more generally.

## Element coverage: try → result → next

**Tried:** `ELEMENT_PROPERTIES` originally covered 12 elements (the ones
in immediate use: Fe, Nd, Co, B, Al, Si, Ni, Cr, Mn, Cu, La, Ga).

**Result:** `calculate_vec()` and `calculate_delta()` silently skipped any
element not in the table rather than erroring — so screening a
composition containing, say, Dy or Ti (both realistic for related alloy
families) would quietly compute VEC/δ from an incomplete subset of the
actual composition, giving a confidently wrong number with no indication
anything was skipped.

**Then:** two separate fixes, at different times:
1. `ELEMENT_PROPERTIES` was expanded to full periodic table coverage
   (103 elements — H through Lr), removing most real-world gaps.
2. Independently, a proper `IncompleteElementDataError` was added,
   raised immediately if any element in a composition still isn't in the
   table, rather than silently proceeding. The calling code (both the CLI
   tool and the GUI) catches this specifically and skips screening for
   that one run — leaving `vec`/`delta`/`delta_h_mix` as `NULL` in the
   database — rather than crashing the whole entry workflow.

## Mixing enthalpy: a milder version of the same gap

`calculate_mixing_enthalpy()`'s pairwise parameter table only covers a
subset of element *pairs* (not all elements individually) — any pair
without a defined parameter silently contributes 0 to ΔH_mix rather than
raising an error. This is a real, still-open gap, milder than the
VEC/δ case since a missing pair just under-counts one contribution rather
than failing outright, but worth being aware of: a ΔH_mix result should
not be read as "all pairwise interactions accounted for" without checking
which pairs actually have parameters defined.

## Output

`screen_composition()` returns `{'VEC': ..., 'delta': ..., 'Delta_H_mix':
...}`. `interpret_screening()` gives a plain-language read (solid solution
vs. intermetallic likely, weak/moderate/strong compound formation) for
quick human interpretation.
