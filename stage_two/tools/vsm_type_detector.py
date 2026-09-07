"""
vsm_type_detector.py

Identifies which QD instrument/option produced a given .dat/.DAT file,
and extracts its column structure -- the first step of the standard VSM
processing pipeline (type -> mass/T/field -> segmentation -> storage).

KEY FINDING (validated against 7 real files spanning DynaCool/PPMS VSM,
MPMS3, and ACMS): raw column COUNT is NOT a reliable type fingerprint.
Different VSM software versions (BYAPP tags "VSM,1.0,1.0" vs "VSM,2.0,2.0"
seen in real files) produce different column counts, and even files
sharing the SAME version tag were found with different column counts
(57 vs 50) -- likely depending on which optional measurement features
were active for that specific run. Column count cannot be trusted alone.

What IS reliable: specific diagnostic column NAMES, present or absent
regardless of version/count differences. Also note: 'Bridge 1 Resistance
(ohms)' was initially assumed to be ACMS-specific but real testing showed
it appears across almost all file types (a generic PPMS bridge-option
column) -- removed as a discriminator after being disproven on real data,
not just from a single case's data.
"""

import csv

# (column_name_or_names_required_together, instrument_type)
# Checked in order; first full match wins.
DIAGNOSTIC_SIGNATURES = [
    (['DC Moment Fixed Ctr (emu)'], 'MPMS3'),
    (["M-DC (emu)", "Calcoil' (emu)"], 'ACMS'),
]

KNOWN_BYAPP_LABELS = {
    'MPMS3 w/ AC': 'MPMS3',
    'VSM': 'PPMS_VSM',  # DynaCool/PPMS VSM option; BYAPP itself doesn't
                         # distinguish DynaCool from other PPMS variants,
                         # and testing showed it doesn't reliably predict
                         # column count either -- kept only as a
                         # confirmatory cross-check, not the primary signal
}


def _find_column_header_line(lines):
    """
    Finds the actual CSV column-header line among the first N lines of
    a file, whether or not a [Header] block precedes it. Matches on
    'Temperature' and 'Field' both being present, since every VSM/MPMS3/
    ACMS variant seen so far names these consistently even when column
    COUNT and other names vary.
    """
    for line in lines:
        if 'Temperature' in line and 'Field' in line:
            return line
    return None


def detect_instrument_type(file_path, encoding='latin-1', scan_lines=60):
    """
    Reads the start of a file and returns a dict describing what
    instrument/option produced it:

        {
            'instrument_type': 'MPMS3' | 'ACMS' | 'PPMS_VSM' | 'unknown',
            'header_present': bool,
            'byapp_raw': str or None,
            'columns': list of str,
            'n_columns': int,
            'diagnostic_columns_found': list of str,
        }

    Detection logic, in order:
    1. Always extract the real column list first (works whether or not
       [Header] survived) -- this is the ground truth for what fields
       are actually available to extract later, regardless of what any
       version tag claims.
    2. Check column names against DIAGNOSTIC_SIGNATURES (MPMS3/ACMS).
    3. If no diagnostic signature matched, default to 'PPMS_VSM' if a
       BYAPP,VSM line is present OR by elimination if a valid column
       header was found at all; otherwise 'unknown'.

    Raises no exceptions for unrecognized formats -- returns
    instrument_type='unknown' instead, so this can be used as a
    pre-filter without crashing on a file we haven't seen a type for yet
    (e.g. TORQUE, METIS -- not yet characterized against real examples).
    """
    with open(file_path, encoding=encoding) as f:
        lines = [f.readline() for _ in range(scan_lines)]

    header_present = any('[Header]' in l for l in lines)
    byapp_line = next((l.strip() for l in lines if l.startswith('BYAPP')), None)

    col_line = _find_column_header_line(lines)
    if col_line is None:
        return {
            'instrument_type': 'unknown',
            'header_present': header_present,
            'byapp_raw': byapp_line,
            'columns': [],
            'n_columns': 0,
            'diagnostic_columns_found': [],
        }

    columns = [c.strip() for c in next(csv.reader([col_line]))]

    instrument_type = 'unknown'
    diagnostic_found = []
    for required_cols, itype in DIAGNOSTIC_SIGNATURES:
        if all(c in columns for c in required_cols):
            instrument_type = itype
            diagnostic_found = required_cols
            break

    if instrument_type == 'unknown':
        # fall back to BYAPP label, or accept as generic PPMS_VSM by
        # elimination since a valid column header was found and no
        # MPMS3/ACMS signature matched
        if byapp_line:
            for label, itype in KNOWN_BYAPP_LABELS.items():
                if label in byapp_line:
                    instrument_type = itype
                    break
        if instrument_type == 'unknown':
            instrument_type = 'PPMS_VSM'

    return {
        'instrument_type': instrument_type,
        'header_present': header_present,
        'byapp_raw': byapp_line,
        'columns': columns,
        'n_columns': len(columns),
        'diagnostic_columns_found': diagnostic_found,
    }
