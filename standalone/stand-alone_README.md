# Stand-alone Analyzer Tools

Directly-usable, interactive tools — built on top of the same
validated analysis logic used in the main database pipeline, each with
an explicit "Save to DB" for the reviewed result.

These are copies of the files in `stage_two/tools/`, which is where they
must be run from: they import sibling modules (`vsm_pipeline.py`,
`xrd_analyzer_dev1.py`, ...) that are not in this folder.

- `xrd_analyzer_standalone.py` — XRD peak fitting, adjustable
  sensitivity, per-peak accept/reject.
- `vsm_mh_analyzer_standalone.py` — VSM analysis (tabs: MH loops, temperature
  coefficients, entropy change, MT candidates), automatic
  segmentation, adjustable branch-detection sensitivity, optional BH_max
  (density + dimensions, field edge as c), per-segment accept/reject.

```bash
pip install customtkinter
python3 xrd_analyzer_standalone.py
python3 vsm_mh_analyzer_standalone.py
```

Full description: [`docs/standalone_tools.md`](../docs/standalone_tools.md)
