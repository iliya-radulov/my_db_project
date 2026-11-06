"""Per-edge edge-check report for one failing combination (run from anywhere)."""
from _common import BIN_DIR, RESULTS
from pycalphad import Database
from tdb_merge import check_edges
combo = ("FeNd-16Che", "FeB-19Wit", "NdB-19Che")
merged = RESULTS / "merged_tdbs" / f"FENDB_merged_v4__{'___'.join(combo)}.tdb"
paths = [next(BIN_DIR.rglob(n + ".tdb")) for n in combo]
check_edges(Database(str(merged)), paths)
