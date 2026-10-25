# Figures of the Stage 3 paper

Scripts that rebuild the figures of *An Open-Source Data Infrastructure for Alloy Synthesis Research:
Stage 3* and repeat two of its checks. Run them from this folder with the main venv; each writes its
output next to itself. No book text is used or stored here.

| Script | Produces | Reads |
|---|---|---|
| `make_fig_rag.py` | Figure 2, `rag_benchmark.pdf/.png` (retrieval hit@5 by subgroup) | numbers in the script (benchmark runs `v2_minilm`, `v2_bge`, 24 Oct 2026) |
| `make_fig_section.py` | Figure 3, `FENDB_section_1375K.pdf/.png` (isothermal section, 1375 K) | `../cache/FENDB_1375K_N200_v3.pkl` (or a path given as argument) |
| `make_fig_feas.py` | Figure 5, `feasibility_threshold.pdf/.png` (threshold vs temperature) | `feasibility_sgte_fixed.json`, `thresholds_assessments.json` |
| `thresholds_assessments.py` | `thresholds_assessments.json` (Hallemans 1995 and Chen 2019, Section 6.5) | the two assessment TDB files (`--chen`, `--hallemans`) |
| `check_validation_step2.py` | printout: phases at the Nd2Fe14B composition, 800–1500 K (Section 5.5) | the two assessment TDB files |

The isolated-point check of the Figure 3 caption is `../check_isolated_points.py`.

The two ternary assessment files are not included; obtain them from their sources:
Chen et al. (2019), Calphad 66, 101627, and Hallemans et al. (1995) in the TDB transcription of the
NIMS Computational Phase Diagram Database (CPDDB). Figure 4 is a screenshot of the web advisor.
