"""
vsm_entropy_integration.py

Connects vsm_pipeline.py's segmenter output to the validated
vsm_entropy_change.py Maxwell-relation math, WITHOUT duplicating
isotherm-detection logic -- vsm_pipeline's segmenter already correctly
splits a discontinuous-protocol file into individual MH segments (each
one an isotherm); this module just adapts that output into the shape
vsm_entropy_change.compute_delta_sm() expects.

Real distinction this module exists to enforce, confirmed directly with
the project owner rather than assumed: a file with multiple 'MH'
segments can mean two structurally similar but physically different
things --
  1. Multiple up-sweep-only isotherms at different fixed temperatures
     (e.g. YCo5_120_MH.dat) -- exactly what entropy-change calculation
     needs.
  2. Multiple FULL bipolar loops at different fixed temperatures (e.g.
     the HD334/HD336 temperature-coefficient files) -- meant for Hc/Mr
     extraction, NOT valid input for entropy-change calculation. Real
     hysteresis between branches would corrupt (dM/dT)_H if a full loop
     were fed in as if it were a single isotherm.
FORC (First Order Reversal Curve) data is a third, related-but-different
case (multiple partial loops from different reversal fields) --
explicitly out of scope here, not handled by this module.

Feeding the wrong kind of MH segment set into the entropy-change math
would silently produce a wrong number, not an error -- so this module
checks each MH segment's shape before attempting the calculation, and
refuses (rather than guesses) if any segment doesn't look like a clean
single-direction sweep.
"""

import numpy as np

from vsm_entropy_change import interpolate_isotherms, compute_delta_sm


def truncate_to_upsweep(H, T, M):
    """
    Truncates a segment's data at its own H-maximum position, discarding
    anything after it.

    Necessary correction, confirmed on real data: vsm_segmenter's MH
    segments are classified purely on "H varying, T not" -- which a
    PARTIAL return sweep (H decreasing back toward zero, before T has
    started changing yet) still satisfies. Confirmed directly on
    YCo5_120_MH.dat: one MH segment's H genuinely rises to its max
    partway through, then continues decreasing afterward (ending far
    below the max) -- a real trailing tail from the next isotherm's
    return sweep, not noise or a bug. Truncating at the segment's own
    H-max recovers the true up-sweep-only isotherm the segmenter's
    boundary doesn't quite give you on its own.

    Returns (H_truncated, T_truncated, M_truncated).
    """
    peak_idx = int(np.argmax(H))
    return H[:peak_idx + 1], T[:peak_idx + 1], M[:peak_idx + 1]


def is_upsweep_only(H, max_negative_excursion_ratio=0.25):
    """
    Checks whether a segment is a genuine single-direction sweep
    (suitable for entropy-change calculation) rather than a full
    bipolar loop reaching comparable positive and negative field.

    Method: compares how far into negative field the segment reaches
    against its positive maximum. Confirmed on real data that simple
    direction-counting (are most point-to-point diffs the same sign)
    does NOT reliably distinguish these cases -- both a genuine
    isotherm (with a small pre-field settling dip before the real
    sweep) and a genuine full bipolar loop can show a similar peak
    POSITION (roughly mid-segment) once the segmenter's trailing-tail
    inclusion is accounted for. What actually differs physically: a
    real isotherm's negative excursion is small relative to its
    positive max (confirmed: YCo5, min=-5000 Oe vs max=+140000 Oe,
    ~3.6%) -- just a brief pre-field settling dip, not a real sweep to
    negative field. A genuine full loop reaches comparable magnitude in
    both directions (confirmed: HD334, min=-40011 Oe vs max=+40012 Oe,
    ~100%) -- real negative saturation, not a dip.

    max_negative_excursion_ratio: threshold for |H_min|/H_max above
    which a segment is considered a full loop, not an isotherm.
    Default 0.25 sits comfortably between the two confirmed real cases
    (3.6% vs ~100%), with considerable margin either side.

    Returns True if this looks like a genuine single-direction sweep
    (small or no negative excursion); False if it reaches comparable
    negative field (a real full loop).
    """
    if len(H) < 3:
        return False
    H_max = np.max(H)
    H_min = np.min(H)
    if H_max <= 0:
        return False  # never reaches positive field at all -- not a normal up-sweep
    if H_min >= 0:
        return True  # never goes negative at all -- unambiguously a pure up-sweep
    return (abs(H_min) / H_max) <= max_negative_excursion_ratio


def segments_to_isotherms(H, T, M, mh_segments):
    """
    Converts a list of MH-type segments (as produced by
    vsm_segmenter.detect_segments -- dicts with 'start'/'end' row
    indices) into the isotherms list format vsm_entropy_change's
    interpolate_isotherms()/compute_delta_sm() expect: dicts with
    'T_median', 'H', 'M'.

    Does NOT check segment suitability itself -- see
    check_isotherm_suitability() for that, kept separate so this stays
    a pure, simple data-reshaping function.
    """
    isotherms = []
    for seg in mh_segments:
        start, end = seg['start'], seg['end']
        seg_H, seg_T, seg_M = H[start:end], T[start:end], M[start:end]
        seg_H, seg_T, seg_M = truncate_to_upsweep(seg_H, seg_T, seg_M)
        valid = ~np.isnan(seg_M)
        isotherms.append({
            'T_median': float(np.nanmedian(seg_T)),
            'H': seg_H[valid],
            'M': seg_M[valid],
        })
    return isotherms


def check_isotherm_suitability(H, mh_segments):
    """
    Checks EVERY MH segment in a file for entropy-change suitability
    (single-direction sweep, not a full bipolar loop -- see module
    docstring for why this distinction matters).

    Checks the RAW segment (not truncated) -- important: truncating at
    the segment's own H-max BEFORE checking would hide the very
    evidence (a large negative excursion, possibly occurring after the
    peak) needed to correctly identify a genuine full bipolar loop.
    Truncation (see truncate_to_upsweep) only happens afterward, once
    suitability is already confirmed, when building the actual isotherm
    data for the calculation.

    Returns (suitable: bool, details: list of bool, one per segment) --
    the file is only suitable overall if ALL of its MH segments pass;
    a mix of isotherms and full loops in the same file would be a
    genuinely unusual/corrupted case, not something to partially
    process silently.
    """
    details = [is_upsweep_only(H[seg['start']:seg['end']]) for seg in mh_segments]
    return all(details), details


def compute_entropy_change_for_file(H, T, M, mh_segments, mass_g,
                                     target_fields_Oe=(10000, 19000), H_grid=None):
    """
    Full entry point: checks suitability, then computes Delta S_M if
    (and only if) every MH segment in the file is a genuine
    single-direction isotherm.

    Returns a dict:
        {
            'suitable': bool,
            'reason': str or None -- set when suitable=False, explains
                why (e.g. which segment(s) look like full loops)
            'n_isotherms': int,
            'results': {target_field_Oe: (T_mid_array, delta_Sm_array)}
                or None if not suitable
        }

    Requires mass_g (not None) -- entropy change is mass-normalized by
    definition; refuses rather than silently computing a
    per-file-volume or otherwise wrongly-normalized number.
    """
    if mass_g is None:
        return {'suitable': False, 'reason': 'mass_g not available for this file',
                'n_isotherms': len(mh_segments), 'results': None}

    if len(mh_segments) < 2:
        return {'suitable': False, 'reason': 'need at least 2 MH segments (isotherms) to differentiate',
                'n_isotherms': len(mh_segments), 'results': None}

    suitable, details = check_isotherm_suitability(H, mh_segments)
    if not suitable:
        bad_indices = [i for i, ok in enumerate(details) if not ok]
        return {
            'suitable': False,
            'reason': f"segment(s) {bad_indices} look like full bipolar loops, not single-direction "
                      f"isotherms -- likely a temperature-coefficient-style file, not suitable for "
                      f"entropy-change calculation",
            'n_isotherms': len(mh_segments),
            'results': None,
        }

    isotherms = segments_to_isotherms(H, T, M, mh_segments)
    results = compute_delta_sm(isotherms, mass_g, H_grid=H_grid, target_fields_Oe=target_fields_Oe)

    return {'suitable': True, 'reason': None, 'n_isotherms': len(mh_segments), 'results': results}
