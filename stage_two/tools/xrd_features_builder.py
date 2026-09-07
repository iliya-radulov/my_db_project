"""
xrd_features_builder.py

Transforms xrd_analyzer_dev1.analyze_xrd()'s output into rows matching
the xrd_peaks (long format) and xrd_features (fixed-width, ML-ready)
tables defined in 002_xrd_peaks_and_features.sql.

Kept separate from xrd_analyzer_dev1.py deliberately: analysis and
DB-row construction are different concerns, and this module doesn't
touch the database itself (no db connection, no INSERT) — it just
produces plain dicts, ready for whatever DB layer (alloy_db.py) the
main app eventually uses to insert them.
"""

TOP_N_PEAKS = 5
DEFAULT_QUALITY_THRESHOLD = 0.9


def build_xrd_peaks_rows(sample_id, result):
    """
    One row per fitted peak, ranked by intensity (peak_rank=1 is the
    strongest). Matches the xrd_peaks table exactly — safe to pass each
    dict straight to an INSERT.

    result: the dict returned by xrd_analyzer_dev1.analyze_xrd().
    """
    peaks_by_intensity = sorted(
        result['fitted_peaks'], key=lambda p: p['intensity'], reverse=True
    )

    rows = []
    for rank, p in enumerate(peaks_by_intensity, start=1):
        fit = p['fit']
        rows.append({
            'sample_id': sample_id,
            'peak_rank': rank,
            'two_theta': fit['center'],
            'd_spacing_angstrom': fit.get('d_spacing_angstrom'),
            'fwhm_deg': fit['fwhm'],
            'r_squared': fit.get('r_squared'),
            'amplitude': fit['amplitude'],
            'intensity': p['intensity'],
            'crystallite_size_nm': fit.get('crystallite_size_nm'),
            'is_doublet_candidate': False,   # set True separately if
                                              # find_ka2_candidate confirmed
                                              # both position AND amplitude match
            'doublet_partner_peak_id': None,
            'anode': result['anode'],
            'wavelength_ka1_angstrom': result['wavelength'],
            'ka2_stripped': result['ka2_stripped'],
        })
    return rows


def build_xrd_features_row(sample_id, result, top_n=TOP_N_PEAKS,
                            quality_threshold=DEFAULT_QUALITY_THRESHOLD):
    """
    One row per sample — the fixed-width ML input. Top-N peaks by
    intensity become peak1_*, peak2_*, ... columns (NULL-padded if
    fewer than top_n peaks exist). Aggregates (mean_crystallite_size_nm,
    mean_r_squared) are computed ONLY from peaks meeting the quality
    threshold, per the schema's own documented reasoning: real data
    showed ~10-15% of "successfully fitted" peaks scoring R² < 0.7,
    which shouldn't silently drag down a sample's aggregate stats.

    result: the dict returned by xrd_analyzer_dev1.analyze_xrd().
    """
    peaks_by_intensity = sorted(
        result['fitted_peaks'], key=lambda p: p['intensity'], reverse=True
    )

    row = {
        'sample_id': sample_id,
        'n_peaks_total': len(peaks_by_intensity),
        'quality_r_squared_threshold': quality_threshold,
        'anode': result['anode'],
        'ka2_stripped': result['ka2_stripped'],
    }

    high_quality = [
        p for p in peaks_by_intensity
        if p['fit'].get('r_squared') is not None and p['fit']['r_squared'] >= quality_threshold
    ]
    row['n_peaks_high_quality'] = len(high_quality)

    for i in range(top_n):
        prefix = f'peak{i+1}_'
        if i < len(peaks_by_intensity):
            fit = peaks_by_intensity[i]['fit']
            row[prefix + 'two_theta'] = fit['center']
            row[prefix + 'd_spacing'] = fit.get('d_spacing_angstrom')
            row[prefix + 'fwhm'] = fit['fwhm']
            row[prefix + 'intensity'] = peaks_by_intensity[i]['intensity']
            row[prefix + 'r_squared'] = fit.get('r_squared')
            row[prefix + 'crystallite_size_nm'] = fit.get('crystallite_size_nm')
        else:
            # NULL-pad: this sample simply has fewer than top_n peaks
            for suffix in ['two_theta', 'd_spacing', 'fwhm', 'intensity',
                            'r_squared', 'crystallite_size_nm']:
                row[prefix + suffix] = None

    if high_quality:
        sizes = [p['fit']['crystallite_size_nm'] for p in high_quality
                  if p['fit'].get('crystallite_size_nm') is not None]
        r2s = [p['fit']['r_squared'] for p in high_quality]
        row['mean_crystallite_size_nm'] = sum(sizes) / len(sizes) if sizes else None
        row['mean_r_squared'] = sum(r2s) / len(r2s)
    else:
        row['mean_crystallite_size_nm'] = None
        row['mean_r_squared'] = None

    return row
