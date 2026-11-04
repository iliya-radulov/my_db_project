"""
compare_tdbs.py — Compare two (or three) TDB files field by field.

Reports where symbols (FUNCTION blocks) and parameters differ between
the files. Built to diagnose Mechanism 2 of the Step 1 analysis:

  NdB-19Che and NdB-95Hal-LB have identical phase structures, yet one
  fails with FeB-19Wit and the other succeeds. The merge rule
  ("first file wins when parameters differ") makes such asymmetries
  invisible; this script surfaces them.

Usage
-----
  # 1. Compare the two Nd-B files directly
  python compare_tdbs.py /path/to/NdB-19Che.tdb /path/to/NdB-95Hal-LB.tdb

  # 2. Compare all three together, so the three-way conflict is visible
  python compare_tdbs.py \
      /path/to/NdB-19Che.tdb \
      /path/to/NdB-95Hal-LB.tdb \
      /path/to/FeB-19Wit.tdb

Output
------
  SECTION 1  — symbols only in one file
  SECTION 2  — symbols in both/all with different expressions
  SECTION 3  — parameters only in one file (by phase)
  SECTION 4  — parameters in both/all with different values

With --out OUTFILE the full output is also written to disk.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")


def _names(sub):
    """Sorted tuple of constituent names for one sublattice."""
    return tuple(sorted(getattr(s, "name", str(s)) for s in sub))


def _pkey(p):
    """Canonical key for a parameter row."""
    return (p["phase_name"],
            tuple(_names(sub) for sub in p["constituent_array"]),
            p["parameter_order"],
            p["parameter_type"],
            getattr(p.get("diffusing_species"), "name", p.get("diffusing_species")))


def load(tdb_path: Path):
    from pycalphad import Database
    db = Database(str(tdb_path))
    symbols = {name: str(expr) for name, expr in db.symbols.items()}
    params = {}
    for p in db._parameters.all():
        key = _pkey(p)
        params[key] = str(p["parameter"])
    phases = {name: {"sublattices": tuple(float(s) for s in ph.sublattices),
                     "constituents": [sorted(_names(sub)) for sub in ph.constituents],
                     "model_hints": dict(ph.model_hints)}
              for name, ph in db.phases.items()}
    return symbols, params, phases


def fmt_pkey(key) -> str:
    phase, sub, order, ptype, dsp = key
    sub_str = ":".join(",".join(s) for s in sub)
    base = f"{ptype}({phase},{sub_str};{order})"
    if dsp:
        base += f" [diff={dsp}]"
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path,
                    help="2 or 3 TDB files to compare")
    ap.add_argument("--out", type=Path, default=None,
                    help="optional output path for the full report")
    ap.add_argument("--max-diff", type=int, default=0,
                    help="truncate long expression values to this many "
                         "characters (0 = no truncation)")
    args = ap.parse_args()

    if len(args.files) < 2 or len(args.files) > 3:
        ap.error("pass 2 or 3 TDB files")

    files = args.files
    short = [p.stem for p in files]

    print(f"Comparing {len(files)} files:")
    for i, p in enumerate(files):
        print(f"  [{i}] {p.name}")
    print()

    loaded = [load(p) for p in files]
    symbols_list = [l[0] for l in loaded]
    params_list = [l[1] for l in loaded]
    phases_list = [l[2] for l in loaded]

    out_lines = []
    def emit(line=""):
        print(line)
        out_lines.append(line)

    def trunc(s):
        if args.max_diff and len(s) > args.max_diff:
            return s[: args.max_diff] + f" … [{len(s)} chars]"
        return s

    # === SECTION 0 — phase structure ===============================
    emit("=" * 78)
    emit("SECTION 0  — phase structure (quick overview)")
    emit("=" * 78)
    all_phases = sorted(set().union(*[set(ph) for ph in phases_list]))
    emit(f"{'phase':30s}  " + "  ".join(f"{s:>15s}" for s in short))
    emit("-" * 78)
    for ph in all_phases:
        presence = []
        for i in range(len(files)):
            if ph in phases_list[i]:
                sl = phases_list[i][ph]["sublattices"]
                presence.append("+".join(f"{s:g}" for s in sl))
            else:
                presence.append("—")
        emit(f"{ph:30s}  " + "  ".join(f"{p:>15s}" for p in presence))
    emit()

    # === SECTION 1 — symbols only in one file ======================
    emit("=" * 78)
    emit("SECTION 1  — symbols (FUNCTION blocks) only in some files")
    emit("=" * 78)
    all_sym = sorted(set().union(*[set(s) for s in symbols_list]))
    unique_count = 0
    for name in all_sym:
        present = [name in symbols_list[i] for i in range(len(files))]
        if not all(present):
            marks = " ".join("+" if p else "." for p in present)
            emit(f"  [{marks}]  {name}")
            unique_count += 1
    if unique_count == 0:
        emit("  (all files define the same symbol set)")
    emit()

    # === SECTION 2 — symbols with different expressions =============
    emit("=" * 78)
    emit("SECTION 2  — shared symbols with different expressions")
    emit("=" * 78)
    diff_sym = []
    for name in all_sym:
        if not all(name in s for s in symbols_list):
            continue
        exprs = [s[name] for s in symbols_list]
        if len(set(exprs)) > 1:
            diff_sym.append((name, exprs))
    if not diff_sym:
        emit("  (all shared symbols have identical expressions)")
    else:
        emit(f"  {len(diff_sym)} symbol(s) differ:\n")
        for name, exprs in diff_sym:
            emit(f"  SYMBOL  {name}")
            for i, e in enumerate(exprs):
                emit(f"    [{short[i]}]  {trunc(e)}")
            emit()

    # === SECTION 3 — parameters only in some files ==================
    emit("=" * 78)
    emit("SECTION 3  — parameters only in some files")
    emit("=" * 78)
    all_keys = sorted(set().union(*[set(p) for p in params_list]))
    unique_param_count = 0
    for key in all_keys:
        present = [key in params_list[i] for i in range(len(files))]
        if not all(present):
            marks = " ".join("+" if p else "." for p in present)
            emit(f"  [{marks}]  {fmt_pkey(key)}")
            unique_param_count += 1
    if unique_param_count == 0:
        emit("  (all files define the same parameter set)")
    emit()

    # === SECTION 4 — parameters with different values ===============
    emit("=" * 78)
    emit("SECTION 4  — shared parameters with different values")
    emit("=" * 78)
    diff_params = []
    for key in all_keys:
        if not all(key in p for p in params_list):
            continue
        vals = [p[key] for p in params_list]
        if len(set(vals)) > 1:
            diff_params.append((key, vals))
    if not diff_params:
        emit("  (all shared parameters have identical values)")
    else:
        emit(f"  {len(diff_params)} parameter(s) differ:\n")
        for key, vals in diff_params:
            emit(f"  PARAM  {fmt_pkey(key)}")
            for i, v in enumerate(vals):
                emit(f"    [{short[i]}]  {trunc(v)}")
            emit()

    # === final summary ==============================================
    emit("=" * 78)
    emit("SUMMARY")
    emit("=" * 78)
    emit(f"  Files compared        : {len(files)}")
    emit(f"  Symbols unique        : {unique_count}")
    emit(f"  Symbols differing     : {len(diff_sym)}")
    emit(f"  Parameters unique     : {unique_param_count}")
    emit(f"  Parameters differing  : {len(diff_params)}")
    emit()

    if args.out:
        args.out.write_text("\n".join(out_lines))
        print(f"\nFull output written to: {args.out}")


if __name__ == "__main__":
    main()
