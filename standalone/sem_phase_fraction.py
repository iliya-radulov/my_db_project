"""
sem_phase_fraction.py

Phase-fraction analysis for SEM BSE/COMPO images -- steps 3-4 of the
original 5-step SEM plan (phase separation, phase fraction), the
actual goal behind the multi-instrument metadata work: quantify what
fraction of the imaged area is a bright secondary phase (e.g. the
Nd-rich intergranular phase in NdFeB magnets) versus the matrix.

Uses Otsu's method (a standard, well-established automatic threshold
selection technique for bimodal intensity distributions) rather than
edge-detection/watershed -- phase fraction is fundamentally a
thresholding question (which pixels belong to which phase), not a
boundary-tracing one.

Handles both 8-bit (Zeiss, JEOL) and 16-bit (Tescan -- confirmed real,
not assumed) source images consistently: normalizes to 8-bit using
each image's OWN actual min/max before segmentation, since only
relative contrast matters for phase separation, not absolute intensity
values (which differ across instruments/settings anyway).

Uses sem_metadata_universal.py for footer cropping and calibration --
built on the now-solved multi-instrument metadata layer, not a
separate implementation.
"""

import numpy as np
import cv2

from sem_metadata_universal import parse_sem_metadata_universal
from sem_grain_analyzer import crop_databar_footer


def load_and_normalize(tif_path, metadata):
    """
    Loads a SEM image and normalizes it to 8-bit for consistent
    downstream processing, regardless of source bit depth.

    Crops the databar footer using metadata['footer_crop_row'] when
    available (JEOL, Tescan -- exact, confirmed against real pixel
    data) rather than the brightness-heuristic auto-detection (which
    remains the fallback for Zeiss, where no direct metadata field
    gives this).

    Returns (image_8bit, footer_detected: bool).
    """
    raw = cv2.imread(tif_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise ValueError(f"Could not load image: {tif_path}")

    # IMREAD_UNCHANGED (needed to preserve 16-bit depth for Tescan) can
    # still return a multi-channel image for palette-mode TIFFs (e.g.
    # JEOL's 'P' mode) -- confirmed on real data, not assumed. Collapse
    # to single-channel grayscale if so, preserving whatever bit depth
    # was already there.
    if raw.ndim == 3:
        raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)

    footer_row = metadata.get('footer_crop_row')
    if footer_row is not None:
        image = raw[:footer_row, :]
        footer_detected = True
    else:
        image, footer_detected, _ = crop_databar_footer(
            raw.astype(np.uint8) if raw.dtype != np.uint8 else raw
        )
        if raw.dtype != np.uint8:
            # the brightness-heuristic fallback was designed for 8-bit
            # data; re-crop the ORIGINAL (not artificially downcast)
            # array to the row it found, rather than use the downcast
            # copy's pixel values for anything beyond finding that row
            image = raw[:image.shape[0], :]

    if image.dtype != np.uint8:
        img_min, img_max = image.min(), image.max()
        if img_max > img_min:
            image = (255 * (image.astype(np.float64) - img_min) / (img_max - img_min)).astype(np.uint8)
        else:
            image = np.zeros_like(image, dtype=np.uint8)

    return image, footer_detected


def compute_phase_fraction(image_8bit):
    """
    Segments the image into two phases via Otsu's automatic threshold
    and computes the bright phase's area fraction.

    Returns a dict:
        {
            'threshold': int -- the Otsu-selected threshold (0-255),
            'bright_phase_fraction': float -- fraction of pixels above
                threshold (0 to 1),
            'matrix_fraction': float -- 1 - bright_phase_fraction,
            'binary_mask': np.array -- the actual segmentation, for
                visual verification (255 = bright phase, 0 = matrix),
        }
    """
    threshold, binary_mask = cv2.threshold(
        image_8bit, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    bright_fraction = float(np.sum(binary_mask == 255)) / binary_mask.size

    return {
        'threshold': int(threshold),
        'bright_phase_fraction': bright_fraction,
        'matrix_fraction': 1.0 - bright_fraction,
        'binary_mask': binary_mask,
    }


def analyze_phase_fraction(tif_path):
    """
    Full pipeline: detect format, load/normalize/crop, segment,
    compute phase fraction.

    Returns a dict combining the metadata (instrument format,
    calibration, etc.) with the phase-fraction result.
    """
    metadata = parse_sem_metadata_universal(tif_path)
    image, footer_detected = load_and_normalize(tif_path, metadata)
    phase_result = compute_phase_fraction(image)

    return {
        'file': tif_path,
        'metadata': metadata,
        'footer_detected': footer_detected,
        'image_shape': image.shape,
        **phase_result,
    }
