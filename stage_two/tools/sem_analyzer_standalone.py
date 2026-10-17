"""
sem_analyzer_standalone.py

Interactive SEM analysis tool: grain size and shape, plus phase fraction,
in one window. It is built on the already-validated modules and adds no new
image-analysis algorithm of its own beyond the per-grain shape measures:

  - sem_metadata_universal.parse_sem_metadata_universal()  format detection
    (Zeiss / JEOL / Tescan), calibration and footer height;
  - sem_phase_fraction.load_and_normalize()                 footer crop, 8-bit;
  - sem_grain_analyzer.detect_grains()                      watershed grains
    (Canny -> dilation -> distance transform -> watershed, adaptive thresholds);
  - Otsu thresholding for the phase fraction (as in
    sem_phase_fraction_standalone.py, which this tool supersedes).

Why this tool exists: the original interactive grain tool (PyQt5) was retired
once its algorithm was extracted into sem_grain_analyzer.py, and the app only
launched the phase-fraction tool. Per-image tuning is a real need here (the
fixed edge thresholds of the old tool failed on most real images), so the
tuning parameters are exposed again, now with live feedback.

Grains tab
  - Edge-threshold percentiles, distance-transform threshold, dilation and
    minimum grain area are adjustable; results update on release.
  - Optional exclusion of grains that touch the image border (their size is
    truncated by the frame), on by default.
  - Per grain: equivalent circular diameter, area, aspect ratio (from the
    second moments), circularity (4*pi*A/P^2; the perimeter of a pixelated
    outline is overestimated, so circularity reads low for small grains).
  - Summary and histograms; sizes in micrometres only when a pixel size is
    known (from the metadata, or typed in by hand); otherwise in pixels.

Phase fraction tab
  - Otsu's threshold as a starting suggestion, a live slider, an invert switch.

Both tabs work on the same region of interest (ROI), so a damaged or
unrepresentative part of an image can be left out.

Saving is explicit and writes to the `properties` table of the file's existing
characterization record (the file must have been imported via the main app):
the selected results replace earlier values of the same names, in one
transaction. The phase fraction is only saved if the operator ticks it, since
an unreviewed Otsu threshold can be wrong in different ways on different
instruments and samples.

Must be run from stage_two/tools/ (or launched from the Data Viewer with the
image path as the first argument), since it imports sibling modules.
"""

import os
import sys
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sem_metadata_universal import parse_sem_metadata_universal
from sem_phase_fraction import load_and_normalize
from sem_grain_analyzer import detect_grains

# property names written by Save (all replaced together when saved again)
GRAIN_PROPERTY_NAMES = (
    "grain_count", "grain_mean_diameter", "grain_median_diameter",
    "grain_mean_aspect_ratio", "grain_mean_circularity",
    "grain_param_dist_thresh", "grain_param_canny_pct_low", "grain_param_canny_pct_high",
    "grain_param_min_area_px", "grain_param_exclude_border",
)
PHASE_PROPERTY_NAMES = ("bright_phase_fraction", "phase_fraction_threshold")


# ---------------------------------------------------------------------------
# Pure functions (no GUI, no database): testable headless
# ---------------------------------------------------------------------------

def load_sem_image(path):
    """Loads an image through the project's metadata/footer logic.
    Returns dict: image (uint8), metadata, footer_detected, pixel_size_nm (float | None)."""
    metadata = parse_sem_metadata_universal(path)
    image, footer_detected = load_and_normalize(path, metadata)
    px = metadata.get("pixel_size_nm")
    return {
        "path": path,
        "image": image,
        "metadata": metadata,
        "footer_detected": bool(footer_detected),
        "pixel_size_nm": float(px) if isinstance(px, (int, float)) and px > 0 else None,
    }


def parse_roi(texts, shape):
    """texts: four strings x0, y0, x1, y1 (pixels, in the footer-cropped image).
    All empty -> None (whole image). Raises ValueError if partly filled or invalid."""
    raw = [str(t).strip() for t in texts]
    if not any(raw):
        return None
    if not all(raw):
        raise ValueError("Fill in all four ROI values (x0, y0, x1, y1) or leave all empty.")
    x0, y0, x1, y1 = (int(float(v)) for v in raw)
    h, w = shape[:2]
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise ValueError(f"ROI must satisfy 0 <= x0 < x1 <= {w} and 0 <= y0 < y1 <= {h}.")
    return x0, y0, x1, y1


def crop_roi(image, roi):
    if roi is None:
        return image
    x0, y0, x1, y1 = roi
    return image[y0:y1, x0:x1]


def grain_shape_table(markers, pixel_size_nm, min_area_px=50, exclude_border=True):
    """
    Per-grain measures from a cv2.watershed marker image (label 1 = background,
    -1 = boundary, >1 = grains; the same convention detect_grains() uses and the
    same area filter: area > min_area_px).

    Returns a list of dicts, one per kept grain:
        label, area_px, area (um^2 if calibrated else px^2), diameter (equivalent
        circular, um or px), aspect_ratio (>= 1, from second moments),
        circularity (0..1), touches_border (bool), cx, cy.
    """
    from scipy import ndimage

    h, w = markers.shape
    lab = np.where(markers > 1, markers, 0).astype(np.int32)
    slices = ndimage.find_objects(lab)
    scale = (pixel_size_nm / 1000.0) ** 2 if pixel_size_nm else 1.0
    rows = []
    for label, sl in enumerate(slices, start=1):
        if sl is None:
            continue
        sub = (lab[sl] == label)
        area_px = int(sub.sum())
        if area_px <= min_area_px:
            continue
        # cv2.watershed writes -1 into the outermost pixel ring, so a grain at the frame
        # edge ends one pixel short of it: test against that ring, not the raw edge
        touches = (sl[0].start <= 1 or sl[1].start <= 1 or sl[0].stop >= h - 1 or sl[1].stop >= w - 1)
        if exclude_border and touches:
            continue
        m8 = sub.astype(np.uint8)
        contours, _ = cv2.findContours(m8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        perimeter = max((cv2.arcLength(c, True) for c in contours), default=0.0)
        circ = 4.0 * np.pi * area_px / perimeter ** 2 if perimeter > 0 else float("nan")
        circ = min(circ, 1.0) if circ == circ else circ
        mu = cv2.moments(m8, binaryImage=True)
        if mu["m00"] > 0:
            cxx = mu["mu20"] / mu["m00"]
            cyy = mu["mu02"] / mu["m00"]
            cxy = mu["mu11"] / mu["m00"]
            common = np.sqrt(((cxx - cyy) / 2.0) ** 2 + cxy ** 2)
            l1 = (cxx + cyy) / 2.0 + common
            l2 = (cxx + cyy) / 2.0 - common
            aspect = float(np.sqrt(l1 / l2)) if l2 > 1e-9 else float("inf")
            cx = sl[1].start + mu["m10"] / mu["m00"]
            cy = sl[0].start + mu["m01"] / mu["m00"]
        else:
            aspect, cx, cy = float("nan"), float("nan"), float("nan")
        area = area_px * scale
        rows.append({
            "label": label, "area_px": area_px, "area": area,
            "diameter": float(np.sqrt(4.0 * area / np.pi)),
            "aspect_ratio": aspect, "circularity": float(circ),
            "touches_border": bool(touches), "cx": cx, "cy": cy,
        })
    return rows


def summarize_grains(rows, pixel_size_nm):
    """Summary statistics of grain_shape_table() rows (None values when no grains)."""
    if not rows:
        return {"n": 0, "calibrated": pixel_size_nm is not None, "unit": "um" if pixel_size_nm else "px",
                "mean_diameter": None, "median_diameter": None, "std_diameter": None,
                "mean_aspect_ratio": None, "mean_circularity": None}
    d = np.array([r["diameter"] for r in rows])
    ar = np.array([r["aspect_ratio"] for r in rows])
    ci = np.array([r["circularity"] for r in rows])
    ar = ar[np.isfinite(ar)]
    ci = ci[np.isfinite(ci)]
    return {
        "n": len(rows), "calibrated": pixel_size_nm is not None,
        "unit": "um" if pixel_size_nm else "px",
        "mean_diameter": float(d.mean()), "median_diameter": float(np.median(d)),
        "std_diameter": float(d.std(ddof=1)) if len(d) > 1 else 0.0,
        "mean_aspect_ratio": float(ar.mean()) if len(ar) else None,
        "mean_circularity": float(ci.mean()) if len(ci) else None,
    }


def run_grain_analysis(image, pixel_size_nm, pct_low=90, pct_high=98, dist_thresh=0.5,
                       dilate_iter=2, min_area_px=50, exclude_border=True):
    """detect_grains() + shape table + summary. Returns (markers, rows, summary)."""
    if pct_low >= pct_high:
        raise ValueError("The lower edge percentile must be below the upper one.")
    markers, _ = detect_grains(image, dist_thresh=dist_thresh, dilate_iter=dilate_iter,
                               min_area_px=min_area_px, adaptive_canny=True,
                               adaptive_lower_percentile=pct_low,
                               adaptive_upper_percentile=pct_high)
    rows = grain_shape_table(markers, pixel_size_nm, min_area_px, exclude_border)
    return markers, rows, summarize_grains(rows, pixel_size_nm)


def phase_fraction(image, threshold, invert=False):
    """Fraction of pixels in the 'phase of interest': above the threshold, or below it
    when invert is set. Returns (fraction, mask uint8 0/255)."""
    if invert:
        mask = np.where(image <= threshold, 255, 0).astype(np.uint8)
    else:
        mask = np.where(image > threshold, 255, 0).astype(np.uint8)
    return float(np.count_nonzero(mask)) / mask.size, mask


def otsu_threshold(image):
    t, _ = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return int(t)


def build_property_rows(grain_summary, grain_params, phase, include_grains, include_phase):
    """
    Rows for the properties table: (name, value, unit).
    grain_summary: summarize_grains() result or None; grain_params: dict with
    dist_thresh, pct_low, pct_high, min_area_px, exclude_border; phase: dict with
    fraction, threshold or None.
    Sizes are only included when calibrated (a value in pixels must not be stored
    under a name that implies micrometres).
    """
    rows = []
    if include_grains and grain_summary and grain_summary["n"] > 0:
        s = grain_summary
        rows.append(("grain_count", float(s["n"]), "count"))
        if s["calibrated"]:
            rows.append(("grain_mean_diameter", s["mean_diameter"], "um"))
            rows.append(("grain_median_diameter", s["median_diameter"], "um"))
        if s["mean_aspect_ratio"] is not None:
            rows.append(("grain_mean_aspect_ratio", s["mean_aspect_ratio"], "ratio"))
        if s["mean_circularity"] is not None:
            rows.append(("grain_mean_circularity", s["mean_circularity"], "ratio"))
        p = grain_params
        rows += [("grain_param_dist_thresh", float(p["dist_thresh"]), "fraction"),
                 ("grain_param_canny_pct_low", float(p["pct_low"]), "percentile"),
                 ("grain_param_canny_pct_high", float(p["pct_high"]), "percentile"),
                 ("grain_param_min_area_px", float(p["min_area_px"]), "px"),
                 ("grain_param_exclude_border", 1.0 if p["exclude_border"] else 0.0, "flag")]
    if include_phase and phase:
        rows.append(("bright_phase_fraction", round(float(phase["fraction"]), 6), "fraction"))
        rows.append(("phase_fraction_threshold", float(phase["threshold"]), "uint8"))
    return rows


# ---------------------------------------------------------------------------
# Database (only on an explicit Save click)
# ---------------------------------------------------------------------------

def save_properties(conn, schema, file_path, rows, replace_names):
    """
    One transaction: find the file's characterization record (exactly one), delete
    its properties named in replace_names, insert rows. Returns the number inserted.
    Raises LookupError if the file has no (or more than one) characterization record.
    """
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id FROM {schema}.characterization WHERE file_path = %s", (file_path,))
        found = cur.fetchall()
        if not found:
            raise LookupError("This file has no characterization record. Import it via the main app first.")
        if len(found) > 1:
            raise LookupError("This file path is stored more than once in characterization; "
                              "remove the duplicate import before saving.")
        char_id = found[0][0]
        cur.execute(f"DELETE FROM {schema}.properties WHERE characterization_id = %s "
                    f"AND property_name = ANY(%s)", (char_id, list(replace_names)))
        for name, value, unit in rows:
            cur.execute(
                f"INSERT INTO {schema}.properties (characterization_id, property_name, "
                f"property_value, property_unit, confidence_score) VALUES (%s, %s, %s, %s, %s)",
                (char_id, name, float(value), unit, 1.0))
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def connect_db():
    from db_config import DB_CONFIG
    import psycopg2
    params = {k: v for k, v in DB_CONFIG.items() if k != "schema"}
    return psycopg2.connect(**params), DB_CONFIG.get("schema", "alloy_lab")


# ---------------------------------------------------------------------------
# GUI (built lazily so the pure functions above work without a display)
# ---------------------------------------------------------------------------

def build_app():
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    class SEMAnalyzerApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("SEM Analyzer - Standalone")
            self.geometry("1400x900")

            self.file_path = None
            self.loaded = None          # load_sem_image() result
            self.work = None            # ROI-cropped image actually analysed
            self.roi = None
            self.markers = None
            self.grain_rows = []
            self.grain_summary = None
            self.grain_params = None
            self.phase = None           # {"fraction", "threshold"} of the current view
            self.phase_mask = None
            self._debounce = None

            self._build_controls()
            self._build_save_bar()      # packed at the bottom first
            self._build_tabs()

        # ---------------- layout ----------------
        def _build_controls(self):
            f = ctk.CTkFrame(self)
            f.pack(side="top", fill="x", padx=8, pady=8)
            ctk.CTkButton(f, text="Load SEM image", command=self.on_load_file).grid(
                row=0, column=0, padx=5, pady=5)
            self.file_label = ctk.CTkLabel(f, text="No file loaded", anchor="w")
            self.file_label.grid(row=0, column=1, columnspan=4, padx=5, sticky="w")
            self.info_label = ctk.CTkLabel(f, text="", anchor="w")
            self.info_label.grid(row=0, column=5, columnspan=6, padx=(20, 5), sticky="w")

            ctk.CTkLabel(f, text="Pixel size (nm), only if missing:").grid(
                row=1, column=0, columnspan=2, padx=5, sticky="w")
            self.px_entry = ctk.CTkEntry(f, width=80)
            self.px_entry.grid(row=1, column=2, padx=2)
            ctk.CTkLabel(f, text="ROI px  x0 y0 x1 y1:").grid(row=1, column=3, padx=(20, 2))
            self.roi_entries = []
            for i in range(4):
                e = ctk.CTkEntry(f, width=60)
                e.grid(row=1, column=4 + i, padx=2)
                self.roi_entries.append(e)
            ctk.CTkButton(f, text="Apply", width=70, command=self.on_apply_inputs).grid(
                row=1, column=8, padx=(10, 2))
            ctk.CTkButton(f, text="Clear ROI", width=80, fg_color="gray", command=self.on_clear_roi).grid(
                row=1, column=9, padx=2)

        def _build_save_bar(self):
            bar = ctk.CTkFrame(self)
            bar.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
            self.save_button = ctk.CTkButton(bar, text="Save to DB", command=self.save_to_db,
                                             state="disabled", fg_color="darkgreen", width=150)
            self.save_button.pack(side="left", padx=8, pady=6)
            self.save_grains_var = tk.BooleanVar(value=True)
            ctk.CTkCheckBox(bar, text="grain results", variable=self.save_grains_var).pack(side="left", padx=8)
            self.save_phase_var = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(bar, text="phase fraction (tick once the threshold is confirmed)",
                            variable=self.save_phase_var).pack(side="left", padx=8)
            self.save_status = ctk.CTkLabel(bar, text="", anchor="w")
            self.save_status.pack(side="left", padx=12)

        def _build_tabs(self):
            self.tabs = ctk.CTkTabview(self)
            self.tabs.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))
            self._build_grains_tab(self.tabs.add("Grains"))
            self._build_phase_tab(self.tabs.add("Phase fraction"))

        def _slider(self, parent, label, lo, hi, init, steps, fmt):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=3)
            lab = ctk.CTkLabel(row, text="", anchor="w", width=250)
            lab.pack(side="top", anchor="w")
            s = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=steps, width=250,
                              command=lambda v, l=lab, t=label, f=fmt: (
                                  l.configure(text=f"{t}: {f(v)}"), self._schedule_grains()))
            s.set(init)
            lab.configure(text=f"{label}: {fmt(init)}")
            s.pack(side="top")
            return s

        def _build_grains_tab(self, tab):
            left = ctk.CTkFrame(tab, width=290)
            left.pack(side="left", fill="y", padx=(0, 8))
            left.pack_propagate(False)
            ctk.CTkLabel(left, text="Grain detection", font=ctk.CTkFont(weight="bold")).pack(
                anchor="w", padx=8, pady=(6, 2))
            self.sl_low = self._slider(left, "Edge percentile, lower", 50, 98, 90, 48, lambda v: f"{v:.0f}")
            self.sl_high = self._slider(left, "Edge percentile, upper", 80, 99.9, 98, 199, lambda v: f"{v:.1f}")
            self.sl_dist = self._slider(left, "Distance threshold", 0.1, 0.9, 0.5, 80, lambda v: f"{v:.2f}")
            self.sl_dil = self._slider(left, "Edge dilation (iterations)", 1, 5, 2, 4, lambda v: f"{v:.0f}")
            self.sl_min = self._slider(left, "Minimum grain area (px)", 10, 1000, 50, 99, lambda v: f"{v:.0f}")
            self.border_var = tk.BooleanVar(value=True)
            ctk.CTkCheckBox(left, text="Exclude grains touching the border", variable=self.border_var,
                            command=self._run_grains).pack(anchor="w", padx=8, pady=8)
            ctk.CTkButton(left, text="Reset to defaults", fg_color="gray",
                          command=self.on_reset_grain_params).pack(padx=8, pady=4)
            self.grain_text = ctk.CTkLabel(left, text="", anchor="nw", justify="left", wraplength=270)
            self.grain_text.pack(fill="x", padx=8, pady=8)

            right = ctk.CTkFrame(tab)
            right.pack(side="left", fill="both", expand=True)
            self.grain_fig = Figure(figsize=(9, 5), dpi=100)
            self.grain_canvas = FigureCanvasTkAgg(self.grain_fig, master=right)
            self.grain_canvas.get_tk_widget().pack(fill="both", expand=True)

        def _build_phase_tab(self, tab):
            top = ctk.CTkFrame(tab)
            top.pack(side="top", fill="x", pady=(0, 4))
            self.phase_label = ctk.CTkLabel(top, text="", anchor="w", font=ctk.CTkFont(size=14))
            self.phase_label.pack(side="bottom", fill="x", padx=10, pady=4)
            self.thr_label = ctk.CTkLabel(top, text="Threshold: -")
            self.thr_label.pack(side="left", padx=10)
            self.thr_slider = ctk.CTkSlider(top, from_=0, to=255, number_of_steps=255, width=380,
                                            command=self._on_threshold)
            self.thr_slider.set(128)
            self.thr_slider.pack(side="left", padx=6, pady=6)
            ctk.CTkButton(top, text="Reset to Otsu", width=110, command=self.on_reset_otsu).pack(side="left", padx=6)
            self.invert_var = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(top, text="Invert (phase is the darker region)", variable=self.invert_var,
                            command=self._refresh_phase).pack(side="left", padx=12)
            self.phase_fig = Figure(figsize=(9, 5), dpi=100)
            self.phase_canvas = FigureCanvasTkAgg(self.phase_fig, master=tab)
            self.phase_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        # ---------------- loading / inputs ----------------
        def on_load_file(self, path=None):
            if path is None:
                path = filedialog.askopenfilename(
                    filetypes=[("SEM images", "*.tif *.tiff"), ("All files", "*.*")])
            if not path:
                return
            try:
                self.loaded = load_sem_image(path)
            except Exception as exc:
                messagebox.showerror("Load failed", str(exc))
                return
            self.file_path = path
            self.file_label.configure(text=os.path.basename(path))
            for e in self.roi_entries:
                e.delete(0, "end")
            self.px_entry.delete(0, "end")
            self.roi = None
            self.save_button.configure(state="normal")
            self.save_status.configure(text="")
            self._apply_inputs(initial=True)

        def _pixel_size_nm(self):
            if self.loaded is None:
                return None
            if self.loaded["pixel_size_nm"]:
                return self.loaded["pixel_size_nm"]
            raw = self.px_entry.get().strip()
            if raw:
                try:
                    v = float(raw)
                    if v <= 0:
                        raise ValueError
                    return v
                except ValueError:
                    messagebox.showerror("Pixel size", "Pixel size must be a positive number (nm).")
            return None

        def on_apply_inputs(self):
            self._apply_inputs()

        def on_clear_roi(self):
            for e in self.roi_entries:
                e.delete(0, "end")
            self._apply_inputs()

        def _apply_inputs(self, initial=False):
            if self.loaded is None:
                return
            try:
                self.roi = parse_roi([e.get() for e in self.roi_entries], self.loaded["image"].shape)
            except ValueError as exc:
                messagebox.showerror("ROI", str(exc))
                return
            self.work = crop_roi(self.loaded["image"], self.roi)
            md = self.loaded["metadata"]
            px = self._pixel_size_nm()
            px_txt = (f"{px:.2f} nm/px" + ("" if self.loaded["pixel_size_nm"] else " (entered by hand)")) \
                if px else "not calibrated: results in pixels"
            self.info_label.configure(
                text=f"Format: {md.get('format')}  |  {px_txt}  |  footer cropped: "
                     f"{'yes' if self.loaded['footer_detected'] else 'no'}  |  analysed region: "
                     f"{self.work.shape[1]} x {self.work.shape[0]} px")
            if initial or self.phase is None:
                t = otsu_threshold(self.work)
                self.thr_slider.set(t)
            else:
                pass
            self._run_grains()
            self._refresh_phase()

        # ---------------- grains ----------------
        def on_reset_grain_params(self):
            for s, v in ((self.sl_low, 90), (self.sl_high, 98), (self.sl_dist, 0.5),
                         (self.sl_dil, 2), (self.sl_min, 50)):
                s.set(v)
                s._command(v)
            self.border_var.set(True)
            self._run_grains()

        def _schedule_grains(self):
            if self._debounce is not None:
                self.after_cancel(self._debounce)
            self._debounce = self.after(250, self._run_grains)

        def _read_grain_params(self):
            return {"pct_low": round(self.sl_low.get()), "pct_high": round(self.sl_high.get(), 1),
                    "dist_thresh": round(self.sl_dist.get(), 2), "dilate_iter": int(round(self.sl_dil.get())),
                    "min_area_px": int(round(self.sl_min.get())), "exclude_border": bool(self.border_var.get())}

        def _run_grains(self):
            self._debounce = None
            if self.work is None:
                return
            p = self._read_grain_params()
            self.grain_fig.clear()
            try:
                self.markers, self.grain_rows, self.grain_summary = run_grain_analysis(
                    self.work, self._pixel_size_nm(), **p)
            except Exception as exc:
                self.grain_summary = None
                self.grain_text.configure(text=f"Detection failed: {exc}")
                self.grain_canvas.draw()
                return
            self.grain_params = p
            self._draw_grains()

        def _draw_grains(self):
            fig = self.grain_fig
            fig.clear()
            gs = fig.add_gridspec(2, 2, width_ratios=[1.6, 1])
            ax = fig.add_subplot(gs[:, 0])
            # display only: stretch contrast so low-contrast images are readable
            lo, hi = np.percentile(self.work, (1, 99))
            disp = np.clip((self.work.astype(np.float64) - lo) / max(hi - lo, 1.0), 0, 1)
            rgb = cv2.cvtColor((disp * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)
            kept = [r["label"] for r in self.grain_rows]
            if kept:
                lab = np.isin(self.markers, kept)
                rgb[lab] = (0.55 * rgb[lab] + 0.45 * np.array([40, 160, 255])).astype(np.uint8)
            bnd = cv2.dilate((self.markers == -1).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            rgb[bnd] = (255, 40, 40)
            ax.imshow(rgb)
            ax.set_xticks([]); ax.set_yticks([])
            s = self.grain_summary
            ax.set_title(f"{s['n']} grains kept (red = boundaries, blue tint = counted)", fontsize=10)

            unit = s["unit"]
            d = [r["diameter"] for r in self.grain_rows]
            a1 = fig.add_subplot(gs[0, 1])
            if d:
                a1.hist(d, bins=min(25, max(5, len(d) // 2)), color="C0", edgecolor="white")
                a1.axvline(s["median_diameter"], color="C1", linestyle="--", label=f"median {s['median_diameter']:.3g}")
                a1.legend(fontsize=8)
            a1.set_xlabel(f"Equivalent diameter ({'µm' if unit == 'um' else 'px'})", fontsize=9)
            a1.set_ylabel("grains", fontsize=9)
            a2 = fig.add_subplot(gs[1, 1])
            ar = [r["aspect_ratio"] for r in self.grain_rows if np.isfinite(r["aspect_ratio"])]
            if ar:
                a2.hist(ar, bins=min(25, max(5, len(ar) // 2)), color="C2", edgecolor="white")
            a2.set_xlabel("Aspect ratio", fontsize=9)
            a2.set_ylabel("grains", fontsize=9)
            fig.tight_layout()
            self.grain_canvas.draw()

            if s["n"] == 0:
                txt = ("No grains kept. Either the image has no resolvable grain structure, or the "
                       "edge thresholds need adjusting (lower the lower percentile, or the distance threshold).")
            else:
                u = "µm" if unit == "um" else "px"
                txt = (f"n = {s['n']}\nmean diameter {s['mean_diameter']:.3g} {u}\n"
                       f"median diameter {s['median_diameter']:.3g} {u}\nstd {s['std_diameter']:.3g} {u}\n"
                       f"mean aspect ratio {s['mean_aspect_ratio']:.2f}\n"
                       f"mean circularity {s['mean_circularity']:.2f}")
                if not s["calibrated"]:
                    txt += "\n\nNot calibrated: enter the pixel size to get micrometres (and to save diameters)."
                if s["n"] <= 3:
                    txt += "\n\nVery few grains: treat the statistics with caution."
            self.grain_text.configure(text=txt)

        # ---------------- phase fraction ----------------
        def _on_threshold(self, _v):
            self._refresh_phase()

        def on_reset_otsu(self):
            if self.work is not None:
                self.thr_slider.set(otsu_threshold(self.work))
                self._refresh_phase()

        def _refresh_phase(self):
            fig = self.phase_fig
            fig.clear()
            if self.work is None:
                self.phase_canvas.draw()
                return
            thr = int(round(self.thr_slider.get()))
            self.thr_label.configure(text=f"Threshold: {thr}  (Otsu suggests {otsu_threshold(self.work)})")
            frac, mask = phase_fraction(self.work, thr, self.invert_var.get())
            self.phase, self.phase_mask = {"fraction": frac, "threshold": thr}, mask
            ax = fig.add_subplot(1, 2, 1)
            rgb = cv2.cvtColor(self.work, cv2.COLOR_GRAY2RGB)
            on = mask == 255
            rgb[on] = (0.55 * rgb[on] + 0.45 * np.array([255, 60, 60])).astype(np.uint8)
            ax.imshow(rgb)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title("phase of interest in red", fontsize=10)
            ah = fig.add_subplot(1, 2, 2)
            ah.hist(self.work.ravel(), bins=64, range=(0, 255), color="gray")
            ah.axvline(thr, color="red")
            ah.set_xlabel("grey level"); ah.set_ylabel("pixels")
            fig.tight_layout()
            self.phase_canvas.draw()
            px = self._pixel_size_nm()
            area = ""
            if px:
                total = self.work.size * (px / 1000.0) ** 2
                area = f"   |   {frac * total:,.0f} of {total:,.0f} µm²"
            self.phase_label.configure(
                text=f"Phase of interest: {frac * 100:.2f}%   (other phase: {(1 - frac) * 100:.2f}%){area}")

        # ---------------- save ----------------
        def save_to_db(self):
            if self.loaded is None:
                return
            want_grains, want_phase = self.save_grains_var.get(), self.save_phase_var.get()
            if not (want_grains or want_phase):
                messagebox.showerror("Nothing selected", "Tick the results you want to save.")
                return
            if want_phase and self.invert_var.get():
                if not messagebox.askyesno(
                        "Inverted phase",
                        "The phase of interest is the DARKER region. It will be stored as "
                        "'bright_phase_fraction', which would then mislabel it. Save anyway?"):
                    return
            rows = build_property_rows(self.grain_summary, self.grain_params, self.phase,
                                       want_grains, want_phase)
            if not rows:
                messagebox.showerror("Nothing to save", "No grains were found, so there are no grain results to save.")
                return
            names = []
            if want_grains and self.grain_summary and self.grain_summary["n"] > 0:
                names += GRAIN_PROPERTY_NAMES
            if want_phase:
                names += PHASE_PROPERTY_NAMES
            if (self.grain_summary and self.grain_summary["n"] > 0
                    and not self.grain_summary["calibrated"] and want_grains):
                messagebox.showinfo("Not calibrated", "No pixel size: grain diameters are not saved, "
                                                      "only count and shape measures.")
            try:
                conn, schema = connect_db()
            except Exception as exc:
                messagebox.showerror("Database", str(exc))
                return
            try:
                n = save_properties(conn, schema, self.file_path, rows, names)
                roi_txt = f" (ROI {self.roi})" if self.roi else ""
                self.save_status.configure(text=f"Saved {n} values{roi_txt}")
            except Exception as exc:
                self.save_status.configure(text=f"Save failed: {exc}")
                messagebox.showerror("Save failed", str(exc))
            finally:
                conn.close()

    return SEMAnalyzerApp


def main():
    app = build_app()()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(200, lambda: app.on_load_file(sys.argv[1]))
    app.mainloop()


if __name__ == "__main__":
    main()
