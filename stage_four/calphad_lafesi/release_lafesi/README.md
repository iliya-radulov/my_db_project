# La-Fe-Si CALPHAD audit: code and calculated data

Supplement to the paper *Reconstructing a published La-Fe-Si thermodynamic
description from its printed tables: transcription errors, a descriptor test
against microstructure data, and failed re-optimisation attempts*
(I. Radulov; paper DOI: to be added).

Environment of record: Python 3.13, pycalphad 0.11.2, numpy 2.5.3.
`HASHES.txt` lists the sha256 value of every other file. Check it with
`shasum -a 256 -c HASHES.txt` (macOS) or `sha256sum -c HASHES.txt` (Linux).

## What is in the folder

| Folder or file | Paper section | Content |
|---|---|---|
| `build_merged_tdb_fixed.py` | 2.1, 2.3 | merge builder: three binary assessments plus the ternary terms of Table 5 quoted from Feng et al. (2023), with attribution |
| `wp4_band_fixed.py`, `results/wp4_band_fixed*.csv` | 2.3 | the 20 combinations of binary files at the frozen point La(Fe11.5Si1.5), 1373 K; the file without "noFesubst" is the one used in the paper |
| `tau36_rerun.py`, `tau_diag.py`, `tdb_build/tau36_block.py` | 2.4 | check of tau3-tau6 |
| `wp4_bcc.py`, `wp4_fecompare.py` | 2.1 | comparison of the merged build with the self-contained database for the bcc Fe-Si parameters (documentation only: they need the self-contained database, which is not released) |
| `tdb_build/binary_checks/` | 2.1 | checks of the binary files |
| `b2d03_check/` | 2.5 | B2/D03 ordering check, `D_ordering_effect.csv`, own `b2d03_hashes.txt` |
| `wp4b_descriptor.py`, `wp4b_test.py` | 3 | descriptor D(x, T) and the pre-registered test |
| `results/D_self.csv`, `results/D_band.csv` | 3 | D for the 15 conditions (primary build) and for the 20 combinations |
| `analyze_dark_phase.py`, `plot_dark_phase.py`, `results/dark_phase_results_two_fields.csv`, `results/dark_phase_vs_anneal.png` | 3.1 | area fractions of the dark phase (tables, not images) |
| `refit_tau12/` | 4 | re-optimisation: scripts, configs, frozen specification (`PreReg_Refit_FROZEN_20261119.md`, `PreReg_Refit.sha256`), fitted values (`results_addB/new_phase_parameters.tsv`, `tau_constants.tsv`), losses, and the window tables `results_addD/` |

## What is not in the folder, and why

* **Database files (.tdb).** They contain parameters of published assessments.
  Take the sources from the original papers (the nine binary files are listed
  with their sources in Section 2.3 of the paper) and rebuild with the scripts.
  Set the environment variable `SGTE_BINARY_DIR` to the folder with the binary
  files; the builder has no default path. The self-contained database of the paper
  (Table 5 of Feng et al.) is not reproducible: its builder needed an
  intermediate file that no longer exists. The reproducible equivalent is the
  merged build FeLa-23Su + LaSi-10Zho + FeSi-12Ohn, which gives the 15 values of
  `D_self.csv` to within about 1 J/mol-atom.
* **Transcribed data of the literature.** The 71 equilibria of Niitsu and
  Kainuma (2012) and the full Table 5 of Feng et al. (2023) must be transcribed
  from the papers. The refit scripts expect the equilibria in the input format
  written by `refit_tau12/make_inputs.py`. Tables that hold the measured
  equilibria (training and held-out sets, residuals) are not released.
* **Microscopy images.** Not published. The area-fraction table and the scripts
  are, so the statistics can be reproduced, but the table cannot be re-derived
  from the images (a limit of reproducibility, stated in the paper).

## Order of the main calculation

1. Build the merged databases with `build_merged_tdb_fixed.py` (needs the binary files).
   The scripts are released exactly as they were run (their hashes are in the paper and the notes), so some contain paths of the machines on which they ran (`wp4b_descriptor.py self`, `wp4_bcc.py`, `wp4_fecompare.py`, `tau36_rerun.py`); set them to your own.
   The scripts of the tau3-tau6 check also need Tables 4 and 6 of Feng et al., which are not released.
2. `wp4b_descriptor.py` (modes `self` and `band`) writes `D_self.csv` and `D_band.csv`.
3. `wp4b_test.py` computes Spearman's rho, the permutation p-value and the band.
   Compare your files with the hashes in `HASHES.txt`: the released
   `D_self.csv` is 663e74c3..., `D_band.csv` is 4d99ec35....
4. The registration of the test was frozen on 16 November 2026 (sha256 71abaac1...47e8).
   Numerical values may change in the last digits with another pycalphad or numpy version.

## Authorship

Code and data: I. Radulov and Claude (Anthropic). The paper has I. Radulov as the
only author; the use of Claude is acknowledged there.

## Licence

Code: MIT. The calculated data are released with the code under the same licence.
Please cite the paper and this record.
