#!/usr/bin/env python3
"""
Alloy Lab Database Manager - Complete Version
Tabs: New Entry | Import Files | Data Viewer | Quick Lookup | Summary
"""

import customtkinter as ctk
from tkinter import messagebox, scrolledtext, filedialog
import sys
import io
import re
import os
from datetime import datetime
from pathlib import Path

# Matplotlib imports for viewer
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

from stage_one.alloy.alloy_db_v1 import get_db
from stage_one.alloy.alloy_screening_v1 import screen_composition
from stage_one.alloy.alloy_calculator_v1 import ATOMIC_WEIGHTS
from stage_one.lookup.lookup_common_v1 import (
    from_mp_results, from_oqmd_results, from_alexandria_results,
    dedup_by_formula, filter_by_distance
)
from stage_one.tools.plot_v1 import plot_xrd, plot_vsm, plot_sem


# Human-readable labels and default cutoffs
LIT_DB_LABELS = {
    'materials_project': 'Materials Project',
    'oqmd': 'OQMD',
    'alexandria': 'Alexandria',
}
LIT_DB_DEFAULT_CUTOFFS = {
    'materials_project': 0.5,
    'oqmd': 0.4,
    'alexandria': 0.3,
}

# Set theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AlloyLabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("🧪 Alloy Lab Database")
        self.geometry("1100x850")

        # Cached literature-check results
        self.lit_results = {'materials_project': [], 'oqmd': [], 'alexandria': []}
        self.lit_cutoffs = dict(LIT_DB_DEFAULT_CUTOFFS)
        self.last_calc_output = []
        
        # Import tab state
        self.import_folder = None
        self.current_files = []
        self.file_widgets = []
        
        # Viewer tab state
        self.viewer_sample_var = None
        self.viewer_files = []
        self.current_figure = None
        self.current_canvas = None

        # Ensure any open matplotlib figures (e.g. the Data Viewer's XRD/
        # VSM/SEM plot) are closed when the app itself closes -- otherwise
        # a plot window can be left dangling after the main app exits.
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame, 
            text="🧪 Alloy Lab Database Manager",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=10)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="✅ Ready",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=(5,0))
        
        # Tabs
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_new = self.tab_view.add("📝 New Entry")
        self.tab_import = self.tab_view.add("📂 Import Files")
        self.tab_viewer = self.tab_view.add("📊 Data Viewer")
        self.tab_lookup = self.tab_view.add("🔍 Quick Lookup")
        self.tab_summary = self.tab_view.add("📊 Summary")
        
        self.setup_new_entry_tab()
        self.setup_import_tab()
        self.setup_viewer_tab()
        self.setup_lookup_tab()
        self.setup_summary_tab()

    def on_closing(self):
        """Close any open matplotlib figures (notably the Data Viewer's
        current plot) before the main window is destroyed. Without this,
        a plot window can be left open/dangling after the app itself has
        closed."""
        try:
            plt.close('all')
        except Exception:
            pass
        self.destroy()
    
    # ============================================
    # Tab 1: New Entry
    # ============================================
    
    def setup_new_entry_tab(self):
        frame = self.tab_new
        
        # Formula input
        ctk.CTkLabel(frame, text="Alloy Formula:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.formula_entry = ctk.CTkEntry(frame, width=300, placeholder_text="e.g., Fe65Nd30Co5")
        self.formula_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.formula_entry.bind("<KeyRelease>", self.validate_formula)
        
        self.validation_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=12))
        self.validation_label.grid(row=1, column=1, padx=10, pady=0, sticky="w")
        
        ctk.CTkLabel(frame, text="Unit:", font=ctk.CTkFont(size=14)).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.unit_var = ctk.StringVar(value="at%")
        self.unit_menu = ctk.CTkOptionMenu(frame, values=["at%", "wt%"], variable=self.unit_var)
        self.unit_menu.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        ctk.CTkLabel(frame, text="Target Mass (g):", font=ctk.CTkFont(size=14)).grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.mass_entry = ctk.CTkEntry(frame, width=100, placeholder_text="10.0")
        self.mass_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        self.mass_entry.insert(0, "10.0")
        
        # Material class
        ctk.CTkLabel(frame, text="Material Class:", font=ctk.CTkFont(size=14)).grid(row=4, column=0, padx=10, pady=10, sticky="w")
        
        self.class_var = ctk.StringVar(value="")
        self.class_menu = ctk.CTkOptionMenu(
            frame, 
            values=["Loading..."],
            variable=self.class_var,
            command=self.on_class_change
        )
        self.class_menu.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        
        self.custom_class_entry = ctk.CTkEntry(frame, width=200, placeholder_text="Enter custom class name")
        self.custom_class_entry.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        self.custom_class_entry.grid_remove()
        
        self.load_material_classes()
        
        ctk.CTkLabel(frame, text="Excess (e.g., Nd:3):", font=ctk.CTkFont(size=14)).grid(row=6, column=0, padx=10, pady=10, sticky="w")
        self.excess_entry = ctk.CTkEntry(frame, width=200, placeholder_text="e.g., Nd:3, Co:2")
        self.excess_entry.grid(row=6, column=1, padx=10, pady=10, sticky="w")

        # Fixed-mass pre-alloy mode -- optional. If "Pre-alloy mass" below
        # is filled in, the "Alloy Formula" field above is reinterpreted as
        # the RAW elements being added on top of a pre-alloy you already
        # have a known, fixed mass of (e.g. 13g of Fe2P) -- rather than the
        # complete target composition. Target Mass above is then ignored,
        # since the total mass is solved for rather than chosen.
        prealloy_box = ctk.CTkFrame(frame)
        prealloy_box.grid(row=7, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="ew")
        ctk.CTkLabel(
            prealloy_box,
            text="Fixed-mass pre-alloy (optional) -- leave 'Pre-alloy mass' blank for normal mode",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, columnspan=4, padx=10, pady=(8, 4), sticky="w")

        ctk.CTkLabel(prealloy_box, text="Pre-alloy formula:", font=ctk.CTkFont(size=13)).grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.prealloy_formula_entry = ctk.CTkEntry(prealloy_box, width=140, placeholder_text="e.g., Fe2P")
        self.prealloy_formula_entry.grid(row=1, column=1, padx=5, pady=6, sticky="w")

        ctk.CTkLabel(prealloy_box, text="Pre-alloy mass (g):", font=ctk.CTkFont(size=13)).grid(row=1, column=2, padx=10, pady=6, sticky="w")
        self.prealloy_mass_entry = ctk.CTkEntry(prealloy_box, width=100, placeholder_text="e.g., 13")
        self.prealloy_mass_entry.grid(row=1, column=3, padx=5, pady=6, sticky="w")

        ctk.CTkLabel(prealloy_box, text="Pre-alloy at% of final:", font=ctk.CTkFont(size=13)).grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")
        self.prealloy_atpct_entry = ctk.CTkEntry(prealloy_box, width=140, placeholder_text="e.g., 85")
        self.prealloy_atpct_entry.grid(row=2, column=1, padx=5, pady=(0, 8), sticky="w")

        ctk.CTkLabel(
            prealloy_box,
            text="When set: 'Alloy Formula' above = raw elements to add (at%, e.g. Co5Si10)",
            font=ctk.CTkFont(size=11), text_color="gray60"
        ).grid(row=2, column=2, columnspan=2, padx=10, pady=(0, 8), sticky="w")
        
        ctk.CTkLabel(frame, text="Sample ID:", font=ctk.CTkFont(size=14)).grid(row=8, column=0, padx=10, pady=10, sticky="w")
        self.sample_id_entry = ctk.CTkEntry(frame, width=300, placeholder_text="Auto-generated")
        self.sample_id_entry.grid(row=8, column=1, padx=10, pady=10, sticky="w")
        self.auto_generate_id()
        
        self.auto_id_btn = ctk.CTkButton(frame, text="🔄 Auto-generate ID", command=self.auto_generate_id, width=150)
        self.auto_id_btn.grid(row=8, column=2, padx=10, pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.grid(row=9, column=0, columnspan=3, pady=20)
        
        self.calc_btn = ctk.CTkButton(btn_frame, text="🧪 Calculate & Preview", command=self.run_calculation, width=200)
        self.calc_btn.pack(side="left", padx=10)
        
        self.submit_btn = ctk.CTkButton(btn_frame, text="💾 Submit to Database", command=self.submit_to_db, width=200, state="disabled")
        self.submit_btn.pack(side="left", padx=10)

        self.skip_search_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            btn_frame, text="Skip literature search (screening + mass calc only)",
            variable=self.skip_search_var
        ).pack(side="left", padx=20)
        
        # Literature controls
        lit_frame = ctk.CTkFrame(frame)
        lit_frame.grid(row=10, column=0, columnspan=3, padx=10, pady=(0, 5), sticky="ew")
        
        ctk.CTkLabel(lit_frame, text="Literature DB:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(10, 5))
        
        self.lit_db_var = ctk.StringVar(value='materials_project')
        for db_key in ('materials_project', 'oqmd', 'alexandria'):
            ctk.CTkRadioButton(
                lit_frame, text=LIT_DB_LABELS[db_key], variable=self.lit_db_var,
                value=db_key, command=self.on_lit_db_change
            ).pack(side="left", padx=8)
        
        ctk.CTkLabel(lit_frame, text="  Cutoff:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(20, 5))
        self.lit_cutoff_slider = ctk.CTkSlider(
            lit_frame, from_=0.05, to=1.0, number_of_steps=19,
            command=self.on_lit_cutoff_change, width=180
        )
        self.lit_cutoff_slider.set(LIT_DB_DEFAULT_CUTOFFS['materials_project'])
        self.lit_cutoff_slider.pack(side="left", padx=5)
        
        self.lit_cutoff_label = ctk.CTkLabel(lit_frame, text="", font=ctk.CTkFont(size=13))
        self.lit_cutoff_label.pack(side="left", padx=10)
        
        self.result_text = scrolledtext.ScrolledText(frame, height=15, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.result_text.grid(row=11, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(11, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        self.update_lit_cutoff_label()
    
    # ============================================
    # Tab 2: Import Files
    # ============================================
    
    def setup_import_tab(self):
        frame = self.tab_import
        
        ctk.CTkLabel(frame, text="Select Folder:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.folder_path_var = ctk.StringVar(value="")
        self.folder_entry = ctk.CTkEntry(frame, width=400, textvariable=self.folder_path_var, placeholder_text="Path to sorted folder...")
        self.folder_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.browse_btn = ctk.CTkButton(frame, text="📁 Browse", command=self.browse_folder, width=100)
        self.browse_btn.grid(row=0, column=2, padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(frame, text="🔄 Refresh", command=self.refresh_files, width=100)
        self.refresh_btn.grid(row=0, column=3, padx=10, pady=10)
        
        list_frame = ctk.CTkFrame(frame)
        list_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        self.file_list_container = ctk.CTkScrollableFrame(list_frame, height=250)
        self.file_list_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.file_widgets = []
        
        action_frame = ctk.CTkFrame(frame)
        action_frame.grid(row=2, column=0, columnspan=4, pady=10)
        
        self.auto_detect_btn = ctk.CTkButton(action_frame, text="🔍 Auto-detect Samples", command=self.auto_detect_samples, width=180)
        self.auto_detect_btn.pack(side="left", padx=10)
        
        self.import_all_btn = ctk.CTkButton(action_frame, text="📥 Import Selected", command=self.import_selected, width=180)
        self.import_all_btn.pack(side="left", padx=10)
        
        self.select_all_btn = ctk.CTkButton(action_frame, text="☑️ Select All", command=self.select_all_files, width=120)
        self.select_all_btn.pack(side="left", padx=10)
        
        self.deselect_all_btn = ctk.CTkButton(action_frame, text="☐ Deselect All", command=self.deselect_all_files, width=120)
        self.deselect_all_btn.pack(side="left", padx=10)
        
        manual_frame = ctk.CTkFrame(frame)
        manual_frame.grid(row=3, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(manual_frame, text="Manual Entry (for selected file):", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10)
        
        self.manual_sample_entry = ctk.CTkEntry(manual_frame, width=200, placeholder_text="Enter sample ID manually")
        self.manual_sample_entry.pack(side="left", padx=10)
        
        self.apply_manual_btn = ctk.CTkButton(manual_frame, text="Apply to Selected", command=self.apply_manual_to_selected, width=120)
        self.apply_manual_btn.pack(side="left", padx=10)
        
        ctk.CTkLabel(manual_frame, text="(or use dropdown per file below)", font=ctk.CTkFont(size=11)).pack(side="left", padx=10)
        
        ctk.CTkLabel(frame, text="Import Log:", font=ctk.CTkFont(size=14)).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        
        self.import_log = scrolledtext.ScrolledText(frame, height=10, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.import_log.grid(row=5, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(5, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    # ============================================
    # Tab 3: Data Viewer
    # ============================================
    
    def setup_viewer_tab(self):
        frame = self.tab_viewer
        
        top_frame = ctk.CTkFrame(frame)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(top_frame, text="Select Sample:", font=ctk.CTkFont(size=14)).pack(side="left", padx=10)
        
        self.viewer_sample_var = ctk.StringVar(value="")
        self.viewer_sample_menu = ctk.CTkOptionMenu(
            top_frame, 
            values=["Loading..."],
            variable=self.viewer_sample_var,
            command=self.on_viewer_sample_change,
            width=200
        )
        self.viewer_sample_menu.pack(side="left", padx=10)
        
        self.viewer_refresh_btn = ctk.CTkButton(top_frame, text="🔄 Refresh", command=self.refresh_viewer_samples, width=100)
        self.viewer_refresh_btn.pack(side="left", padx=10)
        
        middle_frame = ctk.CTkFrame(frame)
        middle_frame.pack(fill="both", expand=True, padx=10, pady=10)
        middle_frame.grid_rowconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(0, weight=1)
        middle_frame.grid_columnconfigure(1, weight=3)
        
        left_frame = ctk.CTkFrame(middle_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        
        ctk.CTkLabel(left_frame, text="Characterization Files:", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
        
        self.viewer_file_listbox = ctk.CTkScrollableFrame(left_frame, height=300)
        self.viewer_file_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.viewer_file_buttons = []
        
        right_frame = ctk.CTkFrame(middle_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        
        ctk.CTkLabel(right_frame, text="Data Plot:", font=ctk.CTkFont(size=13, weight="bold")).pack(pady=5)
        
        self.viewer_plot_frame = ctk.CTkFrame(right_frame)
        self.viewer_plot_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.viewer_plot_label = ctk.CTkLabel(
            self.viewer_plot_frame, 
            text="Select a sample and file to view",
            font=ctk.CTkFont(size=14)
        )
        self.viewer_plot_label.pack(expand=True)
        
        bottom_frame = ctk.CTkFrame(frame)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        
        self.viewer_info_label = ctk.CTkLabel(bottom_frame, text="", font=ctk.CTkFont(size=12))
        self.viewer_info_label.pack(side="left", padx=10)
        
        self.refresh_viewer_samples()
    
    def refresh_viewer_samples(self):
        try:
            db = get_db()
            db.cursor.execute("SELECT sample_id FROM samples ORDER BY sample_id")
            results = db.cursor.fetchall()
            db.close()
            
            samples = [r['sample_id'] for r in results]
            if samples:
                self.viewer_sample_menu.configure(values=samples)
                if not self.viewer_sample_var.get() or self.viewer_sample_var.get() not in samples:
                    self.viewer_sample_var.set(samples[0])
                    self.on_viewer_sample_change(samples[0])
            else:
                self.viewer_sample_menu.configure(values=["No samples"])
                self.viewer_sample_var.set("No samples")
        except Exception as e:
            print(f"Error loading samples: {e}")
    
    def on_viewer_sample_change(self, sample_id):
        if not sample_id or sample_id in ["No samples", "Error loading"]:
            return
        
        for btn in self.viewer_file_buttons:
            btn.destroy()
        self.viewer_file_buttons = []
        
        try:
            db = get_db()
            db.cursor.execute("""
                SELECT id, char_type, file_path, instrument, created_at
                FROM characterization
                WHERE sample_id = (SELECT id FROM samples WHERE sample_id = %s)
                ORDER BY created_at DESC
            """, (sample_id,))
            results = db.cursor.fetchall()
            db.close()
            
            self.viewer_files = results
            
            if not results:
                label = ctk.CTkLabel(self.viewer_file_listbox, text="No characterization files", font=ctk.CTkFont(size=12))
                label.pack(pady=10)
                self.viewer_file_buttons.append(label)
                self.viewer_plot_label.configure(text="No files available for this sample")
                return
            
            for row in results:
                char_id = row['id']
                char_type = row['char_type']
                file_path = row['file_path'] or "No file"
                instrument = row['instrument'] or "Unknown"
                
                btn_frame = ctk.CTkFrame(self.viewer_file_listbox)
                btn_frame.pack(fill="x", padx=2, pady=2)
                
                btn_text = f"{char_type} ({instrument})"
                if file_path and file_path != "No file":
                    btn_text += f" - {Path(file_path).name}"
                
                btn = ctk.CTkButton(
                    btn_frame,
                    text=btn_text,
                    command=lambda fid=char_id: self.viewer_load_plot(fid),
                    width=200,
                    anchor="w",
                    font=ctk.CTkFont(size=11)
                )
                btn.pack(side="left", fill="x", expand=True)
                
                btn.file_info = {
                    'id': char_id,
                    'type': char_type,
                    'path': file_path,
                    'instrument': instrument
                }
                
                self.viewer_file_buttons.append(btn_frame)
        except Exception as e:
            print(f"Error loading characterization: {e}")
    
    def viewer_load_plot(self, char_id):
        # Add this at the beginning of viewer_load_plot
        if self.current_figure is not None:
            plt.close(self.current_figure)
            self.current_figure = None
        file_info = None
        for btn_frame in self.viewer_file_buttons:
            if hasattr(btn_frame.winfo_children()[0], 'file_info'):
                info = btn_frame.winfo_children()[0].file_info
                if info['id'] == char_id:
                    file_info = info
                    break
        
        if not file_info:
            self.viewer_plot_label.configure(text="File info not found")
            return
        
        file_path = file_info['path']
        char_type = file_info['type']
        
        if not file_path or not os.path.exists(file_path):
            self.viewer_plot_label.configure(text=f"File not found: {file_path}")
            return
        
        for widget in self.viewer_plot_frame.winfo_children():
            if widget != self.viewer_plot_label:
                widget.destroy()
        
        self.viewer_plot_label.pack_forget()
        
        try:
            fig = None
            error = None
            
            if char_type == 'XRD':
                fig, error = plot_xrd(file_path)
            elif char_type in ['VSM', 'MH']:
                fig, error = plot_vsm(file_path)
            elif char_type == 'SEM':
                fig, error = plot_sem(file_path)
            else:
                self.viewer_plot_label.pack()
                self.viewer_plot_label.configure(text=f"Unsupported file type: {char_type}")
                return
            
            if error:
                self.viewer_plot_label.pack()
                self.viewer_plot_label.configure(text=f"Error: {error}")
                return
            
            if fig:
                canvas = FigureCanvasTkAgg(fig, master=self.viewer_plot_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)
                self.current_canvas = canvas
                self.current_figure = fig
                self.viewer_info_label.configure(text=f"File: {Path(file_path).name} | Type: {char_type}")
        except Exception as e:
            self.viewer_plot_label.pack()
            self.viewer_plot_label.configure(text=f"Error loading plot: {str(e)}")
    
    # ============================================
    # Tab 4: Quick Lookup
    # ============================================
    
    def setup_lookup_tab(self):
        frame = self.tab_lookup
        
        ctk.CTkLabel(frame, text="Search Sample ID:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.search_entry = ctk.CTkEntry(frame, width=250, placeholder_text="e.g., RP1a")
        self.search_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.search_btn = ctk.CTkButton(frame, text="🔍 Search", command=self.search_sample, width=120)
        self.search_btn.grid(row=0, column=2, padx=10, pady=10)
        
        self.search_result = scrolledtext.ScrolledText(frame, height=20, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.search_result.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    def search_sample(self):
        sample_id = self.search_entry.get().strip()
        if not sample_id:
            return
        
        self.search_result.delete(1.0, "end")
        self.status_label.configure(text=f"Searching for {sample_id}...")
        
        try:
            db = get_db()
            sample = db.get_sample(sample_id)
            
            if not sample:
                self.search_result.insert("end", f"Sample '{sample_id}' not found")
                self.status_label.configure(text=f"Sample '{sample_id}' not found")
                return
            
            output = []
            output.append("="*60)
            output.append(f"Sample: {sample['sample_id']}")
            output.append("="*60)
            output.append(f"Class: {sample['material_class']}")
            output.append(f"Mass: {sample['mass_grams']}g")
            output.append(f"Source: {sample['source_type']}")
            output.append(f"Created: {sample['created_at']}")
            
            output.append("\nComposition (at%):")
            comp = sample['composition']
            for elem, frac in comp.items():
                output.append(f"  {elem}: {frac*100:.2f} at%")
            
            if sample.get('vec') is not None:
                output.append("\nScreening:")
                output.append(f"  VEC = {sample['vec']:.2f}")
                output.append(f"  δ = {sample['delta']:.3f}")
                output.append(f"  ΔH_mix = {sample['delta_h_mix']:.1f} kJ/mol")
            
            db.cursor.execute(
                "SELECT source_db, match_formula, tier, stability, experimentally_known FROM literature_checks WHERE sample_id = %s",
                (sample['id'],)
            )
            lit_checks = db.cursor.fetchall()
            if lit_checks:
                output.append(f"\nLiterature Checks ({len(lit_checks)}):")
                for row in lit_checks:
                    stable = "stable" if row['stability'] == 0 else f"{row['stability']:.3f} eV"
                    known = "known" if row['experimentally_known'] else "theoretical"
                    output.append(f"  {row['source_db']}: {row['match_formula']} (Tier {row['tier']}) - {stable}, {known}")
            
            self.search_result.insert("end", "\n".join(output))
            self.status_label.configure(text=f"Found sample: {sample_id}")
            db.close()
        except Exception as e:
            self.search_result.insert("end", f"Error: {str(e)}")
            self.status_label.configure(text=f"Error: {str(e)}")
    
    # ============================================
    # Tab 5: Summary
    # ============================================
    
    def setup_summary_tab(self):
        frame = self.tab_summary
        
        self.refresh_btn = ctk.CTkButton(frame, text="🔄 Refresh Summary", command=self.load_summary, width=200)
        self.refresh_btn.pack(pady=10)
        
        self.summary_text = scrolledtext.ScrolledText(frame, height=25, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.summary_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.after(100, self.load_summary)
    
    def load_summary(self):
        self.summary_text.delete(1.0, "end")
        self.status_label.configure(text="Loading summary...")
        
        try:
            db = get_db()
            
            db.cursor.execute("SELECT COUNT(*) FROM samples")
            sample_count = db.cursor.fetchone()['count']
            
            db.cursor.execute("""
                SELECT mc.class_name, COUNT(*) 
                FROM samples s 
                JOIN material_classes mc ON s.material_class_id = mc.id 
                GROUP BY mc.class_name
            """)
            class_counts = db.cursor.fetchall()
            
            db.cursor.execute("""
                SELECT sample_id, created_at, source_type 
                FROM samples 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            recent = db.cursor.fetchall()
            
            db.cursor.execute("SELECT COUNT(*) FROM literature_checks")
            lit_count = db.cursor.fetchone()['count']
            
            output = []
            output.append("="*60)
            output.append("Database Summary")
            output.append("="*60)
            output.append(f"\nTotal Samples: {sample_count}")
            output.append(f"Literature Checks: {lit_count}")
            output.append("\nBy Material Class:")
            for row in class_counts:
                output.append(f"  {row['class_name']}: {row['count']}")
            output.append("\nRecent Samples (last 10):")
            for row in recent:
                output.append(f"  {row['sample_id']} ({row['source_type']}) - {row['created_at']}")
            
            self.summary_text.insert("end", "\n".join(output))
            self.status_label.configure(text="Summary loaded")
            db.close()
        except Exception as e:
            self.summary_text.insert("end", f"Error loading summary: {str(e)}")
            self.status_label.configure(text=f"Error: {str(e)}")
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def load_material_classes(self):
        try:
            db = get_db()
            db.cursor.execute("SELECT class_name FROM material_classes ORDER BY class_name")
            results = db.cursor.fetchall()
            db.close()
            
            classes = [row['class_name'] for row in results]
            if not classes:
                classes = ["Permanent Magnet", "Soft Magnetic", "High Entropy Alloy", "Heusler", "Single Crystal"]
            classes.append("Custom...")
            
            self.class_menu.configure(values=classes)
            if not self.class_var.get() or self.class_var.get() not in classes:
                self.class_var.set(classes[0])
        except Exception as e:
            print(f"Could not load material classes: {e}")
    
    def validate_formula(self, event=None):
        formula = self.formula_entry.get().strip()
        if not formula:
            self.validation_label.configure(text="", text_color="gray")
            return
        
        try:
            from stage_one.alloy.alloy_calculator_v1 import parse_composition_input
            parsed = parse_composition_input(formula)
            if parsed:
                invalid = [e for e in parsed.keys() if e not in ATOMIC_WEIGHTS]
                if invalid:
                    self.validation_label.configure(text=f"Unknown element(s): {', '.join(invalid)}", text_color="orange")
                else:
                    self.validation_label.configure(
                        text=f"Valid: {', '.join([f'{k}={v:.1f}' for k,v in parsed.items()])}",
                        text_color="green"
                    )
                    self.auto_generate_id()
        except ValueError as e:
            self.validation_label.configure(text=f"Error: {str(e)}", text_color="red")
        except Exception as e:
            self.validation_label.configure(text=f"Parse error: {str(e)}", text_color="red")
    
    def generate_sample_id(self):
        formula = self.formula_entry.get().strip()
        if not formula:
            formula = "NEW"
        else:
            formula = re.sub(r'[^A-Za-z0-9]', '', formula)[:20]
        
        date_str = datetime.now().strftime('%Y%m%d')
        prefix = f"{formula}-{date_str}"
        
        try:
            db = get_db()
            db.cursor.execute(
                "SELECT sample_id FROM samples WHERE sample_id LIKE %s ORDER BY sample_id DESC LIMIT 1",
                (f"{prefix}%",)
            )
            result = db.cursor.fetchone()
            db.close()
            
            if result:
                last_id = result['sample_id']
                match = re.search(r'-(\d{3})$', last_id)
                next_num = int(match.group(1)) + 1 if match else 1
            else:
                next_num = 1
        except Exception:
            next_num = 1
        
        return f"{prefix}-{next_num:03d}"
    
    def auto_generate_id(self):
        new_id = self.generate_sample_id()
        self.sample_id_entry.delete(0, "end")
        self.sample_id_entry.insert(0, new_id)
    
    def on_class_change(self, choice):
        if choice == "Custom...":
            self.custom_class_entry.grid()
            self.custom_class_entry.focus()
        else:
            self.custom_class_entry.grid_remove()
    
    def get_material_class(self):
        selected = self.class_var.get()
        if selected == "Custom...":
            custom = self.custom_class_entry.get().strip()
            if custom:
                return custom
            else:
                messagebox.showwarning("Warning", "Please enter a custom class name")
                return None
        return selected
    
    def run_calculation(self):
        self.result_text.delete(1.0, "end")
        self.status_label.configure(text="Calculating...")
        
        try:
            formula = self.formula_entry.get().strip()
            if not formula:
                messagebox.showwarning("Warning", "Please enter a formula")
                self.status_label.configure(text="No formula entered")
                return
            
            from stage_one.alloy.alloy_calculator_v1 import (
                parse_composition_input, parse_composition_with_unit, calculate_masses,
                calculate_masses_from_fixed_prealloy, ElementComponent, PreAlloyComponent
            )

            prealloy_mass_str = self.prealloy_mass_entry.get().strip()
            prealloy_mode = bool(prealloy_mass_str)

            if prealloy_mode:
                # Pre-alloy mode: "formula" field = raw elements to add,
                # given as LITERAL at% of the final composition (not
                # renormalized among themselves) -- e.g. "Co5Si10" means
                # exactly 5% Co and 10% Si of the eventual whole, not a
                # 1:2 ratio rescaled to sum to 100.
                try:
                    raw_at_pct = parse_composition_input(formula, normalize=False)
                    invalid = [e for e in raw_at_pct.keys() if e not in ATOMIC_WEIGHTS]
                    if invalid:
                        messagebox.showerror("Invalid Formula", f"Unknown element(s): {', '.join(invalid)}")
                        self.status_label.configure(text="Invalid formula")
                        return
                except ValueError as e:
                    messagebox.showerror("Invalid Formula", str(e))
                    self.status_label.configure(text="Invalid formula")
                    return

                prealloy_formula = self.prealloy_formula_entry.get().strip()
                if not prealloy_formula:
                    messagebox.showwarning("Warning", "Enter the pre-alloy's own formula (e.g. Fe2P)")
                    self.status_label.configure(text="No pre-alloy formula entered")
                    return
                try:
                    prealloy_mass = float(prealloy_mass_str)
                    prealloy_atpct = float(self.prealloy_atpct_entry.get().strip())
                except ValueError:
                    messagebox.showerror("Invalid Input", "Pre-alloy mass and at% must be numbers")
                    self.status_label.configure(text="Invalid pre-alloy input")
                    return

                prealloy_composition = parse_composition_with_unit(prealloy_formula, 'at%')
                prealloy_component = PreAlloyComponent(
                    name=prealloy_formula, at_pct=prealloy_atpct, composition=prealloy_composition
                )
            else:
                try:
                    parsed = parse_composition_input(formula)
                    invalid = [e for e in parsed.keys() if e not in ATOMIC_WEIGHTS]
                    if invalid:
                        messagebox.showerror("Invalid Formula", f"Unknown element(s): {', '.join(invalid)}")
                        self.status_label.configure(text="Invalid formula")
                        return
                except ValueError as e:
                    messagebox.showerror("Invalid Formula", str(e))
                    self.status_label.configure(text="Invalid formula")
                    return
            
            unit = self.unit_var.get()
            mass = float(self.mass_entry.get()) if self.mass_entry.get() else 10.0
            
            material_class = self.get_material_class()
            if material_class is None:
                self.status_label.configure(text="No material class selected")
                return

            excess_input = self.excess_entry.get().strip()
            excess_dict = {}
            if excess_input:
                for item in excess_input.split(','):
                    if ':' in item:
                        elem, pct = item.split(':')
                        excess_dict[elem.strip()] = float(pct.strip())

            if prealloy_mode:
                elements = [
                    ElementComponent(symbol=sym, at_pct=val, excess_pct=excess_dict.get(sym, 0.0))
                    for sym, val in raw_at_pct.items()
                ]
                # Full merged final composition (pre-alloy's own elements +
                # raw additions) -- this is what screening, the literature
                # lookups, and the eventual DB composition column need, same
                # shape as normal mode's at_composition/comp_frac.
                full = calculate_masses(total_mass_g=1.0, elements=elements, pre_alloys=[prealloy_component])
                at_composition = {e.symbol: e.at_pct for e in full.elements}
                comp_frac = {k: v / 100 for k, v in at_composition.items()}

                # The actual masses to weigh -- raw elements only, correctly
                # solved from the pre-alloy's known fixed mass.
                result = calculate_masses_from_fixed_prealloy(
                    known_prealloy_grams=prealloy_mass,
                    prealloy=prealloy_component,
                    elements=elements,
                )
                mass = result.total_mass_g  # solved, not the (ignored) Target Mass field
            else:
                at_composition = parse_composition_with_unit(formula, unit)
                comp_frac = {k: v/100 for k, v in at_composition.items()}
                elements = []
                for symbol, at_pct in at_composition.items():
                    excess = excess_dict.get(symbol, 0.0)
                    elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
                result = calculate_masses(total_mass_g=mass, elements=elements)
            
            from stage_one.alloy.alloy_screening_v1 import IncompleteElementDataError
            try:
                screening = screen_composition(comp_frac)
            except IncompleteElementDataError as e:
                screening = None
                screening_warning = str(e)
            else:
                screening_warning = None
            
            output = []
            output.append("="*60)
            output.append("Calculation Results")
            output.append("="*60)
            if prealloy_mode:
                output.append(f"\nPre-alloy: {self.prealloy_formula_entry.get().strip()} -- {prealloy_mass}g (already have)")
                output.append(f"Raw elements to add (at%): {formula}")
                output.append(f"Total mass (solved): {mass:.4f}g")
            else:
                output.append(f"\nFormula: {formula} (as {unit})")
                output.append(f"Target mass: {mass}g")
            output.append(f"Material class: {material_class}")
            output.append(f"Sample ID: {self.sample_id_entry.get()}")
            
            if screening is not None:
                output.append("\nScreening Results:")
                output.append(f"  VEC = {screening['VEC']:.2f}")
                output.append(f"  δ = {screening['delta']:.3f}")
                output.append(f"  ΔH_mix = {screening['Delta_H_mix']:.1f} kJ/mol")
            else:
                output.append(f"\nScreening skipped: {screening_warning}")
            
            if prealloy_mode:
                output.append(f"\nPre-alloy (already have): {result.pre_alloys[0].name} -- {result.pre_alloys[0].grams:.4f}g")
                output.append("\nRaw elements to add:")
            else:
                output.append("\nMass Breakdown:")
            output.append(f"{'Element':<10}{'at%':>8}{'wt%':>8}{'target(g)':>10}{'weigh(g)':>10}")
            output.append("-" * 46)
            for e in result.elements:
                output.append(f"{e.symbol:<10}{e.at_pct:>8.2f}{e.wt_pct:>8.2f}{e.grams:>10.4f}{e.weigh_grams:>10.4f}")
            output.append("\n" + "="*60)
            
            self.last_calc_output = output

            self.search_was_skipped = self.skip_search_var.get()

            if self.search_was_skipped:
                self.lit_results = {'materials_project': [], 'oqmd': [], 'alexandria': []}
            else:
                self.status_label.configure(text="Checking literature databases...")
                self.update_idletasks()  # force repaint now -- without this the
                                          # label change isn't actually visible
                                          # until after all 3 blocking calls
                                          # below finish, making the app look
                                          # frozen even though it's working

                try:
                    from stage_one.alloy.alloy_entry_full_v1 import get_api_key
                    from stage_one.lookup.mp_lookup_v1 import lookup as mp_lookup_fn
                    api_key = get_api_key()
                    if api_key:
                        self.status_label.configure(text="Checking Materials Project...")
                        self.update_idletasks()
                        mp_raw = mp_lookup_fn(comp_frac, api_key=api_key)
                        self.lit_results['materials_project'] = dedup_by_formula(from_mp_results(mp_raw))
                    else:
                        self.lit_results['materials_project'] = []
                except Exception as e:
                    print(f"MP lookup failed: {e}")
                    self.lit_results['materials_project'] = []

                try:
                    from stage_one.lookup.oqmd_lookup_v1 import lookup as oqmd_lookup_fn
                    self.status_label.configure(text="Checking OQMD...")
                    self.update_idletasks()
                    oqmd_raw = oqmd_lookup_fn(comp_frac)
                    self.lit_results['oqmd'] = dedup_by_formula(from_oqmd_results(oqmd_raw))
                except Exception as e:
                    print(f"OQMD lookup failed: {e}")
                    self.lit_results['oqmd'] = []

                try:
                    from stage_one.lookup.alexandria_lookup_v1 import lookup as alexandria_lookup_fn
                    self.status_label.configure(text="Checking Alexandria...")
                    self.update_idletasks()
                    alexandria_raw = alexandria_lookup_fn(comp_frac)
                    self.lit_results['alexandria'] = dedup_by_formula(from_alexandria_results(alexandria_raw))
                except Exception as e:
                    print(f"Alexandria lookup failed: {e}")
                    self.lit_results['alexandria'] = []
            
            self.render_lit_section()
            self.submit_btn.configure(state="normal")
            self.status_label.configure(text="Calculation complete - ready to submit")
            
        except Exception as e:
            self.result_text.insert("end", f"Error: {str(e)}")
            self.status_label.configure(text=f"Error: {str(e)}")
    
    def render_lit_section(self):
        db_key = self.lit_db_var.get()
        cutoff = self.lit_cutoffs[db_key]
        all_candidates = self.lit_results.get(db_key, [])
        shown = filter_by_distance(all_candidates, cutoff)
        
        lines = []
        if getattr(self, 'search_was_skipped', False):
            lines.append(f"\n{LIT_DB_LABELS[db_key]} literature check -- skipped (checkbox was set)")
            lines.append("-" * 60)
        else:
            lines.append(f"\n{LIT_DB_LABELS[db_key]} literature check (cutoff={cutoff:.2f}) -- {len(shown)} of {len(all_candidates)} shown")
            lines.append("-" * 60)
            if not shown:
                lines.append("  (none within cutoff)" if all_candidates else "  (no results)")
        for c in shown:
            stability = "stable" if c.stability == 0 else (f"{c.stability:.3f} eV/atom" if c.stability is not None else "unknown")
            known = "known" if c.experimentally_known else "computed only"
            dist_str = f", distance={c.composition_distance:.3f}" if c.composition_distance is not None else ""
            lines.append(f"  Tier {c.tier}  {c.formula:<15} {stability:<18} ({known}){dist_str}")
        
        self.result_text.delete(1.0, "end")
        self.result_text.insert("end", "\n".join(self.last_calc_output + [""] + lines))
    
    def on_lit_db_change(self):
        db_key = self.lit_db_var.get()
        self.lit_cutoff_slider.set(self.lit_cutoffs[db_key])
        self.update_lit_cutoff_label()
        if any(self.lit_results.values()):
            self.render_lit_section()
    
    def on_lit_cutoff_change(self, value):
        db_key = self.lit_db_var.get()
        self.lit_cutoffs[db_key] = float(value)
        self.update_lit_cutoff_label()
        if any(self.lit_results.values()):
            self.render_lit_section()
    
    def update_lit_cutoff_label(self):
        db_key = self.lit_db_var.get()
        self.lit_cutoff_label.configure(text=f"{self.lit_cutoffs[db_key]:.2f}")
    
    def submit_to_db(self):
        self.status_label.configure(text="Submitting to database...")
        
        try:
            formula = self.formula_entry.get().strip()
            unit = self.unit_var.get()
            mass = float(self.mass_entry.get()) if self.mass_entry.get() else 10.0
            material_class = self.get_material_class()
            sample_id = self.sample_id_entry.get().strip()
            
            if not sample_id:
                sample_id = self.generate_sample_id()
                self.sample_id_entry.insert(0, sample_id)
            
            if material_class is None:
                self.status_label.configure(text="No material class selected")
                return
            
            from stage_one.alloy.alloy_db_v1 import get_db
            from stage_one.alloy.alloy_calculator_v1 import (
                parse_composition_input, parse_composition_with_unit, calculate_masses,
                calculate_masses_from_fixed_prealloy, ElementComponent, PreAlloyComponent
            )
            from stage_one.alloy.alloy_screening_v1 import screen_composition

            excess_input = self.excess_entry.get().strip()
            excess_dict = {}
            if excess_input:
                for item in excess_input.split(','):
                    if ':' in item:
                        elem, pct = item.split(':')
                        excess_dict[elem.strip()] = float(pct.strip())

            prealloy_mass_str = self.prealloy_mass_entry.get().strip()
            prealloy_mode = bool(prealloy_mass_str)
            prealloy_name = None

            if prealloy_mode:
                raw_at_pct = parse_composition_input(formula, normalize=False)
                prealloy_formula = self.prealloy_formula_entry.get().strip()
                prealloy_mass = float(prealloy_mass_str)
                prealloy_atpct = float(self.prealloy_atpct_entry.get().strip())
                prealloy_composition = parse_composition_with_unit(prealloy_formula, 'at%')
                prealloy_component = PreAlloyComponent(
                    name=prealloy_formula, at_pct=prealloy_atpct, composition=prealloy_composition
                )
                prealloy_name = prealloy_formula

                elements = [
                    ElementComponent(symbol=sym, at_pct=val, excess_pct=excess_dict.get(sym, 0.0))
                    for sym, val in raw_at_pct.items()
                ]
                full = calculate_masses(total_mass_g=1.0, elements=elements, pre_alloys=[prealloy_component])
                at_composition = {e.symbol: e.at_pct for e in full.elements}
                comp_frac = {k: v / 100 for k, v in at_composition.items()}

                result = calculate_masses_from_fixed_prealloy(
                    known_prealloy_grams=prealloy_mass, prealloy=prealloy_component, elements=elements,
                )
                mass = result.total_mass_g
            else:
                at_composition = parse_composition_with_unit(formula, unit)
                comp_frac = {k: v/100 for k, v in at_composition.items()}
                elements = []
                for symbol, at_pct in at_composition.items():
                    excess = excess_dict.get(symbol, 0.0)
                    elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
                result = calculate_masses(total_mass_g=mass, elements=elements)
            
            from stage_one.alloy.alloy_screening_v1 import IncompleteElementDataError
            try:
                screening = screen_composition(comp_frac)
            except IncompleteElementDataError as e:
                screening = None
                print(f"Screening skipped: {e}")
            
            db = get_db()
            
            existing = db.get_sample(sample_id)
            if existing:
                if not messagebox.askyesno("Sample Exists", f"Sample {sample_id} already exists. Override?"):
                    self.status_label.configure(text="Cancelled")
                    db.close()
                    return
            
            composition_frac = {k: v/100 for k, v in at_composition.items()}
            
            db.cursor.execute(
                "SELECT id FROM material_classes WHERE class_name = %s",
                (material_class,)
            )
            mc_result = db.cursor.fetchone()
            if not mc_result:
                db.cursor.execute(
                    "INSERT INTO material_classes (class_name, description) VALUES (%s, %s)",
                    (material_class, f"Custom class added via Desktop App")
                )
                db.commit()
                print(f"Added new material class: {material_class}")
                self.load_material_classes()

            notes = (
                f"Added via Desktop App: pre-alloy {prealloy_name} ({prealloy_mass_str}g) "
                f"+ raw {formula} (at%)"
                if prealloy_mode else
                f"Added via Desktop App: {formula} as {unit}"
            )
            
            sample_db_id = db.add_sample(
                sample_id=sample_id,
                composition=composition_frac,
                material_class=material_class,
                source_type='experimental',
                mass_grams=mass,
                vec=screening['VEC'] if screening else None,
                delta=screening['delta'] if screening else None,
                delta_h_mix=screening['Delta_H_mix'] if screening else None,
                notes=notes
            )
            
            for db_key in ('materials_project', 'oqmd', 'alexandria'):
                candidates = filter_by_distance(self.lit_results.get(db_key, []), self.lit_cutoffs[db_key])
                for c in candidates:
                    db.add_literature_check(
                        sample_db_id=sample_db_id,
                        source_db=db_key,
                        tier=c.tier,
                        match_formula=c.formula,
                        match_id=c.match_id,
                        stability=c.stability,
                        experimentally_known=c.experimentally_known,
                        composition_distance=c.composition_distance
                    )
            
            self.result_text.insert("end", f"\n\nSuccessfully added sample: {sample_id}")
            self.status_label.configure(text=f"Sample {sample_id} added to database")
            self.submit_btn.configure(state="disabled")
            
            self.auto_generate_id()
            messagebox.showinfo("Success", f"Sample {sample_id} added successfully!")
            db.close()
            
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))
    
    # ============================================
    # Import Tab Helper Methods
    # ============================================
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with files to import")
        if folder:
            self.folder_path_var.set(folder)
            self.import_folder = folder
            self.refresh_files()
    
    def refresh_files(self):
        for widget in self.file_widgets:
            for child in widget.values():
                if hasattr(child, 'destroy'):
                    try:
                        child.destroy()
                    except:
                        pass
        self.file_widgets = []
        
        folder = self.folder_path_var.get()
        if not folder or not os.path.exists(folder):
            self.import_log.insert("end", "No folder selected or folder does not exist\n")
            return
        
        files = []
        for f in os.listdir(folder):
            f_path = os.path.join(folder, f)
            if os.path.isfile(f_path):
                ext = os.path.splitext(f)[1].lower()
                size = os.path.getsize(f_path)
                mod_time = datetime.fromtimestamp(os.path.getmtime(f_path)).strftime("%Y-%m-%d %H:%M")
                files.append({
                    'name': f,
                    'path': f_path,
                    'ext': ext,
                    'size': size,
                    'modified': mod_time
                })
        
        files.sort(key=lambda x: x['name'])
        self.current_files = files
        
        if not files:
            self.import_log.insert("end", "No files found in this folder\n")
            return
        
        header = ctk.CTkFrame(self.file_list_container)
        header.pack(fill="x", padx=2, pady=2)
        
        ctk.CTkLabel(header, text="Import", width=40, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="File Name", width=200, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Type", width=60, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Size", width=70, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Sample ID", width=120, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        
    
        for f in files:
            row = ctk.CTkFrame(self.file_list_container)
            row.pack(fill="x", padx=2, pady=1)
            
            check_var = ctk.StringVar(value="0")
            cb = ctk.CTkCheckBox(row, text="", variable=check_var, onvalue="1", offvalue="0", width=30)
            cb.pack(side="left", padx=5)
            
            # Check if file already imported
            is_imported = False
            try:
                db = get_db()
                db.cursor.execute(
                    "SELECT id FROM characterization WHERE file_path = %s",
                    (f['path'],)
                )
                is_imported = db.cursor.fetchone() is not None
                db.close()
            except:
                pass
            
            if is_imported:
                name_label = ctk.CTkLabel(row, text=f"✅ {f['name']}", width=200, anchor="w", text_color="green")
            else:
                name_label = ctk.CTkLabel(row, text=f['name'], width=200, anchor="w")
            name_label.pack(side="left", padx=5)
            
            type_label = ctk.CTkLabel(row, text=f['ext'][1:] if f['ext'] else "unknown", width=60)
            type_label.pack(side="left", padx=5)
            
            size_str = f"{f['size']/1024:.1f} KB" if f['size'] < 1024*1024 else f"{f['size']/(1024*1024):.1f} MB"
            size_label = ctk.CTkLabel(row, text=size_str, width=70)
            size_label.pack(side="left", padx=5)
            
            sample_options = [""] + self.get_all_sample_ids()
            sample_var = ctk.StringVar(value="")
            sample_menu = ctk.CTkOptionMenu(row, values=sample_options, variable=sample_var, width=120)
            sample_menu.pack(side="left", padx=5)
            
            detected = self.detect_sample_from_filename(f['name'])
            if detected:
                sample_var.set(detected)
            
            self.file_widgets.append({
                'frame': row,
                'check_var': check_var,
                'file': f,
                'sample_var': sample_var,
                'sample_menu': sample_menu
            })
            
        self.import_log.insert("end", f"Loaded {len(files)} files from {os.path.basename(folder)}\n")
        self.import_log.see("end")
    
    def get_all_sample_ids(self) -> list:
        try:
            db = get_db()
            db.cursor.execute("SELECT sample_id FROM samples ORDER BY sample_id LIMIT 100")
            results = db.cursor.fetchall()
            db.close()
            return [r['sample_id'] for r in results]
        except Exception as e:
            print(f"Error fetching samples: {e}")
            return []
    
    def detect_sample_from_filename(self, filename: str) -> str:
        patterns = [
            r'(RP\d+[a-z]?)',
            r'(HCS\d+[a-z]?)',
            r'(HDS\d+[a-z]?)',
            r'(\d{4})\.raw',
            r'(\d{4})\.xy',
            r'Sample\s*(\d+)',
            r'S(\d+)_',
            r'_(\d{4})\.tif',
            r'(\d{4})_',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def auto_detect_samples(self):
        count = 0
        for widget in self.file_widgets:
            filename = widget['file']['name']
            detected = self.detect_sample_from_filename(filename)
            if detected:
                widget['sample_var'].set(detected)
                count += 1
        self.import_log.insert("end", f"Auto-detected samples for {count} files\n")
        self.import_log.see("end")
    
    def apply_manual_to_selected(self):
        manual_id = self.manual_sample_entry.get().strip()
        if not manual_id:
            messagebox.showwarning("Warning", "Please enter a sample ID first")
            return
        
        count = 0
        for widget in self.file_widgets:
            if widget['check_var'].get() == "1":
                widget['sample_var'].set(manual_id)
                count += 1
        
        self.import_log.insert("end", f"Applied manual ID '{manual_id}' to {count} selected file(s)\n")
        self.import_log.see("end")
    
    def select_all_files(self):
        for widget in self.file_widgets:
            widget['check_var'].set("1")
    
    def deselect_all_files(self):
        for widget in self.file_widgets:
            widget['check_var'].set("0")
    
    def import_selected(self):
        selected = []
        for widget in self.file_widgets:
            if widget['check_var'].get() == "1":
                sample_id = widget['sample_var'].get()
                if not sample_id:
                    continue
                selected.append({
                    'file': widget['file'],
                    'sample_id': sample_id
                })
        
        if not selected:
            messagebox.showwarning("No files", "No files selected for import.\nSelect files and assign sample IDs first.")
            return
        
        count = len(selected)
        if not messagebox.askyesno("Confirm Import", f"Import {count} file(s) to database?"):
            return
        
        db = get_db()
        db.conn.autocommit = False  # Disable autocommit for transaction control
        
        imported = 0
        errors = 0
        
        for item in selected:
            file_path = item['file']['path']
            filename = item['file']['name']
            sample_id = item['sample_id']
            ext = item['file']['ext']
            
            try:
                char_type = self.detect_char_type(ext, filename)
    
                # --- Check if sample exists, create if not ---
                sample_exists = db.get_sample(sample_id)
                if not sample_exists:
                    db.add_sample(
                        sample_id=sample_id,
                        composition={'placeholder': 1.0},
                        material_class='Unknown',
                        source_type='imported',
                        notes=f"Auto-created from import of {filename}"
                    )
                    self.import_log.insert("end", f"  📝 Created new sample: {sample_id}\n")
                
                # --- Check if this file already exists in database ---
                db.cursor.execute(
                    "SELECT id FROM characterization WHERE file_path = %s",
                    (file_path,)
                )
                existing = db.cursor.fetchone()
                if existing:
                    self.import_log.insert("end", f"⏭️  Skipped {filename} — already imported (ID: {existing['id']})\n")
                    continue    
                                     
                # Add characterization
                char_id = db.add_characterization(
                    sample_id=sample_id,
                    char_type=char_type,
                    file_path=file_path,
                    instrument=self.detect_instrument(filename, ext),
                    notes=f"Imported from: {os.path.basename(os.path.dirname(file_path))}"
                )
                imported += 1
                self.import_log.insert("end", f"Imported: {filename} → {sample_id} ({char_type})\n")
                
                # --- Auto-parse based on file type ---
                if char_type == 'XRD' and ext == '.xy':
                    try:
                        from stage_one.integrations.xrd_integration_v1 import import_xrd_file
                        xrd_result = import_xrd_file(file_path, sample_id, db)
                        if xrd_result['success']:
                            a_val = xrd_result.get('lattice_a', 'N/A')
                            self.import_log.insert("end", f"  📐 XRD: a = {a_val:.4f} Å\n" if a_val != 'N/A' else f"  📐 XRD: a = N/A\n")
                    except Exception as e:
                        self.import_log.insert("end", f"  ⚠️ XRD analysis failed: {str(e)}\n")
                
                elif char_type in ['VSM', 'MH'] and ext == '.dat':
                    try:
                        from stage_one.integrations.vsm_integration_v1 import import_vsm_file
                        vsm_result = import_vsm_file(file_path, sample_id, db)
                        if vsm_result['success']:
                            ms = vsm_result.get('ms', 0)
                            hc = vsm_result.get('hc', 0)
                            self.import_log.insert("end", f"  📊 VSM: Ms = {ms:.4f} emu, Hc = {hc:.1f} Oe\n")
                    except Exception as e:
                        self.import_log.insert("end", f"  ⚠️ VSM analysis failed: {str(e)}\n")
                
                elif char_type == 'SEM' and ext in ['.tif', '.tiff']:
                    try:
                        from stage_one.integrations.sem_integration_v1 import import_sem_file
                        sem_result = import_sem_file(file_path, sample_id, db)
                        if sem_result['success']:
                            mag = sem_result.get('magnification', 'N/A')
                            eht = sem_result.get('eht', 'N/A')
                            self.import_log.insert("end", f"  🔬 SEM: Mag = {mag}, EHT = {eht}\n")
                    except Exception as e:
                        self.import_log.insert("end", f"  ⚠️ SEM analysis failed: {str(e)}\n")
                # ✅ Commit the transaction after successful import
                db.conn.commit()
            
            except Exception as e:
                db.conn.rollback()  # Rollback on error
                errors += 1
                self.import_log.insert("end", f"Error importing {filename}: {str(e)}\n")
        
        # Refresh the viewer samples after import
        self.refresh_viewer_samples()
        
        db.close()
        self.import_log.insert("end", f"\nImport complete: {imported} imported, {errors} errors\n")
        self.import_log.see("end")
        
        messagebox.showinfo("Import Complete", f"Imported {imported} files\nErrors: {errors}")
 
    def detect_char_type(self, ext: str, filename: str) -> str:
        ext_lower = ext.lower()
        if ext_lower in ['.raw', '.xy', '.xrdml']:
            return 'XRD'
        elif ext_lower in ['.tif', '.tiff', '.hdr']:
            return 'SEM'
        elif ext_lower in ['.dat']:
            if 'MH' in filename.upper() or 'MAG' in filename.upper() or 'VSM' in filename.upper():
                return 'VSM'
            return 'MH'
        elif ext_lower in ['.csv', '.xlsx']:
            if 'ICP' in filename.upper() or 'ICPOES' in filename.upper():
                return 'EDS'
            if 'DISPLACEMENT' in filename.upper() or 'SPS' in filename.upper():
                return 'Process'
            return 'CSV'
        else:
            return 'Other'            
        
    def detect_instrument(self, filename: str, ext: str) -> str:
        if ext.lower() in ['.raw', '.xy', '.xrdml']:
            return 'Bruker D8'
        if ext.lower() in ['.tif', '.tiff']:
            return 'Zeiss SEM'
        if '.dat' in filename.lower():
            return 'PPMS/VSM'
        return 'Unknown'

if __name__ == "__main__":
    app = AlloyLabApp()
    app.mainloop()
