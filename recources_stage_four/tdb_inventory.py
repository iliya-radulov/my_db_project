"""
tdb_inventory.py — what is in a folder of thermodynamic database files? (25 Oct 2026)

Walks a folder recursively, finds every file that looks like a TDB (any extension: .tdb, .TDB,
.txt, ...; it must contain ELEMENT and PHASE statements), and for each one records:
  - size and a content hash (identical copies under different names are grouped);
  - whether pycalphad can load it, and the first line of the error if not;
  - its elements (without VA and /-) and number of phases;
  - which phases have parameters involving three or more real elements — ternary compounds or ternary
    interactions. A description with such parameters can represent ternary compounds or ordered ternary
    phases (Nd2Fe14B, 1:13, Heusler L21); one without them is effectively a merge of binaries, whatever
    its file name says;
  - whether the file defines GHSER functions for its elements (both naming styles, e.g. GHSERB / GHSERBB).

Writes tdb_inventory.csv (one row per file) and prints a summary: unique files per element system,
duplicates, files that fail to load.

Usage (main venv; the folder is only read, nothing is changed):
    python tdb_inventory.py PATH/TO/FOLDER
    python tdb_inventory.py PATH/TO/FOLDER --elements FE MN GA     # only files containing these elements
"""
import argparse
import csv
import hashlib
import re
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
SKIP_EXT = {".pdf", ".png", ".jpg", ".py", ".ocm", ".doc", ".docx", ".zip", ".json", ".md", ".ddb", ".pdb"}
NOT_ELEMENTS = {"VA", "/-", "/+", "E"}


def looks_like_tdb(text):
    t = text.upper()
    return "ELEMENT" in t and ("PHASE" in t or "PARAMETER" in t)


def analyse(path):
    raw = path.read_bytes()
    row = {"file": str(path), "size_kB": round(len(raw) / 1024, 1),
           "sha256": hashlib.sha256(raw).hexdigest()[:12]}
    text = raw.decode("utf-8", errors="replace")
    els_text = sorted({m.group(1).upper() for m in re.finditer(r"^\s*ELEM\w*\s+(\S+)", text, re.I | re.M)}
                      - NOT_ELEMENTS)
    row["elements"] = "-".join(els_text)
    try:
        from pycalphad import Database
        db = Database(str(path))
    except Exception as e:  # noqa: BLE001 — record any parser failure
        row.update(loads="no", error=(str(e).splitlines() or [type(e).__name__])[0][:120],
                   n_phases="", ternary_phases="", ghser="")
        return row
    els = sorted(str(e).upper() for e in db.elements if str(e).upper() not in NOT_ELEMENTS)
    row["elements"] = "-".join(els)
    # a phase is "ternary" if at least one of its PARAMETERS involves three or more real elements
    # (a ternary compound, or a ternary interaction); constituent lists alone are not enough, since a
    # merge of binaries also puts three elements into the liquid
    tern = set()
    for prm in db._parameters.all():
        species = {getattr(s, "name", str(s)).upper() for sub in prm["constituent_array"] for s in sub}
        if len(species - NOT_ELEMENTS) >= 3:
            tern.add(prm["phase_name"])
    syms = {str(k).upper() for k in db.symbols}
    missing = [e for e in els if f"GHSER{e}" not in syms and f"GHSER{e}{e}" not in syms]
    row.update(loads="yes", error="", n_phases=len(db.phases),
               ternary_phases=" ".join(sorted(tern)),
               ghser="all" if not missing else "missing: " + " ".join(missing))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--elements", nargs="*", help="keep only files that contain all of these elements")
    ap.add_argument("--out", type=Path, default=Path("tdb_inventory.csv"))
    args = ap.parse_args()
    # fail loudly instead of reporting every file as "does not load" or finding nothing
    try:
        import pycalphad  # noqa: F401
    except ImportError:
        raise SystemExit("pycalphad is not installed in this Python environment — activate the main venv "
                         "(the one the CALPHAD scripts use) and run again.")
    if not args.folder.is_dir():
        raise SystemExit(f"folder not found: {args.folder.resolve()}")

    files = [p for p in args.folder.rglob("*") if p.is_file() and p.suffix.lower() not in SKIP_EXT
             and p.stat().st_size < 50 * 1024 * 1024]
    if not files:
        raise SystemExit(f"no files found under {args.folder.resolve()}")
    rows = []
    for p in sorted(files):
        try:
            head = p.read_bytes()[:200_000].decode("utf-8", errors="replace")
        except OSError:
            continue
        if not looks_like_tdb(head):
            continue
        row = analyse(p)
        if args.elements:
            have = set(row["elements"].split("-"))
            if not {e.upper() for e in args.elements} <= have:
                continue
        rows.append(row)
        print(f"{row['loads']:3s} {row['elements']:30s} {str(row['n_phases']):>4s} ph  "
              f"tern: {row['ternary_phases'][:40]:40s} {p.relative_to(args.folder)}", flush=True)

    fields = ["file", "elements", "loads", "error", "n_phases", "ternary_phases", "ghser", "size_kB", "sha256"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    by_hash = defaultdict(list)
    for r in rows:
        by_hash[r["sha256"]].append(r)
    unique = [v[0] for v in by_hash.values()]
    print(f"\n{len(rows)} TDB files, {len(unique)} unique by content, "
          f"{sum(1 for r in unique if r['loads'] == 'no')} unique ones fail to load.")
    print("\nDuplicates (same content, several paths):")
    for v in by_hash.values():
        if len(v) > 1:
            print(f"  {v[0]['elements']}: " + " | ".join(Path(r['file']).name for r in v))
    print("\nUnique files that load, by element system (* = has ternary phases):")
    for r in sorted((r for r in unique if r["loads"] == "yes"), key=lambda r: (len(r["elements"]), r["elements"])):
        mark = "*" if r["ternary_phases"] else " "
        print(f"  {mark} {r['elements']:30s} {Path(r['file']).name}")
    print(f"\nWritten: {args.out}")


if __name__ == "__main__":
    main()
