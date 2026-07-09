#!/usr/bin/env python3
"""
Alloy Lab Desktop App - with Import Tab for file ingestion
"""

import customtkinter as ctk
from tkinter import messagebox, scrolledtext, filedialog
import sys
import io
import re
import os
from datetime import datetime
from pathlib import Path

from alloy_db import get_db
from alloy_screening import screen_composition
from alloy_calculator import ATOMIC_WEIGHTS

# Set theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AlloyLabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("🧪 Alloy Lab Database")
        self.geometry("1000x750")
        
        # Track current import folder
        self.import_folder = None
        self.current_files = []
        self.selected_files = {}  # file_path -> sample_id
        
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
        
        # --- Tab 1: New Entry (existing) ---
        self.tab_new = self.tab_view.add("📝 New Entry")
        self.setup_new_entry_tab()
        
        # --- Tab 2: Import Files (NEW) ---
        self.tab_import = self.tab_view.add("📂 Import Files")
        self.setup_import_tab()
        
        # --- Tab 3: Quick Lookup (existing) ---
        self.tab_lookup = self.tab_view.add("🔍 Quick Lookup")
        self.setup_lookup_tab()
        
        # --- Tab 4: Summary (existing) ---
        self.tab_summary = self.tab_view.add("📊 Summary")
        self.setup_summary_tab()
    
    # ============================================
    # Tab 1: New Entry (from previous version)
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
        
        # Material class with Custom support
        ctk.CTkLabel(frame, text="Material Class:", font=ctk.CTkFont(size=14)).grid(row=4, column=0, padx=10, pady=10, sticky="w")
        self.class_options = ["Permanent Magnet", "Soft Magnetic", "High Entropy Alloy", "Heusler", "Single Crystal", "Custom..."]
        self.class_var = ctk.StringVar(value="Permanent Magnet")
        self.class_menu = ctk.CTkOptionMenu(frame, values=self.class_options, variable=self.class_var, command=self.on_class_change)
        self.class_menu.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        
        self.custom_class_entry = ctk.CTkEntry(frame, width=200, placeholder_text="Enter custom class name")
        self.custom_class_entry.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        self.custom_class_entry.grid_remove()
        
        ctk.CTkLabel(frame, text="Excess (e.g., Nd:3):", font=ctk.CTkFont(size=14)).grid(row=6, column=0, padx=10, pady=10, sticky="w")
        self.excess_entry = ctk.CTkEntry(frame, width=200, placeholder_text="e.g., Nd:3, Co:2")
        self.excess_entry.grid(row=6, column=1, padx=10, pady=10, sticky="w")
        
        ctk.CTkLabel(frame, text="Sample ID:", font=ctk.CTkFont(size=14)).grid(row=7, column=0, padx=10, pady=10, sticky="w")
        self.sample_id_entry = ctk.CTkEntry(frame, width=300, placeholder_text="Auto-generated")
        self.sample_id_entry.grid(row=7, column=1, padx=10, pady=10, sticky="w")
        self.sample_id_entry.insert(0, self.generate_sample_id())
        
        self.auto_id_btn = ctk.CTkButton(frame, text="🔄 Auto-generate ID", command=self.auto_generate_id, width=150)
        self.auto_id_btn.grid(row=7, column=2, padx=10, pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.grid(row=8, column=0, columnspan=3, pady=20)
        
        self.calc_btn = ctk.CTkButton(btn_frame, text="🧪 Calculate & Preview", command=self.run_calculation, width=200)
        self.calc_btn.pack(side="left", padx=10)
        
        self.submit_btn = ctk.CTkButton(btn_frame, text="💾 Submit to Database", command=self.submit_to_db, width=200, state="disabled")
        self.submit_btn.pack(side="left", padx=10)
        
        self.result_text = scrolledtext.ScrolledText(frame, height=15, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.result_text.grid(row=9, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(9, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    # ============================================
    # Tab 2: Import Files (NEW)
    # ============================================
    
    def setup_import_tab(self):
        frame = self.tab_import
        
        # Top row: Folder selection
        ctk.CTkLabel(frame, text="Select Folder:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.folder_path_var = ctk.StringVar(value="")
        self.folder_entry = ctk.CTkEntry(frame, width=400, textvariable=self.folder_path_var, placeholder_text="Path to sorted folder...")
        self.folder_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.browse_btn = ctk.CTkButton(frame, text="📁 Browse", command=self.browse_folder, width=100)
        self.browse_btn.grid(row=0, column=2, padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(frame, text="🔄 Refresh", command=self.refresh_files, width=100)
        self.refresh_btn.grid(row=0, column=3, padx=10, pady=10)
        
        # File list frame
        list_frame = ctk.CTkFrame(frame)
        list_frame.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Create scrollable frame for file list
        self.file_list_container = ctk.CTkScrollableFrame(list_frame, height=250)
        self.file_list_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # This will hold the file widgets
        self.file_widgets = []
        
        # Action buttons
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
        
        # Import log
        ctk.CTkLabel(frame, text="Import Log:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        
        self.import_log = scrolledtext.ScrolledText(frame, height=10, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.import_log.grid(row=4, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(4, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    def browse_folder(self):
        """Open folder dialog to select import folder"""
        folder = filedialog.askdirectory(title="Select folder with files to import")
        if folder:
            self.folder_path_var.set(folder)
            self.import_folder = folder
            self.refresh_files()
    
    def refresh_files(self):
        """Refresh the file list in the import tab"""
        # Clear existing widgets
        for widget in self.file_widgets:
            widget.destroy()
        self.file_widgets = []
        
        folder = self.folder_path_var.get()
        if not folder or not os.path.exists(folder):
            self.import_log.insert("end", "⚠️ No folder selected or folder does not exist\n")
            return
        
        # Get all files in folder
        files = []
        for f in os.listdir(folder):
            f_path = os.path.join(folder, f)
            if os.path.isfile(f_path):
                # Get file info
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
        
        # Sort by name
        files.sort(key=lambda x: x['name'])
        self.current_files = files
        
        if not files:
            self.import_log.insert("end", "📂 No files found in this folder\n")
            return
        
        # Create a header
        header = ctk.CTkFrame(self.file_list_container)
        header.pack(fill="x", padx=2, pady=2)
        
        ctk.CTkLabel(header, text="Import", width=50, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="File Name", width=250, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Type", width=80, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Size", width=80, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Modified", width=120, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Sample ID", width=120, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        
        # Create a row for each file
        for f in files:
            row = ctk.CTkFrame(self.file_list_container)
            row.pack(fill="x", padx=2, pady=1)
            
            # Checkbox
            check_var = ctk.StringVar(value="0")
            cb = ctk.CTkCheckBox(row, text="", variable=check_var, onvalue="1", offvalue="0", width=40)
            cb.pack(side="left", padx=5)
            
            # File name
            name_label = ctk.CTkLabel(row, text=f['name'], width=250, anchor="w")
            name_label.pack(side="left", padx=5)
            
            # File type
            type_label = ctk.CTkLabel(row, text=f['ext'][1:] if f['ext'] else "unknown", width=80)
            type_label.pack(side="left", padx=5)
            
            # Size
            size_str = f"{f['size']/1024:.1f} KB" if f['size'] < 1024*1024 else f"{f['size']/(1024*1024):.1f} MB"
            size_label = ctk.CTkLabel(row, text=size_str, width=80)
            size_label.pack(side="left", padx=5)
            
            # Modified
            mod_label = ctk.CTkLabel(row, text=f['modified'], width=120)
            mod_label.pack(side="left", padx=5)
            
            # Sample dropdown - try to auto-detect
            sample_id = self.detect_sample_from_filename(f['name'])
            
            sample_var = ctk.StringVar(value=sample_id if sample_id else "")
            sample_menu = ctk.CTkOptionMenu(row, values=[""] + self.get_all_sample_ids(), variable=sample_var, width=120)
            sample_menu.pack(side="left", padx=5)
            
            # Store reference
            self.file_widgets.append({
                'frame': row,
                'check_var': check_var,
                'file': f,
                'sample_var': sample_var
            })
    
    def get_all_sample_ids(self) -> list:
        """Get all sample IDs from database for dropdown"""
        try:
            db = get_db()
            db.cursor.execute("SELECT sample_id FROM samples ORDER BY sample_id")
            results = db.cursor.fetchall()
            db.close()
            return [r['sample_id'] for r in results][:50]  # Limit to 50
        except Exception as e:
            print(f"Error fetching samples: {e}")
            return []
    
    def detect_sample_from_filename(self, filename: str) -> str:
        """Try to detect sample ID from filename"""
        # Patterns to match
        patterns = [
            r'(RP\d+[a-z]?)',
            r'(HCS\d+[a-z]?)',
            r'(HDS\d+[a-z]?)',
            r'(\d{4})\.raw',
            r'(\d{4})\.xy',
            r'Sample\s*(\d+)',
            r'S(\d+)_',
            r'Sample\s*(\d+[a-z]?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Check if it starts with a date
        date_match = re.search(r'^(\d{8})', filename)
        if date_match:
            # Try to find if this date corresponds to a sample
            try:
                db = get_db()
                db.cursor.execute(
                    "SELECT sample_id FROM samples WHERE created_at::date = %s LIMIT 1",
                    (datetime.strptime(date_match.group(1), "%Y%m%d").date(),)
                )
                result = db.cursor.fetchone()
                db.close()
                if result:
                    return result['sample_id']
            except:
                pass
        
        return None
    
    def auto_detect_samples(self):
        """Auto-detect samples for all files in the list"""
        count = 0
        for widget in self.file_widgets:
            filename = widget['file']['name']
            detected = self.detect_sample_from_filename(filename)
            if detected:
                widget['sample_var'].set(detected)
                count += 1
        self.import_log.insert("end", f"🔍 Auto-detected samples for {count} files\n")
        self.import_log.see("end")
    
    def select_all_files(self):
        """Select all files"""
        for widget in self.file_widgets:
            widget['check_var'].set("1")
    
    def deselect_all_files(self):
        """Deselect all files"""
        for widget in self.file_widgets:
            widget['check_var'].set("0")
    
    def import_selected(self):
        """Import selected files to database"""
        selected = []
        for widget in self.file_widgets:
            if widget['check_var'].get() == "1":
                sample_id = widget['sample_var'].get()
                if not sample_id:
                    # Skip if no sample selected
                    continue
                selected.append({
                    'file': widget['file'],
                    'sample_id': sample_id
                })
        
        if not selected:
            messagebox.showwarning("No files", "No files selected for import.\n\nSelect files and assign sample IDs first.")
            return
        
        # Confirm
        count = len(selected)
        if not messagebox.askyesno("Confirm Import", f"Import {count} file(s) to database?"):
            return
        
        # Import
        db = get_db()
        imported = 0
        errors = 0
        
        for item in selected:
            file_path = item['file']['path']
            filename = item['file']['name']
            sample_id = item['sample_id']
            ext = item['file']['ext']
            
            try:
                # Determine characterization type
                char_type = self.detect_char_type(ext, filename)
                
                # Add characterization record
                db.add_characterization(
                    sample_id=sample_id,
                    char_type=char_type,
                    file_path=file_path,
                    instrument=self.detect_instrument(filename, ext),
                    notes=f"Imported from folder: {os.path.basename(os.path.dirname(file_path))}"
                )
                imported += 1
                self.import_log.insert("end", f"✅ Imported: {filename} → {sample_id} ({char_type})\n")
                
            except Exception as e:
                errors += 1
                self.import_log.insert("end", f"❌ Error importing {filename}: {str(e)}\n")
        
        db.close()
        self.import_log.insert("end", f"\n📊 Import complete: {imported} imported, {errors} errors\n")
        self.import_log.see("end")
        
        messagebox.showinfo("Import Complete", f"Imported {imported} files\nErrors: {errors}")
    
    def detect_char_type(self, ext: str, filename: str) -> str:
        """Detect characterization type from file extension"""
        ext_lower = ext.lower()
        if ext_lower in ['.raw', '.xy', '.xrdml']:
            return 'XRD'
        elif ext_lower in ['.tif', '.tiff', '.hdr']:
            return 'SEM'
        elif ext_lower in ['.dat']:
            # Could be MH or other
            if 'MH' in filename.upper() or 'MAG' in filename.upper() or 'VSM' in filename.upper():
                return 'VSM'
            return 'MH'
        elif ext_lower in ['.csv', '.xlsx']:
            # Try to detect from content
            if 'ICP' in filename.upper() or 'ICPOES' in filename.upper():
                return 'EDS'
            if 'DISPLACEMENT' in filename.upper() or 'SPS' in filename.upper():
                return 'Process'
            return 'CSV'
        else:
            return 'Other'
    
    def detect_instrument(self, filename: str, ext: str) -> str:
        """Detect instrument from filename or extension"""
        if ext.lower() in ['.raw', '.xy', '.xrdml']:
            return 'Bruker D8'
        if ext.lower() in ['.tif', '.tiff']:
            return 'Zeiss SEM'
        if '.dat' in filename.lower():
            return 'PPMS/VSM'
        return 'Unknown'
    
    # ============================================
    # Helper methods for New Entry tab
    # ============================================
    
    def validate_formula(self, event=None):
        # ... (keep existing code)
        pass
    
    def on_class_change(self, choice):
        if choice == "Custom...":
            self.custom_class_entry.grid()
            self.custom_class_entry.focus()
        else:
            self.custom_class_entry.grid_remove()
    
    def generate_sample_id(self):
        # ... (keep existing code)
        pass
    
    def auto_generate_id(self):
        # ... (keep existing code)
        pass
    
    def get_material_class(self):
        # ... (keep existing code)
        pass
    
    def run_calculation(self):
        # ... (keep existing code)
        pass
    
    def submit_to_db(self):
        # ... (keep existing code)
        pass
    
    # ============================================
    # Tab 3: Quick Lookup
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
        # ... (keep existing code)
        pass
    
    # ============================================
    # Tab 4: Summary
    # ============================================
    
    def setup_summary_tab(self):
        frame = self.tab_summary
        
        self.refresh_btn = ctk.CTkButton(frame, text="🔄 Refresh Summary", command=self.load_summary, width=200)
        self.refresh_btn.pack(pady=10)
        
        self.summary_text = scrolledtext.ScrolledText(frame, height=25, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.summary_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.after(100, self.load_summary)
    
    def load_summary(self):
        # ... (keep existing code)
        pass

if __name__ == "__main__":
    app = AlloyLabApp()
    app.mainloop()
