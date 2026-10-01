"""
overlay.py — Draw a composition marker on a pre-computed ternary PNG.

Uses barycentric interpolation between the three triangle vertex positions
(defined in CALIB) to convert a ternary composition to pixel coordinates,
then draws a red dot on a copy of the PNG.

── Calibration ─────────────────────────────────────────────────────────────
CALIB holds the pixel positions of the three element corners as fractions
of (image_width, image_height).  Defaults are tuned for a 1746×1264 PNG
with standard matplotlib margins and a right-side colorbar.

To verify or adjust:
  1. Open any FENDB_ternary_*K_v3.png in an image editor.
  2. Note the pixel (x, y) of each triangle corner.
  3. Divide x by 1746 and y by 1264 to get the fractions.
  4. Update CALIB below.

Sanity check: run the stoichiometric Nd₂Fe₁₄B composition
(Nd=0.118, Fe=0.824, B=0.059).  The red dot should appear close to
the Fe-rich (bottom-left) corner, shifted about 15% toward Nd and 6%
toward B.
"""

from __future__ import annotations
from pathlib import Path
import io
from PIL import Image, ImageDraw

STAGE3 = Path(__file__).resolve().parent.parent   # stage_three/

# ── Calibration constants ────────────────────────────────────────────────────
# (x_fraction, y_fraction) of each element's corner in the PNG.
# PIL origin = top-left; y increases downward.
CALIB = {
    "fe": (0.370, 0.04),   # Fe = 1  →  TOP vertex
    "b":  (0.030, 0.93),   # B  = 1  →  bottom-LEFT vertex
    "nd": (0.800, 0.93),   # Nd = 1  →  bottom-RIGHT vertex
}
# Layout confirmed from pre-computed PNGs (1746×1264):
#   top = Fe,  bottom-left = B,  bottom-right = Nd


# ── Geometry ─────────────────────────────────────────────────────────────────
def _tern_to_pixel(
    x_nd: float, x_fe: float, x_b: float,
    W: int, H: int,
) -> tuple[int, int]:
    """
    Barycentric interpolation: ternary fractions → pixel (x, y).
    Compositions must already sum to 1.
    """
    fe = (CALIB["fe"][0] * W, CALIB["fe"][1] * H)
    nd = (CALIB["nd"][0] * W, CALIB["nd"][1] * H)
    b  = (CALIB["b"][0]  * W, CALIB["b"][1]  * H)

    px = x_fe * fe[0] + x_nd * nd[0] + x_b * b[0]
    py = x_fe * fe[1] + x_nd * nd[1] + x_b * b[1]
    return round(px), round(py)


# ── Public API ────────────────────────────────────────────────────────────────
def make_overlay(
    T: int,
    x_nd: float,
    x_fe: float,
    x_b: float,
    img_dir: Path | None = None,
    dot_radius: int = 10,
) -> bytes:
    """
    Open the pre-computed ternary PNG for temperature T, draw a red dot
    at the given composition, and return the modified image as PNG bytes.

    Parameters
    ----------
    T         : temperature in K (must match an existing cache PNG)
    x_nd/x_fe/x_b : mole fractions (will be normalized automatically)
    img_dir   : folder containing the PNG files (default: stage_three/plots)
    dot_radius: radius of the composition marker in pixels
    """
    if img_dir is None:
        img_dir = STAGE3 / "plots"

    png_path = img_dir / f"FENDB_ternary_{T}K_v3.png"
    if not png_path.exists():
        raise FileNotFoundError(f"Ternary PNG not found: {png_path}")

    # Normalize
    total = x_nd + x_fe + x_b
    if total <= 0:
        raise ValueError("All composition fractions are zero.")
    x_nd /= total
    x_fe /= total
    x_b  /= total

    img = Image.open(png_path).convert("RGBA")
    W, H = img.size
    px, py = _tern_to_pixel(x_nd, x_fe, x_b, W, H)

    draw = ImageDraw.Draw(img)
    r = dot_radius

    # White halo — visible on any background colour
    draw.ellipse([px-r-2, py-r-2, px+r+2, py+r+2], fill="white")
    # Red filled dot
    draw.ellipse([px-r, py-r, px+r, py+r], fill="#e63946")
    # Thin black outline
    draw.ellipse([px-r, py-r, px+r, py+r], outline="#111111", width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
