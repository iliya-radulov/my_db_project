# Cr–Fe–Ni Pilot-M: run order (after the freeze)

Environment of record: pycalphad 0.11.2, numpy 2.5.3 (scipy not needed). Scripts together in one folder (e.g. `stage_four/mce_crfeni/`);
`tdb_merge.py` (Track A, unchanged) must be importable and the binary TDBs reachable:
`export PYTHONPATH=/path/to/stage_three/stage4_step1:$PYTHONPATH`
`export SGTE_BINARY_DIR=/path/to/data/tdb/sgte_binary`

0. Hash note and scripts first (`sha256sum`), record, only then run.
1. Edge check, 288 combinations, resumable; unary pre-check runs first (exit 4 = stop):
   `python crfeni_edge_check.py --system crfeni --out edge_check_crfeni --workers 6`
2. Observable S (900 K primary; 800, 1000 K sensitivity); writes `edge_check_crfeni/sigma/sigma_S.csv`:
   `python crfeni_sigma.py --system crfeni --run-dir edge_check_crfeni --workers 6`
3. Gate G1–G3 (writes `sigma/gate.json`, `gate.md`):
   `python crfeni_gate.py --run-dir edge_check_crfeni`
4. Class analysis (refuses unless the gate passed; writes `sigma/analysis.json`, `analysis.md`):
   `python crfeni_analysis.py --run-dir edge_check_crfeni`

A script that ends non-zero (3 = incomplete/invalid, 4 = unary pre-check) is a failed run, not a result
(fault rule: fix or pin, qualify, repeat the whole run). Do not rerun parts of a run, and do not run a stage with a fixed
filename in parallel with another run.
