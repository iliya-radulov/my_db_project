# Desktop GUI (`alloy_desktop_complete.py`)

A `customtkinter`-based desktop application providing a full workflow on
top of every other component: formula entry → screening → literature
cross-check → mass calculation → database submission, plus browsing and
direct data visualization.

## Tabs

Per the app's own docstring: **New Entry | Import Files | Data Viewer |
Quick Lookup | Summary**.

1. **New Entry** — the main workflow described below.
2. **Import Files** — auto-detecting import for XRD/VSM/SEM files,
   dispatching to the appropriate parser (`stage_one/parsers/parse_xrd_v1.py`,
   `stage_one/parsers/parse_vsm_v1.py`, `stage_one/parsers/parse_sem_v1.py`)
   by file extension, with batch import support for large SEM folders
   (see [`characterization.md`](characterization.md)).
3. **Data Viewer** — displays the actual XRD pattern, VSM hysteresis loop,
   or SEM image for a selected characterization record, using
   `stage_one/tools/plot_v1.py` — a dedicated copy kept in Stage 1 so the
   stable app doesn't depend on anything inside `stage_two/`, which is
   under active development (see
   [`characterization.md`](characterization.md) for why this copy
   exists).
4. **Quick Lookup** — search existing samples.
5. **Summary** — aggregate stats (sample counts, class breakdown, recent
   samples).

## Iteration history

The GUI went through many named versions before stabilizing —
`alloy_desktop.py` → `_fixed.py` → `_fixed2.py` → `_fixed3.py` →
`_with_db_classes.py` → `_complete.py` — each fixing a real crash or
missing feature found by actually running it. This mirrors the project's
general pattern (build simplest version, use it, let the first real
failure define the next step) more visibly than any other component,
simply because a GUI surfaces integration problems (widget lifecycle,
state timing) that a script doesn't.

## Key features

- **Real-time formula validation** against the calculator's element
  table, before any calculation is attempted.
- **Dynamic material classes**, loaded from the database at startup
  (`SELECT class_name FROM material_classes`) rather than hardcoded —
  new classes can also be added on the fly from the entry form.
- **Auto-generated sample IDs**, based on formula + date + an
  incrementing suffix, checked against existing samples in the database.
- **Literature database selector + cutoff slider** (see
  [`literature_databases.md`](literature_databases.md) for the full
  design): radio buttons switch between Materials Project / OQMD /
  Alexandria in one shared results area; a slider sets that database's
  own distance cutoff. "Calculate & Preview" fetches all three databases
  once and caches results; switching the selector or dragging the slider
  afterward re-filters instantly from the cache, with no repeat network
  calls. Submission logs all three databases' results, each using its own
  last-set cutoff.
- **Summary tab**: total sample count, literature check count, breakdown
  by material class, most recent samples.
- **Fixed-mass pre-alloy mode**: an optional set of fields (pre-alloy
  formula, known mass, at% share of the final composition) that switches
  the main formula field's meaning from "complete target composition" to
  "raw elements being added on top of a pre-alloy you already have a
  fixed amount of" — solves for the total mass and the raw element
  masses, rather than requiring the total mass upfront. See
  [`calculator.md`](calculator.md) for the underlying math.
- **Skip literature search checkbox**: bypasses all three database
  lookups for an instant screening-and-mass-calc-only preview — added
  specifically to stay usable while OQMD or another provider is having a
  slow/erroring day, rather than waiting through retries every time.

## Bugs found by actually running it (not just reading the code)

Two real bugs were only caught by instantiating the GUI under a virtual
display and exercising it end-to-end, rather than by code review or
syntax checking alone:

1. **`generate_sample_id()` crash on DB failure.** The sample-ID prefix
   variable was only assigned *inside* the same `try` block as the
   database call, after it. If the database connection failed for any
   reason (Postgres not started yet, bad config), the exception handler's
   fallback path referenced a variable that had never been assigned,
   crashing with `UnboundLocalError` instead of degrading gracefully.
   Fixed by moving the prefix assignment before the `try` block. This
   would have crashed the entire app on startup, not just one feature,
   if Postgres happened to be down at launch.

2. **Silent `IncompleteElementDataError` propagation.** Before the
   screening fix (see [`screening.md`](screening.md)) was applied to the
   GUI specifically, an out-of-table element would have crashed the whole
   "Calculate & Preview" or "Submit" action rather than just skipping
   screening for that run. Fixed identically to the CLI tool: catch the
   specific exception, leave `vec`/`delta`/`delta_h_mix` as `None` for
   that submission, and continue.

Separately, earlier iterations hit a `_tkinter.TclError` from a bad
widget insert call and various `AttributeError`s from methods being
called before their owning widgets existed yet (a `status_label`
referenced before `setup_summary_tab()` had finished running) — resolved
by fixing initialization order across the app's `__init__` sequence.

3. **Matplotlib figures not closing with the main app.** No
   `WM_DELETE_WINDOW` handler existed at all, so closing the main window
   never triggered `plt.close('all')` — a plot opened in the Data Viewer
   could be left dangling after the app itself had closed. Fixed by
   binding `self.protocol("WM_DELETE_WINDOW", self.on_closing)` and
   verified directly: 1 figure open → simulated window close → 0 figures
   open.

4. **Literature search looked frozen, but wasn't.** A status label update
   (`"Checking Materials Project..."`, etc.) was already present before
   each blocking network call — but nothing forced Tkinter to actually
   repaint before the call ran, so the label change was invisible until
   everything had already finished. This wasn't a missing feature, it was
   a real bug: the "progress indicator" existed in code but never
   rendered. Fixed with `self.update_idletasks()` after each status
   change.

## Verification approach

Because a GUI can't be meaningfully checked by reading code or parsing
syntax alone, changes to this file were verified by actually
instantiating the app under a virtual framebuffer display (`Xvfb`) with a
fake/unreachable database, confirming both that construction succeeds
without a live Postgres connection (graceful degradation) and that the
specific new interactions (radio button switching moves the slider to
that database's remembered cutoff; dragging the slider re-filters and
re-renders live) behave as designed — not just that the file imports
without error.
