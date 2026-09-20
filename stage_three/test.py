import re
from pathlib import Path

from numpy.strings import index

def build_tdb_index(tdb_dir: Path) -> dict:
    """Returns {frozenset({'FE','LA'}): Path(...FeLa-23Su.tdb), ...}"""
    index = {}
    for f in tdb_dir.glob("*.tdb"):
        # Match two capitalised element names at the start: FeLa, FeNd, FeSi...
        m = re.match(r'^([A-Z][a-z]?)([A-Z][a-z]?)-', f.name)
        if m:
            pair = frozenset([m.group(1).upper(), m.group(2).upper()])
            index.setdefault(pair, []).append(f)
    return index

index = build_tdb_index(Path("../data/tdb/sgte_binary"))
index[frozenset(['FE','ND'])]
print(index[frozenset(['FE','ND'])])