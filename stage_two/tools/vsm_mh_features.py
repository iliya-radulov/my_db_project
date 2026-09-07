"""
vsm_mh_features.py

Extracts coercivity (Hc) and remanence (Mr) from a full bipolar MH loop
via direct crossing-point interpolation -- the physically standard
definition, not a fitted/model-based estimate:
  Hc: the field H at which M crosses zero (interpolated between the two
      consecutive raw points that bracket the sign change).
  Mr: the moment M at which H crosses zero (same idea, interpolated).

A full loop gives two of each (positive and negative branch). This is
NOT meant for one-way sweeps (e.g. isothermal virgin curves used for
entropy-change calculations) -- those don't have real Hc/Mr in this
sense since they never cross back through zero field/moment from the
opposite side.
"""

import numpy as np
from scipy.signal import find_peaks


def find_descending_branch(H, prominence=5000, distance=20):
    """
    Locates the descending branch of an MH sweep -- from the field's
    positive maximum (peak) to its negative minimum (trough) -- which
    is where the second quadrant (H<0, M>0 demagnetization curve) lives.

    Confirmed on real data: this is the practically relevant branch.
    Full 4-quadrant closed loops are rarely measured (cost/time), so
    extracting from the whole concatenated sweep (ascend + descend +
    partial re-ascend) risks mixing crossings from an initial virgin/
    settling excursion with the real demagnetization-curve crossing --
    confirmed directly: one real file gave two 'Hc crossings' differing
    by ~100x once analyzed as a whole sweep, but exactly one clean,
    correct crossing once restricted to just this branch.

    Returns (start_row, end_row) as positions within the given arrays,
    or None if no clear peak+trough pair is found (e.g. a one-way sweep
    with no full excursion to both a positive and negative extreme).
    """
    peaks, _ = find_peaks(H, prominence=prominence, distance=distance)
    troughs, _ = find_peaks(-H, prominence=prominence, distance=distance)
    if len(peaks) == 0 or len(troughs) == 0:
        return None
    # first peak followed by the first trough after it
    peak = peaks[0]
    later_troughs = troughs[troughs > peak]
    if len(later_troughs) == 0:
        return None
    trough = later_troughs[0]
    return peak, trough


def extract_second_quadrant_hc_mr(H, M, prominence=5000, distance=20):
    """
    Extracts Hc and Mr from the second-quadrant (demagnetization curve)
    portion of an MH sweep specifically -- the practically standard
    approach, since full 4-quadrant closed loops are rarely measured.
    Only expects ONE Hc crossing and ONE Mr crossing (not a symmetric
    pair), since this looks at a single branch, not a whole closed loop.

    Returns a dict:
        {
            'branch_found': bool,
            'Hc': float or None (Oe, as a positive magnitude),
            'Mr': float or None (emu, as a positive magnitude),
            'flag': None | 'no_branch_found' | 'wrong_crossing_count'
                    | 'unexpected_sign',
        }

    'unexpected_sign': flagged if the found Hc crossing isn't negative
    or the Mr crossing isn't positive -- for a normal second-quadrant
    demagnetization curve (starting from positive saturation), Hc
    should be a negative field and Mr a positive moment. A different
    sign pattern suggests this branch isn't actually the expected
    quadrant (e.g. sample/instrument sign convention differs, or this
    is actually the ascending branch) -- flagged rather than silently
    reported with a possibly-wrong physical meaning.
    """
    branch = find_descending_branch(H, prominence=prominence, distance=distance)
    if branch is None:
        return {'branch_found': False, 'Hc': None, 'Mr': None, 'flag': 'no_branch_found'}

    start, end = branch
    branch_H = H[start:end + 1]
    branch_M = M[start:end + 1]

    Hc_crossings = _interpolated_crossings(branch_H, branch_M)
    Mr_crossings = _interpolated_crossings(branch_M, branch_H)

    if len(Hc_crossings) != 1 or len(Mr_crossings) != 1:
        return {'branch_found': True, 'Hc': None, 'Mr': None, 'flag': 'wrong_crossing_count'}

    Hc_raw, Mr_raw = Hc_crossings[0], Mr_crossings[0]
    if Hc_raw > 0 or Mr_raw < 0:
        return {'branch_found': True, 'Hc': abs(Hc_raw), 'Mr': abs(Mr_raw), 'flag': 'unexpected_sign'}

    return {'branch_found': True, 'Hc': abs(Hc_raw), 'Mr': abs(Mr_raw), 'flag': None}


def _interpolated_crossings(x, y):
    """
    Finds every point where y crosses zero, walking consecutive
    (x[i], y[i]) pairs and linearly interpolating x at y=0 wherever the
    sign of y flips. Returns a list of interpolated x values, in the
    order encountered.

    NaN values in y are skipped (not interpolated across silently) --
    a crossing adjacent to a dropped NaN row uses the nearest valid
    neighbor instead, which is a reasonable approximation given these
    gaps are single rows (per the empty-row investigation elsewhere in
    this project), not extended stretches.
    """
    valid = ~np.isnan(y)
    x_valid, y_valid = x[valid], y[valid]

    crossings = []
    for i in range(len(y_valid) - 1):
        y0, y1 = y_valid[i], y_valid[i + 1]
        if y0 == 0:
            crossings.append(x_valid[i])
        elif (y0 < 0) != (y1 < 0):  # sign change
            x0, x1 = x_valid[i], x_valid[i + 1]
            # linear interpolation for x where y=0
            frac = -y0 / (y1 - y0)
            crossings.append(x0 + frac * (x1 - x0))
    return crossings


def extract_hc_mr(H, M, max_asymmetry_ratio=3.0):
    """
    Extracts Hc and Mr from one full bipolar MH loop.

    max_asymmetry_ratio: sanity check, confirmed necessary on real data.
    A real closed loop's two Hc crossings (or two Mr crossings) should
    be roughly comparable in magnitude (+Hc close to |-Hc|). Found a
    real case where exactly 2 crossings existed but differed by ~100x
    (198 Oe vs 20692 Oe) -- one came from a genuine loop branch, the
    other from an initial settling/virgin-like excursion at the very
    start of a sweep that never actually closed back to its starting
    field. Averaging these silently would give a physically meaningless
    number despite passing a naive "exactly 2 crossings" check.

    Returns a dict:
        {
            'Hc_crossings': list of H values where M=0,
            'Mr_crossings': list of M values where H=0,
            'Hc': float or None -- mean of |Hc_crossings| ONLY if
                exactly 2 found AND they're within max_asymmetry_ratio
                of each other; else None,
            'Mr': float or None -- same idea for Mr,
            'n_Hc_crossings': int,
            'n_Mr_crossings': int,
            'Hc_flag': None | 'wrong_crossing_count' | 'asymmetric_crossings',
            'Mr_flag': None | 'wrong_crossing_count' | 'asymmetric_crossings',
        }

    Deliberately does NOT force a single Hc/Mr value when the crossings
    look unreliable -- a one-way sweep, a noisy/multi-branch loop, or an
    incomplete/non-closed loop (this function's real-data-confirmed
    failure mode) all get flagged rather than silently averaged.
    """
    Hc_crossings = _interpolated_crossings(H, M)
    Mr_crossings = _interpolated_crossings(M, H)

    def _resolve(crossings, ratio_limit):
        if len(crossings) != 2:
            return None, 'wrong_crossing_count'
        a, b = abs(crossings[0]), abs(crossings[1])
        lo, hi = min(a, b), max(a, b)
        if lo == 0 or (hi / lo) > ratio_limit:
            return None, 'asymmetric_crossings'
        return (a + b) / 2.0, None

    Hc, Hc_flag = _resolve(Hc_crossings, max_asymmetry_ratio)
    Mr, Mr_flag = _resolve(Mr_crossings, max_asymmetry_ratio)

    return {
        'Hc_crossings': Hc_crossings,
        'Mr_crossings': Mr_crossings,
        'Hc': Hc,
        'Mr': Mr,
        'n_Hc_crossings': len(Hc_crossings),
        'n_Mr_crossings': len(Mr_crossings),
        'Hc_flag': Hc_flag,
        'Mr_flag': Mr_flag,
    }
