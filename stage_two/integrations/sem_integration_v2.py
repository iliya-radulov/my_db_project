"""
sem_integration_v2.py

SEM integration module — Stage 2.
Replaces sem_integration_v2_2307.py (Zeiss-only, outdated).

Uses sem_metadata_universal.parse_sem_metadata_universal for
format-agnostic metadata extraction across all three real confirmed
instrument formats (Zeiss/JEOL/Tescan), then stores the result as
properties on the characterization record the app already created.

Design decisions, explicit:
  - Does NOT create a new characterization record. The app creates
    one (with add_characterization) before calling this function;
    this module looks it up by file_path and adds properties to it.
    The old integration (2307) created a second record — a bug, not
    a feature, corrected here.
  - Updates the instrument field in the existing record with the
    correctly auto-detected manufacturer name, replacing the app's
    initial hardcoded 'Zeiss SEM' placeholder.
  - Does NOT compute or store phase fraction. Phase fraction requires
    operator judgment (threshold selection via live slider) and is
    handled separately via sem_phase_fraction_standalone.py. If a
    confirmed phase fraction result needs to be stored after manual
    analysis, use store_sem_phase_fraction() below.
  - format='unknown' (no Zeiss tag, no sidecar) is handled honestly:
    instrument is recorded as 'SEM (format unknown)', properties with
    None values are skipped rather than stored as zero, and confidence
    is set to 0.0 to signal that nothing was extracted reliably.
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from stage_two.parsers.sem_metadata_universal import parse_sem_metadata_universal


# Human-readable instrument labels per detected format.
# 'instrument' field in the sidecar (Tescan's Device= field) is used
# when available; this is the fallback for the other formats.
INSTRUMENT_LABELS = {
    'zeiss':   'Zeiss SEM',
    'jeol':    'JEOL SEM',
    'tescan':  'Tescan SEM',
    'unknown': 'SEM (format unknown)',
}


def import_sem_file(file_path, sample_id, db):
    """
    Store SEM metadata for a single .tif file in the database.

    Expects the characterization record to already exist (the app
    creates it with add_characterization before calling this). Looks
    it up by file_path, updates the instrument field with the
    auto-detected manufacturer, and adds numeric properties.

    Args:
        file_path:  Absolute path to the .tif file.
        sample_id:  Sample ID string (used only in the return dict
                    for the caller's convenience — the char record
                    is already linked to the sample).
        db:         Open database connection from get_db().

    Returns a dict:
        On success:
            {
                'success':       True,
                'char_id':       int,
                'sample_id':     str,
                'file':          str,   -- basename only
                'format':        str,   -- 'zeiss'|'jeol'|'tescan'|'unknown'
                'instrument':    str,   -- human-readable label
                'magnification': float | None,
                'eht':           float | None,   -- kV
                'wd':            float | None,   -- mm
                'pixel_size_nm': float | None,
            }
        On failure:
            {
                'success': False,
                'error':   str,
            }
    """
    try:
        # ── 1. Parse metadata ────────────────────────────────────────
        metadata = parse_sem_metadata_universal(file_path)
        fmt = metadata.get('format', 'unknown')

        # Use sidecar's own device name when available (Tescan gives
        # this directly); fall back to the format-level label otherwise.
        instrument_label = (
            metadata.get('instrument')
            or INSTRUMENT_LABELS.get(fmt, 'SEM (format unknown)')
        )

        # ── 2. Find the existing characterization record ─────────────
        # The app creates this record (with add_characterization) before
        # calling import_sem_file. We look it up rather than create a
        # second one.
        db.cursor.execute(
            "SELECT id FROM characterization WHERE file_path = %s",
            (file_path,)
        )
        row = db.cursor.fetchone()
        if row is None:
            return {
                'success': False,
                'error': (
                    f"No characterization record found for:\n{file_path}\n"
                    "The app should create this before calling import_sem_file."
                ),
            }
        char_id = row['id']

        # ── 3. Update instrument field ───────────────────────────────
        # Replaces the app's initial hardcoded 'Zeiss SEM' placeholder
        # with the correctly detected manufacturer name.
        db.cursor.execute(
            "UPDATE characterization SET instrument = %s WHERE id = %s",
            (instrument_label, char_id)
        )

        # ── 4. Store numeric properties ──────────────────────────────
        # Confidence: 1.0 for a known format with real confirmed metadata;
        # 0.0 for 'unknown' (signals nothing was reliably extracted).
        confidence = 1.0 if fmt != 'unknown' else 0.0

        properties = [
            ('magnification',    metadata.get('magnification'),       'X'),
            ('eht_voltage',      metadata.get('eht_kv'),              'kV'),
            ('working_distance', metadata.get('working_distance_mm'), 'mm'),
            ('pixel_size',       metadata.get('pixel_size_nm'),       'nm'),
        ]

        for name, value, unit in properties:
            if value is not None:   # skip rather than store None as 0
                db.add_property(
                    characterization_id=char_id,
                    property_name=name,
                    property_value=float(value),
                    property_unit=unit,
                    confidence_score=confidence,
                )

        return {
            'success':       True,
            'char_id':       char_id,
            'sample_id':     sample_id,
            'file':          os.path.basename(file_path),
            'format':        fmt,
            'instrument':    instrument_label,
            'magnification': metadata.get('magnification'),
            'eht':           metadata.get('eht_kv'),
            'wd':            metadata.get('working_distance_mm'),
            'pixel_size_nm': metadata.get('pixel_size_nm'),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def store_sem_phase_fraction(char_id, bright_fraction, threshold, db,
                             notes=None):
    """
    Store a manually confirmed phase-fraction result for an existing
    SEM characterization record.

    Call this AFTER the operator has verified the threshold in
    sem_phase_fraction_standalone.py — not from the automated import
    pipeline. Phase fraction from a fully automated Otsu threshold
    without operator review should NOT be stored, since it can be
    wrong in different ways depending on the sample and imaging mode
    (confirmed on real data: directional texture confused Otsu on
    Tescan images; image noise confused it on Zeiss images).

    Args:
        char_id:         int — existing characterization record ID.
        bright_fraction: float — fraction of image area in the bright
                         phase (0.0 to 1.0), as confirmed by operator.
        threshold:       int — the threshold value (0-255) the operator
                         settled on, for reproducibility / audit trail.
        db:              Open database connection from get_db().
        notes:           Optional str — operator notes (e.g. which phase
                         the bright region corresponds to, whether a
                         damaged region was excluded by cropping, etc.).

    Returns:
        {'success': True} or {'success': False, 'error': str}
    """
    try:
        db.add_property(
            characterization_id=char_id,
            property_name='bright_phase_fraction',
            property_value=round(bright_fraction, 6),
            property_unit='fraction',
            confidence_score=1.0,   # operator-confirmed
        )
        db.add_property(
            characterization_id=char_id,
            property_name='phase_fraction_threshold',
            property_value=float(threshold),
            property_unit='uint8',
            confidence_score=1.0,
        )
        if notes:
            db.cursor.execute(
                "UPDATE characterization SET notes = %s WHERE id = %s",
                (notes, char_id)
            )
        return {'success': True}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


def import_sem_folder(folder_path, sample_id, db):
    """
    Import all .tif/.tiff files from a folder.

    Convenience wrapper for standalone / CLI use. The main app handles
    its own folder loop; this is for scripted bulk imports outside the
    GUI (e.g. backfilling existing SEM files already in the database).

    Note: this function creates characterization records itself (unlike
    import_sem_file, which expects the app to have done so). Use it
    only when NOT going through the app's import tab.
    """
    from stage_two.alloy.alloy_db_v2 import get_db as _get_db

    folder = Path(folder_path)
    tif_files = sorted(
        list(folder.glob('*.tif')) + list(folder.glob('*.tiff'))
    )

    if not tif_files:
        print(f"No .tif files found in {folder_path}")
        return []

    print(f"Found {len(tif_files)} .tif file(s) to import")
    results = []

    for tif_path in tif_files:
        print(f"\nProcessing: {tif_path.name}")

        # Create characterization record first (mirrors what the app does)
        metadata = parse_sem_metadata_universal(str(tif_path))
        fmt = metadata.get('format', 'unknown')
        instrument_label = (
            metadata.get('instrument')
            or INSTRUMENT_LABELS.get(fmt, 'SEM (format unknown)')
        )

        char_id = db.add_characterization(
            sample_id=sample_id,
            char_type='SEM',
            file_path=str(tif_path),
            instrument=instrument_label,
            notes=f"Bulk import from: {folder_path}",
        )

        result = import_sem_file(str(tif_path), sample_id, db)
        results.append(result)

        if result['success']:
            print(f"  Imported: {result['file']}")
            print(f"  Format:   {result['format']} ({result['instrument']})")
            if result['magnification']:
                print(f"  Mag:      {result['magnification']:.0f}x")
            if result['eht']:
                print(f"  EHT:      {result['eht']:.1f} kV")
            if result['pixel_size_nm']:
                print(f"  Pixel:    {result['pixel_size_nm']:.2f} nm")
        else:
            print(f"  Error: {result.get('error', 'unknown error')}")

    success_count = sum(1 for r in results if r['success'])
    print(f"\nDone: {success_count}/{len(tif_files)} files imported successfully")
    return results


# ── CLI / standalone use ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sem_integration_v2.py <file_or_folder> <sample_id>")
        sys.exit(1)

    path = sys.argv[1]
    sample_id = sys.argv[2]

    from stage_two.alloy.alloy_db_v2 import get_db
    db = get_db()

    try:
        if os.path.isdir(path):
            import_sem_folder(path, sample_id, db)
        else:
            # Standalone file: create char record first, then import
            metadata = parse_sem_metadata_universal(path)
            fmt = metadata.get('format', 'unknown')
            instrument_label = (
                metadata.get('instrument')
                or INSTRUMENT_LABELS.get(fmt, 'SEM (format unknown)')
            )
            char_id = db.add_characterization(
                sample_id=sample_id,
                char_type='SEM',
                file_path=path,
                instrument=instrument_label,
                notes="CLI import",
            )
            result = import_sem_file(path, sample_id, db)
            if result['success']:
                print(f"Imported: {result['file']}")
                print(f"Format:   {result['format']} ({result['instrument']})")
                print(f"Char ID:  {result['char_id']}")
            else:
                print(f"Failed: {result.get('error')}")
        db.conn.commit()
    finally:
        db.close()
