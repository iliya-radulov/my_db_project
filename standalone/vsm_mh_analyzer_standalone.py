"""
vsm_mh_analyzer_standalone.py

Standalone, directly-usable interactive tool for VSM MH (Hc/Mr)
analysis -- built on top of the already-validated vsm_pipeline.py
machinery (type detection, mass extraction, segmentation,
second-quadrant Hc/Mr extraction), matching the same pattern as
xrd_analyzer_standalone.py. Does NOT re-implement or modify that
analysis logic -- wraps it in a live, interactive GUI:

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
  - Accept/reject PER SEGMENT's result (not per-point/per-click) --
    deliberately no manual crossing-point override: confirmed directly
    that the crossing-point math itself is exact linear interpolation
    once a branch is correctly identified, so there's nothing for a
    human to meaningfully improve by clicking a point. What CAN go
    wrong is branch selection, which the sensitivity controls address;
    if a result still looks wrong after that, the user can do their
    own separate manual recalculation rather than the tool pretending
    to offer a precision it can't add.

Built in customtkinter (not PyQt5), matching the same project decision
as the XRD tool: can later share the main app's process/database
rather than being a disconnected subprocess. Database saving
deliberately NOT included -- quick-check tool only, same as XRD's.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from vsm_pipeline import load_vsm_file
from vsm_segmenter import detect_segments
from vsm_mh_features import extract_second_quadrant_hc_mr, find_descending_branch

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class VSMMHAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VSM MH Analyzer — Standalone")
        self.geometry("1300x800")

        self.file_path = None
        self.loaded = None
        self.segments = []
        self.mh_results = {}       # segment index -> Hc/Mr result dict
        self.segment_accepted = {} # segment index -> bool (MH segments only)
        self.selected_segment = None

        self._build_controls()
        self._build_main_area()
        self._build_summary_bar()

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_controls(self):
        frame = ctk.CTkFrame(self)
        frame.pack(side="top", fill="x", padx=8, pady=8)

        self.load_button = ctk.CTkButton(frame, text="Load .dat file", command=self.on_load_file)
        self.load_button.grid(row=0, column=0, padx=5, pady=5)

        self.file_label = ctk.CTkLabel(frame, text="No file loaded", anchor="w")
        self.file_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.info_label = ctk.CTkLabel(frame, text="", anchor="w")
        self.info_label.grid(row=0, column=2, padx=(20, 5), sticky="w")

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

    def _build_main_area(self):
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))

        # left: segment list
        left = ctk.CTkFrame(container, width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="Segments found:", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=5, pady=5)
        self.segment_list_frame = ctk.CTkScrollableFrame(left)
        self.segment_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # right: plot + result panel
        right = ctk.CTkFrame(container)
        right.pack(side="left", fill="both", expand=True)

        self.figure = Figure(figsize=(7, 4.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        result_frame = ctk.CTkFrame(right)
        result_frame.pack(side="top", fill="x", pady=(8, 0))

        self.result_label = ctk.CTkLabel(result_frame, text="Select a segment to view its result.",
                                          anchor="w", font=ctk.CTkFont(size=14))
        self.result_label.pack(side="left", padx=10, pady=10)

        self.accept_var = tk.BooleanVar(value=True)
        self.accept_check = ctk.CTkCheckBox(result_frame, text="Accept this result",
                                             variable=self.accept_var,
                                             command=self.on_accept_toggle, state="disabled")
        self.accept_check.pack(side="right", padx=10, pady=10)

    def _build_summary_bar(self):
        self.summary_label = ctk.CTkLabel(self, text="", anchor="w")
        self.summary_label.pack(side="bottom", fill="x", padx=8, pady=(0, 8))

    # ---------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------
    def on_load_file(self):
        path = filedialog.askopenfilename(filetypes=[("VSM data", "*.dat *.DAT"), ("All files", "*.*")])
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
            distance = int(self.distance_entry.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Prominence and distance must be numbers.")
            return

        try:
            self.loaded = load_vsm_file(self.file_path)
            self.segments = detect_segments(self.loaded['H'], self.loaded['T'], window=80)
        except Exception as e:
            messagebox.showerror("Load/segmentation failed", str(e))
            return

        self.info_label.configure(
            text=f"Type: {self.loaded['instrument_type']}  |  Mass: {self.loaded['mass_g']} g"
        )

        self.mh_results = {}
        self.segment_accepted = {}
        for i, seg in enumerate(self.segments):
            if seg['type'] != 'MH':
                continue
            seg_H = self.loaded['H'][seg['start']:seg['end']]
            seg_M = self.loaded['M'][seg['start']:seg['end']]
            result = extract_second_quadrant_hc_mr(seg_H, seg_M, prominence=prominence, distance=distance)
            self.mh_results[i] = result
            self.segment_accepted[i] = (result['flag'] is None)

        self._refresh_segment_list()
        self._refresh_summary()

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
        self._refresh_plot()
        self._refresh_result_panel()

    def on_accept_toggle(self):
        if self.selected_segment is not None:
            self.segment_accepted[self.selected_segment] = self.accept_var.get()
            self._refresh_segment_list()
            self._refresh_summary()

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
                text = f"[{i}] MH  rows {seg['start']}-{seg['end']}{events_str}  {mark}"
            else:
                text = f"[{i}] {seg['type']}  rows {seg['start']}-{seg['end']}{events_str}"

            btn = ctk.CTkButton(self.segment_list_frame, text=text, anchor="w",
                                 fg_color="transparent" if i != self.selected_segment else None,
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
            branch = find_descending_branch(seg_H)
            if branch is not None:
                b_start, b_end = branch
                self.ax.plot(seg_H[b_start:b_end + 1], seg_M[b_start:b_end + 1],
                             color='green', linewidth=1.5, label='Descending branch')
            result = self.mh_results.get(idx)
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
            self.result_label.configure(
                text=f"Segment {idx}:  Hc = {result['Hc']:.1f} Oe   Mr = {result['Mr']:.4f} emu"
            )
        self.accept_check.configure(state="normal" if result['flag'] is None else "disabled")
        self.accept_var.set(self.segment_accepted.get(idx, False))

    def _refresh_summary(self):
        n_mh = len(self.mh_results)
        n_accepted = sum(1 for v in self.segment_accepted.values() if v)
        self.summary_label.configure(
            text=f"MH segments: {n_mh}  |  Accepted: {n_accepted}  |  Segments total: {len(self.segments)}"
        )


if __name__ == "__main__":
    app = VSMMHAnalyzerApp()
    app.mainloop()
