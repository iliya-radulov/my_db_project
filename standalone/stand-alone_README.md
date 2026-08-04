# Stand-alone Analyzer Tools

Directly-usable, interactive quick-check tools — built on top of the
same validated analysis logic used in the main database pipeline.
No database saving; view-only checking.

- `xrd_analyzer_standalone.py` — XRD peak fitting, adjustable
  sensitivity, per-peak accept/reject.
- `vsm_mh_analyzer_standalone.py` — VSM Hc/Mr analysis, automatic
  segmentation, adjustable branch-detection sensitivity, per-segment
  accept/reject.

```bash
pip install customtkinter
python3 xrd_analyzer_standalone.py
python3 vsm_mh_analyzer_standalone.py
```

Full description: [`docs/standalone_tools.md`](../docs/standalone_tools.md)
