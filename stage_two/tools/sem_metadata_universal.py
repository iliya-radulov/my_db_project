"""
sem_metadata_universal.py

Unified SEM metadata extraction across three real, confirmed instrument
formats -- auto-detects which applies per file and returns a single,
consistent schema regardless of source, so downstream code (grain
analysis, phase-fraction analysis) never needs to know which
manufacturer produced a given image.

Three real formats, each investigated and confirmed directly against
real data, not assumed:

  ZEISS: proprietary compressed binary TIFF tags (34118/34119).
    Handled by the existing, already-validated parse_sem_v2.py --
    wrapped here, not reimplemented.

  JEOL: NO usable metadata in the TIFF itself (confirmed directly --
    only generic tags present, e.g. XResolution is a print-DPI setting,
    not real spatial calibration). Real metadata lives in a sidecar
    .txt file (same basename, different extension), custom
    "$KEY value" format. Gives magnification ($CM_MAG), kV
    ($CM_ACCEL_VOLT), working distance ($$SM_WD), signal/detector mode
    ($CM_SIGNAL), and pixel calibration via $$SM_MICRON_BAR (scale bar
    length in pixels) + $$SM_MICRON_MARKER (real length, e.g. "10um").
    Footer/databar height comes directly from $CM_FULL_SIZE (the real
    image area) vs. the actual TIFF height -- confirmed exact, no
    brightness-heuristic guessing needed.

  TESCAN: sidecar .hdr file (same basename + "-tif.hdr" pattern seen
    on real data), standard INI format (parsed with configparser).
    Gives Magnification, HV, WD, Detector directly, and PixelSizeX/Y
    in METERS -- the most direct calibration of the three, no
    calculation needed at all. Also 16-bit image data (vs 8-bit for
    Zeiss/JEOL) -- a real difference downstream grain-analysis code
    must handle, not just a metadata quirk. ImageStripSize gives the
    exact footer height directly -- confirmed against real pixel data
    (a sharp, exact brightness transition at precisely
    total_height - ImageStripSize, with a perfectly constant value
    immediately after -- the databar background), not assumed from the
    field name alone.

If neither a Zeiss binary tag nor a matching sidecar file is found,
returns format='unknown' with everything else None -- does NOT guess
or fall back to a brightness-based footer heuristic silently mixed
with unverified calibration, since a wrong pixel_size_nm would
silently corrupt every downstream physical measurement. Real files
without a sidecar (confirmed to occur -- some real JEOL images
uploaded without one) correctly fall into this honest "unknown" case
rather than crashing.
"""

import os
import re
import configparser
import numpy as np
from PIL import Image
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'parsers'))
from parse_sem_v2 import parse_sem_file

def detect_sem_format(tif_path):
    """
    Determines which of the three known formats a given .tif file
    belongs to, checking in this order:
      1. Zeiss: proprietary tag 34118 or 34119 present in the TIFF itself.
      2. JEOL: a sidecar .txt file with the same basename exists.
      3. Tescan: a sidecar file matching the real naming pattern seen
         on real data (basename with '.tif' replaced by '-tif.hdr')
         exists.
    Returns 'zeiss' | 'jeol' | 'tescan' | 'unknown'.
    """
    try:
        img = Image.open(tif_path)
        if 34118 in img.tag_v2 or 34119 in img.tag_v2:
            return 'zeiss'
    except Exception:
        pass

    base = os.path.splitext(tif_path)[0]
    if os.path.exists(base + '.txt'):
        return 'jeol'

    # real naming pattern confirmed on real data: "1500x-1.tif" ->
    # "1500x-1-tif.hdr" (the '.tif' extension is folded into the sidecar
    # filename itself, not simply appended after it)
    tescan_hdr_path = tif_path[:-4] + '-tif.hdr' if tif_path.lower().endswith('.tif') else None
    if tescan_hdr_path and os.path.exists(tescan_hdr_path):
        return 'tescan'

    return 'unknown'


def parse_jeol_sidecar(txt_path, tif_path):
    """
    Parses a JEOL sidecar .txt file ("$KEY value" format, CRLF lines).
    tif_path is needed separately to get the actual TIFF height (for
    computing footer_crop_row against $CM_FULL_SIZE).
    """
    fields = {}
    with open(txt_path, encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('$'):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                fields[parts[0]] = parts[1].strip()

    result = {
        'format': 'jeol',
        'magnification': _to_float(fields.get('$CM_MAG')),
        'eht_kv': _to_float(fields.get('$CM_ACCEL_VOLT')),
        'working_distance_mm': _to_float(fields.get('$$SM_WD')),
        'detector': fields.get('$CM_SIGNAL'),
        'instrument': fields.get('$CM_INSTRUMENT'),
        'date': fields.get('$CM_DATE'),
        'pixel_size_nm': None,
        'footer_crop_row': None,
    }

    micron_bar_px = _to_float(fields.get('$$SM_MICRON_BAR'))
    micron_marker = fields.get('$$SM_MICRON_MARKER')
    if micron_bar_px and micron_marker:
        marker_nm = _parse_length_to_nm(micron_marker)
        if marker_nm is not None:
            result['pixel_size_nm'] = marker_nm / micron_bar_px

    full_size = fields.get('$CM_FULL_SIZE')
    if full_size:
        try:
            _, real_height = [int(v) for v in full_size.split()]
            result['footer_crop_row'] = real_height
        except (ValueError, IndexError):
            pass

    return result


def parse_tescan_sidecar(hdr_path, tif_path):
    """
    Parses a Tescan sidecar .hdr file (standard INI format).
    """
    config = configparser.ConfigParser()
    config.read(hdr_path)

    main = config['MAIN'] if 'MAIN' in config else {}
    sem = config['SEM'] if 'SEM' in config else {}

    result = {
        'format': 'tescan',
        'magnification': _to_float(main.get('Magnification')),
        'eht_kv': _to_float(sem.get('HV'), scale=1e-3),   # volts -> kV
        'working_distance_mm': _to_float(sem.get('WD'), scale=1e3),  # m -> mm
        'detector': sem.get('Detector'),
        'instrument': main.get('Device'),
        'date': main.get('Date'),
        'pixel_size_nm': None,
        'footer_crop_row': None,
    }

    pixel_size_x_m = _to_float(main.get('PixelSizeX'))
    if pixel_size_x_m is not None:
        result['pixel_size_nm'] = pixel_size_x_m * 1e9  # m -> nm

    strip_size = _to_float(main.get('ImageStripSize'))
    if strip_size is not None:
        try:
            img = Image.open(tif_path)
            total_height = img.size[1]
            result['footer_crop_row'] = int(total_height - strip_size)
        except Exception:
            pass

    return result


def parse_sem_metadata_universal(tif_path):
    """
    Main entry point: detects format, dispatches to the right parser,
    returns a UNIFIED schema regardless of source:
        {
            'format': 'zeiss' | 'jeol' | 'tescan' | 'unknown',
            'magnification': float or None,
            'eht_kv': float or None,
            'working_distance_mm': float or None,
            'detector': str or None,
            'instrument': str or None,
            'date': str or None,
            'pixel_size_nm': float or None,
            'footer_crop_row': int or None,
        }
    format='unknown' (with everything else None) if no Zeiss tag and no
    matching sidecar file is found -- confirmed real case (some real
    JEOL images have no sidecar uploaded), handled honestly rather than
    guessed.
    """
    fmt = detect_sem_format(tif_path)

    if fmt == 'zeiss':
        from parse_sem_v2 import parse_sem_file
        zeiss_result = parse_sem_file(tif_path)
        return {
            'format': 'zeiss',
            'magnification': _parse_zeiss_magnification(zeiss_result.get('magnification')),
            'eht_kv': _parse_zeiss_numeric(zeiss_result.get('eht_kv')),
            'working_distance_mm': _parse_zeiss_numeric(zeiss_result.get('working_distance_mm')),
            'detector': zeiss_result.get('detector'),
            'instrument': None,
            'date': zeiss_result.get('date'),
            'pixel_size_nm': _parse_zeiss_numeric(zeiss_result.get('pixel_size_nm')),
            'footer_crop_row': None,  # Zeiss uses the auto-detect brightness heuristic instead
        }

    elif fmt == 'jeol':
        base = os.path.splitext(tif_path)[0]
        return parse_jeol_sidecar(base + '.txt', tif_path)

    elif fmt == 'tescan':
        hdr_path = tif_path[:-4] + '-tif.hdr'
        return parse_tescan_sidecar(hdr_path, tif_path)

    else:
        return {
            'format': 'unknown',
            'magnification': None,
            'eht_kv': None,
            'working_distance_mm': None,
            'detector': None,
            'instrument': None,
            'date': None,
            'pixel_size_nm': None,
            'footer_crop_row': None,
        }


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def _parse_zeiss_numeric(text):
    """
    Extracts the leading number from a Zeiss metadata string that has a
    unit embedded (e.g. '5.4 mm' -> 5.4, '11.09 nm' -> 11.09,
    '0.000 kV' -> 0.0). Values already carry their real unit (mm, nm,
    kV) matching the unified schema's expected units directly -- no
    additional scaling needed here, unlike magnification (see
    _parse_zeiss_magnification).
    """
    if not text:
        return None
    match = re.match(r'([\d.]+)', str(text).strip())
    return float(match.group(1)) if match else None


def _parse_zeiss_magnification(text):
    """
    Extracts magnification from a Zeiss string like '25.00 K X', where
    'K' means the number is in THOUSANDS (25.00 K X = 25000x) --
    confirmed real on actual data, not assumed: this project's earlier
    Zeiss investigation found magnifications like '25.00 K X' for a
    genuine 25000x image. A bare number with no 'K' is taken at face
    value (already in real magnification units).
    """
    if not text:
        return None
    match = re.match(r'([\d.]+)\s*(K)?\s*X?', str(text).strip(), re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2):  # 'K' present -> thousands
        value *= 1000
    return value


def _to_float(value, scale=1.0):
    if value is None:
        return None
    try:
        return float(value) * scale
    except (ValueError, TypeError):
        return None


def _parse_length_to_nm(text):
    """Parses a length string like '10um' or '500nm' into nanometers."""
    match = re.match(r'([\d.]+)\s*(um|µm|nm|mm)', str(text).strip(), re.IGNORECASE)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2).lower()
    if unit in ('um', 'µm'):
        return value * 1000.0
    elif unit == 'nm':
        return value
    elif unit == 'mm':
        return value * 1_000_000.0
    return None
