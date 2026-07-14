# Characterization Data Import

Getting real instrument output — not just calculator/screening results —
into the database as structured, queryable properties.

## Data sorter (`stage_one/tools/sort_data_swamp_v2_v1.py`)

A standalone utility, independent of the database, that organizes a messy
research folder into type-based subfolders. Detection works by file
extension first (`.raw`/`.xy`/`.xrdml` → XRD, `.tif`/`.tiff`/`.hdr` → SEM,
`.dat` → magnetic measurement data, etc.), falling back to parent-folder
name matching, and — for ambiguous `.csv` files — to sniffing the first
line of file content (e.g. `"AV Pyro top"` or `"Nr.;Datum;Zeit"` indicates
process/deformation data; `"Element"` + `"wt%"` indicates ICP-OES data).
Also attempts sample-ID detection from filename patterns (e.g. `RP1a` →
sample `RP1`, `0107.raw` → sample `0107`).

Run for real against the actual multi-year messy desktop research folder
and correctly routed hundreds of files — XRD raw data, ICP spreadsheets,
Origin project files, presentations and drafts — into organized
subfolders in a single pass. This was as much a personal motivation for
the whole project as the database itself.

## XRD (`stage_one/integrations/xrd_integration_v1.py`, `stage_one/parsers/parse_xrd_v1.py` — pre-reorg name `parse_xy_v2.py`)

**Parser**: reads `.xy` files (2θ / intensity columns) directly — no
external XRD library used.

**Peak detection: try → result → next.** First version found only 1 peak
on a real pattern that clearly has many — a bug in the detection
threshold/logic. Fixed to correctly find the expected order of magnitude
(96-102 peaks on the real test samples).

**Lattice parameter**: computed from N matched reflections (`a`, in Å,
with a standard deviation across the matched peaks where available).

**A real integration bug**: `lattice_parameter_a` was originally inserted
into Postgres via a query that let a Python `numpy.float64` value's
`repr()` leak literally into the SQL text, rather than being passed as a
proper parameterized value — producing the error `schema "np" does not
exist` (Postgres tried to parse `np.float64(15.62...)` as SQL, reading
`np` as a schema name). Fixed by properly parameterizing the value
(casting to a native Python `float` before binding). Real results after
the fix, for reference: RP1a — 101 peaks, a = 15.627 Å; RP2a — 96 peaks,
a = 15.630 Å; RP3a — 98 peaks, a = 15.744 Å.

**Stored properties**: `n_peaks`, `lattice_parameter_a` (Å), linked to an
`'XRD'` characterization row per sample.

## VSM (`parse_vsm.py` → `_fixed` → `_fixed2` → `_clean`, `stage_one/integrations/vsm_integration_v1.py`)

**Tried:** the `magnetopy` library for parsing VSM `.dat` files.

**Result:** `ImportError: cannot import name 'VSM' from 'magnetopy'`,
across multiple attempted import paths (`magnetopy.magnetopy`,
`magnetopy.measurement`) — the library's actual API didn't match what was
expected from its top-level name.

**Then:** abandoned the library, wrote a custom parser directly against
the raw CSV-style `.dat` export (PPMS/VSM instrument format — columns
include field, moment, temperature, and dozens of instrument-status
fields not needed here). Extracts saturation moment (Ms), remanence (Mr),
and coercivity (Hc) from the M-H loop.

**A genuine data-quality catch, not just a code bug**: the file's own
`"Mass (grams)"` column reported an implausible value (56 g — far too
heavy for the actual sample), which silently produced a nonsensical
normalized Ms/gram (0.12 emu/g). The real sample mass turned out to be
encoded only in the filename, by lab convention (e.g.
`..._50mg.dat`). Fixed by parsing mass from the filename instead of
trusting the instrument's own recorded value, which corrected the
normalized result to a physically sensible 137.65 emu/g — a reminder that
an instrument's own metadata field isn't automatically trustworthy just
because it looks structured.

**Stored properties**: `saturation_moment` (emu), `remanence` (emu),
`coercivity` (Oe), `saturation_moment_per_g` (emu/g), linked to a
`'VSM'` characterization row per sample.

## VSM refinement, late in the project

After the initial `parse_vsm.py`/`_fixed`/`_fixed2`/`_clean` sequence (see
above), the parser was revised once more (`stage_one/parsers/parse_vsm_v1.py`) to
handle both PPMS header format variants encountered in practice, and
deliberately narrowed to extract only four columns — Temperature, Field,
Moment, Error — dropping everything else the instrument export includes.
Confirmed reading 1447 data points correctly on a real file. A small,
late refinement, but consistent with the project's general pattern:
simplicity earned through direct contact with real files, not assumed
upfront.

## SEM (`parse_sem.py` → `_v2` → `_v3` → `parse_sem_fast.py`, now `stage_one/parsers/parse_sem_v1.py`; DB integration in `stage_one/integrations/sem_integration_v1.py`)

**Tried:** a straightforward TIFF-tag reader (Pillow's standard
`img.tag_v2`), the same approach that worked fine for basic image
dimensions.

**Result:** every SEM-specific field came back `None` — magnification,
voltage, working distance, detector, everything. The instrument
(Zeiss SEM) stores its actual metadata inside two proprietary,
**compressed binary tags** (34118 and 34119), not as plain TIFF fields a
standard reader recognizes.

**Then:** wrote a binary string-extraction routine
(`extract_strings_from_bytes`) to pull readable text directly out of the
compressed tag payloads, then pattern-matched the specific Zeiss field
names (`AP_MAG`, `AP_ACTUALKV`, `AP_WD`, `DP_DETECTOR_CHANNEL`,
`AP_PIXEL_SIZE`, `AP_DATE`, `SV_OPERATOR`, `SV_SAMPLE_ID`, etc.) out of
the extracted strings. Real example, for reference:

| Parameter | Value |
|---|---|
| Magnification | 1.00 KX |
| EHT (accelerating voltage) | 10.00 kV |
| Working distance | 7.1 mm |
| Pixel size | 277.3 nm |
| Detector | SE2 / InLens |
| Image size | 1024 × 768 |

**Stored properties**: `magnification` (X), `eht_voltage` (kV),
`working_distance` (mm), `pixel_size` (nm) — numeric values extracted
from the parsed strings via regex, stored with `confidence_score = 0.9`.
The full metadata (including detector/signal channels, date, operator,
sample ID as recorded by the instrument) is kept as-is in the
`characterization.parameters` JSONB field, not discarded, even though
only a subset became first-class numeric properties.

**A practical, non-parsing problem: import speed.** Importing all 690 SEM
files one at a time (~0.5–1 second each) worked, but took 5–10 minutes —
long enough to be a real annoyance. Solved with batch import
(`import_sem_files()`, 10–20 files per batch) rather than any change to
the parser itself — a reminder that not every rough edge is a parsing bug;
some are just throughput problems with a throughput solution.

## Unified plotting and the Data Viewer

The unified plotting module (`plot_xrd()`, `plot_vsm()`, `plot_sem()` behind
one dispatch point, chosen by file extension or `char_type`) was built
during Stage 1 (as `plot_xrd_v4.py`) to power the desktop app's **Data
Viewer** tab. During the post-Stage-1 reorganization, this file
conceptually moved to `stage_two/tools/plot_xrd_v2.py`, since ongoing
plotting/analysis tooling work is considered Stage 2 scope.

To keep `alloy_desktop_complete.py` (the stable Stage 1 app) from
depending on anything inside `stage_two/` — which will keep changing as
Stage 2 work progresses — a dedicated copy was kept at
`stage_one/tools/plot_v1.py`, and the Stage 1 app imports from there
instead. `stage_two/tools/plot_xrd_v2.py` is free to diverge from this
copy as Stage 2 tooling develops; they are deliberately no longer the
same file.

The dispatch functions display the XRD pattern, VSM hysteresis loop, and
SEM images (with key metadata overlaid as a text box) directly in-app,
without leaving the GUI. See [`gui.md`](gui.md) for the app's full tab
structure.

**Update:** the XRD peak-position marker lines and the VSM Hc/Mr dashed
guide lines were deliberately removed from `stage_one/tools/plot_v1.py`
after real use showed they weren't trustworthy at this stage — worth
building properly (with real peak-fitting, e.g. via PowerXRD) in Stage 2
rather than leaving an approximate, potentially-misleading overlay in
place in the meantime. The underlying data curve, axis crosshairs, and
the numeric Ms/Mr/Hc/peak-count summary box are unaffected and still
shown — only the derived-and-possibly-wrong graphical overlays were cut.

## Common infrastructure note

`stage_one/integrations/xrd_integration_v1.py`, `stage_one/integrations/vsm_integration_v1.py`, and the SEM import functions
all write into the same `characterization` → `properties` schema (see
[`database_schema.md`](database_schema.md)) — a new characterization row
per file, with one or more property rows hanging off it, regardless of
instrument type. A minor known rough edge: repeated plotting in one
session can trigger matplotlib's "more than 20 figures open" warning,
since figures aren't explicitly closed between calls — harmless but
worth cleaning up.
