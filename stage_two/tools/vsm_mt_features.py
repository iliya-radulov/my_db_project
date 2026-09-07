"""
vsm_mt_features.py

MT (M vs T) segment feature extraction -- deliberately generic, not a
transition-type classifier. Different alloys show fundamentally
different M(T) behavior at a magnetic transition (a Curie-type drop is
best found as an INFLECTION POINT / peak in |dM/dT|, not necessarily an
extremum of M itself; a blocking-temperature peak in a ZFC curve IS a
genuine local extremum of M itself; a first-order transition can show a
sharp jump, again better caught in dM/dT). Since this project works
across many different alloy systems without always knowing in advance
which behavior applies, this module reports CANDIDATE features (local
M extrema, and separately, dM/dT extrema) without asserting which one is
"the" transition or what physical mechanism it represents -- that
interpretation is deferred to manual/standalone review, per project
decision (same "flag, don't force a judgment" pattern used elsewhere:
melt/boil caution tier, HT-transition flag, mass-extraction confidence
levels).
"""

import numpy as np
from scipy.signal import find_peaks


def split_monotonic_branches(T, min_branch_length=20, prominence_fraction=0.05, distance=10):
    """
    Splits an MT segment into monotonic-T branches (e.g. a cool-then-warm
    round trip becomes a 'cooling' branch and a 'warming' branch).

    Necessary correction, confirmed on real data: a naive extrema search
    across a full cool-then-warm segment finds a spurious M "extremum"
    sitting EXACTLY at the T turnaround point in every real round-trip
    file tested (two different files, both matched their known T-minimum
    row to within ~1K) -- because M(T) necessarily folds back on itself
    there regardless of any real magnetism, since T itself reverses
    direction. This is not a real transition candidate and must not be
    searched across as if it were one continuous monotonic curve.

    Returns a list of (start, end, direction) tuples, direction in
    {'increasing', 'decreasing'}.
    """
    T_range = np.nanmax(T) - np.nanmin(T)
    prominence = max(T_range * prominence_fraction, 1e-9)

    peaks, _ = find_peaks(T, prominence=prominence, distance=distance)
    troughs, _ = find_peaks(-T, prominence=prominence, distance=distance)
    turnarounds = sorted(list(peaks) + list(troughs))

    bounds = [0] + [t + 1 for t in turnarounds] + [len(T)]
    branches = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        if end - start < min_branch_length:
            continue
        direction = 'increasing' if T[end - 1] >= T[start] else 'decreasing'
        branches.append((start, end, direction))
    return branches


def find_M_extrema(T, M, prominence_fraction=0.05, distance=10):
    """
    Finds local maxima and minima of M(T) itself -- relevant e.g. for a
    genuine blocking-temperature peak in a ZFC curve.

    prominence_fraction: prominence required, as a fraction of the
    overall M range in this segment (adapts to each segment's own
    scale rather than using one fixed absolute threshold across very
    different materials/mass-normalizations).

    Returns a list of {'T': float, 'M': float, 'kind': 'max'|'min'}
    candidates, in temperature order.
    """
    valid = ~np.isnan(M)
    T_v, M_v = T[valid], M[valid]
    if len(M_v) < distance * 2:
        return []

    M_range = M_v.max() - M_v.min()
    prominence = max(M_range * prominence_fraction, 1e-12)

    maxima, _ = find_peaks(M_v, prominence=prominence, distance=distance)
    minima, _ = find_peaks(-M_v, prominence=prominence, distance=distance)

    candidates = [{'T': T_v[i], 'M': M_v[i], 'kind': 'max'} for i in maxima]
    candidates += [{'T': T_v[i], 'M': M_v[i], 'kind': 'min'} for i in minima]
    candidates.sort(key=lambda c: c['T'])
    return candidates


def find_dMdT_extrema(T, M, smoothing_window=5, prominence_fraction=0.1, distance=10):
    """
    Finds where |dM/dT| peaks -- relevant e.g. for a Curie/Neel-type
    transition, which often shows as an inflection in M(T) (a peak in
    its derivative) rather than a literal extremum of M itself.

    smoothing_window: dM/dT from raw consecutive differences is noisy
    (confirmed a general issue throughout this project's real VSM data);
    smoothed with a simple moving average before peak-finding.

    Returns a list of {'T': float, 'dMdT': float} candidates, sorted by
    |dMdT| descending (largest/most significant candidate first) --
    unlike find_M_extrema, order here is by significance, not
    temperature, since a caller reviewing "what's the most likely
    transition" wants the strongest candidate first.
    """
    valid = ~np.isnan(M)
    T_v, M_v = T[valid], M[valid]
    if len(M_v) < smoothing_window * 2 + distance:
        return []

    # sort by T first (dM/dT assumes T is monotonic locally; a segment
    # might be a cool-then-warm round trip, which this does NOT
    # separate into branches -- caller should pre-split by direction if
    # branch-specific behavior matters, same caveat as the isotherm work)
    order = np.argsort(T_v)
    T_sorted, M_sorted = T_v[order], M_v[order]

    dM = np.diff(M_sorted)
    dT = np.diff(T_sorted)
    with np.errstate(divide='ignore', invalid='ignore'):
        dMdT = np.where(dT != 0, dM / dT, 0)

    kernel = np.ones(smoothing_window) / smoothing_window
    dMdT_smooth = np.convolve(dMdT, kernel, mode='same')

    abs_dMdT = np.abs(dMdT_smooth)
    prom = max(abs_dMdT.max() * prominence_fraction, 1e-12) if len(abs_dMdT) else 1e-12
    peak_idx, _ = find_peaks(abs_dMdT, prominence=prom, distance=distance)

    T_mid = (T_sorted[:-1] + T_sorted[1:]) / 2.0  # dM/dT is between two T points
    candidates = [{'T': T_mid[i], 'dMdT': dMdT_smooth[i]} for i in peak_idx]
    candidates.sort(key=lambda c: -abs(c['dMdT']))
    return candidates


def extract_mt_candidates(T, M, **kwargs):
    """
    Convenience wrapper: splits into monotonic T-branches first (see
    split_monotonic_branches -- necessary to avoid a spurious "extremum"
    at any T turnaround within this segment, confirmed on real data),
    then returns candidates PER BRANCH:
        {'branches': [
            {'direction': 'increasing'|'decreasing', 'T_range': (lo, hi),
             'M_extrema': [...], 'dMdT_extrema': [...]},
            ...
        ]}
    Deliberately does not merge/rank across branches or across the two
    candidate kinds -- see module docstring.
    """
    branches = split_monotonic_branches(T)
    if not branches:
        # no clear turnaround found -- treat the whole segment as one branch
        direction = 'increasing' if np.nanmax(T) == T[np.nanargmax(~np.isnan(T))] else 'decreasing'
        branches = [(0, len(T), 'increasing' if T[-1] >= T[0] else 'decreasing')]

    results = []
    for start, end, direction in branches:
        seg_T, seg_M = T[start:end], M[start:end]
        results.append({
            'direction': direction,
            'T_range': (float(np.nanmin(seg_T)), float(np.nanmax(seg_T))),
            'M_extrema': find_M_extrema(seg_T, seg_M),
            'dMdT_extrema': find_dMdT_extrema(seg_T, seg_M),
        })
    return {'branches': results}
