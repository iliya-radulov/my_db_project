import numpy as np
import os
import re
import csv
from pathlib import Path


def parse_vsm_file(file_path):
    """
    Parse a PPMS .dat file and extract:
    - Temperature
    - Field
    - Moment
    - Error

    Returns a dictionary with parsed arrays and basic magnetic parameters.
    """

    file_path = str(file_path)

    if not os.path.exists(file_path):
        return {'error': f'File not found: {file_path}'}

    # Read all lines
    with open(file_path, 'r', encoding='latin-1') as f:
        raw_lines = f.readlines()

    # Split into header/data blocks
    header_lines = []
    data_lines = []
    in_header = False
    in_data = False

    for raw in raw_lines:
        line = raw.strip()

        if line == '[Header]':
            in_header = True
            in_data = False
            continue
        elif line == '[Data]':
            in_header = False
            in_data = True
            continue

        if in_header:
            header_lines.append(line)
        elif in_data:
            if line and not line.startswith(';'):
                data_lines.append(line)

    # If no explicit [Header]/[Data], treat file as older plain format
    if not data_lines:
        data_lines = [line.strip() for line in raw_lines if line.strip() and not line.lstrip().startswith(';')]

    if not data_lines:
        return {'error': 'No data lines found'}

    # Parse mass from filename first
    mass = None
    filename = os.path.basename(file_path)
    match = re.search(r'(\d+\.?\d*)\s*mg', filename, re.IGNORECASE)
    if match:
        mass = float(match.group(1)) / 1000.0  # mg -> g
    else:
        # Fallback to header mass
        mass_from_header = None
        for line in header_lines:
            if 'SAMPLE_MASS' in line:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) > 1:
                    try:
                        mass_from_header = float(parts[1])
                    except ValueError:
                        pass
        mass = mass_from_header

    # Find the table header row
    header_idx = None
    for i, line in enumerate(data_lines):
        if 'Magnetic Field' in line and 'Moment' in line:
            header_idx = i
            break

    if header_idx is None:
        return {'error': 'Could not find column header row'}

    # Use csv reader for safer parsing of commas/quotes
    header_row = next(csv.reader([data_lines[header_idx]], delimiter=','))
    header_row = [col.strip().strip('"').strip("'") for col in header_row]

    field_idx = None
    moment_idx = None
    temp_idx = None
    error_idx = None

    for i, col in enumerate(header_row):
        col_low = col.lower()
        if 'magnetic field' in col_low:
            field_idx = i
        elif col_low == 'moment (emu)' or 'moment' == col_low:
            moment_idx = i
        elif 'temperature' in col_low:
            temp_idx = i
        elif 'std. err' in col_low or 'm. std. err' in col_low:
            error_idx = i

    if field_idx is None or moment_idx is None:
        return {'error': 'Could not find field or moment columns'}

    # Parse rows
    fields = []
    moments = []
    temps = []
    errors = []

    for line in data_lines[header_idx + 1:]:
        row = next(csv.reader([line], delimiter=','))

        # Pad short rows so indexing is safe
        if len(row) <= max(field_idx, moment_idx):
            continue

        def to_float(value):
            value = value.strip()
            if value == '':
                return None
            try:
                return float(value)
            except ValueError:
                return None

        field = to_float(row[field_idx])
        moment = to_float(row[moment_idx])

        if field is None or moment is None:
            continue

        fields.append(field)
        moments.append(moment)

        if temp_idx is not None and len(row) > temp_idx:
            temps.append(to_float(row[temp_idx]))
        else:
            temps.append(None)

        if error_idx is not None and len(row) > error_idx:
            errors.append(to_float(row[error_idx]))
        else:
            errors.append(None)

    if len(fields) == 0:
        return {'error': 'No valid data rows parsed'}

    fields = np.asarray(fields, dtype=float)
    moments = np.asarray(moments, dtype=float)

    # Basic quantities
    ms = float(np.max(np.abs(moments)))

    # Remanence: moment closest to zero field
    zero_idx = int(np.argmin(np.abs(fields)))
    mr = float(moments[zero_idx])

    # Coercivity: first sign change in moment
    hc = None
    for i in range(1, len(moments)):
        y0 = moments[i - 1]
        y1 = moments[i]
        if y0 == 0:
            hc = float(fields[i - 1])
            break
        if y0 * y1 < 0:
            x0 = fields[i - 1]
            x1 = fields[i]
            hc = float(x0 - y0 * (x1 - x0) / (y1 - y0))
            break

    temps_clean = [t for t in temps if t is not None]
    errors_clean = [e for e in errors if e is not None]

    result = {
        'fields': fields.tolist(),
        'moments': moments.tolist(),
        'temps': temps_clean,
        'errors': errors_clean,
        'n_points': int(len(fields)),
        'max_field': float(np.max(np.abs(fields))),
        'ms': ms,
        'mr': mr,
        'hc': hc,
        'mass': mass,
        'ms_per_g': float(ms / mass) if mass is not None and mass > 0 else None,
        'file': file_path,
    }

    return result