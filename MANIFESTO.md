# Manifesto: on the role of AI/ML in this project

This document states a position, not a critique of any specific tool,
company, or person. It exists because this project makes deliberate,
sometimes unusual choices about where AI/ML fits into a materials
discovery pipeline, and those choices deserve to be explained rather than
left implicit.

## The position, briefly

AI and ML models are useful here as **candidate-narrowing tools** —
ranking, filtering, and prioritizing — never as a replacement for
physical reasoning, and never trusted as ground truth without an
independent check. A prediction is a hypothesis to verify, not an answer
to act on.

This isn't a rejection of AI/ML. Several tools used directly in this
project are themselves ML- or heuristic-based (matminer/Magpie-style
composition descriptors are a planned addition; the literature-check
tier already queries ML-adjacent databases). The position is about *how*
such tools are used, not *whether*.

## Why this position, specifically

**Composition-only and structure-only models are interpolation
machines; materials discovery is fundamentally an extrapolation
problem.** A model trained on a given composition space can rank
plausible candidates well within that space. It has no principled way
to know when a new composition crosses a phase boundary into territory
it has never seen — and a small stoichiometric change can do exactly
that. This project treats any model's output as valid only within the
region its training data actually covers, and treats confidence outside
that region as unearned.

**Simulation-derived training data inherits the simulation's own
systematic errors.** A model trained on DFT-derived properties learns
DFT's known failure modes (e.g. band-gap underestimation, difficulty
with strongly correlated electrons) along with whatever real signal
exists. High accuracy against a held-out split of the *same simulated
data* does not mean the model has learned physics; it may simply mean it
has learned the simulation's biases faithfully. The only real test is
independent, physical verification — synthesis, characterization,
comparison against a certified reference — not a better validation
split.

**A prediction without a stated validity envelope isn't falsifiable,
and isn't actionable.** "This model predicts stable compositions" is a
claim that means very little without also stating: stable according to
which target property, verified against what, and within which region
of composition space. Claims framed as universally applicable, without
those boundaries stated, cannot be checked — and can't be usefully
disagreed with either, since there's no specific claim to test against.

## What this looks like in practice, in this project

This project's own screening pipeline is built around exactly this
discipline, not as an abstract principle but as working code:

- **VEC / δ / ΔH_mix** are interpretable physical heuristics, not fitted
  models — every number has a direct physical meaning (electron
  concentration, atomic size mismatch, mixing enthalpy), and the
  reasoning behind each threshold is documented, not hidden behind
  training weights.
- **The synthesis feasibility check** (melt/boil-point based) explicitly
  separates its own outputs into three tiers: a hard physical rule where
  confident, a comfortable "no concern" case, and — deliberately — a
  `caution` tier for the genuinely ambiguous middle ground, where the
  honest answer is "check further" rather than a confident guess dressed
  up as one.
- **The XRD analysis pipeline was validated against a certified external
  reference standard** (NIST SRM 660, LaB6), not just checked for
  internal self-consistency — because internal consistency alone can't
  distinguish a correct pipeline from one that's consistently wrong.
- **A peak-matching result was walked back mid-project** when a second,
  independent check (intensity ratio) contradicted an initial,
  single-criterion conclusion (position match alone). The correction is
  documented in the project history rather than quietly dropped, because
  a project that hides its own reversals doesn't build trust in the
  reversals it doesn't make.

None of this makes the project immune to error. It makes errors visible
and checkable, which is the actual goal — not infallibility, but
falsifiability.

## What this project asks of any AI/ML tool it adopts

- A stated validity envelope: what compositions, targets, or measurement
  types it was validated against, and where it's known to degrade.
- Independent verification against physical data, not only against a
  held-out split of its own training distribution.
- Auditability: enough transparency to understand *why* it produced a
  given output, even if the full internals are proprietary. A ranking
  tool can be usefully opaque about its internal weights while still
  being auditable about its benchmark methodology; a tool that is opaque
  about both is not something this project can build on with confidence.

This project would rather move slower and stay checkable than move fast
on a claim nobody can verify.
