"""
vsm_pipeline.py

Combines the four independently-validated VSM components into one
pipeline function:
  1. vsm_type_detector  -- what instrument produced this file
  2. vsm_mass_extractor  -- sample mass, header-first with flagged
     filename fallback
  3. vsm_segmenter        -- split into MH/MT/idle/corrupted segments
  4. vsm_quality_flags    -- annotate segments with self-centering
     events and the HT-transition flag

Each component was validated separately against real files before being
combined here -- this module's job is only to wire them together
correctly, not to re-derive any of their logic.
"""

import csv
import pandas as pd
import os
import sys
from pathlib import Path
import numpy as np

# Ensures sibling modules (vsm_type_detector, vsm_segmenter, etc.) can be
# found via the bare imports below regardless of how THIS module itself
# is imported. Confirmed necessary on real testing: this worked fine when
# run directly from inside stage_two/tools/, but failed with
# ModuleNotFoundError when imported as stage_two.tools.vsm_pipeline from
# a different directory (stage_two/integrations/) -- Python does not
# automatically add a module's own directory to sys.path just because
# something elsewhere imported it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vsm_type_detector import detect_instrument_type
from vsm_mass_extractor import get_mass
from vsm_segmenter import detect_segments
from vsm_quality_flags import annotate_segment_quality
from vsm_mh_features import extract_second_quadrant_hc_mr, find_descending_branch
from vsm_mt_features import extract_mt_candidates
from vsm_temp_coefficient import fit_temperature_coefficient
from vsm_entropy_integration import compute_entropy_change_for_file
from vsm_bhmax import demag_factor_prozorov_kogan, compute_bhmax


# Which column holds the real moment value, per instrument type.
# Confirmed on real data: MPMS3 leaves 'Moment (emu)' entirely empty
# and reports via 'DC Moment Fixed Ctr (emu)' instead (QD's own
# recommendation: prefer Fixed Ctr over Free Ctr). ACMS and PPMS_VSM
# both populate 'Moment (emu)' directly.
MOMENT_COLUMN_BY_TYPE = {
    'MPMS3': 'DC Moment Fixed Ctr (emu)',
    'ACMS': 'Moment (emu)',
    'PPMS_VSM': 'Moment (emu)',
}


def _find_data_start(file_path, encoding='latin-1', scan_lines=60):
    """Returns (data_start_row, column_list) -- the row index where
    actual data begins, and the parsed column names, regardless of
    whether [Header] survived."""
    with open(file_path, encoding=encoding) as f:
        lines = [f.readline() for _ in range(scan_lines)]
    for i, line in enumerate(lines):
        if 'Temperature' in line and 'Field' in line:
            cols = [c.strip() for c in next(csv.reader([line]))]
            return i + 1, cols
    raise ValueError(f"Could not find a column header line in the first {scan_lines} lines of {file_path}")


def load_vsm_file(file_path, encoding='latin-1'):
    """
    Loads a VSM/PPMS/MPMS3/ACMS file end to end: detects instrument
    type, finds the real data start (header present or stripped),
    extracts mass, and returns everything needed for segmentation.

    Returns a dict:
        {
            'instrument_type': str,
            'mass_g': float or None,
            'mass_source': str,
            'mass_confidence': str or None,
            'H': np.array, 'T': np.array, 'M': np.array,
            'center_position': np.array or None,
            'moment_column_used': str,
            'n_rows': int,
        }
    """
    type_info = detect_instrument_type(file_path, encoding=encoding)
    mass_info = get_mass(file_path, filename=os.path.basename(file_path))

    data_start, cols = _find_data_start(file_path, encoding=encoding)
    df = pd.read_csv(file_path, encoding=encoding, skiprows=data_start, header=None, names=cols)

    moment_col = MOMENT_COLUMN_BY_TYPE.get(type_info['instrument_type'], 'Moment (emu)')
    if moment_col not in df.columns:
        raise ValueError(
            f"Expected moment column '{moment_col}' for instrument type "
            f"'{type_info['instrument_type']}' not found in {file_path}. "
            f"Available columns: {list(df.columns)}"
        )

    center_position = df['Center Position (mm)'].values if 'Center Position (mm)' in df.columns else None

    return {
        'instrument_type': type_info['instrument_type'],
        'mass_g': mass_info['mass_g'],
        'mass_source': mass_info['source'],
        'mass_confidence': mass_info['confidence'],
        'H': df['Magnetic Field (Oe)'].values,
        'T': df['Temperature (K)'].values,
        'M': df[moment_col].values,
        'center_position': center_position,
        'moment_column_used': moment_col,
        'n_rows': len(df),
    }


def process_vsm_file(file_path, encoding='latin-1', segmenter_window=80,
                      density_g_cm3=None, demag_dimensions_mm=None):
    """
    Full pipeline: load -> segment -> annotate each segment with
    quality flags -> attach type-specific physical features -> compute
    file-level temperature coefficients if multiple valid MH segments
    exist (e.g. a multi-temperature Hc/Mr series in one file, confirmed
    on real data: HD334/HD336).

    density_g_cm3, demag_dimensions_mm: OPTIONAL, both required together
    to compute BH_max for cuboid samples. Deliberately NOT defaulted to
    any assumed value -- confirmed directly that density varies
    meaningfully by real composition (e.g. 7.51-7.61 g/cm^3 depending on
    recycled-material fraction) and must be a genuine per-sample input,
    not assumed. Most samples in this project are needle-shaped, where
    shape anisotropy is negligible and this correction isn't needed at
    all -- leave both as None for those (the default), and BH_max simply
    won't be computed.

    demag_dimensions_mm: (full_a, full_b, full_c) in mm, matching
    vsm_bhmax.demag_factor_prozorov_kogan()'s exact convention --
    confirmed on real data that swapping which physical dimension plays
    which of these two roles changes the demagnetizing factor by
    roughly 2x, so the caller must supply these already correctly
    assigned to their own real sample geometry, not guessed here.

    Returns a dict:
        {
            'file_path': str,
            'instrument_type': str,
            'mass_g': float or None,
            'mass_source': str,
            'mass_confidence': str or None,
            'n_rows': int,
            'segments': [ {type, start, end, n_self_centering_events,
                           is_HT_transition, features}, ... ],
            'temperature_coefficients': {
                'alpha_Hc': {...} or None,
                'beta_Mr': {...} or None,
            } or None (if fewer than 2 valid MH segments with distinct T)
            'entropy_change': {
                'suitable': bool, 'reason': str or None, 'n_isotherms': int,
                'results': {target_field_Oe: (T_mid_array, delta_Sm_array)} or None
            } or None (if fewer than 2 MH segments at all). See
            vsm_entropy_integration.py -- 'suitable' distinguishes a
            genuine multi-isotherm entropy-change file (e.g.
            YCo5_120_MH.dat) from a multi-temperature FULL-LOOP file
            meant for temperature_coefficients instead (e.g.
            HD334/HD336) -- the two look structurally similar (both are
            "multiple MH segments in one file") but are NOT
            interchangeable inputs.
            'demag_factor_N': float or None -- the value actually used,
                for audit trail; None if density/dimensions not supplied.
        }

    'features' on each segment:
      - MH segment: the dict from extract_second_quadrant_hc_mr()
        (Hc, Mr, flag, branch_found), PLUS 'bhmax_kJ_m3' (float or None)
        when density_g_cm3/demag_dimensions_mm were both supplied AND
        Hc/Mr extraction succeeded (flag is None) for this segment --
        BH_max is not attempted on a segment whose own branch/crossing
        detection already failed, since that branch data isn't trustworthy
        either way.
      - MT segment: the dict from extract_mt_candidates() ('branches'
        list of M_extrema/dMdT_extrema candidates -- deliberately not a
        single classified value, see that module's docstring).
      - idle/corrupted segments: features is None -- not a physically
        meaningful segment to extract from.
    """
    loaded = load_vsm_file(file_path, encoding=encoding)

    demag_N = None
    if density_g_cm3 is not None and demag_dimensions_mm is not None:
        full_a, full_b, full_c = demag_dimensions_mm
        demag_N = demag_factor_prozorov_kogan(full_a, full_b, full_c)

    raw_segments = detect_segments(loaded['H'], loaded['T'], window=segmenter_window)

    annotated_segments = []
    mh_T_Hc_Mr = []  # collect for file-level temperature-coefficient fit
    all_mh_segments = []  # collect for entropy-change calc -- needs ALL MH segments'
                           # raw data regardless of Hc/Mr flag status, since entropy
                           # change doesn't use Hc/Mr at all

    for seg in raw_segments:
        annotated = annotate_segment_quality(seg, loaded['H'], loaded['T'], loaded['M'],
                                              center_position=loaded['center_position'])
        start, end = seg['start'], seg['end']
        seg_H, seg_M, seg_T = loaded['H'][start:end], loaded['M'][start:end], loaded['T'][start:end]

        if seg['type'] == 'MH':
            all_mh_segments.append(seg)
            features = extract_second_quadrant_hc_mr(seg_H, seg_M)
            if features['flag'] is None:
                T_nominal = float(np.nanmean(seg_T))
                mh_T_Hc_Mr.append((T_nominal, features['Hc'], features['Mr']))

                if demag_N is not None:
                    branch = find_descending_branch(seg_H)
                    if branch is not None:
                        b_start, b_end = branch
                        branch_H, branch_M = seg_H[b_start:b_end + 1], seg_M[b_start:b_end + 1]
                        bhmax_result = compute_bhmax(
                            branch_H, branch_M, mass_g=loaded['mass_g'],
                            density_g_cm3=density_g_cm3, N=demag_N
                        )
                        features['bhmax_kJ_m3'] = bhmax_result['BHmax_kJ_m3']
                    else:
                        features['bhmax_kJ_m3'] = None
                else:
                    features['bhmax_kJ_m3'] = None
            else:
                features['bhmax_kJ_m3'] = None
        elif seg['type'] == 'MT':
            features = extract_mt_candidates(seg_T, seg_M)
        else:
            features = None

        annotated['features'] = features
        annotated_segments.append(annotated)

    temperature_coefficients = None
    if len(mh_T_Hc_Mr) >= 2 and len(set(t for t, _, _ in mh_T_Hc_Mr)) >= 2:
        T_pts = [t for t, _, _ in mh_T_Hc_Mr]
        Hc_pts = [hc for _, hc, _ in mh_T_Hc_Mr]
        Mr_pts = [mr for _, _, mr in mh_T_Hc_Mr]
        temperature_coefficients = {
            'alpha_Hc': fit_temperature_coefficient(T_pts, Hc_pts),
            'beta_Mr': fit_temperature_coefficient(T_pts, Mr_pts),
        }

    entropy_change = None
    if len(all_mh_segments) >= 2:
        entropy_change = compute_entropy_change_for_file(
            loaded['H'], loaded['T'], loaded['M'], all_mh_segments, loaded['mass_g']
        )

    return {
        'file_path': file_path,
        'instrument_type': loaded['instrument_type'],
        'mass_g': loaded['mass_g'],
        'mass_source': loaded['mass_source'],
        'mass_confidence': loaded['mass_confidence'],
        'n_rows': loaded['n_rows'],
        'segments': annotated_segments,
        'temperature_coefficients': temperature_coefficients,
        'entropy_change': entropy_change,
        'demag_factor_N': demag_N,
        'density_g_cm3': density_g_cm3,
        'demag_dimensions_mm': demag_dimensions_mm,
    }
