#!/usr/bin/env bash
# make_release.sh — build release_lafesi/ from stage_four/calphad_lafesi/
# Run it from inside calphad_lafesi/:   bash make_release.sh
# Copies ONLY the files in INCLUDE, never overwrites an existing release folder,
# stops if an included file is missing, and writes HASHES.txt (sha256).
# Files in REVIEW are listed but not copied: check them first, then move them to INCLUDE.
set -euo pipefail

OUT="release_lafesi"
[ -e "$OUT" ] && { echo "ERROR: $OUT exists already. Move or delete it first."; exit 1; }

INCLUDE=(
  # --- scripts: merge builder, band, descriptor, test
  build_merged_tdb_fixed.py
  wp4_band_fixed.py
  wp4b_descriptor.py
  wp4b_test.py
  wp4_bcc.py
  wp4_fecompare.py
  wp4_probe.py
  # --- tau3-tau6 reconstruction
  tau36_rerun.py
  tau_diag.py
  tdb_build/tau36_block.py
  # --- binary checks
  tdb_build/binary_checks/check_binaries.py
  tdb_build/binary_checks/crosscheck_binaries.py
  # --- microstructure analysis (area tables, not the images)
  analyze_dark_phase.py
  plot_dark_phase.py
  # --- calculated data
  results/D_self.csv
  results/D_band.csv
  results/wp4_band_fixed.csv
  results/wp4_band_fixed_noFesubst.csv
  results/dark_phase_results_two_fields.csv
  results/dark_phase_vs_anneal.png
  # --- B2/D03 check
  b2d03_check/b2d03_check/add_order.py
  b2d03_check/b2d03_check/d_ordering_effect.py
  b2d03_check/b2d03_check/d_point.py
  b2d03_check/b2d03_check/fesi_order_check.py
  b2d03_check/b2d03_check/table6_check.py
  b2d03_check/b2d03_check/D_ordering_effect.csv
  b2d03_check/b2d03_hashes.txt
  # --- refit: scripts, frozen rules, own results
  refit_tau12/addD_analysis.py
  refit_tau12/ensemble_analysis.py
  refit_tau12/ensemble_window.py
  refit_tau12/evaluate.py
  refit_tau12/make_inputs.py
  refit_tau12/make_valid_b.py
  refit_tau12/make_valid_tdbs.py
  refit_tau12/residuals.py
  refit_tau12/tau1_window.py
  refit_tau12/config.yaml
  refit_tau12/config_baseline.yaml
  refit_tau12/config_const.yaml
  refit_tau12/config_tern.yaml
  refit_tau12/config_tern_base.yaml
  refit_tau12/FROZEN_SPEC.md
  refit_tau12/PreReg_Refit_FROZEN_20261119.md
  refit_tau12/PreReg_Refit.sha256
  refit_tau12/RESULTS.md
  refit_tau12/results_addB/evaluate_M2_vs_M3.txt
  refit_tau12/results_addB/final_epoch_losses.tsv
  refit_tau12/results_addB/new_phase_parameters.tsv
  refit_tau12/results_addB/tau_constants.tsv
  refit_tau12/results_addD/addD_analysis.txt
  refit_tau12/results_addD/addD_analysis_OHN.txt
  refit_tau12/results_addD/ens_analysis.txt
  refit_tau12/results_addD/M0_D.tsv
  refit_tau12/results_addD/OHN_D.tsv
  refit_tau12/results_addD/M0_ranges.tsv
  refit_tau12/results_addD/OHN_ranges.tsv
  refit_tau12/results_addD/M0_calc_log.txt
)

# Present in the folder but NOT copied. Open each one, then decide.
REVIEW=(
  refit_tau12/results_addB/all_parameters.tsv          # may contain Feng Table 5 values
  refit_tau12/results_addB/residuals_M0_feng.tsv       # measured compositions of Niitsu?
  refit_tau12/results_addB/residuals_M1_M2_M3.tsv      # same
  refit_tau12/results_addB/residuals_paperbuild.tsv    # same
  refit_tau12/results_addD/ens_w0.tsv                  # ensemble outputs: calculated only?
  refit_tau12/results_addD/ens_w1.tsv
  refit_tau12/results_addD/ens_w2.tsv
  refit_tau12/results_addD/ens_w3.tsv
  b2d03_check/Chemical-fit.md                          # not known to me
)

# Excluded by decision (23 Nov): data from papers and TDB files
EXCLUDED=(
  "espei_datasets/*  (transcribed Niitsu equilibria)"
  "data_feng2023/table5_parameters.md  (transcribed Table 5)"
  "refit_tau12/results_addB/train_equilibria.tsv, heldout_1373K_equilibria.tsv  (Niitsu equilibria)"
  "refit_tau12/results_addD/niitsu_text_facts.tsv  (Niitsu text facts)"
  "all *.tdb  (derived from Feng, Ohnuma and others)"
  "tdb_build/build_merged_tdb.py (deprecated), build_tdb.py, audit.py, wp4_band.py (older versions)"
  "notes *.md of the private repo (B2D03 note, TAU36_RECONSTRUCTION, RESULTS_MERGED ...)"
)

missing=0
for f in "${INCLUDE[@]}"; do
  [ -f "$f" ] || { echo "MISSING: $f"; missing=1; }
done
[ "$missing" -eq 0 ] || { echo "Stopped: fix the missing files first."; exit 1; }

# sha256 tool: Linux has sha256sum, macOS has shasum
if command -v sha256sum >/dev/null 2>&1; then H="sha256sum"; else H="shasum -a 256"; fi

for f in "${INCLUDE[@]}"; do
  mkdir -p "$OUT/$(dirname "$f")"
  cp -p "$f" "$OUT/$f"
done

( cd "$OUT" && find . -type f ! -name HASHES.txt | sed 's|^\./||' | sort | xargs $H > HASHES.txt )

echo "Copied ${#INCLUDE[@]} files to $OUT/ ; hashes in $OUT/HASHES.txt"
echo
echo "NOT copied, to review:"; printf '  %s\n' "${REVIEW[@]}"
echo
echo "Excluded by the 23 Nov decision:"; printf '  %s\n' "${EXCLUDED[@]}"
echo
echo "Check also: the .gitignore of this folder contains 'results/'; the release folder is a new folder, so it is not affected."
