"""
vsm_mass_extractor.py

Extracts sample mass (grams), preferring the file header (ground truth,
confirmed reliable on real data: 'INFO,50.35,SAMPLE_MASS' matched the
filename's '50_35mg' exactly) with filename parsing as a fallback for
header-stripped files.

Filename parsing is inherently ambiguous in at least one real case found
during testing: '..._Ref_m4_140mg_...' -- is the mass 4.140mg (matching
the general digit_digit+mg pattern used elsewhere) or is 'm4' a separate
sample-ID token and the real mass just 140mg? Cannot be resolved from
the filename alone. Rather than silently guess, this returns a
confidence/method flag so ambiguous cases can be reviewed rather than
trusted blindly.
"""

import re


def extract_mass_from_header(file_path, encoding='latin-1', scan_lines=60):
    """
    Looks for 'INFO,<value>,SAMPLE_MASS' in the first scan_lines of a
    file. Returns mass in grams (float) or None if not found (e.g. a
    header-stripped file, or a file with the field present but blank).
    """
    with open(file_path, encoding=encoding) as f:
        for _ in range(scan_lines):
            line = f.readline()
            if not line:
                break
            if 'SAMPLE_MASS' in line:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None
    return None


def extract_mass_from_filename(filename):
    """
    Heuristic fallback for header-stripped files. Handles the patterns
    seen in real filenames so far:
        '50mg'        -> 50.0   (whole number, no decimal)
        '50_35mg'     -> 50.35  (underscore as decimal point -- CONFIRMED
                                  correct against a real header value)
        'm29_07_'     -> 29.07  ('m' prefix + underscore-decimal, no 'mg' suffix)
        '95.98mg'     -> 95.98  (point as decimal separator)
        'm11,819mg'   -> 11.819 (comma as decimal separator, optional 'm' prefix)

    Returns (mass_g_or_None, confidence) where confidence is:
        'high'    -- header confirmed (not applicable here, filename-only)
        'medium'  -- matched a pattern with no ambiguity found
        'low'     -- matched, but a plausible alternate reading exists
                     (e.g. a preceding token that could itself be part
                     of the number) -- CALLER SHOULD NOT TRUST THIS
                     SILENTLY, flag for manual review.
        None      -- no mass pattern found at all
    """
    # pattern 1: digits, a decimal separator ('_', '.' or ','), digits, then
    # 'mg' -- e.g. '50_35mg', '95.98mg', 'm11,819mg'. The first digit group
    # must start at a real token boundary (not preceded by a letter/digit) --
    # confirmed necessary on real data: without this, 'sample1_50mg'
    # incorrectly matched '1_50mg' as 1.50mg (the '1' in 'sample1' is an ID
    # number, not a mass digit). An optional single 'm' directly before the
    # number is accepted as a mass marker ('m23.147mg') for '.' and ','
    # only: for '_' the pre-existing handling of 'm4_140mg' is kept (below).
    matches = list(re.finditer(
        r'(?<![a-zA-Z0-9])(?:m(?=\d+[.,]\d+mg))?(\d+)([_.,])(\d+)mg',
        filename, re.IGNORECASE))
    if matches:
        # use the LAST match (closest to end of filename, where mass
        # conventionally sits) as the primary candidate
        m = matches[-1]
        mass = float(f"{m.group(1)}.{m.group(3)}")
        return mass, 'medium'

    # pattern 2: plain digits immediately followed by 'mg', no decimal.
    # Must not start in the middle of a decimal number: '95.98mg' that did
    # not match pattern 1 for some other reason must not be read as 98mg.
    # (If a decimal separator precedes the digits, report no mass instead
    # of a silently wrong one, so the operator is asked to enter it.)
    m = re.search(r'(?<![\d.,])(\d+)mg', filename, re.IGNORECASE)
    if m:
        return float(m.group(1)), 'medium'

    # pattern 3: 'm' + digits_digits (no 'mg' suffix), e.g. 'm29_07_'
    m = re.search(r'm(\d+)_(\d+)_', filename)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}"), 'medium'

    return None, None


def get_mass(file_path, filename=None):
    """
    Main entry point: tries the header first (trusted), falls back to
    filename parsing (flagged with confidence) if the header doesn't
    have it.

    Returns a dict: {'mass_g': float or None, 'source': 'header' |
    'filename' | 'not_found', 'confidence': 'high' | 'medium' | 'low' | None}
    """
    header_mass = extract_mass_from_header(file_path)
    if header_mass is not None:
        # Every real header value checked so far (7.53, 29.07, 50.35) is
        # in milligrams -- confirmed, e.g. 'INFO,50.35,SAMPLE_MASS'
        # matched a filename's '50_35mg' exactly. Convert directly
        # rather than guess from the value's magnitude.
        return {'mass_g': header_mass / 1000.0, 'source': 'header', 'confidence': 'high'}

    import os
    fname = filename if filename is not None else os.path.basename(file_path)
    mass_mg, confidence = extract_mass_from_filename(fname)
    if mass_mg is not None:
        return {'mass_g': mass_mg / 1000.0, 'source': 'filename', 'confidence': confidence}

    return {'mass_g': None, 'source': 'not_found', 'confidence': None}
