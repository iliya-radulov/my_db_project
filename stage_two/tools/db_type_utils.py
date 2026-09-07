"""
db_type_utils.py

Converts numpy scalar types to native Python types before DB insertion.

Real issue found during XRD DB integration testing: psycopg2 has no
default adapter for numpy.float64/int64/bool_ etc., which our XRD (and
VSM) analysis modules produce throughout since they're numpy-based.
Rather than have every builder module (xrd_features_builder.py,
eventual VSM equivalents) worry about a specific DB driver's type
adaptation quirks, this is a single, reusable conversion step applied
right at the DB-insertion boundary, keeping the builder functions
themselves focused on producing correct values.
"""

import numpy as np


def to_native(value):
    """Converts a single numpy scalar to its native Python equivalent.
    Non-numpy values (int, float, str, bool, None) pass through
    unchanged."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def sanitize_row(row_dict):
    """Applies to_native() to every value in a dict, returning a new
    dict -- does not mutate the input."""
    return {k: to_native(v) for k, v in row_dict.items()}
