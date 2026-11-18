# Qualification test (to run on the machine that will decide G1)
From the folder with `nimnsn_edge_check.py` and `tdb_merge.py` (Track A, unchanged):

    pip list | grep -i -E "pycalphad|numpy"          # expect pycalphad 0.11.2
    export SGTE_BINARY_DIR=/path/to/data/tdb/sgte_binary
    python nimnsn_edge_check.py --system alfemn_2g --out qual_alfemn --workers 6

Expected: 78 of 144 combinations pass; per combination the same mismatch/unverified counts as `rescore/run/edge_check.csv` of 14 Nov.
