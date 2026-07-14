# Literature Cross-Checking

Given a composition, answer: is this already known, and if not, is
something similar known? Three databases ended up working; one was tried
and deliberately abandoned.

## The four-tier system

Shared across all three working databases:

| Tier | Meaning |
|---|---|
| 1 | Exact/near-exact composition match found |
| 2 | Same elements, different ratio — similar system documented |
| 3 | Only a subsystem (e.g. a binary instead of the full ternary) is known |
| 4 | Nothing found anywhere |

Tier 1/2 is determined by a composition-distance metric (normalized L1
distance between atomic-fraction vectors, 0 = identical, capped at 1) with
a small default near-match threshold (0.05) splitting tier 1 from tier 2.
Tier 3 is checked by dropping one element at a time from the target
composition and re-querying, only if nothing was found at the full
element count.

## Materials Project (`stage_one/lookup/mp_lookup_v1.py`)

Free API key required (`mp-api` package). Provides `energy_above_hull`
(0 = stable; DFT 0K data, so "above hull but real" is common and expected,
not a contradiction — finite-temperature/kinetic effects aren't captured)
and a `theoretical` flag (computed-only vs. actually observed). Also
exposes a text-mined synthesis-recipe endpoint (precursors, heating steps,
DOI) — coverage is oxide-heavy, often empty for metallic alloys (confirmed
on AlFe2Ni: a real, well-characterized compound with no mined recipe at
all — an honest negative result, not a bug).

## OQMD (`stage_one/lookup/oqmd_lookup_v1.py`)

No API key. Queried via **OPTIMADE**, a standard query protocol shared
across several materials databases — this matters because it means the
same client code and query patterns are reusable for other OPTIMADE
providers (see Alexandria, below). "Experimentally known" comes from
`_oqmd_icsd_id` being set (traces back to a real ICSD structure) rather
than an explicit boolean. OQMD's server is a single academic group's
infrastructure and occasionally returns transient errors (502) or is
slow to respond under load — this is treated as a real error state, not
silently folded into "nothing found" (see Dedup, below).

**Retry logic (both OQMD and Alexandria).** The `optimade` client's own
`max_attempts` setting turned out to be a red herring for this specific
problem: its built-in retry only ever fires on HTTP 429
(`RecoverableHTTPError`, raised only for that status code) — a 502
raises a plain `RuntimeError` internally that the library reports in the
result's `errors` list but never retries on its own. Confirmed by reading
the library's source directly rather than assuming. Both lookup modules
now detect 502/503/504 specifically and retry once after a 45s wait
before surfacing the warning — verified with a mocked client covering
three cases: transient error then success, persistent failure (gives up
after exactly one retry, doesn't loop forever), and a non-transient error
like 404 (never retried at all, no wasted wait).

A GUI-level complement to this: a "skip literature search" checkbox was
added so screening/mass-calc can still be previewed instantly during a
provider outage, without waiting through retries at all — worth knowing
that the retry fix makes a *brief* outage more resilient but a
*sustained* one slower to fail, since it now waits 45s longer before
giving up; the skip checkbox is the escape hatch for that case.

Cross-validation example (Fe70Al15Ni15): Materials Project and OQMD
independently gave 0.235 and 0.236 eV/atom above hull for the same
compound (AlFe2Ni) — two different DFT codes/settings landing within
0.001 eV/atom of each other, a strong signal the result is real rather
than an artifact of one group's specific settings.

## Alexandria (`stage_one/lookup/alexandria_lookup_v1.py`)

Also OPTIMADE (`https://alexandria.icams.rub.de/pbe`) — reused the OQMD
client pattern almost directly. Has a genuine `_alexandria_hull_distance`
field, directly comparable to MP/OQMD's stability numbers (unlike AFLOW,
below). Purely computational database (2.5M+ entries) — no experimental
linkage field found, so `experimentally_known` is always `False` here;
treat it as a third independent stability opinion, not a source of
"has this been made" information.

**The volume problem.** Alexandria's much larger dataset returned 60+
distinct formulas for a single Fe-Al-Ni query — not duplicate DFT runs
(which dedup already handles) but genuinely distinct, mostly unrelated
compositions (many at distance 0.5-0.7, barely related to the actual
target ratio). This motivated the cutoff feature below.

## AFLOW: attempted and abandoned

**Tried:** the unofficial `aflow` python package (AFLUX query language).

**Result:** three independent reasons to stop, discovered in sequence:
1. The package (v0.0.11) hadn't been updated since roughly 2017-2019.
2. Its keyword objects turned out to be **mutable singletons** — calling
   `.filter()` more than once on the same keyword (e.g. `K.species`)
   silently corrupts earlier filter values instead of raising an error.
   Worked around by chaining into one expression before filtering once,
   but this was a real, non-obvious trap.
3. Even after fixing that, whether a comma-separated list within one
   keyword clause means "match ALL of these" or "match ANY of these" in
   AFLUX couldn't be verified without a live server.
4. When actually run against the live server: **HTTP 404** — not a
   timeout or a busy-server error like OQMD's occasional 502s, but a
   clean "not found," suggesting the endpoint itself may have moved or
   been retired.

**Then:** dropped in favor of Alexandria, which turned out to be the
stronger third database anyway (real hull-distance field, proven
OPTIMADE pattern, no query-language guesswork required). This is
presented as a deliberate, correct call — not a failure — three
independent red flags is enough reason to stop pushing on a dead end.

## Deduplication and the cutoff feature (`stage_one/lookup/lookup_common_v1.py`)

`DedupCandidate` + per-database adapters (`from_mp_results()`,
`from_oqmd_results()`, `from_alexandria_results()`) normalize all three
databases' output into one shape. `dedup_by_formula()` then collapses raw
entries down to one row per **distinct formula**, ranked: prefer
experimentally known over theoretical-only, then most stable, then
closest composition match. (Verified concretely: OQMD returned three raw
entries for one composition with different stability values and
experimental-known flags; dedup correctly kept only the experimentally
known, most stable one.)

`filter_by_distance()` then drops tier-2 candidates beyond a
per-database distance cutoff (tier-3/4 candidates have no meaningful
composition distance and are never filtered by this). Default cutoffs,
chosen from what was actually observed flooding vs. not: MP 0.5, OQMD
0.4, Alexandria 0.3.

In the GUI, this is exposed as a radio-button database selector plus a
cutoff slider: **Calculate & Preview fetches all three databases once**
and caches the raw results; switching the selector or dragging the slider
afterward just re-filters the cache with no repeat network calls, and
each database remembers its own cutoff independently.

## A regression worth remembering

An edit meant to add `filter_by_distance()` accidentally deleted the
signature of an existing helper function (`_is_better()`) while leaving
its body behind as orphaned, unreachable dead code inside the wrong
function — silently breaking deduplication for all three databases at
once (`NameError` only surfaced at actual runtime, not at parse time).
It shipped because the fix was verified by testing the newly-added
function in isolation, not the full dedup call chain that depended on the
now-missing one. Caught only because it was run for real, not because
testing caught it first. Retested afterward through the actual full call
chain, not an isolated piece — the lesson that stuck.
