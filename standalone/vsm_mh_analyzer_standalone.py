"""
vsm_mh_analyzer_standalone.py

Standalone, directly-usable interactive tool for VSM MH (Hc/Mr/BH_max)
analysis -- built on top of the already-validated vsm_pipeline.py
machinery (type detection, mass extraction, segmentation, self-centering
quality flags, second-quadrant Hc/Mr extraction, BH_max), matching the
same pattern as xrd_analyzer_standalone.py. Does NOT re-implement that
analysis logic -- every MH segment goes through the same
vsm_pipeline.analyze_mh_segment() that the database import uses, wrapped
in a live, interactive GUI:

  - Load a real .dat file directly (file picker) -- handles the FULL
    file, not a pre-isolated single loop: real files are often
    multi-segment (e.g. a temperature series of several MH loops in
    one file, confirmed common on real data), so requiring the loop to
    already be cut out first would defeat the point of a quick-check
    tool.
  - Automatic segmentation, with a segment list to page through what
    was found (type, row range, self-centering event count).
  - Adjustable branch-detection sensitivity (prominence, distance --
    same parameters validated in vsm_mh_features.find_descending_branch)
    with live re-analysis.
  - Optional BH_max for cuboid samples: density and the three full edge
    lengths, with the edge PARALLEL to the applied field entered as c
    (vsm_bhmax.demag_factor_prozorov_kogan() convention). The
    Prozorov-Kogan factor is the one used and saved (the lab's
    established practice); the Aharoni factor for the same geometry and
    the BH_max it would give are shown alongside for comparison, since
    Prozorov-Kogan is derived for diamagnetic samples.
  - Accept/reject PER SEGMENT's result (not per-point/per-click) --
    deliberately no manual crossing-point override: confirmed directly
    that the crossing-point math itself is exact linear interpolation
    once a branch is correctly identified, so there's nothing for a
    human to meaningfully improve by clicking a point. What CAN go
    wrong is branch selection, which the sensitivity controls address;
    if a result still looks wrong after that, the user can do their
    own separate manual recalculation rather than the tool pretending
    to offer a precision it can't add.
  - Further tabs: temperature coefficients (alpha Hc, beta Mr, fitted live
    from the accepted segments), isothermal entropy change (all MH
    segments, refuses full bipolar loops; mass needed) and MT candidates
    (unclassified, view only).
  - "Save to DB" writes the reviewed result back to the file's existing
    records (the file must already have been imported via the main app):
    accepted segments get the re-analyzed values, every other MH segment
    is stored with NULL Hc/Mr/BH_max and a flag ('operator_rejected' if
    the operator rejected it), and the file's temperature coefficients
    are refitted from the accepted segments only. The entropy-change
    result shown in its tab replaces the one stored at import, and a mass
    typed in by hand (file has none) is stored with mass_source 'manual'.

Built in customtkinter (not PyQt5), matching the same project decision
as the XRD tool: can later share the main app's process/database
rather than being a disconnected subprocess.

Must be run from stage_two/tools/ (or launched from the main app's Data
Viewer), since it imports the sibling vsm_* modules.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import sys
import os
from pathlib import Path

# Project root on path for db_config
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vsm_pipeline import load_vsm_file, analyze_mh_segment
from vsm_segmenter import detect_segments
from vsm_quality_flags import annotate_segment_quality
from vsm_temp_coefficient import fit_temperature_coefficient
from vsm_mt_features import extract_mt_candidates
from vsm_entropy_integration import compute_entropy_change_for_file
from vsm_bhmax import demag_factor_prozorov_kogan
from vsm_demag_correction import demag_factor_from_dimensions
from db_type_utils import sanitize_row

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Same window process_vsm_file() uses -- segment row ranges must match
# the ones stored at import time for "Save to DB" to find them.
SEGMENTER_WINDOW = 80

# vsm_entropy_change.target_field_oe is an INTEGER column
DEFAULT_TARGET_FIELDS_OE = (10000, 19000)


class VSMMHAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VSM MH Analyzer — Standalone")
        self.geometry("1300x850")

        self.file_path = None
        self.loaded = None
        self.segments = []
        self.mh_results = {}       # segment index -> analyze_mh_segment() dict
        self.mh_results_aharoni = {}  # segment index -> BH_max with Aharoni N, or None
        self.segment_accepted = {} # segment index -> bool (MH segments only)
        self.selected_segment = None
        self.geometry_used = None  # (density, (a, b, c), N_PK, N_Aharoni) or None
        self.entropy = None        # compute_entropy_change_for_file() result, or None
        self.mass_override_g = None  # mass typed in by hand because the file has none

        # bottom bars are packed before the expanding main area, otherwise
        # pack gives the plot all the space and pushes them off-screen
        self._build_controls()
        self._build_save_bar()
        self._build_summary_bar()
        self._build_main_area()

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_controls(self):
        frame = ctk.CTkFrame(self)
        frame.pack(side="top", fill="x", padx=8, pady=8)

        self.load_button = ctk.CTkButton(frame, text="Load .dat file", command=self.on_load_file)
        self.load_button.grid(row=0, column=0, padx=5, pady=5)

        self.file_label = ctk.CTkLabel(frame, text="No file loaded", anchor="w")
        self.file_label.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        self.info_label = ctk.CTkLabel(frame, text="", anchor="w")
        self.info_label.grid(row=0, column=4, columnspan=5, padx=(20, 5), sticky="w")

        ctk.CTkLabel(frame, text="Prominence (Oe):").grid(row=1, column=0, padx=5, pady=(5, 0), sticky="w")
        self.prominence_entry = ctk.CTkEntry(frame, width=90)
        self.prominence_entry.insert(0, "5000")
        self.prominence_entry.grid(row=1, column=1, padx=5, pady=(5, 0), sticky="w")

        ctk.CTkLabel(frame, text="Distance (points):").grid(row=1, column=2, padx=(20, 2), pady=(5, 0))
        self.distance_entry = ctk.CTkEntry(frame, width=90)
        self.distance_entry.insert(0, "20")
        self.distance_entry.grid(row=1, column=3, padx=5, pady=(5, 0))

        self.analyze_button = ctk.CTkButton(frame, text="Analyze", command=self.on_analyze,
                                             state="disabled")
        self.analyze_button.grid(row=1, column=4, padx=(20, 5), pady=(5, 0))

        ctk.CTkLabel(frame, text="Mass (mg), only if the file has none:").grid(
            row=1, column=5, columnspan=2, padx=(20, 2), pady=(5, 0), sticky="e")
        self.mass_entry = ctk.CTkEntry(frame, width=70)
        self.mass_entry.grid(row=1, column=7, padx=2, pady=(5, 0), sticky="w")

        # Optional BH_max inputs -- leave all empty for needle-shaped
        # samples, where no demagnetizing correction is needed.
        ctk.CTkLabel(frame, text="BH_max (optional) — density (g/cm³):").grid(
            row=2, column=0, columnspan=2, padx=5, pady=(8, 0), sticky="w")
        self.density_entry = ctk.CTkEntry(frame, width=90)
        self.density_entry.grid(row=2, column=2, padx=5, pady=(8, 0), sticky="w")

        self.dim_entries = {}
        for col, (key, label) in enumerate([('a', "a (mm):"), ('b', "b (mm):"),
                                            ('c', "c ∥ field (mm):")]):
            ctk.CTkLabel(frame, text=label).grid(row=2, column=3 + 2 * col, padx=(12, 2), pady=(8, 0), sticky="e")
            entry = ctk.CTkEntry(frame, width=70)
            entry.grid(row=2, column=4 + 2 * col, padx=2, pady=(8, 0), sticky="w")
            self.dim_entries[key] = entry

        self.demag_label = ctk.CTkLabel(frame, text="", anchor="w")
        self.demag_label.grid(row=3, column=0, columnspan=9, padx=5, pady=(2, 0), sticky="w")

    def _build_main_area(self):
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        # left: segment list
        left = ctk.CTkFrame(container, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="Segments found:", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=5, pady=5)
        self.segment_list_frame = ctk.CTkScrollableFrame(left)
        self.segment_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # right: tabs
        self.tabs = ctk.CTkTabview(container)
        self.tabs.pack(side="left", fill="both", expand=True)
        right = self.tabs.add("MH loops")
        self._build_tc_tab(self.tabs.add("Temp. coefficients"))
        self._build_entropy_tab(self.tabs.add("Entropy change"))
        self._build_mt_tab(self.tabs.add("MT candidates"))

        # result panel packed first (at the bottom) so the plot can't squeeze it
        result_frame = ctk.CTkFrame(right)
        result_frame.pack(side="bottom", fill="x", pady=(8, 0))

        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.result_label = ctk.CTkLabel(result_frame, text="Select a segment to view its result.",
                                          anchor="w", justify="left", font=ctk.CTkFont(size=14))
        self.result_label.pack(side="left", padx=10, pady=10)

        self.accept_var = tk.BooleanVar(value=True)
        self.accept_check = ctk.CTkCheckBox(result_frame, text="Accept this result",
                                             variable=self.accept_var,
                                             command=self.on_accept_toggle, state="disabled")
        self.accept_check.pack(side="right", padx=10, pady=10)

    def _make_canvas(self, parent, figsize=(7, 4.2)):
        fig = Figure(figsize=figsize, dpi=100)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        return fig, canvas

    def _build_tc_tab(self, tab):
        # label packed first (bottom) so the plot cannot squeeze it out
        self.tc_label = ctk.CTkLabel(tab, text="", anchor="w", justify="left")
        self.tc_label.pack(side="bottom", fill="x", padx=10, pady=6)
        self.tc_fig, self.tc_canvas = self._make_canvas(tab)

    def _build_entropy_tab(self, tab):
        top = ctk.CTkFrame(tab)
        top.pack(side="top", fill="x", pady=(0, 4))
        ctk.CTkLabel(top, text="Target fields (Oe, integers):").pack(side="left", padx=8, pady=6)
        self.target_entry = ctk.CTkEntry(top, width=160)
        self.target_entry.insert(0, ", ".join(str(v) for v in DEFAULT_TARGET_FIELDS_OE))
        self.target_entry.pack(side="left", padx=4)
        ctk.CTkButton(top, text="Recompute", width=100,
                      command=self._on_recompute_entropy).pack(side="left", padx=8)
        self.entropy_label = ctk.CTkLabel(tab, text="", anchor="w", justify="left", wraplength=1000)
        self.entropy_label.pack(side="bottom", fill="x", padx=10, pady=6)
        self.entropy_fig, self.entropy_canvas = self._make_canvas(tab)

    def _build_mt_tab(self, tab):
        top = ctk.CTkFrame(tab)
        top.pack(side="top", fill="x", pady=(0, 4))
        ctk.CTkLabel(top, text="MT segment:").pack(side="left", padx=8, pady=6)
        self.mt_var = tk.StringVar(value="-")
        self.mt_menu = ctk.CTkOptionMenu(top, values=["-"], variable=self.mt_var,
                                         command=lambda _v: self._refresh_mt())
        self.mt_menu.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Candidates are unclassified by design; interpretation is yours. "
                              "View only, not saved.", text_color="gray").pack(side="left", padx=12)
        self.mt_text = ctk.CTkTextbox(tab, height=140, font=ctk.CTkFont(family="Courier", size=12))
        self.mt_text.pack(side="bottom", fill="x", padx=6, pady=4)
        self.mt_text.configure(state="disabled")
        self.mt_fig, self.mt_canvas = self._make_canvas(tab, figsize=(7, 3.4))

    def _build_save_bar(self):
        save_frame = ctk.CTkFrame(self)
        save_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

        self.save_button = ctk.CTkButton(
            save_frame, text="💾 Save to DB",
            command=self.save_to_db, state="disabled",
            fg_color="darkgreen", width=160,
        )
        self.save_button.pack(side="left", padx=8, pady=6)

        self.save_status_label = ctk.CTkLabel(save_frame, text="", anchor="w",
                                               font=ctk.CTkFont(size=12))
        self.save_status_label.pack(side="left", padx=8, pady=6)

    def _build_summary_bar(self):
        self.summary_label = ctk.CTkLabel(self, text="", anchor="w")
        self.summary_label.pack(side="bottom", fill="x", padx=8, pady=(0, 4))

    # ---------------------------------------------------------------
    # Input parsing
    # ---------------------------------------------------------------
    def _read_geometry(self):
        """Returns (density, (a, b, c)) or None if all fields are empty.
        Raises ValueError if they are only partly filled or invalid --
        a half-entered geometry must not silently become 'no BH_max'."""
        raw = [self.density_entry.get().strip()] + [self.dim_entries[k].get().strip() for k in 'abc']
        if not any(raw):
            return None
        if not all(raw):
            raise ValueError("Fill in density and all three dimensions for BH_max, "
                             "or leave all four empty.")
        values = [float(v) for v in raw]
        if any(v <= 0 for v in values):
            raise ValueError("Density and dimensions must be positive.")
        return values[0], tuple(values[1:])

    def _set_geometry_fields(self, density, dims):
        for entry, value in zip([self.density_entry] + [self.dim_entries[k] for k in 'abc'],
                                [density, *dims]):
            entry.delete(0, "end")
            entry.insert(0, f"{value:g}")

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    def on_load_file(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("VSM data", "*.dat *.DAT"), ("All files", "*.*")])
        if not path:
            return
        self.file_path = path
        self.file_label.configure(text=os.path.basename(path))
        self.analyze_button.configure(state="normal")
        self.save_button.configure(state="disabled")

    def on_analyze(self):
        if not self.file_path:
            return
        try:
            prominence = float(self.prominence_entry.get())
            distance = int(self.distance_entry.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Prominence and distance must be numbers.")
            return
        try:
            geometry = self._read_geometry()
        except ValueError as e:
            messagebox.showerror("Invalid BH_max input", str(e))
            return

        try:
            self.loaded = load_vsm_file(self.file_path)
            raw_segments = detect_segments(self.loaded['H'], self.loaded['T'], window=SEGMENTER_WINDOW)
            self.segments = [
                annotate_segment_quality(seg, self.loaded['H'], self.loaded['T'], self.loaded['M'],
                                         center_position=self.loaded['center_position'])
                for seg in raw_segments
            ]
        except Exception as e:
            messagebox.showerror("Load/segmentation failed", str(e))
            return

        mass = self.loaded['mass_g']
        self.mass_override_g = None
        if not mass:
            raw = self.mass_entry.get().strip()
            if raw:
                try:
                    mg = float(raw)
                    if mg <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Invalid input", "Mass (mg) must be a positive number.")
                    return
                mass = self.mass_override_g = mg / 1000.0
        mass_str = (f"{mass} g ({self.loaded['mass_source']})" if self.loaded['mass_g']
                    else (f"{mass} g (entered by hand)" if mass else "not found"))
        self.info_label.configure(
            text=f"Type: {self.loaded['instrument_type']}  |  Mass: {mass_str}"
        )

        N_pk = N_aharoni = None
        density = None
        if geometry is not None:
            density, (a, b, c) = geometry
            N_pk = demag_factor_prozorov_kogan(a, b, c)
            N_aharoni = demag_factor_from_dimensions(a, b, c, field_axis='z')
            self.geometry_used = (density, (a, b, c), N_pk, N_aharoni)
            note = "" if mass else "   — no sample mass, BH_max cannot be computed"
            self.demag_label.configure(
                text=f"N (Prozorov–Kogan, used) = {N_pk:.4f}   |   N (Aharoni, comparison) = {N_aharoni:.4f}{note}"
            )
        else:
            self.geometry_used = None
            self.demag_label.configure(text="No geometry entered — BH_max not computed.")

        self.mh_results = {}
        self.mh_results_aharoni = {}
        self.segment_accepted = {}
        for i, seg in enumerate(self.segments):
            if seg['type'] != 'MH':
                continue
            s, e = seg['start'], seg['end']
            seg_H, seg_M, seg_T = self.loaded['H'][s:e], self.loaded['M'][s:e], self.loaded['T'][s:e]
            result = analyze_mh_segment(seg_H, seg_M, seg_T, mass, prominence=prominence,
                                        distance=distance, density_g_cm3=density, demag_N=N_pk)
            self.mh_results[i] = result
            self.segment_accepted[i] = (result['flag'] is None)
            if N_aharoni is not None:
                alt = analyze_mh_segment(seg_H, seg_M, seg_T, mass, prominence=prominence,
                                         distance=distance, density_g_cm3=density, demag_N=N_aharoni)
                self.mh_results_aharoni[i] = alt['bhmax_kJ_m3']

        self.selected_segment = None
        self._compute_entropy()
        self._refresh_segment_list()
        self._refresh_summary()
        self._refresh_tc()
        self._refresh_mt_menu()
        self.save_button.configure(state="normal" if self.mh_results else "disabled")
        self.save_status_label.configure(text="")

        # auto-select the first MH segment found, if any
        first_mh = next((i for i, s in enumerate(self.segments) if s['type'] == 'MH'), None)
        if first_mh is not None:
            self.on_select_segment(first_mh)
        else:
            self.ax.clear()
            self.canvas.draw()
            self.result_label.configure(text="No MH segments found in this file.")
            self.accept_check.configure(state="disabled")

    def on_select_segment(self, idx):
        self.selected_segment = idx
        self._refresh_segment_list()
        if self.segments[idx]['type'] == 'MT':
            self.mt_var.set(f"[{idx}]")
            self._refresh_mt()
            self.tabs.set("MT candidates")
            return
        self.tabs.set("MH loops")
        self._refresh_plot()
        self._refresh_result_panel()

    def on_accept_toggle(self):
        if self.selected_segment is not None:
            self.segment_accepted[self.selected_segment] = self.accept_var.get()
            self._refresh_segment_list()
            self._refresh_summary()
            self._refresh_tc()

    # ---------------------------------------------------------------
    # Temperature coefficients / entropy change / MT candidates
    # ---------------------------------------------------------------
    def _accepted_points(self):
        """(T, Hc, Mr) of the accepted MH segments -- what gets fitted and saved."""
        return [(self.mh_results[i]["temperature_K"], self.mh_results[i]["Hc"],
                 self.mh_results[i]["Mr"])
                for i in self.mh_results if self.segment_accepted.get(i, False)]

    def _refresh_tc(self):
        pts = self._accepted_points()
        fig = self.tc_fig
        fig.clear()
        ax1, ax2 = fig.add_subplot(121), fig.add_subplot(122)
        if len(pts) < 2 or len({round(t, 6) for t, _, _ in pts}) < 2:
            for ax in (ax1, ax2):
                ax.axis("off")
            ax1.text(0.5, 0.5, "Needs at least 2 accepted MH segments\nat different temperatures.",
                     ha="center", va="center", color="gray")
            self.tc_label.configure(text="")
        else:
            T = np.array([p[0] for p in pts])
            fits = {}
            for ax, key, col, ylabel in ((ax1, "alpha_Hc", 1, "Hc (Oe)"), (ax2, "beta_Mr", 2, "Mr (emu)")):
                y = np.array([p[col] for p in pts])
                d = fits[key] = fit_temperature_coefficient(list(T), list(y))
                ax.plot(T, y, "o", color="C0")
                tt = np.linspace(T.min(), T.max(), 50)
                ax.plot(tt, d["Y_ref"] + d["slope"] * (tt - d["T_ref"]), "-", color="C1")
                ax.set_xlabel("T (K)")
                ax.set_ylabel(ylabel)
                ax.set_title(f"{key}: {d['coefficient_pct_per_K']:.3f} %/K")
            a, b = fits["alpha_Hc"], fits["beta_Mr"]
            self.tc_label.configure(
                text=(f"alpha (Hc) = {a['coefficient_pct_per_K']:.3f} %/K   R2 = {a['r_squared']}   "
                      f"n = {a['n_points']}      beta (Mr) = {b['coefficient_pct_per_K']:.3f} %/K   "
                      f"R2 = {b['r_squared']}   (reference T = {a['T_ref']:.1f} K)\n"
                      "Fitted from the accepted MH segments only; reject a segment in the MH tab to exclude it."))
        fig.tight_layout()
        self.tc_canvas.draw()

    def _effective_mass(self):
        if self.loaded is None:
            return None
        return self.loaded['mass_g'] or self.mass_override_g

    def _compute_entropy(self):
        """Delta S_M for the whole file (all MH segments, as the import does).
        Sets self.entropy (None if it could not even be attempted) and redraws."""
        fig = self.entropy_fig
        fig.clear()
        ax = fig.add_subplot(111)
        self.entropy = None
        mh_segs = [s for s in self.segments if s['type'] == 'MH']
        if self.loaded is None or len(mh_segs) < 2:
            ax.axis("off")
            ax.text(0.5, 0.5, "Entropy change needs at least 2 MH segments.", ha="center",
                    va="center", color="gray")
            self.entropy_label.configure(text="", text_color="gray")
            self.entropy_canvas.draw()
            return
        try:
            targets = tuple(int(float(p)) for p in
                            self.target_entry.get().replace(";", ",").split(",") if p.strip())
            if not targets or any(t <= 0 for t in targets):
                raise ValueError
        except ValueError:
            self.entropy_label.configure(text="Target fields must be positive integers in Oe, "
                                              "e.g. 10000, 19000.", text_color="red")
            ax.axis("off")
            self.entropy_canvas.draw()
            return
        try:
            self.entropy = compute_entropy_change_for_file(
                self.loaded['H'], self.loaded['T'], self.loaded['M'], mh_segs,
                self._effective_mass(), target_fields_Oe=targets)
        except Exception as e:
            self.entropy_label.configure(text=f"Entropy change failed: {e}", text_color="red")
            ax.axis("off")
            self.entropy_canvas.draw()
            return
        ent = self.entropy
        if not ent['suitable']:
            ax.axis("off")
            ax.text(0.5, 0.5, "Not suitable for entropy change", ha="center", va="center", color="gray")
            self.entropy_label.configure(text=f"Not suitable: {ent['reason']}", text_color="orange")
        else:
            for target, (t_mid, d_sm) in ent['results'].items():
                ax.plot(t_mid, d_sm, "o-", markersize=3, label=f"{target / 10000:g} T")
            ax.axhline(0, color="gray", linewidth=0.5)
            ax.set_xlabel("T (K)")
            ax.set_ylabel("Delta S_M (J/(kg K))")
            ax.legend()
            ax.set_title(f"Isothermal entropy change, {ent['n_isotherms']} isotherms")
            self.entropy_label.configure(
                text="First and last points are less accurate (finite difference at the boundary). "
                     "Saved with the file when you press Save to DB.", text_color="gray")
        fig.tight_layout()
        self.entropy_canvas.draw()

    def _on_recompute_entropy(self):
        self._compute_entropy()

    def _refresh_mt_menu(self):
        mt = [f"[{i}]" for i, s in enumerate(self.segments) if s['type'] == 'MT']
        self.mt_menu.configure(values=mt or ["-"])
        self.mt_var.set(mt[0] if mt else "-")
        self._refresh_mt()

    def _refresh_mt(self):
        fig = self.mt_fig
        fig.clear()
        ax = fig.add_subplot(111)
        self.mt_text.configure(state="normal")
        self.mt_text.delete("1.0", "end")
        sel = self.mt_var.get()
        if self.loaded is None or not sel.startswith("["):
            ax.axis("off")
            ax.text(0.5, 0.5, "No MT segment in this file.", ha="center", va="center", color="gray")
            self.mt_text.configure(state="disabled")
            self.mt_canvas.draw()
            return
        idx = int(sel.strip("[]"))
        seg = self.segments[idx]
        T = self.loaded['T'][seg['start']:seg['end']]
        M = self.loaded['M'][seg['start']:seg['end']]
        ax.plot(T, M, ".", markersize=2, color="C0")
        try:
            cands = extract_mt_candidates(T, M)
        except Exception as e:
            self.mt_text.insert("1.0", f"Candidate extraction failed: {e}")
            self.mt_text.configure(state="disabled")
            self.mt_canvas.draw()
            return
        lines = []
        for br in cands['branches']:
            lines.append(f"Branch {br['direction']}, T {br['T_range'][0]:.1f}-{br['T_range'][1]:.1f} K")
            for c in br['M_extrema']:
                ax.plot(c['T'], c['M'], "^" if c['kind'] == 'max' else "v", color="red")
                lines.append(f"   M {c['kind']:<3} at T = {c['T']:.2f} K   M = {c['M']:.5g} emu")
            for c in br['dMdT_extrema'][:5]:
                ax.axvline(c['T'], color="green", linestyle="--", linewidth=0.8)
                lines.append(f"   |dM/dT| peak at T = {c['T']:.2f} K   dM/dT = {c['dMdT']:.4g}")
        self.mt_text.insert("1.0", "\n".join(lines) if lines else "No candidates found.")
        self.mt_text.configure(state="disabled")
        ax.set_xlabel("T (K)")
        ax.set_ylabel("M (emu)")
        ax.set_title(f"Segment {idx} (MT); red = M extrema, green = |dM/dT| peaks")
        fig.tight_layout()
        self.mt_canvas.draw()

    # ---------------------------------------------------------------
    # Display refresh
    # ---------------------------------------------------------------
    def _refresh_segment_list(self):
        for widget in self.segment_list_frame.winfo_children():
            widget.destroy()

        for i, seg in enumerate(self.segments):
            n_events = seg.get('n_self_centering_events')
            events_str = f", {n_events} self-centering" if n_events else ""
            if seg['type'] == 'MH':
                accepted = self.segment_accepted.get(i, False)
                mark = "✓" if accepted else "✗"
                T = self.mh_results[i]['temperature_K']
                text = f"[{i}] MH {T:.0f} K  rows {seg['start']}-{seg['end']}{events_str}  {mark}"
            else:
                text = f"[{i}] {seg['type']}  rows {seg['start']}-{seg['end']}{events_str}"

            selected = (i == self.selected_segment)
            btn = ctk.CTkButton(self.segment_list_frame, text=text, anchor="w",
                                 fg_color=None if selected else "transparent",
                                 text_color=None if selected else ("gray10", "gray90"),
                                 command=lambda idx=i: self.on_select_segment(idx))
            btn.pack(fill="x", padx=2, pady=1)

    def _refresh_plot(self):
        self.ax.clear()
        idx = self.selected_segment
        seg = self.segments[idx]
        seg_H = self.loaded['H'][seg['start']:seg['end']]
        seg_M = self.loaded['M'][seg['start']:seg['end']]
        self.ax.plot(seg_H, seg_M, '.', markersize=2, color='C0')

        if seg['type'] == 'MH':
            result = self.mh_results.get(idx)
            # the branch actually analyzed, i.e. found with the operator's
            # current prominence/distance, not the defaults
            branch = result['branch'] if result else None
            if branch is not None:
                b_start, b_end = branch
                self.ax.plot(seg_H[b_start:b_end + 1], seg_M[b_start:b_end + 1],
                             color='green', linewidth=1.5, label='Descending branch')
                self.ax.legend(loc='best')
            if result and result['flag'] is None:
                self.ax.axhline(result['Mr'], color='orange', linestyle='--', linewidth=0.8)
                self.ax.axvline(-result['Hc'], color='red', linestyle='--', linewidth=0.8)

        self.ax.axhline(0, color='gray', linewidth=0.5)
        self.ax.axvline(0, color='gray', linewidth=0.5)
        self.ax.set_xlabel("H (Oe)")
        self.ax.set_ylabel("M (emu)")
        self.ax.set_title(f"Segment {idx} ({seg['type']})")
        self.canvas.draw()

    def _refresh_result_panel(self):
        idx = self.selected_segment
        seg = self.segments[idx]
        if seg['type'] != 'MH':
            self.result_label.configure(text=f"Segment {idx} is type '{seg['type']}' — no Hc/Mr to show.")
            self.accept_check.configure(state="disabled")
            return

        result = self.mh_results.get(idx)
        if result['flag'] is not None:
            self.result_label.configure(text=f"Segment {idx}: not usable — flag: {result['flag']}")
        else:
            text = (f"Segment {idx} ({result['temperature_K']:.1f} K):  "
                    f"Hc = {result['Hc']:.1f} Oe   Mr = {result['Mr']:.4f} emu")
            if result['bhmax_kJ_m3'] is not None:
                text += f"\nBH_max = {result['bhmax_kJ_m3']:.1f} kJ/m³ (Prozorov–Kogan N)"
                alt = self.mh_results_aharoni.get(idx)
                if alt is not None:
                    text += f"   |   {alt:.1f} kJ/m³ with Aharoni N (not saved)"
            elif self.geometry_used is not None:
                text += "\nBH_max: no second-quadrant points on this branch"
            self.result_label.configure(text=text)
        self.accept_check.configure(state="normal" if result['flag'] is None else "disabled")
        self.accept_var.set(self.segment_accepted.get(idx, False))

    def _refresh_summary(self):
        n_mh = len(self.mh_results)
        n_accepted = sum(1 for v in self.segment_accepted.values() if v)
        self.summary_label.configure(
            text=f"MH segments: {n_mh}  |  Accepted: {n_accepted}  |  Segments total: {len(self.segments)}"
        )

    # ---------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------
    def save_to_db(self):
        """
        Writes the reviewed result back to this file's existing records
        (created at import by vsm_integration_v2 / vsm_db_builder), in a
        single transaction:

          - vsm_mh_details, every MH segment: accepted segments get the
            re-analyzed Hc/Mr/T/field range and, with geometry, N and
            BH_max; all others get NULL Hc/Mr/BH_max and a flag (the
            automatic one, or 'operator_rejected'), so a value the
            operator rejected never stays in the database looking valid.
          - vsm_files: density and dimensions, when entered.
          - vsm_temperature_coefficients: refitted from the accepted
            segments only (removed if fewer than two distinct
            temperatures are accepted).

        Segments are matched to the stored ones by (start_row, end_row).
        If any MH segment has no stored match (e.g. the import used a
        different segmentation), nothing is written.
        """
        if not self.mh_results:
            messagebox.showerror("Nothing to save", "Run the analysis first.")
            return
        accepted = [i for i in self.mh_results if self.segment_accepted.get(i, False)]
        any_usable = any(r["flag"] is None for r in self.mh_results.values())
        if any_usable and not accepted and not messagebox.askyesno(
                "No accepted segments",
                "No MH segment is accepted. Save anyway? This clears Hc/Mr/BH_max "
                "for every MH segment of this file."):
            return

        conn = None
        try:
            from db_config import DB_CONFIG
            import psycopg2
            import psycopg2.extras

            conn_params = {k: v for k, v in DB_CONFIG.items() if k != "schema"}
            schema = DB_CONFIG.get("schema", "alloy_lab")
            conn = psycopg2.connect(**conn_params)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cur.execute(
                f"SELECT id, sample_id, density_g_cm3, dimension_a_mm, dimension_b_mm, "
                f"dimension_c_mm FROM {schema}.vsm_files WHERE file_path = %s",
                (self.file_path,)
            )
            rows = cur.fetchall()
            if not rows:
                messagebox.showerror(
                    "Not in database",
                    "This file has no vsm_files record.\nImport it via the main app first."
                )
                return
            if len(rows) > 1:
                ids = ", ".join(str(r["id"]) for r in rows)
                messagebox.showerror(
                    "Ambiguous file",
                    f"This file path is stored more than once (vsm_files ids {ids}).\n"
                    "Remove the duplicate import before saving."
                )
                return
            file_row = rows[0]
            vsm_file_id = file_row["id"]

            # Geometry stored at an earlier save but not entered now: load
            # it and re-analyze, so the operator sees the BH_max before it
            # is written, instead of silently saving without it.
            stored_dims = (file_row["dimension_a_mm"], file_row["dimension_b_mm"],
                           file_row["dimension_c_mm"])
            if (self.geometry_used is None and file_row["density_g_cm3"] is not None
                    and None not in stored_dims):
                self._set_geometry_fields(file_row["density_g_cm3"], stored_dims)
                messagebox.showinfo(
                    "Stored geometry loaded",
                    "This file already has density and dimensions in the database. "
                    "They have been filled in and the analysis re-run.\n"
                    "Review the BH_max values, then press Save again "
                    "(or clear the fields first to save without BH_max)."
                )
                self.on_analyze()
                return

            cur.execute(
                f"SELECT id, start_row, end_row FROM {schema}.vsm_segments "
                f"WHERE vsm_file_id = %s AND segment_type = 'MH'",
                (vsm_file_id,)
            )
            stored = {(r["start_row"], r["end_row"]): r["id"] for r in cur.fetchall()}
            unmatched = [i for i in self.mh_results
                         if (self.segments[i]["start"], self.segments[i]["end"]) not in stored]
            if unmatched:
                messagebox.showerror(
                    "Segments do not match",
                    f"MH segment(s) {unmatched} have no matching stored segment "
                    "(same start/end rows). The file was probably imported with a "
                    "different segmentation. Nothing was saved; re-import the file."
                )
                return

            N_pk = self.geometry_used[2] if self.geometry_used else None
            cur2 = conn.cursor()
            updated = 0
            for i, result in self.mh_results.items():
                seg = self.segments[i]
                seg_id = stored[(seg["start"], seg["end"])]
                ok = i in accepted
                if ok:
                    flag = None
                elif result["flag"] is not None:
                    flag = result["flag"]
                else:
                    flag = "operator_rejected"
                row = sanitize_row({
                    "temperature_k": result["temperature_K"],
                    "field_min_oe": result["field_min_oe"],
                    "field_max_oe": result["field_max_oe"],
                    "hc_oe": result["Hc"] if ok else None,
                    "mr_emu": result["Mr"] if ok else None,
                    "hc_mr_flag": flag,
                    "branch_found": result["branch_found"],
                    "demag_factor_n": N_pk if ok else None,
                    "bhmax_kj_m3": result["bhmax_kJ_m3"] if ok else None,
                    "seg_id": seg_id,
                })
                cur2.execute(
                    f"UPDATE {schema}.vsm_mh_details SET temperature_k = %(temperature_k)s, "
                    f"field_min_oe = %(field_min_oe)s, field_max_oe = %(field_max_oe)s, "
                    f"hc_oe = %(hc_oe)s, mr_emu = %(mr_emu)s, hc_mr_flag = %(hc_mr_flag)s, "
                    f"branch_found = %(branch_found)s, demag_factor_n = %(demag_factor_n)s, "
                    f"bhmax_kj_m3 = %(bhmax_kj_m3)s WHERE vsm_segment_id = %(seg_id)s",
                    row
                )
                if cur2.rowcount == 0:
                    cur2.execute(
                        f"INSERT INTO {schema}.vsm_mh_details (vsm_segment_id, temperature_k, "
                        f"field_min_oe, field_max_oe, hc_oe, mr_emu, hc_mr_flag, branch_found, "
                        f"demag_factor_n, bhmax_kj_m3) VALUES (%(seg_id)s, %(temperature_k)s, "
                        f"%(field_min_oe)s, %(field_max_oe)s, %(hc_oe)s, %(mr_emu)s, "
                        f"%(hc_mr_flag)s, %(branch_found)s, %(demag_factor_n)s, %(bhmax_kj_m3)s)",
                        row
                    )
                updated += 1

            if self.mass_override_g is not None:
                cur2.execute(
                    f"UPDATE {schema}.vsm_files SET mass_g = %s, mass_source = 'manual', "
                    f"mass_confidence = 'high' WHERE id = %s",
                    (self.mass_override_g, vsm_file_id)
                )

            # Entropy change: replace what the import stored with what is shown.
            n_entropy = 0
            if self.entropy is not None:
                ent = self.entropy
                cur2.execute(f"DELETE FROM {schema}.vsm_entropy_change WHERE vsm_file_id = %s",
                             (vsm_file_id,))
                cur2.execute(
                    f"UPDATE {schema}.vsm_files SET entropy_change_suitable = %s, "
                    f"entropy_change_reason = %s WHERE id = %s",
                    (bool(ent['suitable']), ent['reason'], vsm_file_id)
                )
                if ent['suitable'] and ent['results']:
                    for target, (t_mid, d_sm) in ent['results'].items():
                        for t, dsm in zip(t_mid, d_sm):
                            cur2.execute(
                                f"INSERT INTO {schema}.vsm_entropy_change (vsm_file_id, "
                                f"target_field_oe, t_mid_k, delta_sm_j_per_kg_k) "
                                f"VALUES (%(f)s, %(h)s, %(t)s, %(s)s)",
                                sanitize_row({"f": vsm_file_id, "h": int(target),
                                              "t": t, "s": dsm})
                            )
                            n_entropy += 1

            if self.geometry_used is not None:
                density, (a, b, c), _, _ = self.geometry_used
                cur2.execute(
                    f"UPDATE {schema}.vsm_files SET density_g_cm3 = %s, dimension_a_mm = %s, "
                    f"dimension_b_mm = %s, dimension_c_mm = %s WHERE id = %s",
                    (density, a, b, c, vsm_file_id)
                )

            # Temperature coefficients from the accepted segments only --
            # the ones stored at import may include segments the operator
            # has now rejected.
            cur2.execute(
                f"DELETE FROM {schema}.vsm_temperature_coefficients WHERE vsm_file_id = %s",
                (vsm_file_id,)
            )
            pts = [(self.mh_results[i]["temperature_K"], self.mh_results[i]["Hc"],
                    self.mh_results[i]["Mr"]) for i in accepted]
            n_coeffs = 0
            if len(pts) >= 2 and len({t for t, _, _ in pts}) >= 2:
                T_pts = [t for t, _, _ in pts]
                for coeff_type, Y in [("alpha_Hc", [hc for _, hc, _ in pts]),
                                      ("beta_Mr", [mr for _, _, mr in pts])]:
                    fit = fit_temperature_coefficient(T_pts, Y)
                    cur2.execute(
                        f"INSERT INTO {schema}.vsm_temperature_coefficients "
                        f"(vsm_file_id, coefficient_type, slope, t_ref, y_ref, "
                        f"coefficient_pct_per_k, n_points, r_squared) "
                        f"VALUES (%(vsm_file_id)s, %(coefficient_type)s, %(slope)s, %(t_ref)s, "
                        f"%(y_ref)s, %(coefficient_pct_per_k)s, %(n_points)s, %(r_squared)s)",
                        sanitize_row({
                            "vsm_file_id": vsm_file_id,
                            "coefficient_type": coeff_type,
                            "slope": fit["slope"],
                            "t_ref": fit["T_ref"],
                            "y_ref": fit["Y_ref"],
                            "coefficient_pct_per_k": fit["coefficient_pct_per_K"],
                            "n_points": fit["n_points"],
                            "r_squared": fit["r_squared"],
                        })
                    )
                    n_coeffs += 1

            conn.commit()
            cur2.close()
            cur.close()

            ent_str = f", {n_entropy} entropy-change points" if n_entropy else ""
            tc_str = (f", temperature coefficients refitted from {len(pts)} segments"
                      if n_coeffs else ", no temperature coefficients (fewer than 2 accepted temperatures)")
            self.save_status_label.configure(
                text=f"✅ Saved {updated} MH segment(s), {len(accepted)} accepted{tc_str}{ent_str}"
            )

        except Exception as e:
            if conn is not None:
                conn.rollback()
            import traceback
            traceback.print_exc()
            messagebox.showerror("Save failed", str(e))
            self.save_status_label.configure(text=f"❌ Save failed: {e}")
        finally:
            if conn is not None:
                conn.close()


if __name__ == "__main__":
    app = VSMMHAnalyzerApp()
    # When launched from the viewer with a file path, auto-load AND
    # auto-analyze with default parameters so the user sees results
    # immediately. They can still adjust parameters and re-analyze.
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.after(200, lambda: app.on_load_file(sys.argv[1]))
        app.after(500, app.on_analyze)
    app.mainloop()
