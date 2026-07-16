# Alloy Lab Database — Stage 1

A personal experimental database for alloy research: store samples, synthesis
conditions, and characterization results in a structured, queryable way,
cross-check every new composition against public materials databases, and
build toward using all of it as training data for ML models that predict
whether a novel composition is known — and if not, how to try synthesizing it.

This document is the narrative overview. Detailed technical write-ups for
each component live in [`docs/`](docs/).

---

## 1. Motivation

As a materials scientist working on novel alloys for practical applications,
experimental results were scattered across spreadsheets, Origin project
files, raw instrument output, and a genuinely messy desktop folder — the
kind every researcher accumulates over years. Two motives drove this
project, in roughly equal measure:

- **The practical one**: a real, structured lab database — one place to
  record what was made, how, and what it measured, that could later double
  as a backup and as training data for ML.
- **The personal one**: plain curiosity about whether this could actually be
  built solo, and a genuine desire to finally tame the messy desktop folder
  everything had been dumped into for years. Both motives mattered — the
  second one arguably as much as the first.

## 2. Goals / Scope (Stage 1)

**In scope for Stage 1:**
- A real relational database (not spreadsheets) for samples, synthesis,
  and characterization data, with composition stored in a form usable both
  for humans and later ML.
- A mass/stoichiometry calculator to go from "I want this alloy" to "weigh
  out these grams," including practical lab realities like pre-alloys and
  evaporation losses.
- Composition-only screening (VEC, atomic size mismatch δ, mixing enthalpy
  ΔH_mix) as a cheap first filter for synthesis feasibility.
- Cross-checking any composition against public DFT materials databases,
  to answer "is this known, and how similar is it to what's known."
- Ingesting real characterization data (XRD, VSM, and SEM) directly into
  the database, not just leaving it in raw instrument files.
- A usable interface (a desktop GUI) on top of all of it, so the tool is
  actually pleasant to use day to day, not just scriptable.

**Explicitly deferred to Stage 2 (data preparation for ML):**
- An element-fraction table optimized for ML-style queries (e.g. "all
  samples with Fe > 0.6"), as opposed to the JSONB composition column
  used for Stage 1's day-to-day entry work.
- A decision on consolidating the CLI tool and the GUI (the GUI has pulled
  ahead in capability; the CLI tool's future is a Stage 2 question).
- Curve-fitting and data-extraction libraries for turning raw
  characterization curves (XRD patterns, M-H loops) into structured
  features beyond what Stage 1 already extracts.
- A patent-records table, for the case where companies patent a
  composition before publishing on it — relevant to the ML story, not to
  basic data capture.

## 3. Plan

The original plan was much simpler than what actually got built: a
Postgres database, a Python interface, and a calculator script. Nearly
every component grew in scope once real use revealed a gap — the
calculator in particular went through the most iterations of anything in
the project (see [`docs/calculator.md`](docs/calculator.md)). The general
pattern across the whole project was: build the simplest version, use it
for real, let the first real failure define the next iteration. That
pattern is documented explicitly in
[`docs/`](docs/) as try → result → next chains, rather than presented as a
single clean design that was right from the start — it wasn't, and
pretending otherwise would make the docs less useful to future-me.

## 4. Decisions & Implementation (condensed)

Full detail, including the specific bugs and dead ends, lives in the
linked pages. This section is the short version.

### Core database — [`docs/database_schema.md`](docs/database_schema.md)
Postgres, with `samples` (JSONB composition, `parent_sample_id` for
lineage/family-tree tracking, plus real `vec`/`delta`/`delta_h_mix`
columns added later), `synthesis`, `characterization`, `properties`,
`literature_checks`, and supporting tables. Credentials were originally
hardcoded in plaintext — found and fixed via `.env` + `.gitignore`,
**before** the repo's first commit, so nothing ever entered git history.

### Calculator — [`docs/calculator.md`](docs/calculator.md)
Converts alloy formula strings and atomic/weight percent into grams to
weigh out. The single most-iterated component in the project: the formula
parser had to be rewritten to properly reject ambiguous input (e.g. "Cp,"
which looks like a typo but is actually the valid elements C and P
run together), atomic%/weight% conversion needed a real unit-selector fix
rather than a silently-defaulting text field, and lab-realistic features
(pre-alloys as components, excess% to compensate evaporation losses during
melting) each needed their own design pass.

### Screening — [`docs/screening.md`](docs/screening.md)
VEC / atomic size mismatch (δ) / mixing enthalpy (ΔH_mix) as a
composition-only feasibility pre-screen. Started with 12 elements'
properties hardcoded; expanded to full periodic table coverage. A silent
bug (unlisted elements were quietly skipped rather than raising an error,
giving a confidently wrong VEC) was found and replaced with an explicit
`IncompleteElementDataError`.

### Literature cross-checking — [`docs/literature_databases.md`](docs/literature_databases.md)
Three working integrations — Materials Project, OQMD, and Alexandria —
normalized into one common tier system (exact match / similar / partial
subsystem match / nothing found) and one dedup pipeline. A fourth
(AFLOW) was attempted and deliberately abandoned after hitting an
unmaintained library, a live 404, and unresolved query-semantics
ambiguity — a real example of a dead end that was correctly cut rather
than pushed through. Alexandria's much larger dataset surfaced a genuine
volume problem (dozens of barely-related matches), solved with a
per-database, adjustable distance cutoff, now live in the GUI.

### Characterization data — [`docs/characterization.md`](docs/characterization.md)
XRD (peak detection, lattice parameter), VSM (saturation moment,
remanence, coercivity), and SEM (magnification, accelerating voltage,
working distance, pixel size) modules — all built as custom parsers,
after a library (`magnetopy`, for VSM) turned out to be unusable. Two
genuine data-quality/format catches, not just code bugs: the VSM file's
own recorded sample mass was wrong (an instrument placeholder), with the
real mass only available encoded in the filename; and the SEM instrument
(Zeiss) stores its actual metadata inside proprietary compressed binary
TIFF tags rather than standard fields, requiring a custom binary-string
extractor. A practical, non-parsing problem also showed up at SEM scale —
690 files imported one at a time took 5-10 minutes — solved with batch
import rather than a parser change. A standalone data-sorter utility was
also built to bring order to the real, years-accumulated messy desktop
research folder — successfully routing hundreds of real files (XRD, ICP,
Origin projects, presentations) into organized subfolders in one pass.

### Desktop GUI — [`docs/gui.md`](docs/gui.md)
A proper interface on top of everything above, with five tabs — New
Entry, Quick Lookup, Summary, Import (auto-detecting XRD/VSM/SEM, with
batch import), and a Data Viewer that displays XRD patterns, VSM
hysteresis loops, and SEM images directly in-app. Went through many
iterations (`alloy_desktop.py` → `_fixed` → `_fixed2` → `_fixed3` →
`_with_db_classes.py` → `_complete.py`) before stabilizing.

## 5. Problems & Dead Ends

The notable ones that didn't feed back into an existing component above
(full list of smaller issues is in each linked page):

- **AFLOW abandoned.** The `aflow` python package turned out unmaintained
  (last touched ~2017-2019), hit a live HTTP 404 suggesting its endpoint
  moved or died, and separately had a real bug (its keyword objects are
  mutable singletons — repeated `.filter()` calls on the same keyword
  silently corrupt earlier values instead of erroring). Combined with an
  unresolved AND/OR query-semantics ambiguity that couldn't be verified
  without a live server, this was cut rather than pushed through — a
  deliberate, correct call, not a failure.
- **Metabase login/container instability**, resolved in a separate
  troubleshooting session — turned out to be a stale-but-valid browser
  session cookie plus some Docker container/port confusion, not a real
  data-loss risk. Pure ops noise, not a project-design issue, but worth
  a line here since it consumed real time.
- **A regression I (the assistant) introduced and had to fix twice**: an
  edit meant to add the distance-cutoff feature to `stage_one/lookup/lookup_common_v1.py`
  accidentally deleted a function's signature while leaving its body
  behind as dead code, breaking deduplication for all three literature
  databases at once. It shipped because the fix was verified by testing
  the wrong function in isolation rather than the actual full call chain.
  Caught only because it was run for real. A useful reminder that
  "syntax parses" and "logic works" are different bars, and that testing
  the specific path that changed matters more than testing nearby code
  that happens to still parse.
- **A large `data/` folder ended up fully committed to git**, despite
  being listed in `.gitignore` — because the ignore rule was added
  *after* the files were already tracked, which `.gitignore` does nothing
  to undo. Caught before the repository went public for good, but only
  after it had briefly been public once already. Fixed with a full
  history rewrite (`git filter-repo`), not just a new commit removing the
  files (which would have left them recoverable from earlier commits).
  Full detail, including the exact commands used and verification steps,
  in [`docs/setup.md`](docs/setup.md).

## 6. Current Status

**Stage 1 is complete.** Working end-to-end, verified with real data:
- Core database, schema, and credential handling.
- Calculator (formula parsing, at%/wt%, pre-alloys, excess%, and a
  fixed-mass pre-alloy mode — solve for raw elements to add on top of a
  known amount of pre-alloy already on hand, see
  [`docs/calculator.md`](docs/calculator.md)).
- Screening (VEC/δ/ΔH_mix, full periodic table, graceful error on gaps).
- Three literature databases with dedup and adjustable cutoffs, wired into
  both the CLI tool and the GUI, including a retry (once, after 45s) for
  OQMD/Alexandria's transient 502/503/504 errors — the underlying
  `optimade` client's own retry only ever covers HTTP 429, confirmed by
  reading its source, not assumed. A "skip literature search" checkbox
  gives an instant screening-only preview when a provider is having a
  slow/erroring day.
- XRD, VSM, and SEM characterization import, with real extracted
  properties (peak count, lattice parameter, saturation moment, remanence,
  coercivity, magnification, accelerating voltage, working distance,
  pixel size) stored against real samples — 690 SEM files imported in
  practice.
- Desktop GUI (five tabs), covering the full new-entry → screen →
  cross-check → calculate → submit workflow, plus a Data Viewer for
  browsing XRD/VSM/SEM data directly. The XRD/VSM plots deliberately show
  only the raw data curve and numeric summaries now — the peak-marker and
  Hc/Mr guide-line overlays were removed rather than left in an
  approximate, potentially-misleading state; proper peak-fitting is a
  Stage 2 item.
- Data sorter utility, tested against the real messy desktop folder.

**CLI vs. GUI — resolved as a deliberate decision, not left as a gap:**
the CLI stays intentionally dialogue/text-only (fast, scriptable data
import and lookups from existing files), while the GUI is where anything
visual or exploratory happens. Not a temporary imbalance to fix later —
an actual design choice, made explicitly rather than by default.

**Remaining minor items, genuinely open:**
- Large characterization imports (e.g. batch SEM) would benefit from a
  visible progress indicator during the import itself (distinct from the
  literature-search progress indicator, which is fixed).

## 7. Next Steps (Stage 2)

Stage 2 is about shaping this data for ML, not adding new capture
capability:
- Element-fraction table, purpose-built for ML-style compositional queries.
- Proper peak fitting (e.g. via PowerXRD) and a broader feature-extraction
  pipeline, turning raw XRD/VSM curves into structured ML-ready features
  beyond what Stage 1 already extracts as single summary values — this is
  also where the removed plot guide-lines get done properly, not just
  restored.
- Patent-records table, once ML planning defines what's actually needed
  from it.
- Further out: actual ML model training, once the above data-preparation
  work is in place.

---

## Appendix

Verbatim reference commands, configs, and the schema migration SQL are
collected in [`docs/appendix_commands.md`](docs/appendix_commands.md).
