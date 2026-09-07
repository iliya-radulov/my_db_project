"""
vsm_db_builder.py

Inserts a process_vsm_file() result into the vsm_* tables
(003_vsm_tables.sql). Unlike xrd_features_builder.py, this CANNOT be a
set of pure row-building functions with no DB connection: the schema's
FK chain (vsm_files -> vsm_segments -> vsm_mh_details/vsm_mt_details ->
vsm_mt_candidates) means child rows need a DB-generated parent id before
they can be built, not just a caller-supplied sample_id. So this module
takes a live connection and does the insert directly, rather than
returning plain dicts for the caller to insert separately.

Uses db_type_utils.sanitize_row() throughout -- same numpy-type lesson
learned during XRD DB integration (psycopg2 has no default adapter for
numpy scalar types, which every analysis module in this project
produces, being numpy-based).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_type_utils import sanitize_row, to_native
import psycopg2.extensions


def insert_vsm_result(conn, sample_id, result):
    """
    Inserts one process_vsm_file() result across all vsm_* tables in a
    single transaction. Returns the new vsm_files.id.

    Does NOT commit -- caller controls the transaction boundary (same
    convention as the XRD integration test), so multiple files can be
    inserted together and rolled back as a unit if anything fails.
    """
    # Explicitly request a plain, index-style cursor (fetchone()[0]),
    # not whatever the connection's default might be. Real-app testing
    # of the XRD integration confirmed the app's own db.cursor uses
    # RealDictCursor (dict rows, e.g. sample['id']) -- if that turns out
    # to be set at the CONNECTION level rather than per-cursor, a plain
    # conn.cursor() call here would silently inherit dict-row behavior
    # and break this function's index-based fetches. Defensive fix,
    # applied before live-testing against the real app, not after
    # hitting it as a bug.
    cur = conn.cursor(cursor_factory=psycopg2.extensions.cursor)

    # 1. vsm_files
    entropy_change = result.get('entropy_change')
    file_row = sanitize_row({
        'sample_id': sample_id,
        'file_path': result['file_path'],
        'instrument_type': result['instrument_type'],
        'mass_g': result['mass_g'],
        'mass_source': result['mass_source'],
        'mass_confidence': result['mass_confidence'],
        'n_rows': result['n_rows'],
        # NULL when entropy-change wasn't even attempted (< 2 MH segments),
        # NOT the same as FALSE (attempted, found unsuitable) -- see migration
        'entropy_change_suitable': entropy_change['suitable'] if entropy_change else None,
        'entropy_change_reason': entropy_change['reason'] if entropy_change else None,
        # NULL for the majority of (needle-shaped) samples -- only
        # populated when the caller explicitly supplied density_g_cm3/
        # demag_dimensions_mm to process_vsm_file()
        'density_g_cm3': result.get('density_g_cm3'),
        'dimension_a_mm': result.get('demag_dimensions_mm')[0] if result.get('demag_dimensions_mm') else None,
        'dimension_b_mm': result.get('demag_dimensions_mm')[1] if result.get('demag_dimensions_mm') else None,
        'dimension_c_mm': result.get('demag_dimensions_mm')[2] if result.get('demag_dimensions_mm') else None,
    })
    cur.execute(
        """INSERT INTO vsm_files (sample_id, file_path, instrument_type, mass_g,
               mass_source, mass_confidence, n_rows, entropy_change_suitable,
               entropy_change_reason, density_g_cm3, dimension_a_mm,
               dimension_b_mm, dimension_c_mm)
           VALUES (%(sample_id)s, %(file_path)s, %(instrument_type)s, %(mass_g)s,
               %(mass_source)s, %(mass_confidence)s, %(n_rows)s,
               %(entropy_change_suitable)s, %(entropy_change_reason)s,
               %(density_g_cm3)s, %(dimension_a_mm)s, %(dimension_b_mm)s,
               %(dimension_c_mm)s)
           RETURNING id""",
        file_row
    )
    vsm_file_id = cur.fetchone()[0]

    # 2. vsm_segments + type-specific details, one segment at a time
    for seg in result['segments']:
        seg_row = sanitize_row({
            'vsm_file_id': vsm_file_id,
            'segment_type': seg['type'],
            'start_row': seg['start'],
            'end_row': seg['end'],
            'n_self_centering_events': seg['n_self_centering_events'],
            'is_HT_transition': seg['is_HT_transition'],
        })
        cur.execute(
            """INSERT INTO vsm_segments (vsm_file_id, segment_type, start_row, end_row,
                   n_self_centering_events, is_ht_transition)
               VALUES (%(vsm_file_id)s, %(segment_type)s, %(start_row)s, %(end_row)s,
                   %(n_self_centering_events)s, %(is_HT_transition)s)
               RETURNING id""",
            seg_row
        )
        segment_id = cur.fetchone()[0]

        features = seg.get('features')
        if seg['type'] == 'MH' and features is not None:
            mh_row = sanitize_row({
                'vsm_segment_id': segment_id,
                'hc_oe': features['Hc'],
                'mr_emu': features['Mr'],
                'hc_mr_flag': features['flag'],
                'branch_found': features['branch_found'],
                'demag_factor_n': result.get('demag_factor_N'),
                'bhmax_kj_m3': features.get('bhmax_kJ_m3'),
            })
            cur.execute(
                """INSERT INTO vsm_mh_details (vsm_segment_id, hc_oe, mr_emu,
                       hc_mr_flag, branch_found, demag_factor_n, bhmax_kj_m3)
                   VALUES (%(vsm_segment_id)s, %(hc_oe)s, %(mr_emu)s,
                       %(hc_mr_flag)s, %(branch_found)s, %(demag_factor_n)s,
                       %(bhmax_kj_m3)s)"""
                ,
                mh_row
            )

        elif seg['type'] == 'MT' and features is not None:
            cur.execute(
                """INSERT INTO vsm_mt_details (vsm_segment_id)
                   VALUES (%s) RETURNING id""",
                (segment_id,)
            )
            mt_details_id = cur.fetchone()[0]

            for branch in features['branches']:
                for c in branch['M_extrema']:
                    cand_row = sanitize_row({
                        'vsm_mt_details_id': mt_details_id,
                        'branch_direction': branch['direction'],
                        'branch_T_min': branch['T_range'][0],
                        'branch_T_max': branch['T_range'][1],
                        'candidate_kind': 'M_extrema',
                        'T_value': c['T'],
                        'value': c['M'],
                        'extremum_kind': c['kind'],
                    })
                    cur.execute(
                        """INSERT INTO vsm_mt_candidates
                               (vsm_mt_details_id, branch_direction, branch_t_min,
                                branch_t_max, candidate_kind, t_value, value, extremum_kind)
                           VALUES (%(vsm_mt_details_id)s, %(branch_direction)s,
                                %(branch_T_min)s, %(branch_T_max)s, %(candidate_kind)s,
                                %(T_value)s, %(value)s, %(extremum_kind)s)""",
                        cand_row
                    )
                for c in branch['dMdT_extrema']:
                    cand_row = sanitize_row({
                        'vsm_mt_details_id': mt_details_id,
                        'branch_direction': branch['direction'],
                        'branch_T_min': branch['T_range'][0],
                        'branch_T_max': branch['T_range'][1],
                        'candidate_kind': 'dMdT_extrema',
                        'T_value': c['T'],
                        'value': c['dMdT'],
                        'extremum_kind': None,
                    })
                    cur.execute(
                        """INSERT INTO vsm_mt_candidates
                               (vsm_mt_details_id, branch_direction, branch_t_min,
                                branch_t_max, candidate_kind, t_value, value, extremum_kind)
                           VALUES (%(vsm_mt_details_id)s, %(branch_direction)s,
                                %(branch_T_min)s, %(branch_T_max)s, %(candidate_kind)s,
                                %(T_value)s, %(value)s, %(extremum_kind)s)""",
                        cand_row
                    )

    # 3. temperature coefficients, if present
    tc = result.get('temperature_coefficients')
    if tc:
        for coeff_type, coeff_data in [('alpha_Hc', tc['alpha_Hc']), ('beta_Mr', tc['beta_Mr'])]:
            tc_row = sanitize_row({
                'vsm_file_id': vsm_file_id,
                'coefficient_type': coeff_type,
                'slope': coeff_data['slope'],
                't_ref': coeff_data['T_ref'],
                'y_ref': coeff_data['Y_ref'],
                'coefficient_pct_per_k': coeff_data['coefficient_pct_per_K'],
                'n_points': coeff_data['n_points'],
                'r_squared': coeff_data['r_squared'],
            })
            cur.execute(
                """INSERT INTO vsm_temperature_coefficients
                       (vsm_file_id, coefficient_type, slope, t_ref, y_ref,
                        coefficient_pct_per_k, n_points, r_squared)
                   VALUES (%(vsm_file_id)s, %(coefficient_type)s, %(slope)s, %(t_ref)s,
                       %(y_ref)s, %(coefficient_pct_per_k)s, %(n_points)s, %(r_squared)s)""",
                tc_row
            )

    # 4. entropy-change points, if the file was suitable and results exist
    if entropy_change and entropy_change['suitable'] and entropy_change['results']:
        for target_field, (T_mid_array, delta_Sm_array) in entropy_change['results'].items():
            for t_mid, dSm in zip(T_mid_array, delta_Sm_array):
                point_row = sanitize_row({
                    'vsm_file_id': vsm_file_id,
                    'target_field_oe': target_field,
                    't_mid_k': t_mid,
                    'delta_sm_j_per_kg_k': dSm,
                })
                cur.execute(
                    """INSERT INTO vsm_entropy_change
                           (vsm_file_id, target_field_oe, t_mid_k, delta_sm_j_per_kg_k)
                       VALUES (%(vsm_file_id)s, %(target_field_oe)s, %(t_mid_k)s,
                           %(delta_sm_j_per_kg_k)s)""",
                    point_row
                )

    cur.close()
    return vsm_file_id
