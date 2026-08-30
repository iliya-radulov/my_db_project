#!/usr/bin/env python3
"""
path_repair.py

Finds and repairs broken file paths in the alloy_lab database.
Run this whenever files have been moved, renamed, or reorganised.

Tables checked:
  alloy_lab.characterization.file_path  (SEM, XRD, VSM basic records)
  alloy_lab.vsm_files.file_path         (VSM analysis records)

Usage:
  python3 path_repair.py               -- interactive repair
  python3 path_repair.py --report      -- report only, no changes
  python3 path_repair.py --auto /new/root -- auto-search under this folder
"""

import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_config import DB_CONFIG
import psycopg2
import psycopg2.extras


# ── DB connection ────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
    )


# ── Path collection ──────────────────────────────────────────────────

TABLES = [
    {
        'table':  'alloy_lab.characterization',
        'id_col': 'id',
        'path_col': 'file_path',
        'label': 'characterization',
    },
    {
        'table':  'alloy_lab.vsm_files',
        'id_col': 'id',
        'path_col': 'file_path',
        'label': 'vsm_files',
    },
]


def collect_broken(conn):
    """
    Returns a list of dicts for every broken path in the DB:
        {table, id_col, id, path_col, file_path, filename}
    """
    broken = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        for t in TABLES:
            cur.execute(
                f"SELECT {t['id_col']}, {t['path_col']} "
                f"FROM {t['table']} "
                f"WHERE {t['path_col']} IS NOT NULL"
            )
            for row in cur.fetchall():
                path = row[t['path_col']]
                if path and not os.path.exists(path):
                    broken.append({
                        'table':    t['table'],
                        'id_col':   t['id_col'],
                        'id':       row[t['id_col']],
                        'path_col': t['path_col'],
                        'file_path': path,
                        'filename': os.path.basename(path),
                    })
    return broken


# ── Auto-search ──────────────────────────────────────────────────────

def find_file_under(filename, root):
    """
    Recursively searches root for a file with the given basename.
    Returns a list of matching absolute paths (may be empty or >1).
    """
    matches = []
    for dirpath, _, filenames in os.walk(root):
        if filename in filenames:
            matches.append(os.path.join(dirpath, filename))
    return matches


# ── DB update ────────────────────────────────────────────────────────

def update_path(conn, entry, new_path):
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {entry['table']} "
            f"SET {entry['path_col']} = %s "
            f"WHERE {entry['id_col']} = %s",
            (new_path, entry['id'])
        )
    conn.commit()


# ── Report ───────────────────────────────────────────────────────────

def print_report(broken):
    if not broken:
        print("\n✅ All file paths in the database are valid — nothing to repair.")
        return

    print(f"\n⚠️  Found {len(broken)} broken path(s):\n")
    by_table = {}
    for b in broken:
        by_table.setdefault(b['table'], []).append(b)

    for table, entries in by_table.items():
        print(f"  [{table}] — {len(entries)} broken:")
        for e in entries:
            print(f"    ID {e['id']:>6}  {e['file_path']}")
    print()


# ── Interactive repair ───────────────────────────────────────────────

def repair_interactive(conn, broken):
    print(f"\n🔧 Starting interactive repair ({len(broken)} broken paths)\n")
    fixed = 0
    skipped = 0

    for i, entry in enumerate(broken, 1):
        print(f"[{i}/{len(broken)}] {entry['table']} — ID {entry['id']}")
        print(f"  Broken path: {entry['file_path']}")
        print(f"  Filename:    {entry['filename']}")
        print()
        print("  Options:")
        print("    s — skip for now")
        print("    d — delete this record's path (set to NULL)")
        print("    or type/paste the correct full path")
        print()

        while True:
            choice = input("  Your choice: ").strip()

            if choice.lower() == 's':
                print("  → Skipped\n")
                skipped += 1
                break

            elif choice.lower() == 'd':
                confirm = input("  Set path to NULL? This cannot be undone easily. (y/n): ").strip()
                if confirm.lower() == 'y':
                    update_path(conn, entry, None)
                    print("  → Path set to NULL\n")
                    fixed += 1
                else:
                    print("  → Cancelled, skipping\n")
                    skipped += 1
                break

            elif choice:
                new_path = choice.strip('"').strip("'")
                if os.path.exists(new_path):
                    update_path(conn, entry, new_path)
                    print(f"  → Updated to: {new_path}\n")
                    fixed += 1
                    break
                else:
                    print(f"  ❌ Path does not exist: {new_path}")
                    print("     Try again, or type 's' to skip.")

    print(f"\n{'─'*50}")
    print(f"Repair complete: {fixed} fixed, {skipped} skipped")
    print(f"{'─'*50}\n")


# ── Auto repair ──────────────────────────────────────────────────────

def repair_auto(conn, broken, search_root):
    print(f"\n🔍 Auto-searching under: {search_root}")
    print(f"   ({len(broken)} broken paths to resolve)\n")

    fixed = 0
    ambiguous = 0
    not_found = 0

    for entry in broken:
        matches = find_file_under(entry['filename'], search_root)

        if len(matches) == 1:
            new_path = matches[0]
            update_path(conn, entry, new_path)
            print(f"  ✅ Fixed:  {entry['filename']}")
            print(f"            → {new_path}")
            fixed += 1

        elif len(matches) > 1:
            print(f"  ⚠️  Ambiguous ({len(matches)} matches): {entry['filename']}")
            for j, m in enumerate(matches, 1):
                print(f"     {j}. {m}")
            choice = input("     Pick a number (or s to skip): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(matches):
                new_path = matches[int(choice) - 1]
                update_path(conn, entry, new_path)
                print(f"     → Updated\n")
                fixed += 1
            else:
                print(f"     → Skipped\n")
                ambiguous += 1

        else:
            print(f"  ❌ Not found: {entry['filename']}")
            not_found += 1

    print(f"\n{'─'*50}")
    print(f"Auto repair complete:")
    print(f"  Fixed:     {fixed}")
    print(f"  Ambiguous: {ambiguous}")
    print(f"  Not found: {not_found}")
    print(f"{'─'*50}\n")

    if not_found > 0 or ambiguous > 0:
        print("Run without --auto to handle remaining broken paths interactively.\n")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find and repair broken file paths in alloy_lab database."
    )
    parser.add_argument(
        '--report', action='store_true',
        help="Report broken paths only, make no changes."
    )
    parser.add_argument(
        '--auto', metavar='ROOT',
        help="Auto-search for missing files under ROOT folder."
    )
    args = parser.parse_args()

    print("\nAlloy Lab — Path Repair Tool")
    print("=" * 50)

    conn = get_conn()
    print("✅ Connected to database\n")

    broken = collect_broken(conn)
    print_report(broken)

    if not broken:
        conn.close()
        return

    if args.report:
        print("(--report mode: no changes made)")
        conn.close()
        return

    if args.auto:
        root = os.path.expanduser(args.auto)
        if not os.path.isdir(root):
            print(f"❌ Search root does not exist: {root}")
            conn.close()
            sys.exit(1)
        repair_auto(conn, broken, root)

        # If anything remains broken, offer interactive follow-up
        still_broken = collect_broken(conn)
        if still_broken:
            print(f"{len(still_broken)} path(s) still broken.")
            followup = input("Run interactive repair for remaining? (y/n): ").strip()
            if followup.lower() == 'y':
                repair_interactive(conn, still_broken)
    else:
        repair_interactive(conn, broken)

    conn.close()
    print("Done.\n")


if __name__ == "__main__":
    main()
