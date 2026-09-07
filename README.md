# Alloy Lab Database — Stage 1 & Stage 2

A personal experimental database for alloy research: store samples, synthesis
conditions, and characterization results in a structured, queryable way,
cross-check every new composition against public materials databases, and
build toward using all of it as training data for ML models that predict
whether a novel composition is known — and if not, how to try synthesizing it.

This document is the narrative overview. Detailed technical write-ups for
each component live in [`docs/`](docs/). For a more detailed statement of
the principles behind how AI/ML is used in this project, see
[`MANIFESTO.md`](MANIFESTO.md).

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

## 4. Decisions & Implementation — Stage 1 (condensed)

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

## 5. Problems & Dead Ends — Stage 1

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
- **A regression introduced and fixed twice**: an edit meant to add the
  distance-cutoff feature to `stage_one/lookup/lookup_common_v1.py`
  accidentally deleted a function's signature while leaving its body
  behind as dead code, breaking deduplication for all three literature
  databases at once. It shipped because the fix was verified by testing
  the wrong function in isolation rather than the actual full call chain.
  Caught only because it was run for real. A useful reminder that
  "syntax parses" and "logic works" are different bars, and that testing
  the specific path that changed matters more than testing nearby code
  that happens to still parse.

---

## 6. Stage 2 — The Characterisation Layer

Stage 2 transformed the lab-book foundation into a validated research
platform. Every instrument pipeline was built on real data, not synthetic
tests. The schema was designed for machine learning. The infrastructure
was migrated to a dedicated home server shared by all machines.

**Stage 2 is complete** as of September 2026.

### 6.1 XRD Pipeline

`stage_two/tools/xrd_analyzer_dev1.py` — a general-purpose peak-fitting
pipeline, validated against NIST SRM 660c (LaB₆ certified reference
material). Lattice parameter converges to within 0.0001 Å of the certified
value.

- Background subtraction and Rachinger Kα2 stripping (Cu anode, default-on)
- Neighbour-aware peak fitting — each peak's fit window uses local context,
  not isolated regions; fixed a duplicate-peak bug present in the naive approach
- R² fit-quality metric per peak — low-quality fits flagged, never silently
  averaged into summary statistics
- Scherrer crystallite size and d-spacing extracted automatically
- Results in two tables: `xrd_peaks` (long format, one row per peak) and
  `xrd_features` (wide format, ML-ready, one row per sample)
- Standalone interactive tool (`xrd_analyzer_standalone.py`): live
  sensitivity controls, per-peak accept/reject, Save to DB
- Integration (`xrd_integration_v2.py`) tested end-to-end against real
  production database with real samples

### 6.2 VSM Pipeline

A full multi-component pipeline replacing the Stage 1 single-value parser.

- Instrument auto-detection (PPMS VSM / MPMS3 / ACMS) — each instrument
  type uses different column conventions; detection is by diagnostic column
  name, not raw column count (confirmed unreliable across versions)
- Mass extraction from file header (primary, confirmed reliable on real
  data) or filename (fallback, returned with a confidence flag)
- Automatic segmentation into MH loops / MT scans / idle / corrupted
  segments, using a rolling-window local-range classifier — not naive
  point-to-point derivatives, which fail near H=0 and during instrument
  self-centering events
- Second-quadrant Hc/Mr extraction via crossing-point interpolation on the
  descending branch specifically — confirmed on real data that whole-loop
  analysis gives wrong results when an initial settling excursion is present
- Temperature coefficients α(Hc) and β(Mr) fitted when multiple loops at
  different fixed temperatures exist in one file
- Isothermal entropy change ΔSm via Maxwell relation, with a check that
  the input is genuinely a set of single-direction isothermal sweeps, not
  full bipolar loops (the two look structurally similar but are not
  interchangeable inputs for the calculation)
- Demagnetising correction and BHmax for cuboid samples
  (Prozorov-Kogan formula, validated against a real worked example)
- 6-table schema: `vsm_files`, `vsm_segments`, `vsm_mh_details`,
  `vsm_mt_details`, `vsm_mt_candidates`, `vsm_temperature_coefficients`
- Standalone interactive tool (`vsm_mh_analyzer_standalone.py`):
  multi-segment, adjustable branch-detection sensitivity, per-segment
  accept/reject, Save to DB
- Three real bugs found and fixed during end-to-end integration testing,
  including a NaN-masking issue that silently hid a 60 K temperature jump

### 6.3 SEM Pipeline

Three manufacturers, three completely different metadata conventions —
unified into one schema, auto-detected per file.

- **Zeiss**: proprietary compressed binary TIFF tags (34118/34119) —
  wraps the Stage 1 Zeiss parser, with regex-based unit extraction added
  (raw values come back as embedded strings like `'25.00 K X'`)
- **JEOL**: sidecar `.txt` file, `$KEY value` format — confirmed directly
  on real files; calibration from `$$SM_MICRON_BAR`/`$$SM_MICRON_MARKER`;
  footer height from `$CM_FULL_SIZE` vs actual TIFF height, no
  brightness-heuristic guessing needed
- **Tescan**: sidecar `.hdr` file, standard INI format — `PixelSizeX`
  directly in metres, the most direct calibration of the three; 16-bit
  image data handled throughout
- Missing-sidecar case returns `format='unknown'` rather than guessing —
  confirmed to occur on real JEOL files uploaded without their sidecar
- Phase fraction via Otsu thresholding — offered as a starting suggestion
  only, not forced: confirmed on real data that global thresholding fails
  in different ways depending on the sample and imaging mode. A key
  finding during development: what appeared to be a texture artifact on a
  Tescan image was confirmed via Kerr microscopy to be real magnetic domain
  contrast — the algorithm was detecting the right thing, but for the wrong
  physical purpose. The tool puts the threshold decision in the operator's
  hands
- Grain-detection module (`sem_grain_analyzer.py`) with adaptive per-image
  Canny thresholds, validated on 16 real images across formats; correctly
  flagged 2 deliberately low-quality test images as unreliable rather than
  forcing a confident wrong answer
- Tescan 16-bit support: `sem_grain_analyzer.py` updated to use
  `sem_metadata_universal` internally, and `parse_pixel_size()` extended
  to handle both float (universal parser) and string (`'11.09 nm'`, Zeiss
  parser) inputs
- Standalone interactive tool (`sem_phase_fraction_standalone.py`): live
  threshold slider, Otsu suggestion, optional invert, calibrated area
  readout in µm², Save to DB

### 6.4 Element-Fraction Auto-Wiring

- `compositions` table extended with `composition_type` column:
  `'aimed'` (nominal, set at sample creation) / `'measured'` (EDX/ICP
  result) / `'reference'` (literature data added manually)
- `add_compositions()` method added to `alloy_db_v2.py`: called
  automatically after every new sample entry, stores both wt% and at%
  from the calculator's output — no separate computation needed, the mass
  calculator already has both
- Backfill script (`compute_atomic_percent.py`, inline) used to populate
  `atomic_percent` for the three samples entered before this was wired in,
  using IUPAC atomic weights from `alloy_calculator_v2.ATOMIC_WEIGHTS`
- `element_fraction_table.py`: wide-format reshaping for ML consumption —
  one row per sample, one column per element, zero-filled for absent elements

### 6.5 Synthesis Route Auto-Save

- Screening module (`alloy_screening_v2.py`) already computed
  `synthesis_feasibility` with `suggested_routes` — this information was
  previously display-only
- Now auto-saved to the `synthesis` table after every new sample entry,
  one row per suggested route, with the full screening reasoning (status
  + message) stored in the `notes` column
- Means a researcher picking up a sample months later can see immediately
  why a particular route was suggested (or blocked) and what the physical
  reasoning was, without re-running the screener

### 6.6 Infrastructure — Database Migration to Home Server

On 3 September 2026, the database was migrated from a local Docker
container on the development Mac to a dedicated home server
(`192.168.2.42`). Migration: `pg_dump` (compressed format) → `scp` →
`pg_restore`. One session, zero data loss.

- **Home server**: AMD FX-4320, Ubuntu Server 26.04, Docker Engine,
  `postgres:17` container with persistent volume at `~/docker/postgres/data`
- **Wake-on-LAN**: NIC supports magic packet (`wol g`); systemd service
  persists the setting across reboots; BIOS `Power On By PCI-E/PCI`
  enabled. Server wakes from cold poweroff in ~60 seconds via
  `wakeonlan 2c:56:dc:74:c4:ff`
- **Remote access**: `pg_hba.conf` allows `192.168.2.0/24`; `listen_addresses = '*'`
  in `postgresql.conf`
- **All machines updated**: `.env` changed to `POSTGRES_HOST=192.168.2.42`
  on Mac and ML Desktop. SSH installed on ML Desktop during this session
- **`path_repair.py`**: scans `characterization.file_path` and
  `vsm_files.file_path` for broken paths, auto-searches by filename under
  a given root, handles ambiguous matches interactively. Run post-migration:
  zero broken paths

Post-migration database state: 50 samples, 16 tables, 170 XRD peaks,
92 characterization records, 4 synthesis route records.

### 6.7 Data Viewer — Standalone Tool Integration

All three standalone tools now launch from the Data Viewer with the
current file pre-loaded and auto-analysed:

- `plot_xrd()` and `plot_vsm()` updated to accept a `master` tkinter
  frame, embedding canvas + launch button directly — same pattern as the
  existing SEM viewer
- **📐 Analyze XRD** → `xrd_analyzer_standalone.py` (pre-loaded, auto-analyzed)
- **📊 Analyze VSM** → `vsm_mh_analyzer_standalone.py` (pre-loaded, auto-analyzed)
- **📊 Phase Fraction** → `sem_phase_fraction_standalone.py` (pre-loaded)
- Fixed a bug where the child-clearing loop in the plot functions was
  destroying `viewer_plot_label`, causing the Data Viewer to break after
  the first plot was loaded

### 6.8 Codebase Cleanup

- `stage_one/outdated/` and `stage_two/outdated/` removed entirely —
  dozens of intermediate development versions (`parse_vsm_fixed3.py`,
  `alloy_desktop_fixed2.py`, etc.). All history preserved in git
- Old PyQt5 SEM tool (`sem_analyzer_gui_v6.py`) retired and removed
- `vsm_entropy_integration.py` copied to `stage_two/tools/` to resolve
  a `ModuleNotFoundError` when VSM standalone was launched as a subprocess

## 7. Problems & Dead Ends — Stage 2

- **`parse_sem_v2` import failures as subprocess**: when standalone tools
  are launched via `subprocess.Popen`, Python's `sys.path` doesn't
  include the project's `parsers/` directory. Fixed with `sys.path.insert`
  using `pathlib.Path(__file__).resolve().parent` in each affected module.
- **`viewer_plot_label` destroyed by plot functions**: the child-clearing
  loop inside `plot_xrd`/`plot_vsm`/`plot_sem` was destroying all widgets
  in the frame including the error-display label the app needed for
  subsequent "file not found" messages. Removed — the app already clears
  the frame before calling the plot functions.
- **XRD Save to DB — `sample_id` NULL**: `characterization.sample_id` was
  NULL for existing records (imported before the FK was fully wired).
  Fixed by prompting the operator for the sample ID string at save time,
  then looking up the integer PK from the `samples` table.
- **Tescan `pixel_size_nm` None despite correct metadata**: `parse_pixel_size()`
  used a regex expecting a string like `'11.09 nm'`, but
  `sem_metadata_universal` returns a plain float. Fixed by checking the
  type before regex extraction.
- **Synthesis routes not auto-saving**: `screening.get('suggested_routes')`
  was wrong — `suggested_routes` is nested inside
  `screening['synthesis_feasibility']`. Fixed by extracting `_synth` first.
- **pptxgenjs 8-digit hex colors**: `'FFFFFF99'` (hex + alpha) is not
  supported and silently produces black. Fixed by using a plain 6-digit
  equivalent.
- **Docker schema — tables "not found"**: `\dt` in `psql` searched the
  `public` schema by default; all tables live in the `alloy_lab` schema.
  Fixed by using `\dt alloy_lab.*`.

## 8. Current Status

**Stage 1: complete.**
**Stage 2: complete** as of September 2026.

Working end-to-end, verified with real data:
- Three validated characterisation pipelines: XRD (NIST reference),
  VSM (three instrument types, 3 real bugs caught in integration),
  SEM (Zeiss/JEOL/Tescan, 16-bit support)
- 16-table schema: all populated with real data
- Standalone interactive tools for all three techniques, with Save to DB
- Element-fraction auto-wiring (wt% + at% on every new sample entry)
- Synthesis route auto-save from screening results
- Database migrated to home server; three machines connected
- `path_repair.py` for broken-path recovery after file moves

## 9. Next Steps — Stage 3 (ML)

Stage 3 is about closing the loop: composition → measurement → prediction
→ new composition recommendation.

**Feature matrix (X):**
- `compositions` — element fractions wt% + at%, all samples
- `xrd_features` — n_peaks, mean R², crystallite size, d-spacing
- `vsm_mh_details` — Hc, Mr, BHmax per segment
- `vsm_temperature_coefficients` — α(Hc), β(Mr)
- `properties` — SEM phase fraction

**Target properties (y):**
- Magnetic: Hc, Mr, BHmax
- Thermal stability: α, β temperature coefficients
- Structural: phase fraction, crystallite size

**Planned ML workflow:**
1. Assemble feature matrix from existing DB tables via
   `element_fraction_table.py` + joins
2. Start with Gaussian Process regression (appropriate for small datasets)
3. Move to neural networks as data volume grows
4. Prediction → new composition recommendation → back into calculator →
   new sample → new measurements → back into DB

**Infrastructure:**
- ML Desktop: Ryzen 9900X, RTX 5060 Ti 16 GB, Ubuntu 26.04, CUDA 13.2
- Database: home server `192.168.2.42`, always-on, wake-on-LAN
- All machines read/write the same canonical database

---

## Appendix

Verbatim reference commands, configs, and the schema migration SQL are
collected in [`docs/appendix_commands.md`](docs/appendix_commands.md).
