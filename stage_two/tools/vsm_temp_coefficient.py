"""
vsm_temp_coefficient.py

Fits the reversible temperature coefficients of coercivity (alpha) and
remanence (beta) from a set of (T, Hc) / (T, Mr) points extracted from
multiple MH loops at different fixed temperatures -- the standard
permanent-magnet datasheet quantities.

Standard definition: a linear fit of the quantity vs. T, normalized by
its value at a reference temperature, expressed as %/K:
    Y(T) = Y_ref + slope * (T - T_ref)
    coefficient [%/K] = (slope / Y_ref) * 100

Does not require T points in any particular order -- a linear
regression is valid on out-of-order or repeated-direction T values (e.g.
a repeatability check that returns to a lower T after a higher one),
since it only depends on the (T, Y) pairs themselves, not measurement
sequence.
"""

import numpy as np


def fit_temperature_coefficient(T_values, Y_values, T_ref=None):
    """
    Fits Y(T) = Y_ref + slope*(T - T_ref) via least-squares linear
    regression, then reports the coefficient as %/K.

    T_ref: reference temperature to normalize against. If not given,
    uses whichever provided T value is closest to 293 K (room
    temperature) -- the conventional reference point for permanent
    magnet datasheets. Y_ref is then the FITTED line's value at T_ref
    (not just the raw data point), so the reported coefficient is
    consistent with the fit even if the data isn't perfectly linear.

    Returns a dict:
        {
            'slope': float (Y units per K),
            'T_ref': float,
            'Y_ref': float (fitted value at T_ref),
            'coefficient_pct_per_K': float,
            'n_points': int,
            'r_squared': float,
        }

    Requires at least 2 distinct T values -- raises ValueError otherwise
    rather than silently returning a meaningless fit.
    """
    T_arr = np.asarray(T_values, dtype=float)
    Y_arr = np.asarray(Y_values, dtype=float)

    if len(np.unique(T_arr)) < 2:
        raise ValueError(
            f"Need at least 2 distinct temperature points to fit a "
            f"coefficient; got {len(np.unique(T_arr))}."
        )

    slope, intercept = np.polyfit(T_arr, Y_arr, 1)

    if T_ref is None:
        T_ref = T_arr[np.argmin(np.abs(T_arr - 293.0))]

    Y_ref = slope * T_ref + intercept
    coefficient_pct_per_K = (slope / Y_ref) * 100.0

    Y_pred = slope * T_arr + intercept
    ss_res = np.sum((Y_arr - Y_pred) ** 2)
    ss_tot = np.sum((Y_arr - np.mean(Y_arr)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None

    return {
        'slope': slope,
        'T_ref': T_ref,
        'Y_ref': Y_ref,
        'coefficient_pct_per_K': coefficient_pct_per_K,
        'n_points': len(T_arr),
        'r_squared': r_squared,
    }
