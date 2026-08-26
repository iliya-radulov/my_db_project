"""
sem_grain_analyzer.py

Standalone SEM grain-size analysis -- no GUI, no interactive tuning.
Built per explicit project decision (Option C): extract the validated
watershed algorithm from the earlier PyQt5 exploratory tool
(sem_analyzer_gui_v6.py) into a clean, tested, standalone module,
matching the same pattern already used for XRD/VSM (analysis logic
first, GUI/integration decided separately afterward).

Scope, deliberately limited to finish step 2 of the original 5-step
plan properly, not attempt all 5 at once:
  1. Metadata extraction -- already done (parse_sem_v2.py)
  2. Basic grain detection -- THIS MODULE
  3. Phase separation -- deferred
  4. Phase fraction -- deferred
  5. Morphology (aspect ratio, circularity) -- deferred

Two real gaps closed relative to the old exploratory tool:
  - Pixel-to-physical-unit calibration (grain sizes were pixel-only
    before, despite pixel_size_nm already being available in the
    metadata this whole time).
  - A real databar footer, confirmed on real data (identical across
    4 different real files, different magnifications: rows 718-767 of
    a 768-row image), which the old tool never cropped -- meaning its
    edge detection was being run partly on scale-bar/text graphics
    baked into the image, not just the real micrograph.
"""

import re
import os
import numpy as np
import cv2


def parse_pixel_size(pixel_size_str):
    """
    Parses a pixel size string like '11.09 nm' (the format
    parse_sem_v2.py's metadata extraction returns) into a clean float,
    in nanometers. Returns None if it can't be parsed (e.g. metadata
    field was itself None) -- doesn't guess or default silently, since
    a wrong calibration value would silently corrupt every downstream
    physical-unit measurement.
    """
    if pixel_size_str is None:
        return None
    match = re.search(r'([\d.]+)\s*(nm|[uµ]m|mm)', str(pixel_size_str), re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == 'nm':
        return value
    elif unit in ('um', 'µm'):
        return value * 1000.0
    elif unit == 'mm':
        return value * 1_000_000.0
    return None


def crop_databar_footer(image, brightness_drop_threshold=30, min_footer_brightness_below=30):
    """
    Auto-detects and crops a Zeiss-style databar footer baked directly
    into the image pixels (scale bar, magnification, HV/WD text on a
    black background) -- confirmed present and IDENTICAL in location
    across 4 different real test files (different magnifications), not
    assumed. Detected by finding the first row where mean row
    brightness drops sharply from "real micrograph" levels to
    "black databar background" levels.

    Uses auto-detection rather than a hardcoded row count, so this
    stays robust if a different image size/instrument ever produces a
    different footer height, rather than silently cropping the wrong
    amount.

    Returns (cropped_image, footer_detected: bool, crop_row: int or None).
    If no footer is detected (e.g. a genuinely footer-less image), the
    original image is returned unchanged with footer_detected=False.
    """
    row_means = image.mean(axis=1)
    for i in range(len(row_means) - 1):
        if row_means[i] > brightness_drop_threshold * 2 and row_means[i + 1] < min_footer_brightness_below:
            return image[:i + 1, :], True, i + 1
    return image, False, None


def compute_adaptive_canny_thresholds(image, lower_percentile=90, upper_percentile=98):
    """
    Computes Canny thresholds from THIS image's own gradient magnitude
    distribution, rather than using fixed absolute values.

    Necessary correction, confirmed on real data: the old exploratory
    tool's fixed defaults (canny1=50, canny2=150) were tuned against
    whatever image was used during its own development, and FAILED on
    9 of 12 real test images from this project -- each producing
    "1 grain" covering the entire frame (confirmed: for one image, the
    reported single-grain diameter matched the full cropped image area
    almost exactly). Root cause: these real images are genuinely
    low-contrast (std ~5, gradient magnitude maxing out around 100-120),
    so a fixed upper threshold of 150 is literally unreachable -- Canny
    finds essentially no edges (confirmed: 0.02% edge pixels on one
    image) rather than failing loudly, which is what made this
    dangerous to leave as a hidden fixed default.

    Using percentiles of each image's OWN gradient distribution instead
    (a standard technique for exactly this problem) resolved 7 of the 9
    broken cases when tested against real data. Default percentiles
    (90th/98th) were chosen from that same real-data testing, not
    picked arbitrarily.

    Returns (lower, upper) as float threshold values for cv2.Canny.
    """
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    grad_mag = np.sqrt(sobelx ** 2 + sobely ** 2)
    lower = float(np.percentile(grad_mag, lower_percentile))
    upper = float(np.percentile(grad_mag, upper_percentile))
    return lower, upper


def detect_grains(image, canny1=None, canny2=None, dist_thresh=0.5, dilate_iter=2,
                   min_area_px=50, adaptive_canny=True,
                   adaptive_lower_percentile=90, adaptive_upper_percentile=98):
    """
    Core watershed grain-detection algorithm -- Canny edges -> dilation
    -> distance transform -> connected components -> watershed.

    Watershed math itself is UNCHANGED from the working exploratory tool
    (sem_analyzer_gui_v6.py) -- extracted cleanly, not redesigned.

    Canny thresholds default to ADAPTIVE (computed from this image's own
    gradient distribution, see compute_adaptive_canny_thresholds) rather
    than the old tool's fixed defaults -- confirmed necessary on real
    data, not a stylistic preference: the fixed defaults
    (canny1=50, canny2=150) failed on 9 of 12 real test images (see
    compute_adaptive_canny_thresholds docstring for details).

    Pass explicit canny1/canny2 values to override adaptive behavior and
    use fixed thresholds instead (sets adaptive_canny=False
    automatically when both are given).

    Returns (markers, grain_areas_px): the labeled region array from
    cv2.watershed, and a list of per-grain pixel areas (already
    filtered by min_area_px).
    """
    if canny1 is not None and canny2 is not None:
        adaptive_canny = False
    elif adaptive_canny:
        pass  # will compute below
    else:
        # neither adaptive nor explicit thresholds given -- fall back
        # to the old tool's fixed defaults, but this combination isn't
        # recommended given real-data testing showed it fails often
        canny1 = canny1 if canny1 is not None else 50
        canny2 = canny2 if canny2 is not None else 150

    blurred = cv2.GaussianBlur(image, (5, 5), 0)

    if adaptive_canny:
        canny1, canny2 = compute_adaptive_canny_thresholds(
            image, adaptive_lower_percentile, adaptive_upper_percentile
        )

    edges = cv2.Canny(blurred, canny1, canny2)

    kernel = np.ones((3, 3), np.uint8)
    edges_dilated = cv2.dilate(edges, kernel, iterations=dilate_iter)

    inv = cv2.bitwise_not(edges)
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist, dist_thresh * dist.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)

    unknown = cv2.subtract(edges_dilated, sure_fg)

    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0

    img_color = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    markers = cv2.watershed(img_color, markers)

    regions = np.unique(markers)
    regions = regions[regions > 1]  # exclude background (1) and boundary (-1)

    grain_areas_px = []
    for region in regions:
        mask = (markers == region)
        area = int(np.sum(mask))
        if area > min_area_px:
            grain_areas_px.append(area)

    return markers, grain_areas_px


def analyze_sem_grains(file_path, sem_metadata=None, canny1=None, canny2=None,
                        dist_thresh=0.5, dilate_iter=2, min_area_px=50,
                        crop_footer=True, adaptive_canny=True):
    """
    Full pipeline: load image, crop databar footer if present, run
    grain detection (adaptive Canny thresholding by default -- see
    detect_grains), calibrate to real physical units using the
    pixel_size_nm metadata.

    sem_metadata: optionally pass an already-parsed metadata dict (from
    parse_sem_v2.parse_sem_file) to avoid re-parsing the file; if not
    given, this function parses it itself.

    Returns a dict:
        {
            'file': str,
            'footer_detected': bool,
            'pixel_size_nm': float or None,
            'calibrated': bool,  -- False if pixel_size_nm unavailable;
                areas/diameters below are then in pixels² / pixels,
                NOT real units -- caller must check this before
                trusting the units of the returned values
            'n_grains': int,
            'grain_areas': list of float (µm² if calibrated, else px²),
            'grain_diameters': list of float (equivalent circular
                diameter, µm if calibrated, else px),
            'mean_area': float or None,
            'median_area': float or None,
            'mean_diameter': float or None,
            'median_diameter': float or None,
        }
    """
    image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not load image: {file_path}")

    if crop_footer:
        image, footer_detected, _ = crop_databar_footer(image)
    else:
        footer_detected = False

    if sem_metadata is None:
        from parse_sem_v2 import parse_sem_file
        sem_metadata = parse_sem_file(file_path)

    pixel_size_nm = parse_pixel_size(sem_metadata.get('pixel_size_nm'))
    calibrated = pixel_size_nm is not None

    _, grain_areas_px = detect_grains(
        image, canny1=canny1, canny2=canny2, dist_thresh=dist_thresh,
        dilate_iter=dilate_iter, min_area_px=min_area_px,
        adaptive_canny=adaptive_canny
    )

    if calibrated:
        px_area_to_um2 = (pixel_size_nm / 1000.0) ** 2  # nm -> um, then squared
        grain_areas = [a * px_area_to_um2 for a in grain_areas_px]
    else:
        grain_areas = [float(a) for a in grain_areas_px]

    # equivalent circular diameter: d = sqrt(4*area/pi)
    grain_diameters = [np.sqrt(4 * a / np.pi) for a in grain_areas]

    return {
        'file': os.path.basename(file_path),
        'footer_detected': footer_detected,
        'pixel_size_nm': pixel_size_nm,
        'calibrated': calibrated,
        'n_grains': len(grain_areas),
        'grain_areas': grain_areas,
        'grain_diameters': grain_diameters,
        'mean_area': float(np.mean(grain_areas)) if grain_areas else None,
        'median_area': float(np.median(grain_areas)) if grain_areas else None,
        'mean_diameter': float(np.mean(grain_diameters)) if grain_diameters else None,
        'median_diameter': float(np.median(grain_diameters)) if grain_diameters else None,
    }
