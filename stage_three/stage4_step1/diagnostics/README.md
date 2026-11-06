# Edge-check diagnostics (Track A, 6 Nov 2026)

Place this folder at `stage_three/stage4_step1/diagnostics/`. Every script runs from any working directory
(`python3 diagnostics/<script>.py`); paths come from `_common.py`.

| Order | Script | Question | Result recorded |
|---|---|---|---|
| 1 | `extract_all_T.py` | thresholds of the 78 survivors at all 8 T | `results_v2/ensemble_all_T.csv` |
| 2 | `which_edge_fails.py` | which edge fails for FeNd-16Che/FeB-19Wit/NdB-19Che? | Fe-B: 6.2 J/mol at 1600 K, x_Fe=0.95; Fe-Nd 0.0; Nd-B 0.1 |
| 3 | `sensitivity_relaxed.py` | do the six failures change the ensemble? | `results_v2/sensitivity_relaxed.csv`; no: min/max unchanged, median shift <= 0.07 kJ |
| 4 | `diag_fcc_B_v2.py` | do the Nd-B files reference GBCCBB? | no (symbols irrelevant; end-members are numeric + GHSERBB) |
| 5 | `merge_conflicts.py` | what does the merge report as conflict? | only G(FCC_A1,ND:VA;0), also in passing combinations |
| 6 | `fe_b_edge_additions.py` | what does the merge add on the Fe-B edge? | four parameters; no symbol redefined |
| 7 | `test_remove_added.py` | are those four parameters the cause? | no: 2.5 J/mol remain |
| 8 | `phase_models.py` | are magnetic model constants the cause? | no: identical in all files |
| 9 | `constituent_union_test.py` | is the united sublattice model the cause? | yes: restoring FeB-19Wit constituents -> 0.0 J/mol |

Rejected hypotheses (kept for the record): extra MB_B33 polymorph (all 6 FeB-19Wit x {NdB-95Hal-LB, NdB-98Che} pass);
silent introduction of GBCCBB/GHCPBB (no Nd-B parameter references them; no FeB-19Wit symbol is redefined).
