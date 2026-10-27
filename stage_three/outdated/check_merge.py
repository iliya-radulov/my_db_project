"""
check_merge.py — does the Fe-Nd-B merge count any Gibbs energy twice?   (read-only, ~1 min)

The feasibility screen (Section 6) finds a threshold of -12.0 kJ/mol-atom with the merged SGTE
binaries, against -8.4 (Hallemans 1995) and -8.7 (Chen 2019) for full ternary assessments.
-12.0 is what the lever rule gives if the Gibbs energy of Fe2B were counted twice. This script
merges the three binaries exactly as the app does (tdb_lookup + merge_tdb_files) and reports:
  1. which files were merged;
  2. PARAMETER lines that occur more than once in the merged text, and in the loaded database;
  3. the formation Gibbs energy at 800 K of every binary compound, in the merged database and in
     its own single binary file — they must be identical;
  4. the energy of the binary-phase assemblage at Nd2Fe14B, which should reproduce -12.0.
All energies in kJ per mole of atoms, relative to the GHSER functions (as in feasibility.py).

Usage (stage_three/, MAIN venv with pycalphad):   python check_merge.py
"""
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tdb_lookup import build_index, find_binaries, select_preferred   # noqa: E402
from phase_diagram_ternary_v3 import merge_tdb_files                   # noqa: E402
from pycalphad import Database, calculate, equilibrium, variables as v  # noqa: E402

TDB_DIR = HERE.parent / "data" / "tdb" / "sgte_binary"
T = 800.0
ELS = ["FE", "ND", "B"]
PAR = re.compile(r"^\s*PARAMETER\s+(\w+)\(\s*([^,]+?)\s*,\s*([^;]+?)\s*;\s*(\d+)\s*\)", re.I)


def ghser(db, el):
    for name in (f"GHSER{el}", f"GHSER{el}{el}"):
        if name in db.symbols:
            return float(db.symbols[name].subs({v.T: T}))
    raise KeyError(f"no GHSER function for {el}")


def g_form(db, phase):
    """Formation Gibbs energy (kJ/mol-atom) of a line compound vs the GHSER functions."""
    els = sorted({c for sub in db.phases[phase].constituents for c in sub} - {"VA"})
    r = calculate(db, els + ["VA"], phase, T=T, P=101325, N=1, output="GM")
    gm = r.GM.values.reshape(-1)
    i = int(gm.argmin())
    x = r.X.values.reshape(-1, len(r.component))[i]
    ref = sum(xi * ghser(db, str(c)) for c, xi in zip(r.component.values, x) if xi > 1e-9)
    comp = " ".join(f"{c}{xi:.3f}" for c, xi in zip(r.component.values, x) if xi > 1e-9)
    return (gm[i] - ref) / 1000, comp


def main():
    index = build_index(TDB_DIR)
    cand = find_binaries(ELS, index)
    selected = {p: select_preferred(f) for p, f in cand.items()}
    paths = sorted(selected.values(), key=lambda p: p.name)
    print("1. Merged files:", ", ".join(p.name for p in paths))

    text = merge_tdb_files(paths)
    merged = HERE / "_check_merge.tdb"
    merged.write_text(text, encoding="utf-8")
    try:
        keys = Counter()
        for line in text.splitlines():
            m = PAR.match(line.upper())
            if m:
                keys[tuple(s.replace(" ", "") for s in m.groups())] += 1
        dup = {k: n for k, n in keys.items() if n > 1}
        print(f"\n2. PARAMETER lines in the merged text: {sum(keys.values())}, "
              f"occurring more than once: {len(dup)}")
        for k, n in sorted(dup.items()):
            print(f"     {n}x  {k[0]}({k[1]},{k[2]};{k[3]})")
        db = Database(str(merged))
        pk = Counter((p["phase_name"], str(p["constituent_array"]), p["parameter_order"],
                      p["parameter_type"]) for p in db._parameters.all())
        pdup = {k: n for k, n in pk.items() if n > 1}
        print(f"   in the loaded database: {len(pdup)} duplicated parameter keys")
        for k, n in sorted(pdup.items())[:20]:
            print(f"     {n}x  {k}")

        print(f"\n3. Formation Gibbs energy at {T:.0f} K, kJ/mol-atom   merged   own file   difference")
        for path in paths:
            single = Database(str(path))
            for ph in sorted(single.phases):
                cons = single.phases[ph].constituents
                if not all(len(sub) == 1 for sub in cons) or len(cons) < 2 or ph not in db.phases:
                    continue                              # line compounds only
                try:
                    g_m, comp = g_form(db, ph)
                    g_s, _ = g_form(single, ph)
                except Exception as e:
                    print(f"   {ph:14s} ({path.name}): could not compute ({e})")
                    continue
                flag = "" if abs(g_m - g_s) < 0.01 else "   <-- DIFFERENT"
                print(f"   {ph:14s} {comp:28s} {g_m:8.2f} {g_s:9.2f} {g_m - g_s:10.2f}{flag}")

        x = {"FE": 14 / 17, "ND": 2 / 17, "B": 1 / 17}
        r = equilibrium(db, ELS + ["VA"], list(db.phases),
                        {v.X("ND"): x["ND"], v.X("B"): x["B"], v.T: T, v.P: 101325, v.N: 1})
        names = [str(n) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1)) if n and f > 1e-3]
        fr = [round(float(f), 3) for n, f in zip(r.Phase.values.reshape(-1), r.NP.values.reshape(-1)) if n and f > 1e-3]
        ser = sum(x[e] * ghser(db, e) for e in ELS)
        print(f"\n4. Binary-phase assemblage at Nd2Fe14B, {T:.0f} K: {dict(zip(names, fr))}")
        print(f"   energy vs GHSER: {(float(r.GM.values.squeeze()) - ser) / 1000:.2f} kJ/mol-atom "
              f"(the feasibility screen reported -12.0)")
    finally:
        merged.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
