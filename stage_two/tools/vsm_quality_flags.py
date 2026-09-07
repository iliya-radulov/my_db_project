"""
vsm_quality_flags.py

General-purpose data-quality annotation for VSM segments -- detects
known instrument artifacts and attaches them as flags/counts on a
record, rather than trying to auto-correct them. Correction is
deliberately deferred (per project decision): mark what needs attention,
improve the standalone VSM analyzer's handling of flagged cases
incrementally, rather than solving every edge case before the general
pipeline can be used at all.
"""

import numpy as np


def detect_self_centering_events(T, M, center_position, position_tolerance_mm=0.02):
    """
    Detects likely self-centering events two ways, since real data
    showed the blank-Moment-row proxy alone isn't the most direct
    signal available:
      1. Moment (emu) is NaN at that row.
      2. Center Position (mm) shifts away from its local baseline by
         more than position_tolerance_mm -- confirmed directly on real
         data that Center Position moves at the same row the Moment
         reading goes blank (e.g. 15.11mm vs. a stable 15.12-15.14mm
         baseline), so this is a real, independent corroborating signal,
         not just inferred from the gap.

    Returns a sorted array of row indices flagged as likely
    self-centering events (union of both signals).

    IMPORTANT, confirmed quantitatively on real data (not assumed):
    the points immediately ADJACENT to a detected event show
    measurably elevated deviation from a local smooth fit compared to
    normal scatter elsewhere -- typically ~1-2.5x, occasionally up to
    ~5.5x in one real case. This is NOT negligible. Any differentiation
    or fitting that spans across a detected event should treat at least
    the immediate neighbor points with caution (see
    exclusion_window_for_events below) -- dropping only the single NaN
    row is confirmed INSUFFICIENT by the residual check performed on
    real data.
    """
    nan_events = np.where(np.isnan(M))[0]

    # local baseline for center position: rolling median, excluding NaN
    valid = ~np.isnan(center_position)
    baseline = np.full(len(center_position), np.nan)
    window = 5
    for i in range(len(center_position)):
        lo, hi = max(0, i - window), min(len(center_position), i + window + 1)
        local_valid = center_position[lo:hi][valid[lo:hi]]
        if len(local_valid) > 0:
            baseline[i] = np.median(local_valid)

    position_shift_events = np.where(
        valid & ~np.isnan(baseline) &
        (np.abs(center_position - baseline) > position_tolerance_mm)
    )[0]

    return np.union1d(nan_events, position_shift_events)


def exclusion_window_for_events(event_indices, n_total, pad=1):
    """
    Given detected event row indices, returns the full set of row
    indices that should be treated with caution (excluded from
    differentiation/fitting) -- the event rows themselves PLUS `pad`
    points on each side, per the quantitative finding above that
    dropping only the event row itself is insufficient.

    Returns a boolean mask, length n_total, True = exclude.
    """
    mask = np.zeros(n_total, dtype=bool)
    for idx in event_indices:
        lo, hi = max(0, idx - pad), min(n_total, idx + pad + 1)
        mask[lo:hi] = True
    return mask


def annotate_segment_quality(segment, H, T, M, center_position=None):
    """
    Attaches quality flags to a segment dict (as produced by
    vsm_segmenter.detect_segments) -- does NOT modify the segment's
    type or boundaries, just adds metadata for downstream record
    creation to act on.

    Adds:
      'n_self_centering_events': int (0 if center_position not provided
         -- flagged as 'unknown' via None instead of a false 0, so
         downstream code can distinguish "checked, none found" from
         "not checked at all")
      'is_HT_transition': bool -- True if this segment's type is
         'corrupted' (both H and T varying at once). Left as a flag for
         downstream interpretation, not auto-discarded here -- per
         project decision, whether this is a real problem or an
         expected transition period between measurement blocks is a
         domain judgment made at record-creation time, not baked into
         segmentation.
    """
    start, end = segment['start'], segment['end']
    seg_M = M[start:end]

    if center_position is not None:
        seg_T = T[start:end]
        seg_center = center_position[start:end]
        events = detect_self_centering_events(seg_T, seg_M, seg_center)
        n_events = len(events)
    else:
        n_events = None

    annotated = dict(segment)
    annotated['n_self_centering_events'] = n_events
    annotated['is_HT_transition'] = (segment['type'] == 'corrupted')
    return annotated
