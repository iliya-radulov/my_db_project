# Alloy Lab Database — Stage 2 Handoff

Moving to a new conversation mid-Stage-2 due to the image-sharing limit
in the current thread, not because Stage 2 is finished. Paste this
document at the start of the new conversation as the seed message.

## Project context (one-liner)

A materials-science database project (NdFeB/MnGa/recycled-magnet
research) with three stages: Stage 1 (complete — lab-book style
capture) → Stage 2 (in progress — validated characterization
pipelines + database integration + eventual ML feature prep) → Stage 3
(future — ML modeling). Repo structure: `stage_one/`, `stage_two/`,
`stage_three/` (placeholder), `stand-alone/` (interactive tools),
`docs/` (shared documentation), with `db_config.py`/`.env` shared at
the true root.

## Stage 2 status — what's done

**XRD — complete.** Full analysis pipeline (background subtraction,
Kα2 stripping, peak fitting, R² quality, Scherrer size, d-spacing,
doublet detection), validated against a certified reference standard
(NIST LaB6). Database schema + real production integration tested
end-to-end against real samples. Standalone interactive tool built and
tested (`xrd_analyzer_standalone.py`).

**VSM — complete.** Full pipeline (instrument detection, mass
extraction, segmentation, Hc/Mr, temperature coefficients, entropy
change/ΔSm, demagnetizing correction + BHmax). Database schema + real
production integration tested end-to-end, catching and fixing several
real bugs along the way. Standalone interactive tool built and tested
(`vsm_mh_analyzer_standalone.py`).

**SEM — real progress, in progress.**
- Grain-detection module validated on 16 real images.
- Unified metadata parser built and validated across three real
  instrument formats (Zeiss, JEOL, Tescan) — different proprietary
  metadata conventions, all reconciled into one interface
  (`sem_metadata_universal.py`).
- Phase-fraction analysis: found that simple automatic thresholding
  fails in different, real ways depending on the sample (confirmed:
  one "failure" was actually genuine physical structure, not an
  artifact — confirmed via a second imaging technique). Resulted in a
  deliberate design decision: automate what's reliably automatable
  (loading, calibration, footer cropping), keep phase judgment in the
  operator's hands via a live threshold tool
  (`sem_phase_fraction_standalone.py`).
- Not yet done: SEM database integration, re-testing the grain-detector
  against real 16-bit Tescan data, using the phase-fraction tool on
  real samples to see if the approach holds up in practice.

**Cross-cutting work done:**
- Element-fraction table: real atomic-percent backfill + wide-format
  reshaping built and validated, automatic wiring deliberately deferred
  to end-of-Stage-2.
- Project reorganization (stage folders, shared config) completed.
- Stage 2 progress presentation built for a colleague review in Munich.

## Immediate task: safe file cleanup

Hitting the image-sharing limit in the old conversation — need to
review and likely delete a batch of images/files to keep working
there, or fully move to this new conversation instead. Needs care:
distinguish files that are still real, validated deliverables from
files that were exploratory/superseded along the way.

**Likely safe to keep / still needed** (validated, delivered modules —
should already be in the real repo under `stage_two/`):
- XRD: `xrd_analyzer_dev1.py`, `xrd_features_builder.py`,
  `xrd_integration_v2.py`, `002_xrd_peaks_and_features.sql`,
  `xrd_analyzer_standalone.py`
- VSM: `vsm_pipeline.py`, `vsm_segmenter.py`, `vsm_type_detector.py`,
  `vsm_mass_extractor.py`, `vsm_quality_flags.py`, `vsm_mh_features.py`,
  `vsm_mt_features.py`, `vsm_temp_coefficient.py`,
  `vsm_entropy_change.py`, `vsm_entropy_integration.py`,
  `vsm_demag_correction.py`, `vsm_bhmax.py`, `vsm_db_builder.py`,
  `vsm_integration_v2.py`, `db_type_utils.py`,
  `003_vsm_tables.sql`, `004_vsm_entropy_change.sql`,
  `005_vsm_bhmax.sql`, `vsm_mh_analyzer_standalone.py`
- SEM: `sem_grain_analyzer.py`, `sem_metadata_universal.py`,
  `sem_phase_fraction.py`, `sem_phase_fraction_standalone.py`
- Database/element-fraction: `compute_atomic_percent.py`,
  `element_fraction_table.py`
- Documentation: `standalone_tools.md`, session summary files (useful
  history, low priority to keep all of them)

**Likely safe to clean up** (exploratory/one-off, not deliverables):
- Synthetic test files generated purely for GUI-mechanics testing
  (e.g. throwaway `.xy`/`.dat` test patterns) — real project data, not
  these.
- Intermediate/debug images generated during investigation (edge-check
  overlays, threshold-comparison PNGs) — useful at the time, not
  needed going forward unless specifically referenced again.
- Old superseded module versions if any duplicates exist on disk.

**Genuinely uncertain, worth checking before deleting**: the real SEM
images uploaded for phase-fraction work (Zeiss/JEOL/Tescan samples,
including sidecar `.txt`/`.hdr` files) — these are real data, not
throwaway, and may still be needed for further SEM work.

## Open items carried into the new conversation
- SEM database integration.
- Grain-detector re-test on real Tescan 16-bit data.
- Phase-fraction tool tested on real samples in practice.
- Element-fraction table automatic wiring — end-of-Stage-2.
- Inventory table — end-of-Stage-2.
- Lakeshore VSM / Metis magnetometer — not started, lower priority.
- Kerr microscopy / EBSD — deliberately parked, future topics.
- Final BH_max cross-check against a trusted reference number, once
  available.
