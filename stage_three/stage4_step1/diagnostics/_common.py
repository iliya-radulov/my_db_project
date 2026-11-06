"""Shared paths for the Track A edge-check diagnostics. Works from any working directory.
Expected layout:  my_db_project/stage_three/stage4_step1/diagnostics/<this file>
"""
import sys
from pathlib import Path
DIAG = Path(__file__).resolve().parent
S4 = DIAG.parent                      # stage4_step1
S3 = S4.parent                        # stage_three  (tdb_merge.py lives here)
for p in (str(S3), str(S4)):
    if p not in sys.path:
        sys.path.insert(0, p)
BIN_DIR = S3.parent / "data" / "tdb" / "sgte_binary"
RESULTS = S4 / "results_v2"
