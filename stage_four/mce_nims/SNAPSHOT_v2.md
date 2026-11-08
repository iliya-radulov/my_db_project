# Literature Snapshot v2

**Date:** 8 November 2026
**Added since v1:** MCEdatabase, Kelly & Cole 2025, Court & Cole 2018
**Status:** frozen for modelling. Any change to sources or cleaning rules creates v3.

## Counts per source

| Source | Records | Papers | Keys | With Tc | Points |
|---|---|---|---|---|---|
| nims_lafesi_1_13 | 1,113 | 221 | 660 | 979 | 1,539 |
| mcedb_github | 202 | 106 | 150 | 117 | 156 |
| curie_neel_kelly_cole_2025 | 100 | 52 | 44 | 100 | 0 (Tc only) |
| curie_neel_court_cole_2018 | 80 | 22 | 44 | 80 | 0 (Tc only) |
| **Total** | **1,495** | **~400** | **127 shared, ~600 unique** | | **1,695** |

## New composition coverage
- MCEdatabase: 51 keys new to the database
- Kelly & Cole: 10 new keys
- Court & Cole: 5 new keys

## Cross-source Tc agreement (same paper + same composition key)

| Pair | Pairs | Within 2 K |
|---|---|---|
| NIMS <-> MCEdatabase | 53 | 79% |
| NIMS <-> Court & Cole | 33 | 79% |
| NIMS <-> Kelly & Cole | 25 | 64% |
| Court & Cole <-> Kelly & Cole | 20 | 70% |

## Licences / permissions
- NIMS: CC BY 4.0 (doi:10.48505/nims.4909)
- Kelly & Cole 2025 (figshare 29559686), Court & Cole 2018 (figshare c.3954418): CC BY 4.0
- MCEdatabase: reuse with citation confirmed by Bolin Lau (Xuchao), MCEdatabase group; records flagged `quality_flag='unverified'` (LLM-extracted)

## Decision (unchanged from v1)
Train on NIMS only. The additional sources are retained as provenance and may serve as independent held-out validation.

## Data received but NOT imported (future scope, not La(Fe,Si)13)

Location: `stage_four/mce_nims/data/` (gitignored, third-party data).

### Franco et al. 2017 supplement (Tables S1-S8), used with permission from Victorino and Dr. Ucar
Source: Franco, Blazquez, Ipus, Law, Moreno-Ramirez, Conde, *Magnetocaloric effect: from materials research to refrigeration devices*, Prog. Mater. Sci. (2017), doi:10.1016/j.pmatsci.2017.10.005.
The PDF (`1-s2.0-S0079642517301299-mmc1.pdf`, 127 pages) and the Word file (`SupplementaryMaterial_TablesS1_S8.docx`) contain the same tables. Extracted from the .docx on 8 Nov 2026; first-column string match against the PDF text found most rows (S8 patents matched poorly due to line wrapping), so overlap is likely complete but not verified row by row.

| Table | Material | Rows | Relevance |
|---|---|---|---|
| S1 | Laves phases | 116 | future |
| S2 | La(Fe,Si)13 | 189 | in Track B scope; secondary source (rows cite reviews), candidate for Tc cross-check |
| S3 | Gd5(Si,Ge)4 | 139 | future |
| S4 | ThCr2Si2-type | 70 | future |
| S5 | La manganites | 506 | future |
| S6 | Heusler (Ni-Mn-Ga etc.) | 313 | Heusler scope |
| S7 | Amorphous alloys | 492 | future |
| S8 | Refrigerator patents | 62 | not materials data |
| refs | Reference list | ~634 | needed to resolve `[n]` citations |

Extracted CSVs (outside git for now): `S1_laves.csv` ... `S8_patents.csv`, `references.csv`.
Format notes: field and value cells may hold several values separated by `/` (e.g. `1/4/7`); some rows have `a)/b)/c)` sub-entries; `*` flags (single crystals, assumed density) are kept in the text.

### Heusler CSVs in `Heusler/`
`DatasetMCE.csv` and `HeuslerDescriptors-*.csv` come with calculation notebooks (electronegativity descriptors). Not needed now; ignored.

### Other unused folders in `data/`
- `curie_neel/` and `court_cole_2018/` raw JSON/Mongo exports: already imported (Kelly & Cole, Court & Cole)
- `magneticmaterialsdatabase.zip`: not yet opened
- `1-13_dataset.xlsx`: NIMS source file (imported)

### Next steps for this material
1. Decide schema fit: these compounds are not covered by the current `composition_key` rules (La/Fe/Si focus); needs a family-aware extension and a new snapshot (v3).
2. Parse the multi-value field/entropy cells into one row per field.
3. Resolve `[n]` citations via `references.csv` to DOIs where possible.
4. Cross-check S2 against NIMS / MCEdatabase Tc values.
5. Confirm and record the written permissions (Victorino, Dr. Ucar) in the repo.
