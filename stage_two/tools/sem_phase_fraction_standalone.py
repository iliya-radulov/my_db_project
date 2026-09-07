"""
sem_phase_fraction_standalone.py

Standalone, directly-usable interactive tool for SEM phase-fraction
analysis -- built on top of sem_metadata_universal.py (auto format
detection, calibration, footer cropping across Zeiss/JEOL/Tescan) and
sem_phase_fraction.py (Otsu threshold as a starting SUGGESTION, not a
forced answer).

Deliberate design philosophy, confirmed directly rather than assumed:
which pixels belong to which phase depends on the specific material
system, imaging mode, and sample history -- real domain judgment a
general algorithm can't reliably infer from pixel intensities alone
(confirmed concretely: the same simple Otsu approach worked well on
one real image and failed in two different ways -- texture confusion,
noise confusion -- on two others). Working with new/unfamiliar alloys
means often not having enough prior information to fully automate this
step at all. So: automate what's genuinely reliable (loading,
calibration, footer cropping -- confirmed solid across all three real
instrument formats), suggest a reasonable starting threshold, and put
a live slider in the operator's hands for the actual judgment call --
simple, with real room for interpretation, not a rigid pipeline
pretending to a precision it can't have.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import os
import sys
from pathlib import Path

# Project root on path for db_config
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sem_metadata_universal import parse_sem_metadata_universal
from sem_phase_fraction import load_and_normalize, compute_phase_fraction

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class SEMPhaseFractionApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SEM Phase Fraction — Standalone")
        self.geometry("1150x850")

        self.file_path = None
        self.metadata = None
        self.image = None
        self.binary_mask = None          # stored for Save to DB
        self.invert_var = tk.BooleanVar(value=False)

        self._build_controls()
        self._build_plot_area()
        self._build_summary_bar()
        self._build_save_bar()

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_controls(self):
        frame = ctk.CTkFrame(self)
        frame.pack(side="top", fill="x", padx=8, pady=8)

        self.load_button = ctk.CTkButton(
            frame, text="Load .tif file", command=self.on_load_file)
        self.load_button.grid(row=0, column=0, padx=5, pady=5)

        self.file_label = ctk.CTkLabel(frame, text="No file loaded", anchor="w")
        self.file_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.info_label = ctk.CTkLabel(frame, text="", anchor="w", justify="left")
        self.info_label.grid(row=1, column=0, columnspan=7, padx=5, pady=(0, 5), sticky="w")

        ctk.CTkLabel(frame, text="Threshold:").grid(row=0, column=2, padx=(20, 2))
        self.threshold_slider = ctk.CTkSlider(
            frame, from_=0, to=255, number_of_steps=255,
            command=self.on_threshold_change, width=300)
        self.threshold_slider.grid(row=0, column=3, padx=5)
        self.threshold_slider.set(128)

        self.threshold_value_label = ctk.CTkLabel(frame, text="128", width=40)
        self.threshold_value_label.grid(row=0, column=4, padx=5)

        self.reset_button = ctk.CTkButton(
            frame, text="Reset to Otsu",
            command=self.on_reset_to_otsu, state="disabled")
        self.reset_button.grid(row=0, column=5, padx=(10, 5))

        self.invert_check = ctk.CTkCheckBox(
            frame, text="Invert (phase is darker)",
            variable=self.invert_var,
            command=self.on_threshold_change_event)
        self.invert_check.grid(row=0, column=6, padx=(10, 5))

    def _build_plot_area(self):
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.figure = Figure(figsize=(10, 5), dpi=100)
        self.ax_original = self.figure.add_subplot(121)
        self.ax_mask = self.figure.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_summary_bar(self):
        self.summary_label = ctk.CTkLabel(self, text="", anchor="w",
                                           font=ctk.CTkFont(size=14))
        self.summary_label.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    def _build_save_bar(self):
        save_frame = ctk.CTkFrame(self)
        save_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

        self.save_button = ctk.CTkButton(
            save_frame, text="💾 Save to DB",
            command=self.save_to_db, state="disabled",
            fg_color="darkgreen", width=160, height=35,
        )
        self.save_button.pack(side="left", padx=8, pady=6)

        self.save_status_label = ctk.CTkLabel(
            save_frame, text="", anchor="w",
            font=ctk.CTkFont(size=12))
        self.save_status_label.pack(side="left", padx=8, pady=6)

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    def on_load_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("SEM image", "*.tif *.tiff"), ("All files", "*.*")])
        if not path:
            return
        self.file_path = path
        self.file_label.configure(text=path.split("/")[-1])

        try:
            self.metadata = parse_sem_metadata_universal(path)
            self.image, footer_detected = load_and_normalize(path, self.metadata)
        except Exception as e:
            messagebox.showerror("Load failed", str(e))
            return

        m = self.metadata
        px_str = (f"{m['pixel_size_nm']:.2f} nm/px"
                  if m['pixel_size_nm'] else "not calibrated")
        self.info_label.configure(
            text=(f"Format: {m['format']}   Mag: {m['magnification']}   "
                  f"kV: {m['eht_kv']}   Detector: {m['detector']}   "
                  f"Calibration: {px_str}")
        )

        # Suggest Otsu threshold as starting point
        otsu_result = compute_phase_fraction(self.image)
        self.threshold_slider.set(otsu_result['threshold'])
        self.reset_button.configure(state="normal")
        self._otsu_suggestion = otsu_result['threshold']
        self.save_status_label.configure(text="")

        self._refresh()
        self.save_button.configure(state="normal")

    def on_reset_to_otsu(self):
        self.threshold_slider.set(self._otsu_suggestion)
        self._refresh()

    def on_threshold_change(self, value):
        self._refresh()

    def on_threshold_change_event(self):
        self._refresh()

    # ---------------------------------------------------------------
    # Display
    # ---------------------------------------------------------------
    def _refresh(self):
        if self.image is None:
            return
        threshold = int(self.threshold_slider.get())
        self.threshold_value_label.configure(text=str(threshold))

        if self.invert_var.get():
            mask = (self.image < threshold).astype(np.uint8) * 255
        else:
            mask = (self.image >= threshold).astype(np.uint8) * 255

        self.binary_mask = mask          # store for Save to DB

        fraction = float(np.sum(mask == 255)) / mask.size

        self.ax_original.clear()
        self.ax_original.imshow(self.image, cmap='gray')
        self.ax_original.set_title("Original")
        self.ax_original.axis('off')

        self.ax_mask.clear()
        overlay = np.stack([self.image] * 3, axis=-1)
        overlay[mask == 255] = [255, 60, 60]
        self.ax_mask.imshow(overlay)
        self.ax_mask.set_title(f"Threshold = {threshold}")
        self.ax_mask.axis('off')

        self.canvas.draw()

        px_area_str = ""
        if self.metadata and self.metadata.get('pixel_size_nm'):
            px_nm = self.metadata['pixel_size_nm']
            total_area_um2 = self.image.size * (px_nm / 1000.0) ** 2
            px_area_str = (f"  |  Highlighted area: "
                           f"{fraction * total_area_um2:.2f} µm² "
                           f"of {total_area_um2:.2f} µm²")

        self.summary_label.configure(
            text=f"Phase fraction: {fraction*100:.2f}%{px_area_str}"
        )

    # ---------------------------------------------------------------
    # Save to DB
    # ---------------------------------------------------------------
    def save_to_db(self):
        """
        Saves the current operator-confirmed phase fraction and threshold
        to the properties table, replacing any previous phase fraction
        result for this characterization record.

        Looks up the characterization record by file_path. Requires the
        file to have been imported via the main app first.
        """
        if self.file_path is None or self.binary_mask is None:
            messagebox.showerror("Nothing to save",
                "Load and adjust an image first.")
            return

        threshold = int(self.threshold_slider.get())
        fraction = float(np.sum(self.binary_mask == 255)) / self.binary_mask.size

        try:
            from db_config import DB_CONFIG
            import psycopg2
            import psycopg2.extras

            conn_params = {k: v for k, v in DB_CONFIG.items() if k != "schema"}
            schema = DB_CONFIG.get("schema", "alloy_lab")
            conn = psycopg2.connect(**conn_params)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Find characterization record by file_path
            cur.execute(
                f"SELECT id FROM {schema}.characterization WHERE file_path = %s",
                (self.file_path,)
            )
            row = cur.fetchone()
            if not row:
                messagebox.showerror(
                    "Not in database",
                    "This file has no characterization record.\n"
                    "Import it via the main app first."
                )
                conn.close()
                return
            char_id = int(row["id"])

            # Replace any existing phase fraction properties
            cur2 = conn.cursor()
            cur2.execute(
                f"DELETE FROM {schema}.properties "
                f"WHERE characterization_id = %s "
                f"AND property_name IN "
                f"('bright_phase_fraction', 'phase_fraction_threshold')",
                (char_id,)
            )

            # Insert confirmed values
            for name, value, unit in [
                ("bright_phase_fraction",    round(fraction, 6), "fraction"),
                ("phase_fraction_threshold", float(threshold),   "uint8"),
            ]:
                cur2.execute(
                    f"INSERT INTO {schema}.properties "
                    f"(characterization_id, property_name, property_value, "
                    f"property_unit, confidence_score) "
                    f"VALUES (%s, %s, %s, %s, %s)",
                    (char_id, name, value, unit, 1.0)
                )

            conn.commit()
            cur2.close()
            cur.close()
            conn.close()

            self.save_status_label.configure(
                text=(f"✅ Saved: {fraction*100:.2f}% bright phase  "
                      f"(threshold={threshold})")
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Save failed", str(e))
            self.save_status_label.configure(text=f"❌ Save failed: {e}")


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app = SEMPhaseFractionApp()
    # Auto-load file when launched from the viewer with a path argument
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(200, lambda: app.on_load_file(sys.argv[1]))
    app.mainloop()
