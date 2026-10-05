# Standalone Analyzer Tools

Two directly-usable, standalone tools for quick sample checking —
built on top of the same validated analysis logic used in the main
database pipeline, wrapped in a live, interactive GUI. Built in
customtkinter (matching the main app), so they can later share the
same process/database rather than living as disconnected tools. Both
have an explicit **Save to DB** button that writes only what the
operator has reviewed.

## XRD Analyzer (`xrd_analyzer_standalone.py`)

Load a `.xy` pattern directly and see the automatic peak-fitting result
(background subtraction, Kα2 stripping, R² fit quality, crystallite
size, d-spacing — the same validated pipeline used elsewhere in this
project). Adjust peak-finding sensitivity (prominence, distance,
anode, Kα2 stripping) and re-analyze live. Review each detected peak
individually and accept or reject it — rejecting a spurious/noisy peak
immediately updates the summary statistics (peak count, mean R² of the
accepted set), making it easy to spot and remove a bad fit.

## VSM Analyzer (`vsm_mh_analyzer_standalone.py`)

Load a full `.dat` file directly — handles real, multi-segment files
(e.g. a temperature series of several MH loops in one file), not just
a single pre-isolated loop. Automatically segments the file and lists
what was found (type, row range, self-centering events); select any
segment to see its plot (descending branch highlighted, Hc/Mr
crossings marked) and result. Adjust branch-detection sensitivity
(prominence, distance) and re-analyze live. Accept or reject each
segment's result as a whole. Each MH segment goes through the same
`vsm_pipeline.analyze_mh_segment()` used at import, so the tool and the
database import cannot give different numbers for the same settings.

**Tabs.** *MH loops* (above), *Temp. coefficients* (α(Hc) and β(Mr),
fitted live from the accepted segments only), *Entropy change* (ΔS_M
from all MH segments of the file, at editable integer target fields in
Oe; refuses files whose segments are full bipolar loops, and needs a
sample mass), and *MT candidates* (M extrema and |dM/dT| peaks per
temperature branch, unclassified and view-only, never saved). Clicking
an MT segment in the list opens its tab. If the file has no mass, enter
it in mg in the controls; it is used for BH_max and entropy change and is
stored on save with `mass_source = 'manual'`.

**BH_max (optional, cuboid samples).** Enter the density (g/cm³) and
the three full edge lengths in mm, with the edge **parallel to the
applied field as c**. The tool shows the Prozorov–Kogan factor (used
and saved, the lab's established practice) and the Aharoni factor for
the same geometry, with the BH_max each one gives, since Prozorov–Kogan
is derived for diamagnetic samples. Leave all four fields empty for
needle-shaped samples. A partly filled geometry is an error, not
"no BH_max".

**Save to DB.** The file must already have been imported through the
main app. Saving updates that import's records in one transaction:

- accepted MH segments get the re-analyzed Hc, Mr, temperature, field
  range and (with geometry) N and BH_max;
- every other MH segment is stored with NULL Hc/Mr/BH_max and a flag
  (the automatic one, or `operator_rejected`), so a rejected value never
  stays in the database looking valid;
- density and dimensions are stored on `vsm_files`; if they are already
  stored and the fields are empty, the tool fills them in and re-runs the
  analysis so the BH_max can be reviewed before saving;
- the file's temperature coefficients are refitted from the accepted
  segments only (removed if fewer than two temperatures are accepted);
- the entropy-change result shown in its tab replaces the one stored at
  import (`vsm_entropy_change`, plus `entropy_change_suitable/_reason` on
  `vsm_files`); a file that is not suitable is recorded as such;
- a hand-entered mass is stored on `vsm_files`.

Segments are matched to the stored ones by start/end row. If any MH
segment has no match (the file was imported with a different
segmentation), nothing is written.

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
