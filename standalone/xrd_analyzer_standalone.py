"""
xrd_analyzer_standalone.py

Standalone, directly-usable interactive tool for XRD peak analysis --
built on top of the already-validated xrd_analyzer_dev1.py (background
subtraction, Ka2 stripping, peak fitting, R^2 quality, Scherrer size,
d-spacing, validated against the LaB6 certified reference standard in
an earlier session). This tool does NOT re-implement or modify that
analysis logic -- it wraps it in a live, interactive GUI:

  - Load a real .xy file directly (file picker)
  - Adjust peak-finding sensitivity (prominence, distance) and see the
    fit update live
  - Manually accept/reject individual detected peaks -- e.g. to
    exclude a peak the auto-fit found but which the operator judges as
    noise/artifact, or to flag one worth a second look
  - Summary statistics (n peaks, mean R^2) recompute based on ONLY the
    currently-accepted peaks, not the raw auto-detected set

Built in customtkinter (not PyQt5), matching the explicit project
decision from an earlier session: a tool built this way can later
share the same process/database as the main app, rather than being a
disconnected subprocess (the problem found with the old SEM PyQt5
tool). Database saving is deliberately NOT included here -- confirmed
directly this should be a quick-check tool only for now.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import io
import sys
import os
import contextlib
from pathlib import Path

# Project root on path for db_config and shared tools
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from xrd_analyzer_dev1 import analyze_xrd
from xrd_features_builder import build_xrd_peaks_rows, build_xrd_features_row
from db_type_utils import sanitize_row

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class XRDAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("XRD Analyzer — Standalone")
        self.geometry("1200x750")

        self.file_path = None
        self.analysis_result = None
        self.peak_accepted = {}  # peak index -> bool

        self._build_controls()
        self._build_plot_area()
        self._build_peak_table()
        self._build_summary_bar()
        self._build_save_bar()

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_controls(self):
        frame = ctk.CTkFrame(self)
        frame.pack(side="top", fill="x", padx=8, pady=8)

        self.load_button = ctk.CTkButton(frame, text="Load .xy file", command=self.on_load_file)
        self.load_button.grid(row=0, column=0, padx=5, pady=5)

        self.file_label = ctk.CTkLabel(frame, text="No file loaded", anchor="w")
        self.file_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(frame, text="Anode:").grid(row=0, column=2, padx=(20, 2))
        self.anode_var = ctk.StringVar(value="Cu")
        self.anode_menu = ctk.CTkOptionMenu(frame, values=["Cu", "Mo", "Co", "Cr", "Fe", "Ag"],
                                             variable=self.anode_var)
        self.anode_menu.grid(row=0, column=3, padx=5)

        self.strip_ka2_var = ctk.BooleanVar(value=True)
        self.strip_ka2_check = ctk.CTkCheckBox(frame, text="Strip Ka2", variable=self.strip_ka2_var)
        self.strip_ka2_check.grid(row=0, column=4, padx=(20, 5))

        ctk.CTkLabel(frame, text="Prominence:").grid(row=1, column=2, padx=(20, 2), pady=(5, 0))
        self.prominence_entry = ctk.CTkEntry(frame, width=80)
        self.prominence_entry.insert(0, "0.03")
        self.prominence_entry.grid(row=1, column=3, padx=5, pady=(5, 0))

        ctk.CTkLabel(frame, text="Distance (deg):").grid(row=1, column=4, padx=(20, 2), pady=(5, 0))
        self.distance_entry = ctk.CTkEntry(frame, width=80)
        self.distance_entry.insert(0, "0.15")
        self.distance_entry.grid(row=1, column=5, padx=5, pady=(5, 0))

        self.analyze_button = ctk.CTkButton(frame, text="Analyze", command=self.on_analyze,
                                             state="disabled")
        self.analyze_button.grid(row=0, column=6, rowspan=2, padx=(20, 5))

        self.save_button = ctk.CTkButton(frame, text="💾 Save to DB",
                                          command=self.save_to_db, state="disabled",
                                          fg_color="darkgreen")
        self.save_button.grid(row=0, column=7, rowspan=2, padx=(10, 5))

    def _build_plot_area(self):
        self.plot_frame = ctk.CTkFrame(self)
        self.plot_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_peak_table(self):
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=False, padx=8, pady=(0, 8))

        ctk.CTkLabel(container, text="Detected peaks (uncheck to reject):",
                     anchor="w").pack(side="top", fill="x", padx=5, pady=(5, 0))

        self.peak_table_frame = ctk.CTkScrollableFrame(container, height=180)
        self.peak_table_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        header = ctk.CTkFrame(self.peak_table_frame, fg_color="transparent")
        header.pack(fill="x")
        for col, text in enumerate(["Use", "2θ (°)", "d (Å)", "FWHM (°)", "R²", "Size (nm)", "Intensity"]):
            ctk.CTkLabel(header, text=text, width=90, anchor="w",
                         font=ctk.CTkFont(weight="bold")).grid(row=0, column=col, padx=3)

    def _build_summary_bar(self):
        self.summary_label = ctk.CTkLabel(self, text="", anchor="w")
        self.summary_label.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    def _build_save_bar(self):
        self.save_status_label = ctk.CTkLabel(self, text="", anchor="w",
                                               font=ctk.CTkFont(size=12))
        self.save_status_label.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    def on_load_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("XRD pattern", "*.xy"), ("All files", "*.*")])
        if not path:
            return
        self.file_path = path
        self.file_label.configure(text=path.split("/")[-1])
        self.analyze_button.configure(state="normal")

    def on_analyze(self):
        if not self.file_path:
            return
        try:
            prominence = float(self.prominence_entry.get())
            distance = float(self.distance_entry.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Prominence and distance must be numbers.")
            return

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                result = analyze_xrd(
                    self.file_path,
                    prominence=prominence,
                    distance_deg=distance,
                    anode=self.anode_var.get(),
                    strip_ka2=self.strip_ka2_var.get(),
                )
        except Exception as e:
            messagebox.showerror("Analysis failed", str(e))
            return

        self.analysis_result = result
        self.peak_accepted = {i: True for i in range(len(result['fitted_peaks']))}
        self._refresh_plot()
        self._refresh_peak_table()
        self._refresh_summary()
        self.save_button.configure(state="normal")
        self.save_status_label.configure(text="")

    def on_peak_toggle(self, idx):
        def callback():
            self.peak_accepted[idx] = not self.peak_accepted[idx]
            self._refresh_plot()
            self._refresh_summary()
        return callback

    # ---------------------------------------------------------------
    # Display refresh
    # ---------------------------------------------------------------
    def _refresh_plot(self):
        self.ax.clear()
        result = self.analysis_result
        self.ax.plot(result['x'], result['y'], linewidth=0.7, color='C0', label='Pattern')

        for i, p in enumerate(result['fitted_peaks']):
            color = 'green' if self.peak_accepted.get(i, True) else 'lightgray'
            self.ax.axvline(p['fit']['center'], color=color, linewidth=0.8, alpha=0.7)

        self.ax.set_xlabel("2θ (°)")
        self.ax.set_ylabel("Intensity")
        self.ax.set_title(self.file_path.split("/")[-1] if self.file_path else "")
        self.canvas.draw()

    def _refresh_peak_table(self):
        for widget in self.peak_table_frame.winfo_children()[1:]:
            widget.destroy()

        for i, p in enumerate(self.analysis_result['fitted_peaks']):
            row = ctk.CTkFrame(self.peak_table_frame, fg_color="transparent")
            row.pack(fill="x")

            var = tk.BooleanVar(value=True)
            self._peak_vars = getattr(self, '_peak_vars', {})
            self._peak_vars[i] = var

            check = ctk.CTkCheckBox(row, text="", variable=var, width=20,
                                     command=self.on_peak_toggle(i))
            check.grid(row=0, column=0, padx=3)

            fit = p['fit']
            values = [f"{fit['center']:.3f}", f"{fit['d_spacing_angstrom']:.4f}",
                      f"{fit['fwhm']:.3f}", f"{fit['r_squared']:.3f}",
                      f"{fit.get('crystallite_size_nm', float('nan')):.1f}",
                      f"{p.get('intensity', float('nan')):.0f}"]
            for col, val in enumerate(values, start=1):
                ctk.CTkLabel(row, text=val, width=90, anchor="w").grid(row=0, column=col, padx=3)

    def _refresh_summary(self):
        accepted = [p for i, p in enumerate(self.analysis_result['fitted_peaks'])
                    if self.peak_accepted.get(i, True)]
        n_total = len(self.analysis_result['fitted_peaks'])
        n_accepted = len(accepted)
        mean_r2 = np.mean([p['fit']['r_squared'] for p in accepted]) if accepted else float('nan')
        self.summary_label.configure(
            text=f"Peaks: {n_accepted} of {n_total} accepted  |  Mean R² (accepted): {mean_r2:.4f}"
        )



    def save_to_db(self):
        """
        Saves the currently accepted peaks to xrd_peaks and xrd_features,
        REPLACING any previous analysis for this sample. Looks up the
        sample via the characterization table using the loaded file_path.
        """
        if not self.analysis_result or not self.file_path:
            messagebox.showerror("Nothing to save", "Run analysis first.")
            return

        accepted_peaks = [
            p for i, p in enumerate(self.analysis_result["fitted_peaks"])
            if self.peak_accepted.get(i, True)
        ]
        if not accepted_peaks:
            messagebox.showerror("Nothing accepted", "Accept at least one peak before saving.")
            return

        try:
            from db_config import DB_CONFIG
            import psycopg2
            import psycopg2.extras

            conn_params = {k: v for k, v in DB_CONFIG.items() if k != "schema"}
            schema = DB_CONFIG.get("schema", "alloy_lab")
            conn = psycopg2.connect(**conn_params)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Look up sample_id via characterization table
            cur.execute(
                f"SELECT sample_id FROM {schema}.characterization WHERE file_path = %s",
                (self.file_path,)
            )
            row = cur.fetchone()
            if not row:
                messagebox.showerror(
                    "Not in database",
                    "This file has no characterization record.\nImport it via the main app first."
                )
                conn.close()
                return
            sample_db_id = row["sample_id"]

            # Build rows from accepted peaks only
            modified_result = dict(self.analysis_result)
            modified_result["fitted_peaks"] = accepted_peaks

            peaks_rows = [sanitize_row(r) for r in build_xrd_peaks_rows(
                sample_id=sample_db_id, result=modified_result)]
            features_row = sanitize_row(build_xrd_features_row(
                sample_id=sample_db_id, result=modified_result))

            # Replace existing analysis (DELETE + INSERT)
            cur2 = conn.cursor()
            cur2.execute(f"DELETE FROM {schema}.xrd_peaks WHERE sample_id = %s", (sample_db_id,))
            cur2.execute(f"DELETE FROM {schema}.xrd_features WHERE sample_id = %s", (sample_db_id,))

            for r in peaks_rows:
                cols = list(r.keys())
                cur2.execute(
                    f"INSERT INTO {schema}.xrd_peaks ({\", \".join(cols)}) "
                    f"VALUES ({\", \".join([f\"%({{c}})s\" for c in cols])})", r
                )

            cols = list(features_row.keys())
            cur2.execute(
                f"INSERT INTO {schema}.xrd_features ({\", \".join(cols)}) "
                f"VALUES ({\", \".join([f\"%({{c}})s\" for c in cols])})", features_row
            )

            conn.commit()
            cur2.close()
            cur.close()
            conn.close()

            n_saved = len(accepted_peaks)
            n_total = len(self.analysis_result["fitted_peaks"])
            self.save_status_label.configure(
                text=f"✅ Saved {n_saved} peak(s) to DB  ({n_total - n_saved} rejected)"
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Save failed", str(e))
            self.save_status_label.configure(text=f"❌ Save failed: {e}")

if __name__ == "__main__":
    app = XRDAnalyzerApp()
    # When launched from the viewer with a file path, auto-load AND
    # auto-analyze with default parameters so the user sees results
    # immediately. They can still adjust parameters and re-analyze.
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(200, lambda: app.on_load_file(sys.argv[1]))
        app.after(500, app.on_analyze)
    app.mainloop()
