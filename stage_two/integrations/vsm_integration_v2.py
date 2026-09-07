"""
VSM Integration Module (v2, replaced)

REPLACES the previous version's approach, per the same project decision
already applied to XRD (Option 1: replace, not run alongside):
  - OLD: parse_vsm_v2.py's simple parser (single Ms/Hc/Mr per file, no
    segmentation, no multi-loop/multi-temperature handling, no
    self-centering detection) + storage into the older generic
    characterization/property tables.
  - NEW: the validated multi-component pipeline (vsm_pipeline.py --
    instrument type detection, mass extraction, segmentation,
    self-centering quality flags, second-quadrant Hc/Mr, MT candidate
    features, automatic temperature-coefficient fitting) + storage into
    the new vsm_* tables (003_vsm_tables.sql), tested end-to-end
    against a real live database before this integration was written.

The OLD characterization/property tables are deliberately NOT touched
or dropped here -- Stage 1 (v1) still actively uses them. Purging is
planned for the end of Stage 2, not now. Same convention as
xrd_integration_v2.py.

REAL DIFFERENCE FROM XRD's INTEGRATION, worth stating explicitly: XRD
assumed one sample -> one pattern, so "does this sample have ANY XRD
data" was a valid duplicate check. VSM is different -- a single sample
can legitimately have several distinct real files (an MH loop at room
temperature, a separate MT scan, a temperature series...). Duplicate
detection here is per (sample, file_path) PAIR, not per-sample, so a
second genuinely different file for the same sample is never wrongly
blocked.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stage_two.tools.vsm_pipeline import process_vsm_file
from stage_two.tools.vsm_db_builder import insert_vsm_result
from stage_two.alloy.alloy_db_v2 import get_db


def import_vsm_file(file_path, sample_id, db=None):
    """
    Imports a VSM/PPMS/MPMS3/ACMS .dat file: runs the validated
    analysis pipeline, stores results across vsm_files / vsm_segments /
    vsm_mh_details / vsm_mt_details / vsm_mt_candidates /
    vsm_temperature_coefficients as applicable.

    Args:
        file_path: path to the .dat file
        sample_id: the STRING sample identifier used throughout the
            app -- NOT the integer DB primary key (same convention as
            xrd_integration_v2.py -- looked up here via db.get_sample()).
        db: optional existing db connection; creates one if not provided.

    Returns:
        dict: {'success': bool, 'error': str} on failure, or on success:
        {'success': True, 'sample_id': str, 'file': str,
         'instrument_type': str, 'mass_g': float or None,
         'n_segments': int, 'segment_types': {'MH': n, 'MT': n, ...},
         'has_temperature_coefficients': bool}
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

        # duplicate check: per (sample, file_path) PAIR, not per-sample
        # -- see module docstring for why this differs from XRD's check
        db.cursor.execute(
            "SELECT id FROM vsm_files WHERE sample_id = %s AND file_path = %s",
            (sample_db_id, file_path)
        )
        if db.cursor.fetchone():
            return {'success': False, 'error': f"This exact file already imported for sample '{sample_id}'"}

        result = process_vsm_file(file_path)

        vsm_file_id = insert_vsm_result(db.conn, sample_db_id, result)
        db.commit()

        segment_types = {}
        for seg in result['segments']:
            segment_types[seg['type']] = segment_types.get(seg['type'], 0) + 1

        return {
            'success': True,
            'sample_id': sample_id,
            'file': os.path.basename(file_path),
            'vsm_file_id': vsm_file_id,
            'instrument_type': result['instrument_type'],
            'mass_g': result['mass_g'],
            'n_segments': len(result['segments']),
            'segment_types': segment_types,
            'has_temperature_coefficients': result['temperature_coefficients'] is not None,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

    finally:
        if close_db:
            db.close()


def import_vsm_files(folder_path, sample_id=None, db=None):
    """Imports all .dat files from a folder -- same interface as before."""
    close_db = False
    if db is None:
        db = get_db()
        close_db = True

    results = []
    folder = Path(folder_path)
    dat_files = list(folder.glob('*.dat')) + list(folder.glob('*.DAT'))

    if not dat_files:
        print(f"No .dat files found in {folder_path}")
        return []

    print(f"📄 Found {len(dat_files)} .dat files to import")

    for file_path in dat_files:
        print(f"\n📄 Processing: {file_path.name}")
        result = import_vsm_file(str(file_path), sample_id, db)
        results.append(result)

        if result['success']:
            types_str = ', '.join(f"{k}:{v}" for k, v in result['segment_types'].items())
            print(f"  ✅ Imported: {result['file']} ({result['instrument_type']}, {types_str})")
        else:
            print(f"  ❌ Error: {result.get('error', 'Unknown error')}")

    if close_db:
        db.close()

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        sample_id = sys.argv[2] if len(sys.argv) > 2 else "TEST-VSM"

        print(f"📄 Testing VSM import: {file_path}")
        result = import_vsm_file(file_path, sample_id)

        if result['success']:
            print(f"\n✅ Import successful!")
            print(f"  Sample: {result['sample_id']}")
            print(f"  File: {result['file']}")
            print(f"  Instrument type: {result['instrument_type']}")
            print(f"  Mass: {result['mass_g']} g")
            print(f"  Segments ({result['n_segments']} total): {result['segment_types']}")
            print(f"  Temperature coefficients computed: {result['has_temperature_coefficients']}")
        else:
            print(f"\n❌ Import failed: {result.get('error')}")
    else:
        print("Usage: python vsm_integration_v2.py <file_path> [sample_id]")
