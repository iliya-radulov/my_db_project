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

## AI assistance in the work itself

The sections above are about AI/ML models used *inside* a pipeline. The same
question applies to the assistant used to *build* the pipeline, and it deserves
the same answer.

**Where this started.** I began working with an AI assistant roughly four
months ago, without having thought through what role it should play. The
rules below are not a plan I wrote beforehand. They are the habits that
survived contact with real work, and I am still learning.

**An assistant's explanation is a hypothesis too.** The rule of this project is
that a prediction is a hypothesis to verify. That holds for an assistant's
output exactly as it holds for a model's. A fluent, confident explanation is not
evidence. It becomes a result only after a test that could have failed.

**A worked example.** In the Track A study (an ensemble of open CALPHAD
assessments for Nd-Fe-B), six of 84 combinations failed a consistency check.
Two explanations were proposed in turn, an extra crystal phase in one
assessment and a set of silently introduced symbols. Both were plausible and
both were wrong. They were rejected by direct tests, the cause was then
isolated by a test that restored the original sublattice model and removed the
deviation completely, and the rejected hypotheses stayed in the supplementary
material instead of being deleted. A project that hides its reversals does not
earn trust in the claims it does not reverse.

**The assistant makes ordinary errors, and the process has to catch them.**
During the same work, the direction of a key quantity was stated backwards
in the draft and had to be corrected, the assistant stated that a folder was
excluded from version control without checking, and it overwrote a text edit made
on another machine. None of these were
dramatic, and all of them were found because the work leaves checkable
traces: checksums, tests, a README that has to run, and a record that is
compared against the files.

**Dialogue, not orders.** What I need is not an assistant that executes
commands to assemble a pipeline. Mining documents and moving data are
necessary and I do some of it that way, but the valuable part is the
discussion: objecting, proposing a test, saying that an argument does not follow.
The decision, and the responsibility for it, stay with the author.

**The data must not simply confess.** There is an old saying that if you
torture the data long enough, it will confess to anything. An assistant that
is eager to please makes this easier, because it will help to build a
convincing story for whatever result is wanted. The defence is the same as
for any analysis: fix the criterion before looking (the 1 J/mol edge check was
fixed in advance), report what does not fit, and show how conclusions change
if the criterion is relaxed (the six failures were re-admitted and the result
was unchanged).

**Disclosure.** Where an assistant contributed to code or text, it is stated:
the software records list it as a creator, the paper acknowledges it by name
and version, and the author reviewed the content and is responsible for it.
This is not an apology and not a claim of credit. It tells the reader what
kind of checking to expect.

**What I would not do.** I would not publish a claim whose only support is that
the assistant said so, and I would not use an assistant to produce results I
cannot reproduce without it. If the work cannot be re-run from the released
files, it is not finished.
