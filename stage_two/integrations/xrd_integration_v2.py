"""
XRD Integration Module (v2, replaced)

REPLACES the previous version's approach entirely, per explicit project
decision (Option 1: replace, not run alongside):
  - OLD: parse_xrd_v2.py's simple peak-finder (no background
    subtraction, no Ka1/Ka2 handling, no neighbor-aware fit windowing --
    the exact duplicate-peak bug found and fixed early in this
    project's XRD work) + a lattice-parameter calculation hard-coded
    specifically for Nd2Fe14B (a fixed reflection table, only useful if
    the sample actually IS that phase) + storage into the older generic
    characterization/property tables.
  - NEW: the validated general-purpose pipeline (xrd_analyzer_dev1.py --
    real error handling, Ka2 stripping, R^2 fit quality, Scherrer size,
    d-spacing, validated against a certified reference standard) +
    storage into the new xrd_peaks/xrd_features tables
    (002_xrd_peaks_and_features.sql), tested end-to-end against a real
    live database before this integration was written.

The OLD characterization/property tables are deliberately NOT touched
or dropped here -- Stage 1 (v1) still actively uses them. Purging is
planned for the end of Stage 2, not now.

Known limitation, not solved here: anode is defaulted to 'Cu' (the vast
majority of lab XRD sources), since the app has no UI yet for selecting
it per import. Revisit if/when a non-Cu source needs importing through
this flow.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stage_two.tools.xrd_analyzer_dev1 import analyze_xrd
from stage_two.tools.xrd_features_builder import build_xrd_peaks_rows, build_xrd_features_row
from stage_two.tools.db_type_utils import sanitize_row
from stage_two.alloy.alloy_db_v2 import get_db


def import_xrd_file(file_path, sample_id, db=None, anode='Cu'):
    """
    Imports an XRD .xy file: runs the validated analysis pipeline,
    stores results in xrd_peaks (long format, one row per peak) and
    xrd_features (one row per sample, ML-ready).

    Args:
        file_path: path to the .xy file
        sample_id: the STRING sample identifier used throughout the
            app (e.g. 'HD334') -- NOT the integer DB primary key. This
            function looks up the integer id via db.get_sample()
            itself, since the new tables' foreign key needs that, not
            the string.
        db: optional existing db connection (matches the calling
            convention already used throughout alloy_desktop_v2.py);
            creates one if not provided.
        anode: X-ray source, default 'Cu' -- see module docstring.

    Returns:
        dict: {'success': bool, 'error': str} on failure, or on success:
        {'success': True, 'sample_id': str, 'file': str, 'n_peaks': int,
         'n_peaks_high_quality': int, 'mean_r_squared': float or None}
    """
    close_db = False
    if db is None:
        db = get_db()
        close_db = True

    try:
        sample = db.get_sample(sample_id)
        if not sample:
            return {'success': False, 'error': f"Sample '{sample_id}' not found in database"}
        sample_db_id = sample['id']

        # check for a prior import of this exact file, same convention
        # as the batch-import duplicate check elsewhere in the app
        db.cursor.execute(
            "SELECT sample_id FROM xrd_features WHERE sample_id = %s",
            (sample_db_id,)
        )
        if db.cursor.fetchone():
            return {'success': False, 'error': f"XRD data for sample '{sample_id}' already imported"}

        result = analyze_xrd(file_path, anode=anode)

        peaks_rows = [sanitize_row(r) for r in build_xrd_peaks_rows(sample_id=sample_db_id, result=result)]
        features_row = sanitize_row(build_xrd_features_row(sample_id=sample_db_id, result=result))

        for row in peaks_rows:
            cols = list(row.keys())
            col_names = ', '.join(cols)
            placeholders = ', '.join([f'%({c})s' for c in cols])
            db.cursor.execute(f"INSERT INTO xrd_peaks ({col_names}) VALUES ({placeholders})", row)

        cols = list(features_row.keys())
        col_names = ', '.join(cols)
        placeholders = ', '.join([f'%({c})s' for c in cols])
        db.cursor.execute(f"INSERT INTO xrd_features ({col_names}) VALUES ({placeholders})", features_row)

        db.commit()

        return {
            'success': True,
            'sample_id': sample_id,
            'file': os.path.basename(file_path),
            'n_peaks': features_row['n_peaks_total'],
            'n_peaks_high_quality': features_row['n_peaks_high_quality'],
            'mean_r_squared': features_row.get('mean_r_squared'),
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

    finally:
        if close_db:
            db.close()


def import_xrd_files(folder_path, sample_id=None, db=None, anode='Cu'):
    """Imports all .xy files from a folder -- same interface as before."""
    close_db = False
    if db is None:
        db = get_db()
        close_db = True

    results = []
    folder = Path(folder_path)
    xy_files = list(folder.glob('*.xy'))

    if not xy_files:
        print(f"No .xy files found in {folder_path}")
        return []

    print(f"📄 Found {len(xy_files)} .xy files to import")

    for file_path in xy_files:
        print(f"\n📄 Processing: {file_path.name}")
        result = import_xrd_file(str(file_path), sample_id, db, anode=anode)
        results.append(result)

        if result['success']:
            print(f"  ✅ Imported: {result['file']}")
            print(f"     peaks = {result['n_peaks']} ({result['n_peaks_high_quality']} high-quality)")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")

    if close_db:
        db.close()

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else "TEST-XRD"

        print(f"📄 Testing XRD import: {file_path}")
        result = import_xrd_file(file_path, sample_id)

        if result['success']:
            print(f"\n✅ Import successful!")
            print(f"  Sample: {result['sample_id']}")
            print(f"  File: {result['file']}")
            print(f"  Peaks: {result['n_peaks']} ({result['n_peaks_high_quality']} high-quality)")
            if result.get('mean_r_squared') is not None:
                print(f"  Mean R²: {result['mean_r_squared']:.4f}")
        else:
            print(f"\n❌ Import failed: {result.get('error')}")
    else:
        print("Usage: python xrd_integration_v2.py <file_path> [sample_id]")
