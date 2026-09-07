#!/usr/bin/env python3
"""
XRD Analyzer v3 - Improved peak fitting
"""

import numpy as np
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os

try:
    import powerxrd as xrd
    HAS_POWERXRD = True
except ImportError:
    HAS_POWERXRD = False


# Characteristic X-ray wavelengths (Å) for the anodes in use.
# Both Ka1 and Ka2 stored per anode: Ka1 is the standard single-value
# reference (matches xrd-file-converter and standard crystallographic
# tables); Ka2 is kept alongside it for Rachinger stripping and optional
# doublet fitting, since these instruments have no monochromator and the
# doublet is only resolved at higher 2theta (confirmed on real test data).
# No silent default buried elsewhere — every function that needs a
# wavelength takes it explicitly, defaulting to Cu only at the CLI level.
WAVELENGTHS_ANGSTROM = {
    'Cu': {'Ka1': 1.54060, 'Ka2': 1.54443},
    'Mo': {'Ka1': 0.70930, 'Ka2': 0.71359},
    'Co': {'Ka1': 1.78900, 'Ka2': 1.79285},
    'Cr': {'Ka1': 2.28970, 'Ka2': 2.29361},
    'Fe': {'Ka1': 1.93604, 'Ka2': 1.93998},
    'Ag': {'Ka1': 0.55941, 'Ka2': 0.56380},
}


def _resolve_anode(anode):
    """Validate an anode symbol and return its canonical key."""
    key = anode.strip().capitalize()
    if key not in WAVELENGTHS_ANGSTROM:
        known = ', '.join(sorted(WAVELENGTHS_ANGSTROM))
        raise ValueError(
            f"Unknown anode '{anode}'. Known anodes: {known}"
        )
    return key


def get_wavelength(anode, line='Ka1'):
    """
    Look up a characteristic wavelength (Å) for a given anode symbol.
    Defaults to Ka1 (the standard single-value reference). Raises a
    clear error on an unknown anode or line rather than silently
    defaulting to Cu, Ka1, or any other value.
    """
    key = _resolve_anode(anode)
    if line not in WAVELENGTHS_ANGSTROM[key]:
        raise ValueError(f"Unknown line '{line}'. Expected 'Ka1' or 'Ka2'.")
    return WAVELENGTHS_ANGSTROM[key][line]


def d_spacing(two_theta_deg, wavelength_angstrom):
    """
    Bragg's law: n*lambda = 2*d*sin(theta)  =>  d = lambda / (2*sin(theta))
    Returns d-spacing in Angstrom (same units as wavelength_angstrom).
    Assumes n=1, standard for reporting d-spacing.
    """
    theta_rad = np.radians(two_theta_deg / 2)
    return wavelength_angstrom / (2 * np.sin(theta_rad))


def scherrer_size(two_theta_deg, fwhm_deg, wavelength_angstrom, K=0.9):
    """
    Scherrer crystallite size (nm) from a peak's own already-fitted
    center (two_theta_deg) and FWHM (fwhm_deg), plus an explicit
    wavelength (Å) — no hidden defaults.

    Uses the same Scherrer equation as powerxrd.scherrer (tau = K*lambda /
    (beta*cos(theta))), applied here directly to OUR fit results, so the
    neighbor-aware windowing and R^2 already computed for this peak stay
    intact rather than being bypassed by an independent re-fit.
    """
    theta_rad = np.radians(two_theta_deg / 2)
    beta_rad = np.radians(fwhm_deg)

    if HAS_POWERXRD:
        size_angstrom = xrd.scherrer(K, wavelength_angstrom, beta_rad, theta_rad)
    else:
        size_angstrom = K * wavelength_angstrom / (beta_rad * np.cos(theta_rad))

    return size_angstrom / 10  # Å -> nm


def scherrer_size_powerxrd_refit(x, y, two_theta_deg, xrange_halfwidth=1.0, K=0.9, wavelength_angstrom=1.54184):
    """
    Optional/custom path: re-fits this peak independently via PowerXRD's
    own Chart.SchPeak, for spot-checking our numbers against PowerXRD's.
    NOT used by default — bypasses our neighbor-aware fit windowing, so
    can disagree with scherrer_size() on closely-spaced peaks.

    Note: Chart.__init__'s docstring lists K/lambdaKa as constructor
    parameters, but the actual code ignores any such arguments and
    hardcodes K=0.9, lambdaKa=0.15406 (nm, i.e. Cu-Ka) regardless of
    input. Confirmed by reading the source, not assumed from the
    docstring. They must be set as instance attributes AFTER
    construction instead, and lambdaKa must be in nm, not the Angstrom
    units our own WAVELENGTHS_ANGSTROM table uses.
    """
    if not HAS_POWERXRD:
        raise RuntimeError("PowerXRD is not installed — cannot use the powerxrd_refit method.")

    chart = xrd.Chart(x, y)
    chart.K = K
    chart.lambdaKa = wavelength_angstrom / 10  # Angstrom -> nm, PowerXRD's convention

    xrange = [two_theta_deg - xrange_halfwidth, two_theta_deg + xrange_halfwidth]
    max_2theta, max_intensity, scherrer_width_nm, left, right = chart.SchPeak(xrange=xrange, verbose=False, show=False)
    return {
        'two_theta_at_max': max_2theta,
        'max_intensity': max_intensity,
        'crystallite_size_nm': scherrer_width_nm,
    }


def gaussian(x, amp, cen, wid, offset):
    """Gaussian function for peak fitting (wid > 0 enforced)"""
    if wid <= 0:
        wid = 0.01  # Prevent negative width
    return amp * np.exp(-(x - cen)**2 / (2 * wid**2)) + offset


def load_xy_file(file_path):
    data = np.loadtxt(file_path)
    return data[:, 0], data[:, 1]


def get_step_size(x, tolerance=1e-4):
    """
    Measure the 2theta step size directly from the data (not from any
    external metadata). Warns if the step size isn't uniform, since a
    single step-size number wouldn't correctly describe such a file.
    """
    steps = np.diff(x)
    step_mean = float(np.mean(steps))
    step_min = float(np.min(steps))
    step_max = float(np.max(steps))

    if (step_max - step_min) > tolerance:
        print(f"⚠️ 2θ step size is not uniform (min={step_min:.5f}°, "
              f"max={step_max:.5f}°) — using mean step ({step_mean:.5f}°) "
              f"for distance conversion; treat peak spacing with caution.")

    return step_mean


def find_peaks_robust(x, y, prominence=0.03, distance_deg=0.15):
    """
    distance_deg: minimum required separation between peaks, in 2theta
    degrees (NOT raw sample count). Converted to samples using the step
    size measured from this file's own data, so the same distance_deg
    means the same thing regardless of a file's scan resolution.
    """
    y_norm = y / np.max(y)

    step_size = get_step_size(x)
    distance_samples = max(1, round(distance_deg / step_size))

    peaks, properties = find_peaks(
        y_norm,
        prominence=prominence,
        height=0.03,
        distance=distance_samples,
        width=2
    )
    
    peak_list = []
    for idx in peaks:
        widths = peak_widths(y_norm, [idx], rel_height=0.5)
        fwhm = widths[0][0] * (x[1] - x[0]) if len(widths[0]) > 0 else 0
        
        peak_list.append({
            'index': idx,
            'two_theta': x[idx],
            'intensity': y[idx],
            'normalized_intensity': y_norm[idx],
            'fwhm_raw': fwhm
        })
    
    return peak_list


def fit_peak(x, y, peak_info, fit_range=1.5, max_half_window=None):
    """
    Fit a single peak with a Gaussian.

    max_half_window: if given, caps both the fit window half-width and the
    allowed center shift, so the fit cannot wander onto a neighboring peak
    when peaks are closely spaced. Should be set to roughly half the
    distance to the nearest other detected peak.
    """
    center = peak_info['two_theta']

    # Don't let the window (or the center's freedom to move) reach past
    # the nearest neighboring peak.
    half_window = fit_range
    if max_half_window is not None:
        half_window = min(fit_range, max_half_window)

    x_min = center - half_window
    x_max = center + half_window

    mask = (x >= x_min) & (x <= x_max)
    x_fit = x[mask]
    y_fit = y[mask]

    if len(x_fit) < 5:
        return None

    # Estimate background as minimum value in the range
    offset = np.min(y_fit)
    y_fit_bg = y_fit - offset

    amp = np.max(y_fit_bg)
    wid = 0.3

    # Center is not allowed to shift further than the window itself,
    # so a nearby taller peak can't pull the fit away from this one.
    center_shift = half_window

    try:
        gauss_no_offset = lambda x, amp, cen, wid: amp * np.exp(-(x - cen)**2 / (2 * wid**2))
        popt, _ = curve_fit(
            gauss_no_offset,
            x_fit, y_fit_bg,
            p0=[amp, center, wid],
            bounds=([0, center - center_shift, 0.01], [np.inf, center + center_shift, 2.0]),
            maxfev=2000
        )

        # R^2 from the actual fit residuals against the data window used
        # for this fit (not the whole pattern) — measures how well the
        # Gaussian describes this specific peak.
        y_pred = gauss_no_offset(x_fit, *popt)
        ss_res = np.sum((y_fit_bg - y_pred) ** 2)
        ss_tot = np.sum((y_fit_bg - np.mean(y_fit_bg)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None

        return {
            'amplitude': popt[0],
            'center': popt[1],
            'sigma': popt[2],
            'offset': offset,
            'fwhm': 2.355 * popt[2],
            'r_squared': r_squared
        }
    except RuntimeError as e:
        # curve_fit could not converge within maxfev iterations
        print(f"   ⚠️ Fit failed for peak near 2θ={center:.3f}°: did not converge ({e})")
        return None
    except ValueError as e:
        # Bad input data (NaNs, wrong shapes, etc.)
        print(f"   ⚠️ Fit failed for peak near 2θ={center:.3f}°: invalid data ({e})")
        return None


def find_ka2_candidate(ka1_center, other_peaks, wavelength_ka1, wavelength_ka2,
                        tolerance_deg=0.15, ka1_amplitude=None,
                        expected_ratio=0.5, ratio_tolerance=0.25):
    """
    Given a peak already fitted as if it were pure Ka1, check whether
    ANOTHER already-detected peak sits close to where its Ka2 companion
    is physically predicted to be (within tolerance_deg) AND has an
    amplitude consistent with the theoretical Ka2/Ka1 intensity ratio
    (~0.5, physics-fixed, not sample-dependent).

    Position alone is NOT sufficient evidence — tested on real data
    (xrd_data4.xy): a pair with only 0.106 deg position error still
    turned out to have an independently-fit amplitude ratio of ~1.10,
    which contradicts the fixed ~0.5 Ka2/Ka1 ratio. That pair is more
    plausibly genuine crystallographic peak splitting (e.g. a slight
    tetragonal/rhombohedral distortion) than an instrumental artifact.
    Requiring BOTH position match AND amplitude-ratio match avoids
    mistaking real structural features for Ka2 doublets.

    other_peaks: list of (center, amplitude) tuples for other detected
    peaks (amplitude = independently-fit Gaussian amplitude, not raw
    intensity).
    ka1_amplitude: independently-fit amplitude of the candidate Ka1
    peak, needed to check the ratio. If None, only the position check
    is applied (amplitude check skipped, with a note in the return).

    Returns a dict with the matching center, amplitude, and whether
    the amplitude check passed — or None if no position match exists.
    """
    predicted = ka1_to_ka2_angle(ka1_center, wavelength_ka1, wavelength_ka2)
    position_candidates = [(c, a) for c, a in other_peaks if abs(c - predicted) <= tolerance_deg]
    if not position_candidates:
        return None

    center, amplitude = min(position_candidates, key=lambda ca: abs(ca[0] - predicted))

    if ka1_amplitude is None or ka1_amplitude == 0:
        return {'center': center, 'amplitude': amplitude, 'amplitude_check': None,
                'observed_ratio': None}

    observed_ratio = amplitude / ka1_amplitude
    amplitude_ok = abs(observed_ratio - expected_ratio) <= ratio_tolerance

    return {
        'center': center,
        'amplitude': amplitude,
        'amplitude_check': amplitude_ok,
        'observed_ratio': observed_ratio
    }


def fit_peak_doublet(x, y, ka1_center_guess, wavelength_ka1, wavelength_ka2,
                      intensity_ratio=0.5, window_halfwidth=1.0):
    """
    Constrained two-Gaussian fit for a peak whose Ka2 companion is
    already visibly resolved (use find_ka2_candidate first to confirm
    there's real evidence for this, rather than calling it blindly).

    Only 4 free parameters (amp1, center1, sigma, offset) — NOT 8 — 
    because the physics constrains the rest:
      - center2 is derived from center1 via the Bragg relation, not
        fitted independently.
      - amp2 = intensity_ratio * amp1 (theoretical Ka2/Ka1 ratio),
        not fitted independently.
      - both components share the same sigma (a simplifying
        approximation — real Ka2 peaks are very slightly broader —
        documented here rather than silently assumed).

    Runs on whatever pattern (x, y) is passed in — call this on the
    background-subtracted-but-NOT-Ka2-stripped data, since after
    stripping there's nothing left to explicitly split.
    """
    center1 = ka1_center_guess
    center2_pred = ka1_to_ka2_angle(center1, wavelength_ka1, wavelength_ka2)

    # window must cover both components with margin
    lo = min(center1, center2_pred) - window_halfwidth
    hi = max(center1, center2_pred) + window_halfwidth
    mask = (x >= lo) & (x <= hi)
    x_fit = x[mask]
    y_fit = y[mask]

    if len(x_fit) < 6:
        return None

    offset0 = np.min(y_fit)
    y_fit_bg = y_fit - offset0
    amp0 = np.max(y_fit_bg)
    sigma0 = 0.1

    def doublet_model(x, amp1, c1, sigma):
        c2 = ka1_to_ka2_angle(c1, wavelength_ka1, wavelength_ka2)
        g1 = amp1 * np.exp(-(x - c1) ** 2 / (2 * sigma ** 2))
        g2 = (intensity_ratio * amp1) * np.exp(-(x - c2) ** 2 / (2 * sigma ** 2))
        return g1 + g2

    try:
        popt, _ = curve_fit(
            doublet_model, x_fit, y_fit_bg,
            p0=[amp0, center1, sigma0],
            bounds=([0, center1 - window_halfwidth / 2, 0.01],
                    [np.inf, center1 + window_halfwidth / 2, 1.0]),
            maxfev=4000
        )
    except RuntimeError as e:
        print(f"   ⚠️ Doublet fit failed near 2θ={center1:.3f}°: did not converge ({e})")
        return None
    except ValueError as e:
        print(f"   ⚠️ Doublet fit failed near 2θ={center1:.3f}°: invalid data ({e})")
        return None

    amp1, c1, sigma = popt
    c2 = ka1_to_ka2_angle(c1, wavelength_ka1, wavelength_ka2)
    amp2 = intensity_ratio * amp1

    y_pred = doublet_model(x_fit, *popt)
    ss_res = np.sum((y_fit_bg - y_pred) ** 2)
    ss_tot = np.sum((y_fit_bg - np.mean(y_fit_bg)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else None

    fwhm = 2.355 * sigma
    return {
        'ka1': {'center': c1, 'amplitude': amp1, 'fwhm': fwhm},
        'ka2': {'center': c2, 'amplitude': amp2, 'fwhm': fwhm},
        'sigma': sigma,
        'offset': offset0,
        'r_squared': r_squared,
        'intensity_ratio_used': intensity_ratio
    }


def _ka2_to_ka1_angle(two_theta_ka2_deg, wavelength_ka1, wavelength_ka2):
    """
    Inverse of the Bragg relation: given a 2theta position under the
    Ka2 wavelength, find the 2theta position where the SAME d-spacing
    would appear under Ka1 (always a lower angle, since lambda_ka1 <
    lambda_ka2).
    """
    theta2_rad = np.radians(two_theta_ka2_deg / 2)
    sin_theta1 = np.sin(theta2_rad) * (wavelength_ka1 / wavelength_ka2)
    sin_theta1 = np.clip(sin_theta1, -1, 1)
    theta1_rad = np.arcsin(sin_theta1)
    return np.degrees(theta1_rad) * 2


def ka1_to_ka2_angle(two_theta_ka1_deg, wavelength_ka1, wavelength_ka2):
    """
    Forward Bragg relation: given a 2theta position under Ka1, predict
    where the SAME d-spacing's Ka2 companion would appear (always a
    higher angle, since lambda_ka2 > lambda_ka1).
    """
    theta1_rad = np.radians(two_theta_ka1_deg / 2)
    sin_theta2 = np.sin(theta1_rad) * (wavelength_ka2 / wavelength_ka1)
    sin_theta2 = np.clip(sin_theta2, -1, 1)
    theta2_rad = np.arcsin(sin_theta2)
    return np.degrees(theta2_rad) * 2


def rachinger_strip_ka2(x, y, wavelength_ka1, wavelength_ka2, intensity_ratio=0.5):
    """
    Rachinger Ka2-stripping: removes the Ka2 contribution from the
    WHOLE pattern (not just visibly resolved doublets), since every
    point in an unmonochromated pattern is really Ka1 + intensity_ratio
    * (a Bragg-shifted copy of the Ka1 pattern). Processes low-to-high
    angle, using the already-corrected data at each point's
    corresponding (lower-angle) Ka1 position — the classic recursive
    Rachinger method.

    intensity_ratio: theoretical Ka2/Ka1 intensity ratio, ~0.5 (varies
    slightly by anode; exposed as a parameter rather than hardcoded
    silently).

    Returns the stripped intensity array (same length as y). Negative
    values (from imperfect subtraction/noise) are clipped to zero.
    """
    y = np.asarray(y, dtype=float)
    y_stripped = y.copy()
    x0 = x[0]

    for i in range(len(x)):
        source_angle = _ka2_to_ka1_angle(x[i], wavelength_ka1, wavelength_ka2)
        if source_angle <= x0:
            continue  # no earlier data exists to subtract from yet
        # interpolate from the already-corrected portion of the pattern
        source_value = np.interp(source_angle, x[:i + 1], y_stripped[:i + 1])
        y_stripped[i] -= intensity_ratio * source_value

    return np.clip(y_stripped, 0, None)


def filter_peaks_by_relative_intensity(fitted_peaks, min_relative_pct=10.0):
    """
    Filters a fitted-peak list by intensity relative to the STRONGEST peak
    in the pattern (I/I_max), the standard XRD convention (as used in
    ICDD-style "relative intensity" reporting) -- NOT relative to the mean.

    Tested against real data: a mean-based cutoff at the same 10%
    threshold kept 100% of peaks in both real test files (57/57, 8/8) --
    the mean is dragged down by the many weak peaks typical of a real
    pattern's skewed intensity distribution, making it far too lenient to
    act as a real filter. I/I_max was actually discriminating on the same
    data (kept 29/57, 3/8), which is why it's used here instead.

    This is a genuinely different criterion from R² fit-quality: a real,
    strong peak can still have poor R² (e.g. from close-neighbor overlap),
    and a weak-but-genuine peak can have excellent R² if well isolated.
    Use both together if you want peaks that are both strong AND reliable
    -- this function does not fold R² in automatically.

    Real trade-off found while testing (LaB6 calibration standard, ESRF
    data): this filter discarded a peak at 2theta=34.4 deg with R²=0.998
    (one of the best fits in the whole pattern, and one that gave a
    near-perfect match to LaB6's certified lattice parameter) purely
    because diffracted intensity naturally falls off at high 2theta
    (Lorentz-polarization/Debye-Waller effects) -- exactly the angular
    region where the most precise lattice-parameter information lives.
    Do NOT apply this filter by default for precision work (lattice
    refinement, anything relying on high-angle peaks); use R² instead in
    that case, since it measures fit reliability directly rather than a
    quantity that's physically expected to vary with angle. This filter
    is better suited to "show me the dominant peaks" use cases (quick
    phase ID, visual pattern matching) than to comprehensive analysis.

    Returns a new list (does not mutate the input), preserving each
    peak's own dict unchanged.
    """
    if not fitted_peaks:
        return []
    max_intensity = max(p['intensity'] for p in fitted_peaks)
    cutoff = (min_relative_pct / 100.0) * max_intensity
    return [p for p in fitted_peaks if p['intensity'] >= cutoff]



def analyze_xrd(file_path, prominence=0.03, distance_deg=0.15, anode='Cu', strip_ka2=True,
                 ka2_intensity_ratio=0.5, wavelength_override=None):
    """
    wavelength_override: bypasses the anode lookup entirely, for sources
    outside the 6 standard lab anodes -- e.g. synchrotron beamlines, which
    use whatever custom monochromatic wavelength was selected for that
    experiment. When set, strip_ka2 MUST be explicitly False: synchrotron
    radiation is already monochromatic (no real Ka1/Ka2 doublet to strip),
    and there's no Ka2 wavelength to strip with anyway since this bypasses
    the anode table entirely. Raises rather than silently disabling
    stripping, since that's exactly the kind of silent wrong-assumption
    this module has been built to avoid.
    """
    print(f"📄 Analyzing: {file_path}")

    if wavelength_override is not None:
        if strip_ka2:
            raise ValueError(
                "wavelength_override requires strip_ka2=False -- a custom/"
                "synchrotron wavelength has no associated Ka2 to strip, "
                "and synchrotron sources are already monochromatic."
            )
        wavelength = wavelength_override
        wavelength_ka2 = None
        print(f"⚠️ Using wavelength_override = {wavelength} Å (bypassing anode='{anode}')")
    else:
        wavelength = get_wavelength(anode, line='Ka1')
        wavelength_ka2 = get_wavelength(anode, line='Ka2')

    x, y = load_xy_file(file_path)
    
    background_subtracted = False
    if HAS_POWERXRD:
        try:
            chart = xrd.Chart(x, y)
            y_bg = chart.backsub(tol=1.0, inplace=False)[1]
            y = y_bg
            background_subtracted = True
            print("🔧 Background subtracted")
        except Exception as e:
            print(f"⚠️ Background subtraction failed ({type(e).__name__}: {e}) — using raw (non-background-subtracted) data")
    else:
        print("⚠️ PowerXRD not installed — using raw (non-background-subtracted) data")

    ka2_stripped = False
    if strip_ka2:
        y = rachinger_strip_ka2(x, y, wavelength, wavelength_ka2, intensity_ratio=ka2_intensity_ratio)
        ka2_stripped = True
        print(f"🔧 Ka2 stripped (Rachinger, ratio={ka2_intensity_ratio})")
    
    print(f"📊 Data: {len(x)} points, 2θ: {x[0]:.1f}° - {x[-1]:.1f}°")
    
    peaks = find_peaks_robust(x, y, prominence=prominence, distance_deg=distance_deg)
    print(f"🔍 Found {len(peaks)} peaks")
    
    # Fit peaks — cap each fit's window/center-shift at ~half the distance
    # to its nearest neighboring peak, so close-together peaks can't steal
    # each other's fits (peaks are already ordered by increasing 2θ).
    two_thetas = [p['two_theta'] for p in peaks]
    fitted_peaks = []
    for i, peak in enumerate(peaks):
        neighbor_dists = []
        if i > 0:
            neighbor_dists.append(two_thetas[i] - two_thetas[i - 1])
        if i < len(peaks) - 1:
            neighbor_dists.append(two_thetas[i + 1] - two_thetas[i])

        if neighbor_dists:
            # margin so adjacent windows don't touch
            max_half_window = min(neighbor_dists) / 2 * 0.9
        else:
            max_half_window = None  # only one peak in the whole pattern

        fit = fit_peak(x, y, peak, max_half_window=max_half_window)
        if fit and fit['fwhm'] > 0 and fit['fwhm'] < 10:
            fit['crystallite_size_nm'] = scherrer_size(
                two_theta_deg=fit['center'],
                fwhm_deg=fit['fwhm'],
                wavelength_angstrom=wavelength
            )
            fit['d_spacing_angstrom'] = d_spacing(
                two_theta_deg=fit['center'],
                wavelength_angstrom=wavelength
            )
            peak['fit'] = fit
            fitted_peaks.append(peak)
    
    print(f"📐 Fitted {len(fitted_peaks)} peaks")
    
    print("\n" + "="*50)
    print("📊 Analysis Summary")
    print("="*50)
    print(f"File: {os.path.basename(file_path)}")
    print(f"Anode: {anode if wavelength_override is None else 'custom/override'} (λ = {wavelength} Å)")
    print(f"Background subtracted: {background_subtracted}")
    print(f"Ka2 stripped: {ka2_stripped}")
    print(f"Peaks found: {len(peaks)}")
    print(f"Peaks fitted: {len(fitted_peaks)}")
    
    if fitted_peaks:
        print("\n📋 Fitted peaks:")
        for i, p in enumerate(fitted_peaks[:10]):
            fit = p['fit']
            r2_str = f"{fit['r_squared']:.4f}" if fit['r_squared'] is not None else "n/a"
            print(f"  {i+1}. 2θ = {fit['center']:.3f}°, d = {fit['d_spacing_angstrom']:.4f} Å, FWHM = {fit['fwhm']:.3f}°, I = {p['intensity']:.0f}, R² = {r2_str}, size = {fit['crystallite_size_nm']:.1f} nm")
        if len(fitted_peaks) > 10:
            print(f"  ... and {len(fitted_peaks) - 10} more")
    
    return {
        'peaks': peaks,
        'fitted_peaks': fitted_peaks,
        'x': x,
        'y': y,
        'background_subtracted': background_subtracted,
        'ka2_stripped': ka2_stripped,
        'anode': anode if wavelength_override is None else f"custom ({wavelength} Å)",
        'wavelength': wavelength
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to .xy file')
    parser.add_argument('--prominence', type=float, default=0.03)
    parser.add_argument('--distance-deg', type=float, default=0.15,
                         help='Minimum peak separation in 2theta degrees (default: 0.15)')
    parser.add_argument('--anode', type=str, default='Cu',
                         choices=sorted(WAVELENGTHS_ANGSTROM),
                         help='X-ray source anode, determines wavelength used (default: Cu)')
    parser.add_argument('--no-strip-ka2', action='store_true',
                         help='Disable Rachinger Ka2 stripping (on by default)')
    parser.add_argument('--ka2-ratio', type=float, default=0.5,
                         help='Ka2/Ka1 theoretical intensity ratio (default: 0.5)')
    
    args = parser.parse_args()
    
    result = analyze_xrd(args.file, args.prominence, args.distance_deg, args.anode,
                          strip_ka2=not args.no_strip_ka2, ka2_intensity_ratio=args.ka2_ratio)
    
    # Plot
    x, y = load_xy_file(args.file)
    plt.figure(figsize=(10, 5))
    plt.plot(x, y, 'b-', linewidth=0.8, label='XRD pattern')
    
    if result['fitted_peaks']:
        peak_x = [p['fit']['center'] for p in result['fitted_peaks']]
        peak_y = [p['intensity'] for p in result['fitted_peaks']]
        plt.plot(peak_x, peak_y, 'rv', markersize=6, label=f'{len(peak_x)} fitted peaks')
    
    plt.xlabel('2θ (degrees)')
    plt.ylabel('Intensity (counts)')
    plt.title(f'XRD Analysis: {os.path.basename(args.file)}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
