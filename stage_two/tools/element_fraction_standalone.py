"""
element_fraction_standalone.py

Standalone element-fraction tool for the Alloy Lab Database (Stage 2).

Type a composition into the table (element + value, in wt% or at%), press
Evaluate, and get:
  * the weight-percent AND atomic-percent composition (the missing one is
    computed from standard atomic weights),
  * the wide-format row (one column per element, atomic percent, zero-filled)
    that the ML-facing element-fraction table uses,
  * validation (unknown elements, duplicates, non-positive values, sums that
    are not ~100%).

Optional actions after Evaluate:
  * Export CSV (long format + wide row)
  * Copy the wide row to the clipboard
  * Save to DB: writes the long-format rows to the `compositions` table with
    an explicit composition_type (aimed / measured / reference), replacing any
    existing rows of that type for the sample after confirmation.

Design notes (same stance as the XRD / VSM / SEM standalone tools):
  * The calculation is a set of pure functions (top of file) with no GUI or
    database dependency, so they can be tested and reused on their own.
  * Nothing is written to the database without an explicit Save click, and a
    save is refused if the table has been edited since the last Evaluate.
  * Unknown elements are an error, never silently skipped: dropping one would
    change the normalisation of every other element.

Run:
    python element_fraction_standalone.py            # empty table
    python element_fraction_standalone.py SAMPLE_ID  # pre-fills the Save field

Atomic weights: the project's ATOMIC_WEIGHTS (stage_two.alloy.alloy_calculator_v2)
are used when importable, so numbers agree with the main app. Otherwise a
built-in table (standard atomic weights, Z = 1..94) is used.

Assumptions about the database (checked against the Stage 2 summaries, not
against a live database from this environment): table `<schema>.compositions`
with columns sample_id (integer FK to samples.id), element, weight_percent,
atomic_percent, composition_type; table `<schema>.samples` with columns id and
sample_id (the human-readable string).
"""

import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Atomic weights
# ---------------------------------------------------------------------------

_FALLBACK_WEIGHTS = {
    "H": 1.008, "He": 4.0026, "Li": 6.94, "Be": 9.0122, "B": 10.81, "C": 12.011,
    "N": 14.007, "O": 15.999, "F": 18.9984, "Ne": 20.1797, "Na": 22.9898, "Mg": 24.305,
    "Al": 26.9815, "Si": 28.085, "P": 30.9738, "S": 32.06, "Cl": 35.45, "Ar": 39.95,
    "K": 39.0983, "Ca": 40.078, "Sc": 44.9559, "Ti": 47.867, "V": 50.9415, "Cr": 51.9961,
    "Mn": 54.938, "Fe": 55.845, "Co": 58.9332, "Ni": 58.6934, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.63, "As": 74.9216, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.4678, "Sr": 87.62, "Y": 88.9058, "Zr": 91.224, "Nb": 92.9064, "Mo": 95.95,
    "Tc": 98.0, "Ru": 101.07, "Rh": 102.9055, "Pd": 106.42, "Ag": 107.8682, "Cd": 112.414,
    "In": 114.818, "Sn": 118.71, "Sb": 121.76, "Te": 127.6, "I": 126.9045, "Xe": 131.293,
    "Cs": 132.9055, "Ba": 137.327, "La": 138.9055, "Ce": 140.116, "Pr": 140.9077, "Nd": 144.242,
    "Pm": 145.0, "Sm": 150.36, "Eu": 151.964, "Gd": 157.25, "Tb": 158.9254, "Dy": 162.5,
    "Ho": 164.9303, "Er": 167.259, "Tm": 168.9342, "Yb": 173.045, "Lu": 174.9668, "Hf": 178.486,
    "Ta": 180.9479, "W": 183.84, "Re": 186.207, "Os": 190.23, "Ir": 192.217, "Pt": 195.084,
    "Au": 196.9666, "Hg": 200.592, "Tl": 204.38, "Pb": 207.2, "Bi": 208.9804, "Po": 209.0,
    "At": 210.0, "Rn": 222.0, "Fr": 223.0, "Ra": 226.0, "Ac": 227.0, "Th": 232.0377,
    "Pa": 231.0359, "U": 238.0289, "Np": 237.0, "Pu": 244.0,
}


def _load_atomic_weights():
    """Project table if importable (keeps numbers identical to the main app)."""
    here = Path(__file__).resolve()
    for parent in [here.parent] + list(here.parents):
        if (parent / "db_config.py").exists() and str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
            break
    try:
        from stage_two.alloy.alloy_calculator_v2 import ATOMIC_WEIGHTS as proj
        weights = {k: float(v) for k, v in proj.items()}
        return weights, "project table (alloy_calculator_v2)"
    except Exception:
        return dict(_FALLBACK_WEIGHTS), "built-in standard atomic weights"


ATOMIC_WEIGHTS, WEIGHT_SOURCE = _load_atomic_weights()

# Order columns by atomic number (stable, predictable column order).
_Z_ORDER = list(_FALLBACK_WEIGHTS.keys())
_Z_INDEX = {sym: i for i, sym in enumerate(_Z_ORDER)}

COMPOSITION_TYPES = ("aimed", "measured", "reference")
SUM_TOLERANCE = 0.5  # percentage points; wider gaps raise a warning


# ---------------------------------------------------------------------------
# Pure calculation (no GUI, no database)
# ---------------------------------------------------------------------------

def canonical_symbol(text):
    """'fe', ' FE ' -> 'Fe'. Returns None for an empty string."""
    text = str(text if text is not None else "").strip()
    if not text:
        return None
    return text[0].upper() + text[1:].lower()


def sort_by_z(elements):
    """Sort element symbols by atomic number; unknown symbols go last."""
    return sorted(elements, key=lambda s: (_Z_INDEX.get(s, 10_000), s))


def weight_to_atomic(wt):
    """{element: wt%} -> {element: at%}, normalised to sum to 100."""
    moles = {e: w / ATOMIC_WEIGHTS[e] for e, w in wt.items()}
    total = sum(moles.values())
    return {e: 100.0 * n / total for e, n in moles.items()}


def atomic_to_weight(at):
    """{element: at%} -> {element: wt%}, normalised to sum to 100."""
    mass = {e: x * ATOMIC_WEIGHTS[e] for e, x in at.items()}
    total = sum(mass.values())
    return {e: 100.0 * m / total for e, m in mass.items()}


def parse_pasted(text):
    """
    Parse 'Nd 26.7, Fe 72.3, B 1.0' / 'Nd:26.7; Fe=72.3' / one pair per line
    into [(element, value_string), ...]. Raises ValueError on malformed items.
    """
    rows = []
    for item in re.split(r"[,;\n]+", text):
        item = item.strip()
        if not item:
            continue
        m = re.fullmatch(r"([A-Za-z]{1,2})\s*[:=\s]\s*([0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?)", item)
        if not m:
            raise ValueError(f"Cannot read '{item}' (expected e.g. 'Fe 72.3')")
        rows.append((m.group(1), m.group(2)))
    return rows


def evaluate(rows, unit, zero_fill=()):
    """
    rows: iterable of (element_text, value_text); unit: 'wt%' or 'at%'.

    Returns a dict:
        ok        bool    False if there are errors (then nothing else is valid)
        errors    [str]   problems that block the result
        warnings  [str]   things to look at but not blocking
        input_sum float   sum of the values as typed
        wt, at    {element: percent} both normalised to 100 (None if not ok)
        order     [element]  atomic-number order of the entered elements
        wide      {element: at%} entered elements + zero_fill columns
    """
    errors, warnings = [], []
    values = {}

    for i, (el_text, val_text) in enumerate(rows, start=1):
        el_text = str(el_text if el_text is not None else "").strip()
        val_text = str(val_text if val_text is not None else "").strip()
        if not el_text and not val_text:
            continue  # empty row
        el = canonical_symbol(el_text)
        if el is None:
            errors.append(f"Row {i}: value given but no element.")
            continue
        if el not in ATOMIC_WEIGHTS:
            errors.append(f"Row {i}: unknown element '{el_text}'.")
            continue
        try:
            val = float(val_text.replace(",", "."))
        except ValueError:
            errors.append(f"Row {i} ({el}): '{val_text}' is not a number.")
            continue
        if not val > 0:
            errors.append(f"Row {i} ({el}): value must be greater than zero.")
            continue
        if el in values:
            errors.append(f"Row {i}: element {el} appears more than once.")
            continue
        values[el] = val

    if not values and not errors:
        errors.append("The table is empty.")

    result = {"ok": False, "errors": errors, "warnings": warnings,
              "input_sum": sum(values.values()) if values else 0.0,
              "wt": None, "at": None, "order": [], "wide": {}}
    if errors:
        return result

    total = result["input_sum"]
    if abs(total - 100.0) > SUM_TOLERANCE:
        warnings.append(
            f"Values sum to {total:.3f}, not 100. Results are normalised to 100; "
            "check that no element is missing."
        )
    if unit == "wt%":
        wt = {e: 100.0 * v / total for e, v in values.items()}
        at = weight_to_atomic(wt)
    elif unit == "at%":
        at = {e: 100.0 * v / total for e, v in values.items()}
        wt = atomic_to_weight(at)
    else:
        raise ValueError(f"unit must be 'wt%' or 'at%', got {unit!r}")

    zero_fill = [canonical_symbol(z) for z in zero_fill if canonical_symbol(z)]
    unknown_fill = [z for z in zero_fill if z not in ATOMIC_WEIGHTS]
    if unknown_fill:
        warnings.append("Ignored unknown zero-fill column(s): " + ", ".join(unknown_fill))
    columns = sort_by_z(set(at) | {z for z in zero_fill if z in ATOMIC_WEIGHTS})

    result.update(ok=True, wt=wt, at=at, order=sort_by_z(at),
                  wide={e: at.get(e, 0.0) for e in columns})
    return result


def long_rows(result):
    """[(element, weight_percent, atomic_percent)] in atomic-number order."""
    return [(e, result["wt"][e], result["at"][e]) for e in result["order"]]


def write_csv(path, result, sample_id="", composition_type=""):
    """Long-format table, then a blank line and the wide row."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sample_id", "composition_type", "element", "weight_percent", "atomic_percent"])
        for e, wp, ap in long_rows(result):
            w.writerow([sample_id, composition_type, e, f"{wp:.6f}", f"{ap:.6f}"])
        w.writerow([])
        cols = list(result["wide"])
        w.writerow(["sample_id"] + cols)
        w.writerow([sample_id] + [f"{result['wide'][c]:.6f}" for c in cols])


# ---------------------------------------------------------------------------
# Database (only used when the user clicks Save to DB)
# ---------------------------------------------------------------------------

def save_composition(conn, schema, sample_string_id, composition_type, result,
                     overwrite=False):
    """
    Replace the (sample, composition_type) rows in `<schema>.compositions`.

    Returns the number of rows written. Raises LookupError if the sample does
    not exist, FileExistsError if rows exist and overwrite is False. All writes
    happen in one transaction (rolled back on any error).
    """
    if composition_type not in COMPOSITION_TYPES:
        raise ValueError(f"composition_type must be one of {COMPOSITION_TYPES}")
    if not result.get("ok"):
        raise ValueError("Nothing valid to save.")
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id FROM {schema}.samples WHERE sample_id = %s",
                    (sample_string_id,))
        row = cur.fetchone()
        if not row:
            raise LookupError(f"Sample '{sample_string_id}' is not in the database.")
        sample_pk = row[0]

        cur.execute(
            f"SELECT COUNT(*) FROM {schema}.compositions "
            "WHERE sample_id = %s AND composition_type = %s",
            (sample_pk, composition_type))
        existing = cur.fetchone()[0]
        if existing and not overwrite:
            raise FileExistsError(existing)

        cur.execute(
            f"DELETE FROM {schema}.compositions "
            "WHERE sample_id = %s AND composition_type = %s",
            (sample_pk, composition_type))
        for e, wp, ap in long_rows(result):
            cur.execute(
                f"INSERT INTO {schema}.compositions "
                "(sample_id, element, weight_percent, atomic_percent, composition_type) "
                "VALUES (%s, %s, %s, %s, %s)",
                (sample_pk, e, float(wp), float(ap), composition_type))
        conn.commit()
        return len(result["order"])
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def count_existing(conn, schema, sample_string_id, composition_type):
    """Rows already stored for (sample, type); None if the sample is unknown."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT id FROM {schema}.samples WHERE sample_id = %s",
                    (sample_string_id,))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            f"SELECT COUNT(*) FROM {schema}.compositions "
            "WHERE sample_id = %s AND composition_type = %s",
            (row[0], composition_type))
        return cur.fetchone()[0]
    finally:
        cur.close()


def db_elements(conn, schema):
    """Distinct elements present in the compositions table, by atomic number."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT DISTINCT element FROM {schema}.compositions")
        return sort_by_z([r[0] for r in cur.fetchall()])
    finally:
        cur.close()


def connect_db():
    """Open a psycopg2 connection from db_config.DB_CONFIG; returns (conn, schema)."""
    from db_config import DB_CONFIG
    import psycopg2
    params = {k: v for k, v in DB_CONFIG.items() if k != "schema"}
    return psycopg2.connect(**params), DB_CONFIG.get("schema", "alloy_lab")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def build_app():
    """Imported lazily so the calculation functions work without a display."""
    import customtkinter as ctk
    from tkinter import filedialog, messagebox

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    class ElementFractionApp(ctk.CTk):
        INITIAL_ROWS = 6

        def __init__(self, sample_id=""):
            super().__init__()
            self.title("Element Fraction Tool")
            self.geometry("980x860")
            self.minsize(900, 780)
            self.rows = []          # [(element_entry, value_entry, row_frame)]
            self.result = None
            self._evaluated_snapshot = None

            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(2, weight=1)

            self._build_header()
            self._build_input()
            self._build_output()
            self._build_actions(sample_id)
            for _ in range(self.INITIAL_ROWS):
                self.add_row()

        # ---- layout -------------------------------------------------------
        def _build_header(self):
            f = ctk.CTkFrame(self)
            f.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
            ctk.CTkLabel(f, text="Input unit:").grid(row=0, column=0, padx=(10, 6), pady=8)
            self.unit_var = ctk.StringVar(value="wt%")
            self.unit_btn = ctk.CTkSegmentedButton(
                f, values=["wt%", "at%"], variable=self.unit_var,
                command=lambda _v: self._mark_stale())
            self.unit_btn.grid(row=0, column=1, padx=6)
            ctk.CTkLabel(f, text="Paste:").grid(row=0, column=2, padx=(20, 6))
            self.paste_entry = ctk.CTkEntry(
                f, width=330, placeholder_text="e.g. Nd 26.7, Fe 72.3, B 1.0")
            self.paste_entry.grid(row=0, column=3, padx=6)
            ctk.CTkButton(f, text="Fill table", width=90,
                          command=self.fill_from_paste).grid(row=0, column=4, padx=6)
            ctk.CTkLabel(f, text=f"Atomic weights: {WEIGHT_SOURCE}",
                         text_color="gray").grid(row=1, column=0, columnspan=5,
                                                 sticky="w", padx=10, pady=(0, 6))

        def _build_input(self):
            f = ctk.CTkFrame(self)
            f.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
            f.grid_columnconfigure(0, weight=1)
            head = ctk.CTkFrame(f, fg_color="transparent")
            head.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
            ctk.CTkLabel(head, text="Element", width=120, anchor="w",
                         font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=4)
            self.value_header = ctk.CTkLabel(head, text="Value (wt%)", width=140, anchor="w",
                                             font=ctk.CTkFont(weight="bold"))
            self.value_header.grid(row=0, column=1, padx=4)
            self.table = ctk.CTkScrollableFrame(f, height=150)
            self.table.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
            btns = ctk.CTkFrame(f, fg_color="transparent")
            btns.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
            ctk.CTkButton(btns, text="+ Add row", width=100,
                          command=self.add_row).grid(row=0, column=0, padx=4)
            ctk.CTkButton(btns, text="Clear", width=80, fg_color="gray40",
                          command=self.clear).grid(row=0, column=1, padx=4)
            self.evaluate_btn = ctk.CTkButton(
                btns, text="Evaluate", width=160, height=36,
                font=ctk.CTkFont(weight="bold"), command=self.on_evaluate)
            self.evaluate_btn.grid(row=0, column=2, padx=20)
            self.unit_var.trace_add("write", lambda *_: self.value_header.configure(
                text=f"Value ({self.unit_var.get()})"))

        def _build_output(self):
            f = ctk.CTkFrame(self)
            f.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(f, text="Result", font=ctk.CTkFont(weight="bold")
                         ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 0))
            self.output = ctk.CTkTextbox(f, height=250, font=ctk.CTkFont(family="Courier", size=13))
            self.output.grid(row=1, column=0, sticky="nsew", padx=8, pady=6)
            self.output.configure(state="disabled")
            self.msg_label = ctk.CTkLabel(f, text="", anchor="w", justify="left",
                                          wraplength=900)
            self.msg_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))

        def _build_actions(self, sample_id):
            f = ctk.CTkFrame(self)
            f.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
            ctk.CTkButton(f, text="Export CSV", width=110,
                          command=self.export_csv).grid(row=0, column=0, padx=8, pady=8)
            ctk.CTkButton(f, text="Copy wide row", width=130,
                          command=self.copy_wide_row).grid(row=0, column=1, padx=4)
            ctk.CTkLabel(f, text="Zero-fill columns:").grid(row=0, column=2, padx=(16, 4))
            self.fill_entry = ctk.CTkEntry(f, width=170, placeholder_text="e.g. Al,B,Co,Fe,Ga,Nd")
            self.fill_entry.grid(row=0, column=3, padx=4)
            ctk.CTkButton(f, text="From DB", width=80, fg_color="gray40",
                          command=self.fill_columns_from_db).grid(row=0, column=4, padx=4)

            ctk.CTkLabel(f, text="Sample ID:").grid(row=1, column=0, padx=(8, 4), pady=8, sticky="e")
            self.sample_entry = ctk.CTkEntry(f, width=240)
            self.sample_entry.grid(row=1, column=1, columnspan=2, padx=4, sticky="w")
            if sample_id:
                self.sample_entry.insert(0, sample_id)
            self.type_var = ctk.StringVar(value="aimed")
            ctk.CTkComboBox(f, values=list(COMPOSITION_TYPES), variable=self.type_var,
                            width=120, state="readonly").grid(row=1, column=3, padx=4, sticky="w")
            self.save_btn = ctk.CTkButton(f, text="Save to DB", width=130,
                                          fg_color="darkgreen", command=self.save_to_db)
            self.save_btn.grid(row=1, column=4, padx=8)

        # ---- table handling -------------------------------------------------
        def add_row(self, element="", value=""):
            fr = ctk.CTkFrame(self.table, fg_color="transparent")
            fr.pack(fill="x", pady=1)
            el = ctk.CTkEntry(fr, width=120)
            va = ctk.CTkEntry(fr, width=140)
            el.grid(row=0, column=0, padx=4)
            va.grid(row=0, column=1, padx=4)
            if element:
                el.insert(0, element)
            if value:
                va.insert(0, value)
            rm = ctk.CTkButton(fr, text="x", width=28, fg_color="gray40",
                               command=lambda f=fr: self.remove_row(f))
            rm.grid(row=0, column=2, padx=4)
            for w in (el, va):
                w.bind("<KeyRelease>", lambda _e: self._mark_stale())
            self.rows.append((el, va, fr))
            return el, va

        def remove_row(self, frame):
            self.rows = [r for r in self.rows if r[2] is not frame]
            frame.destroy()
            self._mark_stale()

        def clear(self):
            for _el, _va, fr in self.rows:
                fr.destroy()
            self.rows = []
            for _ in range(self.INITIAL_ROWS):
                self.add_row()
            self.result = None
            self._evaluated_snapshot = None
            self._show("")
            self.msg_label.configure(text="")

        def fill_from_paste(self):
            text = self.paste_entry.get()
            try:
                pairs = parse_pasted(text)
            except ValueError as exc:
                self.msg_label.configure(text=str(exc), text_color="red")
                return
            if not pairs:
                return
            for _el, _va, fr in self.rows:
                fr.destroy()
            self.rows = []
            for el, va in pairs:
                self.add_row(el, va)
            self._mark_stale()
            self.msg_label.configure(text=f"{len(pairs)} rows filled. Press Evaluate.",
                                     text_color="gray")

        def _table_values(self):
            return [(el.get(), va.get()) for el, va, _fr in self.rows]

        def _zero_fill(self):
            return [t for t in re.split(r"[,\s;]+", self.fill_entry.get()) if t]

        def _snapshot(self):
            return (tuple(self._table_values()), self.unit_var.get(),
                    tuple(self._zero_fill()))

        def _mark_stale(self):
            if self.result is not None and self._snapshot() != self._evaluated_snapshot:
                self.msg_label.configure(
                    text="Table changed since the last Evaluate. Press Evaluate again.",
                    text_color="orange")

        # ---- actions --------------------------------------------------------
        def _show(self, text):
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.insert("1.0", text)
            self.output.configure(state="disabled")

        def on_evaluate(self):
            res = evaluate(self._table_values(), self.unit_var.get(), self._zero_fill())
            if not res["ok"]:
                self.result = None
                self._evaluated_snapshot = None
                self._show("")
                self.msg_label.configure(text="\n".join(res["errors"]), text_color="red")
                return
            self.result = res
            self._evaluated_snapshot = self._snapshot()
            self._show(self.format_result(res))
            if res["warnings"]:
                self.msg_label.configure(text="\n".join(res["warnings"]), text_color="orange")
            else:
                self.msg_label.configure(text="Evaluated.", text_color="green")

        @staticmethod
        def format_result(res):
            lines = [f"{'Element':<9}{'wt%':>12}{'at%':>12}", "-" * 33]
            for e, wp, ap in long_rows(res):
                lines.append(f"{e:<9}{wp:>12.3f}{ap:>12.3f}")
            lines.append("-" * 33)
            lines.append(f"{'Sum':<9}{sum(res['wt'].values()):>12.3f}{sum(res['at'].values()):>12.3f}")
            lines.append(f"Input values summed to {res['input_sum']:.3f}")
            lines.append("")
            lines.append("Wide row (at%):")
            cols = list(res["wide"])
            lines.append("  " + "  ".join(f"{c:>8}" for c in cols))
            lines.append("  " + "  ".join(f"{res['wide'][c]:>8.3f}" for c in cols))
            return "\n".join(lines)

        def _require_fresh_result(self):
            if self.result is None:
                messagebox.showinfo("Nothing to use", "Press Evaluate first.")
                return False
            if self._snapshot() != self._evaluated_snapshot:
                messagebox.showinfo("Table changed",
                                    "The table changed since the last Evaluate. Press Evaluate again.")
                return False
            return True

        def export_csv(self):
            if not self._require_fresh_result():
                return
            path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                filetypes=[("CSV", "*.csv")])
            if not path:
                return
            write_csv(path, self.result, self.sample_entry.get().strip(), self.type_var.get())
            self.msg_label.configure(text=f"Saved {path}", text_color="green")

        def copy_wide_row(self):
            if not self._require_fresh_result():
                return
            cols = list(self.result["wide"])
            text = "\t".join(cols) + "\n" + "\t".join(f"{self.result['wide'][c]:.6f}" for c in cols)
            self.clipboard_clear()
            self.clipboard_append(text)
            self.msg_label.configure(text="Wide row copied (tab-separated).", text_color="green")

        def fill_columns_from_db(self):
            try:
                conn, schema = connect_db()
                try:
                    elems = db_elements(conn, schema)
                finally:
                    conn.close()
            except Exception as exc:
                messagebox.showerror("Database", str(exc))
                return
            self.fill_entry.delete(0, "end")
            self.fill_entry.insert(0, ",".join(elems))
            self._mark_stale()

        def save_to_db(self):
            if not self._require_fresh_result():
                return
            sample_id = self.sample_entry.get().strip()
            ctype = self.type_var.get()
            if not sample_id:
                messagebox.showerror("Sample ID", "Enter the sample ID to save under.")
                return
            try:
                conn, schema = connect_db()
            except Exception as exc:
                messagebox.showerror("Database", str(exc))
                return
            try:
                existing = count_existing(conn, schema, sample_id, ctype)
                if existing is None:
                    messagebox.showerror(
                        "Unknown sample",
                        f"'{sample_id}' is not in the database.\n"
                        "Create the sample in the main app first.")
                    return
                overwrite = False
                if existing:
                    overwrite = messagebox.askyesno(
                        "Replace existing composition?",
                        f"{sample_id} already has {existing} '{ctype}' composition row(s).\n"
                        "Replace them with the new values?")
                    if not overwrite:
                        return
                n = save_composition(conn, schema, sample_id, ctype, self.result,
                                     overwrite=overwrite)
                self.msg_label.configure(
                    text=f"Saved {n} '{ctype}' rows for {sample_id}.", text_color="green")
            except Exception as exc:
                messagebox.showerror("Save failed", str(exc))
            finally:
                conn.close()

    return ElementFractionApp


def main():
    sample_id = sys.argv[1] if len(sys.argv) > 1 else ""
    app = build_app()(sample_id=sample_id)
    app.mainloop()


if __name__ == "__main__":
    main()
