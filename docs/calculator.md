# Calculator (`stage_one/alloy/alloy_calculator_v1.py`)

Converts an alloy formula and a target sample mass into grams of each
element to weigh out. By a wide margin, the most-iterated module in the
whole project — nearly every feature that seemed simple at first revealed
a real edge case once used on actual formulas.

## Formula parsing: try → result → next

**Tried:** a straightforward parser splitting on element symbol vs. digit
characters.

**Result:** it worked for clean input, but silently mishandled genuinely
ambiguous cases. The clearest example: `"Cp"` looks like a typo (maybe
meant "Co" or "Cu"), but naive character-based parsing can't distinguish
that from **C** followed by **P** — both are real, valid one-letter
element symbols. There is no purely syntactic way to know which the user
meant.

**Then:** the parser was rewritten with strict validation — a fixed set of
known valid single-letter elements (`B, C, F, H, I, K, N, O, P, S, U, V,
W, Y`) and known two-letter combinations, requiring a number immediately
after each recognized element. Anything that doesn't match a valid
element unambiguously now raises a clear `ValueError` naming the invalid
token, rather than silently guessing. Two-letter elements are matched
case-insensitively (`'lafe11.6si1.4'` parses the same as
`'LaFe11.6Si1.4'`).

## at% ↔ wt% conversion

Originally a free-text unit field defaulting silently to `at%` on any
unrecognized input — meaning a typo (`"wt"` instead of `"wt%"`) would
silently reinterpret a weight-percent composition as atomic-percent with
no warning, and the wrong composition would go straight into the
database. Solved structurally once the GUI existed: a proper selector
(radio buttons/dropdown) replaces free-text entry, removing the typo
class of bug entirely rather than patching around it.

Conversion itself (`at_to_wt` / `wt_to_at`) is standard: atomic
percent × atomic weight, normalized, in both directions, using the
`ATOMIC_WEIGHTS` table (standard IUPAC values, ~90 elements).

## Pre-alloys

A pre-alloy (master alloy) is defined by its own internal atomic-percent
composition and contributes a share of the final alloy's total atoms.
The calculator reports both the elemental breakdown of the final alloy
*and* the grams of the pre-alloy itself to weigh out — since in practice
you weigh a chunk of an existing master alloy, not its constituent
elements separately.

## Fixed-mass pre-alloy mode (`calculate_masses_from_fixed_prealloy`)

The mode above assumes you're choosing a target total mass and the
calculator tells you how much pre-alloy that implies. The opposite,
equally common lab situation: you already have a **fixed, known mass**
of a pre-alloy (e.g. 13 g of Fe2P), and want to know how much of the
other raw elements to add on top, given a target at% split between the
pre-alloy and the additions.

**Key insight, not a new equation:** every output of `calculate_masses()`
scales linearly with `total_mass_g`. So this mode runs the *existing*
function once with a placeholder total mass, compares the pre-alloy's
placeholder-run grams to the actual known grams on hand, and rescales
everything by that ratio to solve for the real total mass. No new
mixing/composition math was needed — just an inverse framing of the same
calculation.

**A subtlety that matters, not just a rescale:** if the same element
appears in *both* the pre-alloy's own composition and the raw elements
being added (e.g. adding extra pure Fe on top of an Fe-containing
pre-alloy), a naive rescale-and-merge would double-count the pre-alloy's
own share as something you still need to weigh. This mode computes each
raw element's mass **directly** from its own contribution fraction,
never from a merged total, so only the genuinely additional amount is
reported. Verified against this exact overlap case before shipping.

**Worked example:** 13 g of Fe2P (85 at% of final) + Co (5 at%) + Si
(10 at%) → solves to a 14.85 g total, needing 0.9475 g Co and 0.9031 g Si.

**Scope limit, deliberate:** the raw "elements to add" side of this mode
only supports at% input, not wt% — converting a *partial* wt% (relative
to a whole that includes an already-fixed pre-alloy mass) to at% is a
meaningfully different calculation than the normal wt%↔at% conversion
above, and risked getting subtly wrong rather than being worth rushing.

## Excess percent (evaporation-loss compensation)

**Motivation:** during melting, some elements (notably rare earths and
other volatile elements) evaporate preferentially, so labs commonly weigh
in extra of the volatile element to compensate.

**Design:** `excess_pct` is a per-element field that adds extra weighed
mass **on top of** the target amount, without changing the recorded
target composition. This distinction matters for data integrity — the
composition stored in the database should reflect the *intended*
stoichiometry, not the as-weighed mass including compensation. Internally,
this is tracked per-contribution (not just per-element), so an element
sourced partly from a raw addition and partly from a pre-alloy is handled
correctly — the excess only applies to the raw portion, since a pre-alloy
is treated as fixed, already-made stock, not something being melted in
this step.

Only raw element rows carry an excess field — not pre-alloy
sub-compositions — since a pre-alloy is fixed stock you're taking a piece
of, not melting from scratch in that step.

## Output shape

`CalculationResult.as_composition_dict()` returns exactly the
`{element: atomic_fraction}` shape the `samples.composition` JSONB column
expects, so calculator output feeds directly into `AlloyDB.add_sample()`
with no reshaping.
