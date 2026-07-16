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
..., 'synthesis_feasibility': {...}}` (the last key added in Stage 2, see
below). `interpret_screening()` gives a plain-language read (solid solution
vs. intermetallic likely, weak/moderate/strong compound formation, plus
melt/boil feasibility) for quick human interpretation.

---

## Stage 2 addition: synthesis feasibility (melt/boil check)

Added after Stage 1 closed, to the same module and same `ELEMENT_PROPERTIES`
table — not part of the original Stage 1 build, called out separately here
so the history stays accurate. Motivated by a real practical need: knowing
*whether a melt-based synthesis route is even physically possible* before
attempting it, given how different constituent melting points can be.

### The physical logic

`check_synthesis_feasibility()` answers a different question from
VEC/δ/ΔH_mix — not "will this form a solid solution," but "can this even be
melted together." The core insight: melting-point *spread* alone isn't the
right signal. What actually matters is whether homogenizing the melt
requires heating past the **boiling point** of the most volatile
constituent:

- To melt the highest-melting element, the whole melt must reach at least
  its melting point.
- If that temperature is at or above the lowest-melting element's
  **boiling point**, that element doesn't just risk *some* evaporation —
  it boils off before or as the alloy homogenizes. Classic real cases:
  Mg (melts 923 K, boils 1363 K) or Zn (melts 693 K, boils 1180 K) paired
  with almost any refractory metal.

This gives three tiers, deliberately not collapsed into a single
confidence level:
- **`blocked`** — required melt temperature is at/above the volatile
  element's boiling point (minus a 125 K safety margin, since real
  vacuum/inert-atmosphere furnaces generally *lower* effective boiling
  point further, not raise it). A hard physical block: suggests
  mechanical alloying, powder sintering, or diffusion bonding instead.
- **`caution`** — a real but non-decisive gap. Pure-element numbers alone
  aren't sufficient here: a strongly negative ΔH_mix can suppress a
  volatile element's effective vapor pressure once alloyed, which this
  composition-only check cannot quantify. Flagged rather than resolved —
  points to checking `calculate_mixing_enthalpy()`, literature precedent,
  or a small test melt.
- **`ok`** — comfortable margin, no melt-based volatility concern from
  composition alone.

### A real data anomaly this surfaced

Arsenic's melting point (1090 K) is *above* its boiling point (887 K) in
the reference table used to build `melt_K`/`boil_K` — not a data error:
As sublimes directly at 1 atm and only shows a true liquid phase under
~3.6 MPa pressure. Astatine shows the same inversion, though that's more
about how poorly-characterized At is (only ever produced in trace
quantities). Documented directly in `ELEMENT_PROPERTIES` so future logic
doesn't silently assume boiling point always exceeds melting point.

### What this deliberately does NOT do

No attempt is made to auto-adjust the `caution` threshold using ΔH_mix,
even though the two numbers are conceptually related (ΔH_mix affects real
vapor pressure via activity coefficients, Raoult's-law-type effects) —
that would require real thermodynamic modeling this composition-only
check isn't trying to do. The `caution` tier exists specifically to avoid
presenting false precision on genuinely open questions.

### Validation

Tested against real element pairs, not just internal consistency:
FeCoNi → `ok`; W+Mg → `blocked` (textbook incompatible pair); Fe+Nb →
`caution` (both common alloying elements, non-extreme mismatch — a
genuinely useful example of the middle tier). The module's own
pre-existing `Fe2P` self-test also independently confirms `blocked`,
which matches real metallurgical practice — Fe-P compounds are
typically made via solid-state routes, not open arc melting.

