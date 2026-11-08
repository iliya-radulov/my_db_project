# Track B Checklist — Literature Data Layer
## Working rule

> Every change to sources or cleaning rules creates a new named snapshot.
> All modelling and evaluation must point at a named snapshot.
*(updated 8 November 2026)*

## Priority 1 — Freeze the current state  (DONE, 7 Nov)

- [x] Re-run `import_nims.py` and confirm it still reports 1 113 records / 1 539 points
- [x] Run `link_samples.py` (7 exact matches, 29 placeholder skips)
- [x] Run `consistency_report.py` (0 collisions)
- [x] Run the section-4b query from `SERVER_SETUP.md` (bracket compositions); 1 expected pre-alloy Fe2P entry
- [x] Write and commit a short "Literature snapshot v1" note containing:
  - [x] date
  - [x] exact row counts per source
  - [x] quality-flag summary
  - [x] statement that this snapshot is frozen for modelling
- [x] Extra: full LaTeX report with ER diagram (`SNAPSHOT_v1.tex` / `.pdf`)

## Priority 2 — Add the already-planned extra sources  (DONE, 8 Nov)

- [x] Download / clone:
  - [x] MCEdatabase (GitHub)
  - [x] Kelly & Cole Curie/Néel (figshare)
  - [x] Court & Cole set
- [x] Run each import with `--dry-run` first
- [x] Run the real imports (202 / 100 / 80 records)
- [x] Re-run `consistency_report.py` (4 sources, 127 shared keys, agreement 64-90%)
- [x] Update the snapshot note with the new totals (`SNAPSHOT_v2.md`)

## Priority 3 — Make the data modelling-ready

- [ ] Decide and document the hydride policy (keep / flag / exclude) in one place
- [ ] Change the evaluation scripts so the test set defaults to EDX compositions (keep a flag for nominal if needed)
- [ ] Run one clean evaluation on the frozen snapshot (v2, train on NIMS only):
  - [ ] paper-holdout
  - [ ] family-holdout
  - [ ] targets: Tc and/or |ΔS|
- [ ] Record the exact command lines and the resulting MAE tables

## Priority 4 — Later / optional

- [ ] Further refinement of `correct.py`
- [ ] Any new author datasets that arrive
- [ ] Metabase or other visualisation layers

## Future datasets (received, not imported)

- [x] Heusler CSVs inspected: calculation notebooks / descriptors, not needed now
- [x] Extract tables from `SupplementaryMaterial_TablesS1_S8.docx` (S1-S8 + references to CSV, 8 Nov)
- [x] PDF `1-s2.0-S0079642517301299-mmc1.pdf` confirmed to be the same supplement as the .docx
- [ ] Verify PDF/docx overlap row by row (currently first-column string match only)
- [ ] Cross-check S2 (La(Fe,Si)13, 189 rows) against NIMS / MCEdatabase Tc
- [ ] Decide schema extension for Heusler (S6, 313 rows) and other families; new snapshot v3
- [ ] Parse multi-value field/entropy cells; resolve `[n]` refs to DOIs
- [ ] Record Victorino and Dr. Ucar permissions in the repo
- [ ] Open `magneticmaterialsdatabase.zip` and assess
- [ ] ORCHID sub-datasets (Values, Hulls, Parity): explore for later-stage funnel approach
