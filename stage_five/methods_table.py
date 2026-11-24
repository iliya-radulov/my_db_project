#!/usr/bin/env python3
"""
stage_five/methods_table.py

Publication-style summary table of the Stage 5 screening for several systems: CALPHAD
binary-ensemble threshold band ΔG_f*(T), survival ratio and gate status, and, where a SISSO
report exists, the candidate (with its provenance: exact_match / nearest_prototype and Δx),
ΔG_f^SISSO(T), the stability margin and the verdict.

The table is built from saved JSON reports, so it needs no network and no Materials Project key:

    python stage_five/methods_table.py \\
        --system B-Fe-Nd=stage5_bfend.json,sisso_nd2fe14b.json \\
        --system Al-Fe-Mn=stage5_alfemn.json \\
        --system Fe-La-Si=stage5_felasi.json,sisso_felasi.json \\
        --temp 800 --out methods_table.md --tsv methods_table.tsv

`ensemble.json` is the output of general_ensemble.py (or screen_ternary.py --out, key "ensemble");
`sisso.json` of dft_sisso_predictor.py (or screen_ternary.py --out, key "sisso"). Without a SISSO
report the SISSO columns say "not run" - they are never filled with a guess.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dft_sisso_predictor import compare_with_calphad_ensemble
from prototype_match import provenance_label

COLUMNS = [
    "System", "Target (atomic fractions)", "Merge priority", "Survivors", "Gates",
    "ΔG_f*(T) median [5%, 95%] kJ/mol-atom", "Competing assemblage",
    "SISSO entry (provenance)", "ΔG_f^SISSO(T) kJ/mol-atom", "Margin kJ/mol-atom", "Verdict",
]


def _load_json(path: str | Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d


def _ens(d: dict) -> dict:
    return d["ensemble"] if "ensemble" in d and "gates" not in d else d


def _sisso(d: dict | None) -> dict | None:
    if d is None:
        return None
    return d["sisso"] if "sisso" in d and "candidates" not in d else d


def system_row(label: str, ensemble: dict, sisso: dict | None = None, T: float = 800.0) -> dict:
    t_key = str(float(T))
    g = ensemble["gates"]
    stats = ensemble["threshold_distribution"].get(t_key)
    surv = g["G1_survival"]
    lin = g["G2_lineage_coverage"]["surviving_lineages_per_edge"]
    gate_txt = (
        f"{'PASS' if g['gate_passed'] else 'FAIL'} (G1 {'ok' if g['G1_survival']['pass'] else 'no'}, "
        f"G2 {'ok' if g['G2_lineage_coverage']['pass'] else 'no'}; lineages/edge "
        + "/".join(str(len(v)) for v in lin.values()) + ")"
    )
    row = {
        "System": label or ensemble.get("system", ""),
        "Target (atomic fractions)": ", ".join(f"{k} {v:.3f}" for k, v in ensemble["target_composition"].items()),
        "Merge priority": " > ".join(ensemble.get("edge_priority", [])) or "n/a (pre-fix report)",
        "Survivors": f"{surv['survived']}/{surv['total']} ({100 * surv['survived'] / max(surv['total'], 1):.0f} %)",
        "Gates": gate_txt,
        "ΔG_f*(T) median [5%, 95%] kJ/mol-atom": (
            f"{stats['median_kJ']:+.2f} [{stats['p05_kJ']:+.2f}, {stats['p95_kJ']:+.2f}]" if stats else "n/a"),
        "Competing assemblage": stats["dominant_competing_assemblage"] if stats else "n/a",
    }
    rows = compare_with_calphad_ensemble(sisso, ensemble) if sisso else []
    rows_T = [r for r in rows if str(float(r["T_K"])) == t_key]
    if sisso is None:
        row.update({"SISSO entry (provenance)": "not run (needs a SISSO report / MP_API_KEY)",
                    "ΔG_f^SISSO(T) kJ/mol-atom": "—", "Margin kJ/mol-atom": "—", "Verdict": "—"})
    elif not rows_T:
        note = sisso.get("match_type") or "no comparable row"
        row.update({"SISSO entry (provenance)": "no_dft_entry" if note == "no_dft_entry" else f"none at {T:.0f} K",
                    "ΔG_f^SISSO(T) kJ/mol-atom": "—", "Margin kJ/mol-atom": "—",
                    "Verdict": "—" if g["gate_passed"] else "gate failed: no verdict"})
    else:
        top = rows_T[0]
        extra = f" (+{len(rows_T) - 1} more)" if len(rows_T) > 1 else ""
        mark = "†" if not top["comparable"] else ""
        row.update({
            "SISSO entry (provenance)": provenance_label(top) + (f", {top['spacegroup']}" if top.get("spacegroup") else "") + extra,
            "ΔG_f^SISSO(T) kJ/mol-atom": f"{top['dGf_sisso_kJ']:+.2f}",
            "Margin kJ/mol-atom": ("—" if top["stability_margin_kJ"] is None else f"{top['stability_margin_kJ']:+.2f}{mark}"),
            "Verdict": top["verdict"],
        })
    return row


def build_table(systems: list[tuple[str, dict, dict | None]], T: float = 800.0) -> tuple[str, list[dict]]:
    rows = [system_row(lbl, e, s, T) for lbl, e, s in systems]
    md = [f"Stage 5 screening at {T:.0f} K. ΔG in kJ/mol-atom relative to SER.", "",
          "| " + " | ".join(COLUMNS) + " |", "|" + "|".join("---" for _ in COLUMNS) + "|"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]).replace("|", "/") for c in COLUMNS) + " |")
    notes = [
        "",
        "Notes",
        "- ΔG_f*: distribution over the surviving combinations of the open binary assessments "
        "(competing-assemblage energy at the target composition, binaries only, no ternary phase).",
        "- Merge priority: the first file wins on conflicting parameters, so the edge order can change the "
        "survivor count; the order is part of the specification.",
        "- Gate parameters are Stage-5 engineering defaults unless registered otherwise "
        f"(preregistered={any(e['gates'].get('parameters', {}).get('preregistered') for _, e, _ in systems)}).",
        "- Classes (stable_across_band / borderline_within_band / metastable_above_band) come from the CALPHAD band "
        "only: ΔG_f^SISSO against the 5th and 95th percentile edges. The SISSO error is not part of the class; "
        "it is usually larger than the band (SISSO slope of about +15 J/(mol-atom·K) for Nd2Fe14B).",
    ]
    notes.append("")
    notes.append("Per-system provenance (frozen reports): specification hash, hash of the accepted TDB files, engine rules version")
    for lbl, e, _ in systems:
        notes.append(f"- {lbl or e.get('system', '')}: spec {str(e.get('spec_sha256', 'n/a'))[:12]}, "
                     f"TDB collection {str(e.get('tdb_collection_sha256', 'n/a'))[:12]}, "
                     f"{e.get('engine_rules_version', 'n/a')}")
    for lbl, e, _ in systems:
        excluded = sorted(a["file"] for a in e.get("audit_log", []) if a.get("status") == "excluded")
        always = sorted(f for f, v in e.get("failure_summary", {}).get("by_file", {}).items()
                        if v["total"] and v["failed"] == v["total"])
        if excluded or always:
            notes.append(f"- {lbl or e.get('system', '')}: audit-excluded files: {', '.join(excluded) or 'none'}; "
                         f"files that fail the edge check in every combination: {', '.join(always) or 'none'}")
    if any("†" in r["Margin kJ/mol-atom"] for r in rows):
        notes.append("- † nearest_prototype: the DFT entry is at a different composition (Δx in the entry label); "
                     "energy and margin are indicative, not a stability verdict.")
    return "\n".join(md + notes) + "\n", rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", action="append", required=True, metavar="LABEL=ensemble.json[,sisso.json]")
    ap.add_argument("--temp", type=float, default=800.0)
    ap.add_argument("--out", type=Path, default=None, help="Markdown output")
    ap.add_argument("--tsv", type=Path, default=None, help="Tab-separated output")
    args = ap.parse_args()

    systems = []
    for spec in args.system:
        label, _, files = spec.partition("=")
        parts = [p for p in files.split(",") if p]
        systems.append((label, _ens(_load_json(parts[0])), _sisso(_load_json(parts[1])) if len(parts) > 1 else None))
    md, rows = build_table(systems, args.temp)
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    if args.tsv:
        args.tsv.write_text("\n".join("\t".join(str(r[c]) for c in COLUMNS) for r in [dict(zip(COLUMNS, COLUMNS))] + rows) + "\n",
                            encoding="utf-8")


if __name__ == "__main__":
    main()
