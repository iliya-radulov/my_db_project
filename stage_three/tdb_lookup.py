"""
tdb_lookup.py — SGTE binary TDB index and lookup utilities.

Build an index of available binary TDB files, look up all assessments for a
given element pair, and select the preferred one for merging.

Usage:
    from stage_three.tdb_lookup import build_index, find_binaries, select_preferred

    index = build_index(Path("/path/to/sgte_binary"))
    paths = find_binaries(["FE", "ND", "B"], index)   # all pairs for ternary
    selected = {pair: select_preferred(files) for pair, files in paths.items()}
"""

from __future__ import annotations

import re
from pathlib import Path


# ── Element name normalisation ────────────────────────────────────────────────
# pycalphad uses ALL-CAPS element names; TDB filenames use Title-case (FeNd).
# We normalise everything to upper-case for comparison.

def _parse_pair(stem: str) -> tuple[str, str] | None:
    """
    Extract the two element symbols from a TDB filename stem like 'FeNd-16Wan'
    or 'NdB-16Zho-corrected'.
    Returns (EL1_UPPER, EL2_UPPER) or None if the pattern doesn't match.
    """
    m = re.match(r'^([A-Z][a-z]?)([A-Z][a-z]?)-', stem)
    if not m:
        return None
    return m.group(1).upper(), m.group(2).upper()


def _year_from_stem(stem: str) -> int:
    m = re.search(r'-(\d{2})', stem)
    if not m:
        return 0
    yy = int(m.group(1))
    return (2000 + yy) if yy <= 29 else (1900 + yy)

# ── Index builder ─────────────────────────────────────────────────────────────

def build_index(tdb_dir: Path) -> dict[frozenset, list[Path]]:
    """
    Scan *tdb_dir* for *.tdb files and return a dict mapping each element pair
    (as a frozenset of two upper-case element symbols) to a list of Path
    objects, sorted newest-first by the two-digit year in the filename.

    Example:
        {frozenset({'FE', 'ND'}): [Path('FeNd-16Wan.tdb'),
                                    Path('FeNd-16Che.tdb'),
                                    Path('FeNd-95Hal-LB.tdb')], ...}
    """
    tdb_dir = Path(tdb_dir)
    index: dict[frozenset, list[Path]] = {}

    for f in sorted(tdb_dir.glob("*.tdb")):
        pair = _parse_pair(f.stem)
        if pair is None:
            continue
        key = frozenset(pair)
        index.setdefault(key, []).append(f)

    # Sort each list: newest year first; '-corrected' files preferred over plain
    for key in index:
        index[key].sort(
            key=lambda p: (_year_from_stem(p.stem), "corrected" in p.stem.lower()),
            reverse=True,
        )

    return index


# ── Lookup ────────────────────────────────────────────────────────────────────

def find_binaries(
    elements: list[str],
    index: dict[frozenset, list[Path]],
) -> dict[frozenset, list[Path]]:
    """
    Given a list of element symbols (e.g. ['FE', 'ND', 'B']) return a dict of
    all binary pairs that exist in the index.

    Missing pairs are reported but not raised — the caller decides how to handle
    a gap in the database.

    Example:
        paths = find_binaries(['FE', 'ND', 'B'], index)
        # → {frozenset({'FE','ND'}): [...], frozenset({'FE','B'}): [...],
        #    frozenset({'ND','B'}): [...]}
    """
    elements = [e.upper() for e in elements]
    result: dict[frozenset, list[Path]] = {}
    missing: list[frozenset] = []

    from itertools import combinations
    for a, b in combinations(elements, 2):
        key = frozenset([a, b])
        if key in index:
            result[key] = index[key]
        else:
            missing.append(key)

    if missing:
        for m in missing:
            el1, el2 = sorted(m)
            print(f"  [tdb_lookup] WARNING: no TDB found for {el1}-{el2}")

    return result


# ── Selection ─────────────────────────────────────────────────────────────────

def select_preferred(
    paths: list[Path],
    prefer_lb: bool = False,
) -> Path:
    """
    Pick the best single TDB from a list of candidates for one binary pair.

    Strategy (default):
      1. Newest year wins.
      2. Among same-year files, '-corrected' beats plain.
      3. If prefer_lb=True, Landolt-Börnstein ('-LB') files are moved to
         the top instead (useful as a stable fallback).

    The list is already sorted newest-first by build_index(); this function
    just applies the LB preference override if requested.
    """
    if not paths:
        raise ValueError("Empty path list — no TDB candidates to choose from.")

    if prefer_lb:
        lb = [p for p in paths if "-LB" in p.stem]
        if lb:
            return lb[0]

    return paths[0]


# ── Convenience: full pipeline ────────────────────────────────────────────────

def get_tdb_paths(
    elements: list[str],
    tdb_dir: Path,
    prefer_lb: bool = False,
) -> dict[frozenset, Path]:
    """
    One-call helper: scan *tdb_dir*, find all binary pairs for *elements*,
    return the preferred TDB path per pair.

    Example:
        paths = get_tdb_paths(['FE', 'ND', 'B'],
                               Path('data/tdb/sgte_binary'))
        # → {frozenset({'FE','ND'}): Path('...FeNd-16Wan.tdb'),
        #    frozenset({'FE','B'}):  Path('...FeB-20Tak.tdb'),
        #    frozenset({'ND','B'}):  Path('...NdB-19Che.tdb')}
    """
    index = build_index(tdb_dir)
    candidates = find_binaries(elements, index)
    return {
        pair: select_preferred(files, prefer_lb=prefer_lb)
        for pair, files in candidates.items()
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tdb_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/tdb/sgte_binary")
    elements = sys.argv[2:] if len(sys.argv) > 2 else ["FE", "ND", "B"]

    print(f"TDB directory : {tdb_dir}")
    print(f"Elements      : {elements}")
    print()

    index = build_index(tdb_dir)
    print(f"Index built   : {len(index)} binary pairs indexed")
    print()

    candidates = find_binaries(elements, index)
    print("All candidates:")
    for pair, files in candidates.items():
        el1, el2 = sorted(pair)
        print(f"  {el1}-{el2}:")
        for f in files:
            print(f"    {f.name}")

    print()
    print("Preferred (newest):")
    for pair, files in candidates.items():
        el1, el2 = sorted(pair)
        best = select_preferred(files)
        print(f"  {el1}-{el2}: {best.name}")

    print()
    print("Preferred (Landolt-Börnstein):")
    for pair, files in candidates.items():
        el1, el2 = sorted(pair)
        best = select_preferred(files, prefer_lb=True)
        print(f"  {el1}-{el2}: {best.name}")
