import sys; sys.path.insert(0, "../stage_three") ; sys.path.insert(0, ".")
from pathlib import Path
from pycalphad import Database
from tdb_merge import check_edges
bin_dir = Path("../../data/tdb/sgte_binary")      # adjust if different
merged = Path("results_v2/merged_tdbs/FENDB_merged_v4__FeNd-16Che___FeB-19Wit___NdB-19Che.tdb")
paths = [next(bin_dir.rglob("FeNd-16Che.tdb")), next(bin_dir.rglob("FeB-19Wit.tdb")), next(bin_dir.rglob("NdB-19Che.tdb"))]
check_edges(Database(str(merged)), paths)