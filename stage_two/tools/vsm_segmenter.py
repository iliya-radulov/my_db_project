"""
vsm_segmenter.py

Splits a VSM/PPMS/MPMS3/ACMS (H, T) stream into segments by which
quantity is actively varying: H constant + T varying -> 'MT' segment;
T constant + H varying -> 'MH' segment. Both varying at once is treated
as corrupted data, not a new segment type -- confirmed directly (not
assumed) that on real QD hardware, field and temperature are never
deliberately varied simultaneously; if both move together, something is
wrong with that stretch of data.

Uses a rolling-window LOCAL range (not raw point-to-point differences)
to classify each point, since single-point derivatives are too
noise-sensitive -- confirmed on real data earlier (isotherm boundary
detection) that raw sign-change/derivative checks pick up spurious noise
particularly near H=0 and during PPMS self-centering events.
"""

import numpy as np


def _rolling_range(x, window):
    """Local (max-min) over a centered rolling window, via numpy stride
    tricks -- avoids a slow Python loop for large files (some real VSM
    files here run 30,000+ rows).

    NaN-aware: uses nanmax/nanmin, not plain max/min. Confirmed a real
    bug on real data without this -- a single blank Temperature row
    (e.g. an initial settling row, or any of the periodic empty rows
    documented elsewhere in this project) anywhere inside an 80-row
    window caused plain max/min to return NaN for the WHOLE window,
    which then silently evaluated as "not varying" (NaN > threshold is
    False, not an error) -- completely masking a real ~60K temperature
    jump between two isotherms in one real file. A window that is
    entirely NaN still correctly returns NaN here (nothing to compare).
    """
    n = len(x)
    half = window // 2
    padded = np.pad(x, (half, window - half - 1), mode='edge')
    windows = np.lib.stride_tricks.sliding_window_view(padded, window)
    with np.errstate(invalid='ignore'):
        return np.nanmax(windows, axis=1) - np.nanmin(windows, axis=1)


def classify_points(H, T, window=10, H_noise_floor=50.0, T_noise_floor=1.0):
    """
    Classifies every point as 'MH' (H varying, T ~constant), 'MT'
    (T varying, H ~constant), 'idle' (neither varying -- e.g. a settling
    period), or 'corrupted' (both varying at once).

    H_noise_floor (Oe), T_noise_floor (K): minimum local range required
    to call a quantity "actively varying" rather than just measurement
    noise. Defaults chosen from real data: constant-field MT segments
    showed ~0.1-0.5 Oe fluctuation (50 Oe floor is safely above that,
    well below any real sweep range); constant-T MH isotherms showed
    ~0.01-0.05 K fluctuation (1.0 K floor is safely above that).
    Rescale if your data's noise floor differs meaningfully.

    Returns an array of labels, same length as H/T.
    """
    H_range = _rolling_range(H, window)
    T_range = _rolling_range(T, window)

    H_varying = H_range > H_noise_floor
    T_varying = T_range > T_noise_floor

    labels = np.full(len(H), 'idle', dtype=object)
    labels[H_varying & ~T_varying] = 'MH'
    labels[T_varying & ~H_varying] = 'MT'
    labels[H_varying & T_varying] = 'corrupted'
    return labels


def detect_segments(H, T, window=10, H_noise_floor=50.0, T_noise_floor=1.0,
                     min_segment_length=20, max_bridge_gap=200):
    """
    Groups classified points into contiguous segments. Segments shorter
    than min_segment_length are merged into the following segment if
    same-adjacent-type, or dropped/flagged if they're isolated noise
    blips between two different segment types -- avoids over-segmenting
    from brief classification flicker at transition boundaries.

    max_bridge_gap: a second, distinct merge pass (see below) -- bridges
    'idle'/'corrupted' gaps of up to this length when flanked by the
    SAME real segment type on both sides. This exists because of a real
    root cause confirmed on real data: near a smooth reversal (e.g. a
    cooling ramp turning into warming) or an asymptotic approach to a
    limit, the LOCAL rate of change genuinely passes through/toward zero
    -- this is NOT a windowing artifact fixable by picking a different
    window size, it's an inherent property of smooth turning points.
    Confirmed directly: an 'idle' gap was found sitting exactly at a
    known T-minimum turnaround row. No fixed window avoids this; a
    larger window just relocates where the effect shows up. Bridging
    same-type-flanked gaps handles the real cause (turning point / edge
    of range slowdown) instead of chasing window size.

    Returns a list of dicts: {'type': 'MH'|'MT'|'idle'|'corrupted',
    'start': int, 'end': int} (end exclusive), in row order.
    """
    labels = classify_points(H, T, window, H_noise_floor, T_noise_floor)

    # collapse into raw contiguous runs first
    raw_segments = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            raw_segments.append({'type': labels[start], 'start': start, 'end': i})
            start = i

    # merge short segments into a neighbor rather than keep tiny noise blips
    merged = []
    for seg in raw_segments:
        length = seg['end'] - seg['start']
        if length < min_segment_length and merged and merged[-1]['type'] == seg['type']:
            merged[-1]['end'] = seg['end']
        elif length < min_segment_length and merged:
            # extend the previous real segment over this short blip
            # rather than keep a spurious tiny segment
            merged[-1]['end'] = seg['end']
        else:
            merged.append(seg)

    # collapse any now-adjacent same-type segments left behind by the merge above
    collapsed = []
    for seg in merged:
        if collapsed and collapsed[-1]['type'] == seg['type']:
            collapsed[-1]['end'] = seg['end']
        else:
            collapsed.append(dict(seg))

    # gap-bridging passes. Root cause (confirmed on real data, not
    # assumed): near a smooth reversal (e.g. cooling turning into
    # warming) or an asymptotic approach to a limit (e.g. slow initial
    # ramp, or slow final approach to a target), the LOCAL rate of
    # change genuinely passes through/toward zero -- an inherent
    # property of smooth turning points, not a windowing artifact fixable
    # by picking a different window size. Confirmed directly: an 'idle'
    # gap was found sitting exactly at a known T-minimum turnaround row.
    # Bridges 'idle' only (not 'corrupted') -- a 'corrupted' block is a
    # real, separate finding (project decision: flag for downstream
    # review, don't silently merge it away).
    bridged = [dict(s) for s in collapsed]

    # pass 1: leading idle block, followed by a real segment -> drop it,
    # extend the real segment's start back to 0
    if (len(bridged) > 1 and bridged[0]['type'] == 'idle'
            and (bridged[0]['end'] - bridged[0]['start']) <= max_bridge_gap
            and bridged[1]['type'] in ('MH', 'MT')):
        bridged[1]['start'] = bridged[0]['start']
        bridged = bridged[1:]

    # pass 2: trailing idle block, preceded by a real segment -> drop it,
    # extend the real segment's end to the file end
    if (len(bridged) > 1 and bridged[-1]['type'] == 'idle'
            and (bridged[-1]['end'] - bridged[-1]['start']) <= max_bridge_gap
            and bridged[-2]['type'] in ('MH', 'MT')):
        bridged[-2]['end'] = bridged[-1]['end']
        bridged = bridged[:-1]

    # pass 3: middle idle blocks flanked by the SAME real type on both sides
    final = []
    i = 0
    while i < len(bridged):
        seg = bridged[i]
        if (seg['type'] == 'idle' and 0 < i < len(bridged) - 1
                and (seg['end'] - seg['start']) <= max_bridge_gap
                and bridged[i - 1]['type'] == bridged[i + 1]['type']
                and bridged[i - 1]['type'] in ('MH', 'MT')):
            final[-1]['end'] = bridged[i + 1]['end']
            i += 2
            continue
        final.append(dict(seg))
        i += 1

    return final
