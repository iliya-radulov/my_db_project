#!/usr/bin/env python3
"""
Alloy Lab Desktop App
Built with CustomTkinter
Hooks into existing alloy_entry_full.py workflow
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import sys
import io
from datetime import datetime

# Import your existing backend
from alloy_entry_full import interactive_add_alloy_full
from alloy_db import get_db
from alloy_screening import screen_composition, interpret_screening

# Set theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AlloyLabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("🧪 Alloy Lab Database")
        self.geometry("900x700")
        
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
        
        # Status bar - create BEFORE tabs
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="✅ Ready",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.status_label.pack(fill="x", pady=(5,0))
        
        # Tab view
        self.tab_view = ctk.CTkTabview(self.main_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Tab 1: New Entry
        self.tab_new = self.tab_view.add("📝 New Entry")
        self.setup_new_entry_tab()
        
        # Tab 2: Quick Lookup
        self.tab_lookup = self.tab_view.add("🔍 Quick Lookup")
        self.setup_lookup_tab()
        
        # Tab 3: Database Summary
        self.tab_summary = self.tab_view.add("📊 Summary")
        self.setup_summary_tab()
    
    # ============================================
    # Tab 1: New Entry
    # ============================================
    
    def setup_new_entry_tab(self):
        frame = self.tab_new
        
        # Formula input
        ctk.CTkLabel(frame, text="Alloy Formula:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.formula_entry = ctk.CTkEntry(frame, width=300, placeholder_text="e.g., Fe65Nd30Co5")
        self.formula_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        # Unit selection
        ctk.CTkLabel(frame, text="Unit:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.unit_var = ctk.StringVar(value="at%")
        self.unit_menu = ctk.CTkOptionMenu(frame, values=["at%", "wt%"], variable=self.unit_var)
        self.unit_menu.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        
        # Mass input
        ctk.CTkLabel(frame, text="Target Mass (g):", font=ctk.CTkFont(size=14)).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.mass_entry = ctk.CTkEntry(frame, width=100, placeholder_text="10.0")
        self.mass_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        self.mass_entry.insert(0, "10.0")
        
        # Material class
        ctk.CTkLabel(frame, text="Material Class:", font=ctk.CTkFont(size=14)).grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.class_var = ctk.StringVar(value="Permanent Magnet")
        self.class_menu = ctk.CTkOptionMenu(
            frame, 
            values=["Permanent Magnet", "Soft Magnetic", "High Entropy Alloy", "Heusler", "Single Crystal"],
            variable=self.class_var
        )
        self.class_menu.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        
        # Excess input
        ctk.CTkLabel(frame, text="Excess (e.g., Nd:3):", font=ctk.CTkFont(size=14)).grid(row=4, column=0, padx=10, pady=10, sticky="w")
        self.excess_entry = ctk.CTkEntry(frame, width=200, placeholder_text="e.g., Nd:3, Co:2")
        self.excess_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        self.calc_btn = ctk.CTkButton(btn_frame, text="🧪 Calculate & Preview", command=self.run_calculation, width=200)
        self.calc_btn.pack(side="left", padx=10)
        
        self.submit_btn = ctk.CTkButton(btn_frame, text="💾 Submit to Database", command=self.submit_to_db, width=200, state="disabled")
        self.submit_btn.pack(side="left", padx=10)
        
        # Results area
        self.result_text = scrolledtext.ScrolledText(frame, height=15, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.result_text.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        # Configure grid weights
        frame.grid_rowconfigure(6, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    def run_calculation(self):
        """Run the calculation and show results (without DB insert)"""
        self.result_text.delete(1.0, "end")
        self.status_label.configure(text="⏳ Calculating...")
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            # Build composition from formula
            formula = self.formula_entry.get().strip()
            unit = self.unit_var.get()
            mass = float(self.mass_entry.get()) if self.mass_entry.get() else 10.0
            
            # Parse and screen
            from alloy_calculator import parse_composition_with_unit, calculate_masses, ElementComponent
            from alloy_screening import screen_composition, interpret_screening
            
            at_composition = parse_composition_with_unit(formula, unit)
            
            # Screening
            comp_frac = {k: v/100 for k, v in at_composition.items()}
            screening = screen_composition(comp_frac)
            
            # Mass calculation
            elements = []
            excess_input = self.excess_entry.get().strip()
            excess_dict = {}
            if excess_input:
                for item in excess_input.split(','):
                    if ':' in item:
                        elem, pct = item.split(':')
                        excess_dict[elem.strip()] = float(pct.strip())
            
            for symbol, at_pct in at_composition.items():
                excess = excess_dict.get(symbol, 0.0)
                elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
            
            result = calculate_masses(total_mass_g=mass, elements=elements)
            
            # Build output
            output = []
            output.append("="*60)
            output.append("📋 Calculation Results")
            output.append("="*60)
            output.append(f"\nFormula: {formula} (as {unit})")
            output.append(f"Target mass: {mass}g")
            output.append(f"Material class: {self.class_var.get()}")
            output.append(f"\n📊 Screening Results:")
            output.append(f"  VEC = {screening['VEC']:.2f}")
            output.append(f"  δ = {screening['delta']:.3f}")
            output.append(f"  ΔH_mix = {screening['Delta_H_mix']:.1f} kJ/mol")
            
            output.append(f"\n📐 Mass Breakdown:")
            output.append(f"{'Element':<10}{'at%':>8}{'wt%':>8}{'target(g)':>10}{'weigh(g)':>10}")
            output.append("-" * 46)
            for e in result.elements:
                output.append(f"{e.symbol:<10}{e.at_pct:>8.2f}{e.wt_pct:>8.2f}{e.grams:>10.4f}{e.weigh_grams:>10.4f}")
            
            output.append("\n" + "="*60)
            
            self.result_text.insert("end", "\n".join(output))
            self.submit_btn.configure(state="normal")
            self.status_label.configure(text="✅ Calculation complete - ready to submit")
            
        except Exception as e:
            self.result_text.insert("end", f"❌ Error: {str(e)}")
            self.status_label.configure(text=f"❌ Error: {str(e)}")
        
        finally:
            sys.stdout = old_stdout
    
    def submit_to_db(self):
        """Submit the calculated alloy to the database"""
        from alloy_entry_full import get_api_key
        from mp_lookup import lookup, print_report
        
        self.status_label.configure(text="⏳ Submitting to database...")
        
        try:
            formula = self.formula_entry.get().strip()
            unit = self.unit_var.get()
            mass = float(self.mass_entry.get()) if self.mass_entry.get() else 10.0
            material_class = self.class_var.get()
            
            # Generate sample ID
            date_str = datetime.now().strftime('%Y%m%d')
            # Use a simple input dialog - since we're in GUI, use a popup
            sample_id = ctk.CTkInputDialog(text="Enter Sample ID:", title="Sample ID").get_input()
            if not sample_id:
                sample_id = f"NEW-{date_str}-001"
            
            # Add to DB using existing workflow
            from alloy_db import get_db
            from alloy_calculator import parse_composition_with_unit, calculate_masses, ElementComponent
            
            at_composition = parse_composition_with_unit(formula, unit)
            comp_frac = {k: v/100 for k, v in at_composition.items()}
            
            # Build elements
            elements = []
            excess_input = self.excess_entry.get().strip()
            excess_dict = {}
            if excess_input:
                for item in excess_input.split(','):
                    if ':' in item:
                        elem, pct = item.split(':')
                        excess_dict[elem.strip()] = float(pct.strip())
            
            for symbol, at_pct in at_composition.items():
                excess = excess_dict.get(symbol, 0.0)
                elements.append(ElementComponent(symbol=symbol, at_pct=at_pct, excess_pct=excess))
            
            result = calculate_masses(total_mass_g=mass, elements=elements)
            
            # Check screening
            from alloy_screening import screen_composition
            screening = screen_composition(comp_frac)
            
            # Add to DB
            db = get_db()
            
            # Check if sample exists
            existing = db.get_sample(sample_id)
            if existing:
                if not messagebox.askyesno("Sample Exists", f"Sample {sample_id} already exists. Override?"):
                    self.status_label.configure(text="❌ Cancelled")
                    return
            
            composition_frac = {k: v/100 for k, v in at_composition.items()}
            sample_db_id = db.add_sample(
                sample_id=sample_id,
                composition=composition_frac,
                material_class=material_class,
                source_type='experimental',
                mass_grams=mass,
                vec=screening['VEC'],
                delta=screening['delta'],
                delta_h_mix=screening['Delta_H_mix'],
                notes=f"Added via Desktop App: {formula} as {unit}"
            )
            
            # Add literature checks (MP + OQMD)
            api_key = get_api_key()
            if api_key:
                mp_results = lookup(comp_frac, api_key=api_key)
                from lookup_common import dedup_by_formula, from_mp_results
                deduped = dedup_by_formula(from_mp_results(mp_results))
                for match in deduped:
                    db.add_literature_check(
                        sample_db_id=sample_db_id,
                        source_db='materials_project',
                        tier=match.tier,
                        match_formula=match.formula,
                        match_id=match.material_id,
                        stability=match.energy_above_hull,
                        experimentally_known=not match.theoretical,
                        composition_distance=match.composition_distance
                    )
            
            self.result_text.insert("end", f"\n\n✅ Successfully added sample: {sample_id}")
            self.status_label.configure(text=f"✅ Sample {sample_id} added to database")
            self.submit_btn.configure(state="disabled")
            
            messagebox.showinfo("Success", f"Sample {sample_id} added successfully!")
            
        except Exception as e:
            self.status_label.configure(text=f"❌ Error: {str(e)}")
            messagebox.showerror("Error", str(e))
    
    # ============================================
    # Tab 2: Quick Lookup
    # ============================================
    
    def setup_lookup_tab(self):
        frame = self.tab_lookup
        
        # Search by sample ID
        ctk.CTkLabel(frame, text="Search Sample ID:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.search_entry = ctk.CTkEntry(frame, width=250, placeholder_text="e.g., RP1a")
        self.search_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.search_btn = ctk.CTkButton(frame, text="🔍 Search", command=self.search_sample, width=120)
        self.search_btn.grid(row=0, column=2, padx=10, pady=10)
        
        # Results area
        self.search_result = scrolledtext.ScrolledText(frame, height=20, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.search_result.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(1, weight=1)
    
    def search_sample(self):
        """Search for a sample by ID"""
        sample_id = self.search_entry.get().strip()
        if not sample_id:
            return
        
        self.search_result.delete(1.0, "end")
        self.status_label.configure(text=f"🔍 Searching for {sample_id}...")
        
        try:
            db = get_db()
            sample = db.get_sample(sample_id)
            
            if not sample:
                self.search_result.insert("end", f"❌ Sample '{sample_id}' not found")
                self.status_label.configure(text=f"❌ Sample '{sample_id}' not found")
                return
            
            # Display sample info
            output = []
            output.append("="*60)
            output.append(f"📋 Sample: {sample['sample_id']}")
            output.append("="*60)
            output.append(f"Class: {sample['material_class']}")
            output.append(f"Mass: {sample['mass_grams']}g")
            output.append(f"Source: {sample['source_type']}")
            output.append(f"Created: {sample['created_at']}")
            
            # Composition
            output.append(f"\n📊 Composition (at%):")
            comp = sample['composition']
            for elem, frac in comp.items():
                output.append(f"  {elem}: {frac*100:.2f} at%")
            
            # Screening results if available
            if sample.get('vec') is not None:
                output.append(f"\n📐 Screening:")
                output.append(f"  VEC = {sample['vec']:.2f}")
                output.append(f"  δ = {sample['delta']:.3f}")
                output.append(f"  ΔH_mix = {sample['delta_h_mix']:.1f} kJ/mol")
            
            # Literature checks
            db.cursor.execute(
                "SELECT source_db, match_formula, tier, stability, experimentally_known FROM literature_checks WHERE sample_id = %s",
                (sample['id'],)
            )
            lit_checks = db.cursor.fetchall()
            if lit_checks:
                output.append(f"\n📚 Literature Checks ({len(lit_checks)}):")
                for row in lit_checks:
                    stable = "✅ stable" if row['stability'] == 0 else f"{row['stability']:.3f} eV"
                    known = "✓ known" if row['experimentally_known'] else "theoretical"
                    output.append(f"  {row['source_db']}: {row['match_formula']} (Tier {row['tier']}) - {stable}, {known}")
            
            self.search_result.insert("end", "\n".join(output))
            self.status_label.configure(text=f"✅ Found sample: {sample_id}")
            
        except Exception as e:
            self.search_result.insert("end", f"❌ Error: {str(e)}")
            self.status_label.configure(text=f"❌ Error: {str(e)}")
    
    # ============================================
    # Tab 3: Summary
    # ============================================
    
    def setup_summary_tab(self):
        frame = self.tab_summary
        
        self.refresh_btn = ctk.CTkButton(frame, text="🔄 Refresh Summary", command=self.load_summary, width=200)
        self.refresh_btn.pack(pady=10)
        
        self.summary_text = scrolledtext.ScrolledText(frame, height=25, width=80, bg="#1e1e1e", fg="#ffffff", font=("Courier", 10))
        self.summary_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Load initial summary
        self.load_summary()
    
    def load_summary(self):
        """Load database summary"""
        self.summary_text.delete(1.0, "end")
        self.status_label.configure(text="📊 Loading summary...")
        
        try:
            db = get_db()
            
            # Count samples
            db.cursor.execute("SELECT COUNT(*) FROM samples")
            sample_count = db.cursor.fetchone()['count']
            
            # Count by material class
            db.cursor.execute("""
                SELECT mc.class_name, COUNT(*) 
                FROM samples s 
                JOIN material_classes mc ON s.material_class_id = mc.id 
                GROUP BY mc.class_name
            """)
            class_counts = db.cursor.fetchall()
            
            # Recent samples
            db.cursor.execute("""
                SELECT sample_id, created_at, source_type 
                FROM samples 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            recent = db.cursor.fetchall()
            
            # Literature checks count
            db.cursor.execute("SELECT COUNT(*) FROM literature_checks")
            lit_count = db.cursor.fetchone()['count']
            
            output = []
            output.append("="*60)
            output.append("📊 Database Summary")
            output.append("="*60)
            output.append(f"\nTotal Samples: {sample_count}")
            output.append(f"Literature Checks: {lit_count}")
            
            output.append(f"\n📁 By Material Class:")
            for row in class_counts:
                output.append(f"  {row['class_name']}: {row['count']}")
            
            output.append(f"\n📋 Recent Samples (last 10):")
            for row in recent:
                output.append(f"  {row['sample_id']} ({row['source_type']}) - {row['created_at']}")
            
            self.summary_text.insert("end", "\n".join(output))
            self.status_label.configure(text="✅ Summary loaded")
            
        except Exception as e:
            self.summary_text.insert("end", f"❌ Error loading summary: {str(e)}")
            self.status_label.configure(text=f"❌ Error: {str(e)}")

if __name__ == "__main__":
    app = AlloyLabApp()
    app.mainloop()
