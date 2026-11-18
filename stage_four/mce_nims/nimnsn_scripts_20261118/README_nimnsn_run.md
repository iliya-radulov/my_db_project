# Ni–Mn–Sn Pilot-v1: run order (after the freeze)

Environment of record: the qualified one (pycalphad 0.11.2, numpy 2.5.3; scipy needed for the test).
Scripts go to `stage_four/mce_nims/` (public repo), `tdb_merge.py` (Track A, unchanged) must be importable:
`export PYTHONPATH=/path/to/stage_three/stage4_step1:$PYTHONPATH`
`export SGTE_BINARY_DIR=/path/to/data/tdb/sgte_binary`


1. Edge check (154 combinations; resumable):
   `python nimnsn_edge_check.py --system nimnsn --out edge_check_nimnsn --workers 6`
2. Thresholds of the survivors (1000 K primary; 800, 1200 K sensitivity):
   `python nimnsn_thresholds.py --system nimnsn --run-dir edge_check_nimnsn --rows nimnsn_rows.csv --workers 6`
3. Gate G1–G3 (writes `edge_check_nimnsn/thresholds/gate.json` and `gate.md`):
   `python nimnsn_gate.py --run-dir edge_check_nimnsn --rows nimnsn_rows.csv`
4. Test (refuses to run unless the gate passed; 100 000 permutations, seed 20261118):
   `python nimnsn_test.py --run-dir edge_check_nimnsn --rows nimnsn_rows.csv`

Exit codes: a script that ends non-zero or writes fewer rows than expected is a failed run, not a result
(implementation-and-environment fault rule: fix or pin, qualify, repeat the whole run).
Validation done before the freeze (no Ni–Mn–Sn file used): edge check on Al–Fe–Mn reproduces 78/144 (user's machine);
thresholds equal `threshold_alfemn.py` to 5e-6 kJ/mol; gate and test on synthetic data (pass / flat / low survival / invalid run;
planted relation → PASS, null → FAIL).
