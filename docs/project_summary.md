# Alloy Lab Database Project — Summary (Phase 1 nearing completion)

**Goal:** database of experimental alloy results (samples → synthesis →
characterization → properties), usable as (1) a searchable lab notebook and
(2) training data for ML models predicting whether a novel composition is
known, and if not, how to try synthesizing it.

**Where things stand:** the core loop — composition in, screening +
multi-database literature checks out, everything queryable and permanently
attached to the sample — is fully working, in both a CLI tool and now a
proper desktop GUI. What's left before Phase 1 is genuinely done is mostly
data-completeness work (raw files, element-fraction table), not new
capability.

## Core infrastructure (stable since early sessions)

- Postgres schema: `samples` (JSONB `composition`, plus real `vec`/`delta`/
  `delta_h_mix` columns), `synthesis`, `characterization`, `properties`,
  `compositions`, `literature_sources`, `material_classes`,
  `literature_checks` (one row per deduped candidate phase per source db
  per sample).
- `.env`-based credentials, git-initialized with proper `.gitignore` —
  password issue closed out for good.
- `alloy_calculator.py`: rewritten with a strict formula parser (catches
  genuinely ambiguous cases like "Cp" — since C and P are both real
  elements, this needed real validation logic, not just a lookup), at%/wt%
  conversion, pre-alloy support, excess_pct for evaporation-loss
  compensation.
- `alloy_screening.py`: VEC/δ/ΔH_mix, now with **full periodic table
  coverage** (was 12 elements, user expanded it independently) and a clean
  `IncompleteElementDataError` for any still-missing element instead of
  silently computing a wrong number.

## Literature-check databases: three working, one abandoned

| Database | Status | Notes |
|---|---|---|
| Materials Project | ✅ working | `mp_lookup.py`. Tier 1-4, hull-distance, theoretical flag, text-mined synthesis recipes (coverage is oxide-heavy, often empty for metals). |
| OQMD | ✅ working | `oqmd_lookup.py`, via OPTIMADE. No API key. `_oqmd_icsd_id` = experimentally known. Occasionally 502s (busy academic server) -- **retry logic not yet added, see open items.** |
| Alexandria | ✅ working | `alexandria_lookup.py`, via OPTIMADE (same client/pattern as OQMD). Real `_alexandria_hull_distance` field (directly comparable to MP/OQMD). Purely computational -- `experimentally_known` always False. Much larger dataset (2.5M+) -- this is the one that needed the cutoff feature (see below). |
| AFLOW | ❌ abandoned | `aflow` python package (v0.0.11, unmaintained since ~2017-2019) hit a live 404 -- likely a moved/dead endpoint. Also had a real bug (keyword objects are mutable singletons; repeated `.filter()` calls silently corrupt earlier values) and an unresolved AND/OR semantic ambiguity in AFLUX. Not worth pursuing further; Alexandria filled the "third database" role better anyway. |

All three normalize into one shape via `lookup_common.py`:
- `DedupCandidate` + `from_mp_results()` / `from_oqmd_results()` /
  `from_alexandria_results()` adapters.
- `dedup_by_formula()`: collapses raw entries to one per distinct formula
  (prefer experimentally known > most stable > closest composition match).
- `filter_by_distance()`: drops tier-2 candidates beyond a distance cutoff
  (tier-3/4 untouched, since they have no meaningful distance value).

## The cutoff feature (today's main addition)

Alexandria's larger dataset returned 60+ distinct formulas for a single
query, most barely related (distance 0.5-0.7) -- the existing dedup
handled *duplicates* fine but not this kind of *volume*. Solution: a
per-database distance cutoff, now live in the desktop GUI:
- Radio buttons (Materials Project / OQMD / Alexandria) select which
  cached result set is shown in one shared results area.
- A slider sets **that database's own** cutoff (defaults: MP 0.5, OQMD
  0.4, Alexandria 0.3 -- based on actually observed flood behavior, not
  guessed).
- "Calculate & Preview" fetches all three databases **once, upfront**;
  switching radio buttons or dragging the slider afterward just re-filters
  the cache -- no repeat network calls.
- "Submit to Database" logs all three databases' results, each using its
  *own* last-set cutoff (not just whichever was on-screen), reusing the
  same cache rather than re-querying.

## Bugs found and fixed today

1. **`alloy_screening.py` silent element-skip** (queued from a previous
   session): now raises `IncompleteElementDataError` instead of silently
   computing VEC/δ from a partial subset. Both the CLI tool and the GUI
   catch this gracefully (skip screening for that one run, continue with
   `vec`/`delta`/`delta_h_mix` left `NULL`) rather than crashing.
2. **GUI `generate_sample_id()` crash**: `prefix` was only assigned
   *inside* the same `try` block as the DB call, after it -- if
   `get_db()` failed for any reason (Postgres not started, bad config),
   the `except` fallback hit an `UnboundLocalError` instead of degrading
   gracefully. Found by actually instantiating the GUI under a virtual
   display (Xvfb) with Postgres deliberately unreachable. Fixed by moving
   `prefix` assignment before the `try`.
3. **`lookup_common.py` regression introduced by a sloppy edit, same
   session**: an edit meant to add `filter_by_distance()` accidentally
   deleted `_is_better()`'s function signature while leaving its body
   behind as orphaned dead code inside the wrong function -- broke
   `dedup_by_formula()` for all three databases at once
   (`NameError: name '_is_better' is not defined`). This shipped because
   the fix was verified by testing `filter_by_distance()` in isolation,
   not the full `dedup_by_formula()` path that actually depends on
   `_is_better()`. Caught only because the user ran it for real and got a
   live error. Fixed, and this time re-verified through the actual full
   call chain (`MatchResult` → `from_mp_results` → `dedup_by_formula` →
   `filter_by_distance` → GUI render), not an isolated piece.

## Open items for next session

1. **OQMD automatic retry on 502** (wait ~30-60s, one retry before
   surfacing the warning) -- queued a while ago, still not implemented.
2. **`alloy_entry_full.py` (CLI tool) is now behind the GUI**: only calls
   MP + OQMD (no Alexandria), and has no distance-cutoff filtering at all
   -- dumps every deduped entry straight to the DB. Worth deciding whether
   the CLI still matters now that the GUI exists, or whether it's fine to
   let it lag/retire.
3. **Element-fraction table** for easier ML-style querying (e.g. "all
   samples with Fe > 0.6") -- open since the earliest sessions.
4. **Raw characterization file handling** (XRD/SEM auto-import) -- open
   since day one. User is planning to work on this independently before
   the next session.
5. **Patent records table** (companies patenting before publishing) --
   explicitly deferred to the ML-planning phase, not a near-term item.

## Files (cumulative)

| File | Purpose |
|---|---|
| `db_config.py` | DB connection settings, reads from `.env` |
| `alloy_db.py` | `AlloyDB` class -- `add_sample()` w/ screening columns, `add_literature_check()` |
| `alloy_calculator.py` | Strict formula parser + mass calculator (excess%, pre-alloys) |
| `alloy_screening.py` | VEC/δ/ΔH_mix, full periodic table, `IncompleteElementDataError` |
| `mp_lookup.py` | Materials Project tier 1-4 lookup + synthesis recipes |
| `oqmd_lookup.py` | OQMD tier 1-4 lookup via OPTIMADE |
| `alexandria_lookup.py` | Alexandria tier 1-4 lookup via OPTIMADE |
| `lookup_common.py` | Shared dedup + distance-filter logic for all three databases |
| `alloy_entry_full.py` | CLI one-command workflow (MP + OQMD only, no cutoff -- see open item #2) |
| `alloy_desktop_with_db_classes.py` | Desktop GUI -- all 3 databases, cutoff sliders, dynamic material classes |
| `001_screening_and_literature_checks.sql` | Schema migration (samples columns + literature_checks table) |
| `.env` / `.gitignore` | Credentials |

## Quick commands reference

```bash
# Activate environment / start DB
cd /Users/r/Documents/Projects/my_db_project
source venv/bin/activate
docker start postgres

# Run the desktop GUI
python alloy_desktop_with_db_classes.py

# Run the CLI workflow (currently behind the GUI, see open item #2)
python alloy_entry_full.py

# Check a sample's screening columns + literature checks
docker exec -it postgres psql -U postgres -d alloy_lab -c \
  "SELECT sample_id, vec, delta, delta_h_mix FROM alloy_lab.samples WHERE sample_id = '...';"
docker exec -it postgres psql -U postgres -d alloy_lab -c \
  "SELECT source_db, match_formula, tier, stability, experimentally_known FROM alloy_lab.literature_checks WHERE sample_id = <id> ORDER BY source_db, stability;"
```

## Suggested opening for next session

"I worked on raw characterization file handling -- here's what I've got.
Let's also do the OQMD retry, decide what to do with alloy_entry_full.py
now that the GUI exists, and look at the element-fraction table."
