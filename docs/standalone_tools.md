# Standalone Analyzer Tools

Two directly-usable, standalone tools for quick sample checking —
built on top of the same validated analysis logic used in the main
database pipeline, wrapped in a live, interactive GUI. Built in
customtkinter (matching the main app), so they can later share the
same process/database rather than living as disconnected tools. No
database saving in either — quick-check only, by design.

## XRD Analyzer (`xrd_analyzer_standalone.py`)

Load a `.xy` pattern directly and see the automatic peak-fitting result
(background subtraction, Kα2 stripping, R² fit quality, crystallite
size, d-spacing — the same validated pipeline used elsewhere in this
project). Adjust peak-finding sensitivity (prominence, distance,
anode, Kα2 stripping) and re-analyze live. Review each detected peak
individually and accept or reject it — rejecting a spurious/noisy peak
immediately updates the summary statistics (peak count, mean R² of the
accepted set), making it easy to spot and remove a bad fit.

## VSM MH Analyzer (`vsm_mh_analyzer_standalone.py`)

Load a full `.dat` file directly — handles real, multi-segment files
(e.g. a temperature series of several MH loops in one file), not just
a single pre-isolated loop. Automatically segments the file and lists
what was found (type, row range, self-centering events); select any
segment to see its plot (descending branch highlighted, Hc/Mr
crossings marked) and result. Adjust branch-detection sensitivity
(prominence, distance) and re-analyze live. Accept or reject each
segment's result as a whole.

No manual point-clicking to override where Hc/Mr is read: once a
branch is correctly identified, the crossing point itself is exact
linear interpolation — nothing for a click to meaningfully improve.
What can go wrong is which branch gets selected, which the sensitivity
controls address directly; if a result still looks wrong after that,
it's better handled with a separate manual recalculation than a false
sense of precision from clicking a point.

## Running either tool

```bash
pip install customtkinter
python3 xrd_analyzer_standalone.py
python3 vsm_mh_analyzer_standalone.py
```
