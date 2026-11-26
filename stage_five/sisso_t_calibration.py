#!/usr/bin/env python3
"""
stage_five/sisso_t_calibration.py

SISSO temperature-calibration study (pre-registration note v1.5, Option C).

For each fit compound and each retained grid temperature:

    dG_SISSO(T)   Stage-5 path (dft_sisso_predictor: MP entry + GibbsComputedStructureEntry),
                  relative to pymatgen's elemental table g_els            [kJ/mol-atom]
    dG_CALPHAD(T) = GM_eq(compound, T) - sum_i x_i GM_eq(element i, T), both computed in the
                  compound's named TDB; element = lowest-G condensed phase incl. the magnetic
                  term, boron fixed to BETA_RHOMBO_B                      [kJ/mol-atom]
    Residual(T)   = dG_SISSO(T) - dG_CALPHAD(T)

A grid point is retained only if the expected phase is the single equilibrium phase of the
compound's TDB at that temperature (phase fraction >= PHASE_FRACTION_MIN).

Per compound: OLS slope of Residual(T) [J/mol-atom/K]. alpha = unweighted mean of the slopes
(one weight per compound). Sign convention: positive alpha means SISSO becomes too positive with
rising T; the correction dG_corr = dG_SISSO - alpha * (T - T0) lowers the high-T value.
Mean absolute residual (MAE) = equal-weight mean over compounds of each compound's mean |Residual|
over its retained points.

Modes (in the order of the study):
    --check-calphad        CALPHAD side only: phase check, dG_CALPHAD, reference tables.
                           Contains no SISSO evaluation, so it may run before the freeze.
    --manifest OUT.json    SHA-256 of this script, the note, every TDB, unary50.tdb, g_els.json and
                           the package versions. Hash the note, then write the manifest (freeze).
    --run                  Full study. Refuses to run unless --note hashes to --note-sha256 and every
                           file in --manifest still has its recorded hash.

Usage (desktop, from the repository root):
    python stage_five/sisso_t_calibration.py --check-calphad
    python stage_five/sisso_t_calibration.py --note NOTE.md --manifest freeze_manifest.json
    python stage_five/sisso_t_calibration.py --run --note NOTE.md --note-sha256 <sha> \
        --manifest freeze_manifest.json --out stage_five/results/sisso_t_calibration
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

# ---------------------------------------------------------------------------
# Pre-registered settings (part of the hashed script; change only by a new contract version)
# ---------------------------------------------------------------------------
GRID = [800.0, 1000.0, 1100.0, 1200.0, 1300.0, 1375.0, 1450.0, 1600.0]
T0 = 800.0
EV_TO_KJ = 96.48533212331002          # same constant as dft_sisso_predictor
PHASE_FRACTION_MIN = 0.999            # expected phase must carry at least this fraction
MIN_POINTS = 3                        # a compound with fewer retained grid points is dropped
MAE_GAIN_MIN = 1.5                    # kJ/mol-atom, condition 1 of the decision rule
V1_0_WORSEN_LIMIT = 2.0               # kJ/mol-atom, only used by decision rule "v1.0"
DECISION_RULE = "v1.4"                # "v1.4": no compound worsened by more than the mean gain
                                      # "v1.0": at most one compound worsened by > 2.0 kJ
# Element reference phases: None = lowest-G condensed phase; a list = fixed to these phases.
ELEMENT_PHASES = {"B": ["BETA_RHOMBO_B"]}
EXCLUDED_PHASE_WORDS = ("GAS",)       # condensed phases only
UNARY_TDB = "unary50.tdb"

# Fit set (note v1.5, section 3). x = mole fractions; tdb = first file of the preference list that
# loaded in test4.py (selection rule recorded in the note).
COMPOUNDS = [
    {"name": "Fe3Si",  "formula": "Fe3Si",  "mp_id": "mp-2199", "tdb": "FeSi-14Yua.tdb",
     "x": {"Fe": 3 / 4, "Si": 1 / 4}, "phase": ["B2_BCC"], "magnetic": True},
    {"name": "Fe2B",   "formula": "Fe2B",   "mp_id": "mp-1915", "tdb": "FeB-02Rom.tdb",
     "x": {"Fe": 2 / 3, "B": 1 / 3}, "phase": ["M2B_C16"], "magnetic": True},
    {"name": "CoSi",   "formula": "CoSi",   "mp_id": "mp-7577", "tdb": "CoSi-06Zha.tdb",
     "x": {"Co": 1 / 2, "Si": 1 / 2}, "phase": ["COSI_B20"], "magnetic": False},
    {"name": "TiB2",   "formula": "TiB2",   "mp_id": "mp-1145", "tdb": "TiB-04Ma.tdb",
     "x": {"Ti": 1 / 3, "B": 2 / 3}, "phase": ["TIB2_C32"], "magnetic": False},
    {"name": "LaB6",   "formula": "LaB6",   "mp_id": "mp-2680", "tdb": "LaB-13Tan.tdb",
     "x": {"La": 1 / 7, "B": 6 / 7}, "phase": ["LAB6_D21"], "magnetic": False},
    {"name": "NiAl",   "formula": "NiAl",   "mp_id": "mp-1487", "tdb": "AlNi-01Dup-4sl.tdb",
     "x": {"Ni": 1 / 2, "Al": 1 / 2}, "phase": ["B2_BCC"], "magnetic": False},
    {"name": "YAl2",   "formula": "YAl2",   "mp_id": "mp-2322", "tdb": "AlY-95Gro-LB.tdb",
     "x": {"Y": 1 / 3, "Al": 2 / 3}, "phase": ["AL2Y_C15"], "magnetic": False},
    {"name": "Ti5Si3", "formula": "Ti5Si3", "mp_id": "mp-2108", "tdb": "SiTi-96Sei-LB.tdb",
     "x": {"Ti": 5 / 8, "Si": 3 / 8}, "phase": ["SI3TI5_D88"], "magnetic": False},
    {"name": "Mg2Si",  "formula": "Mg2Si",  "mp_id": "mp-1367", "tdb": "MgSi-04Kev.tdb",
     "x": {"Mg": 2 / 3, "Si": 1 / 3}, "phase": ["MG2SI_C1"], "magnetic": False},
]
SENSITIVITY_DROP = "Fe3Si"            # pre-registered: alpha and decision also without this compound


# ---------------------------------------------------------------------------
# Pure helpers (no pycalphad / pymatgen / network: unit-tested offline)
# ---------------------------------------------------------------------------
def phase_fraction(names, fractions, wanted) -> float:
    """Total fraction of the phases in `wanted` among the equilibrium vertices (names, NP)."""
    total = 0.0
    for n, f in zip(names, fractions):
        if str(n) in wanted and f == f:  # f == f filters NaN
            total += float(f)
    return total


def ols_slope_J(temps, values) -> float:
    """OLS slope of values [kJ/mol-atom] vs T [K], returned in J/mol-atom/K."""
    t = np.asarray(temps, float)
    y = np.asarray(values, float)
    return float(np.polyfit(t, y, 1)[0] * 1000.0)


def mae_by_compound(residuals: dict[str, dict[float, float]]) -> dict[str, float]:
    return {c: float(np.mean([abs(r) for r in pts.values()])) for c, pts in residuals.items()}


def apply_correction(residuals, alpha_J: float, t0: float = T0):
    """Residual after dG_corr = dG_SISSO - alpha (T - T0); alpha in J/mol-atom/K."""
    return {c: {T: r - alpha_J / 1000.0 * (T - t0) for T, r in pts.items()} for c, pts in residuals.items()}


def evaluate(residuals: dict[str, dict[float, float]], rule: str = DECISION_RULE) -> dict:
    """Slopes, alpha, MAE before/after and the pre-registered decision on `residuals`
    ({compound: {T: residual kJ/mol-atom}}, retained points only)."""
    slopes = {c: ols_slope_J(list(p), list(p.values())) for c, p in residuals.items()}
    alpha = float(np.mean(list(slopes.values())))
    scatter = float(np.std(list(slopes.values()), ddof=1)) if len(slopes) > 1 else float("nan")
    before = mae_by_compound(residuals)
    after = mae_by_compound(apply_correction(residuals, alpha))
    mae_before = float(np.mean(list(before.values())))
    mae_after = float(np.mean(list(after.values())))
    gain = mae_before - mae_after
    worsening = {c: after[c] - before[c] for c in residuals}   # > 0: compound got worse
    cond1 = gain >= MAE_GAIN_MIN
    if rule == "v1.4":
        cond2 = max(worsening.values()) <= gain
        cond2_text = f"max worsening {max(worsening.values()):+.3f} <= mean gain {gain:+.3f} kJ"
    elif rule == "v1.0":
        n_bad = sum(1 for w in worsening.values() if w > V1_0_WORSEN_LIMIT)
        cond2 = n_bad <= 1
        cond2_text = f"{n_bad} compound(s) worsened by > {V1_0_WORSEN_LIMIT} kJ (at most 1 allowed)"
    else:
        raise ValueError(f"unknown decision rule {rule!r}")
    return {
        "rule": rule, "n_compounds": len(residuals),
        "slopes_J_mol_atom_K": slopes, "alpha_J_mol_atom_K": alpha, "slope_scatter_sd": scatter,
        "mae_before_kJ": before, "mae_after_kJ": after,
        "mean_mae_before_kJ": mae_before, "mean_mae_after_kJ": mae_after, "mean_gain_kJ": gain,
        "worsening_kJ": worsening,
        "condition_1": {"pass": bool(cond1), "text": f"mean gain {gain:+.3f} >= {MAE_GAIN_MIN} kJ"},
        "condition_2": {"pass": bool(cond2), "text": cond2_text},
        "correction_adopted": bool(cond1 and cond2),
    }


def leave_one_out(residuals) -> dict[str, dict]:
    """Secondary: alpha from the other compounds, applied to the left-out one."""
    out = {}
    for c in residuals:
        others = {k: v for k, v in residuals.items() if k != c}
        if not others:
            continue
        a = float(np.mean([ols_slope_J(list(p), list(p.values())) for p in others.values()]))
        b = mae_by_compound({c: residuals[c]})[c]
        aft = mae_by_compound(apply_correction({c: residuals[c]}, a))[c]
        out[c] = {"alpha_without_J": a, "mae_before_kJ": b, "mae_after_kJ": aft, "change_kJ": aft - b}
    return out


def restrict(residuals, t_max: float):
    sub = {c: {T: r for T, r in p.items() if T <= t_max} for c, p in residuals.items()}
    return {c: p for c, p in sub.items() if len(p) >= MIN_POINTS}


def pick_sisso_candidate(report: dict, mp_id: str) -> dict | None:
    """The candidate of a dft_sisso_predictor report that is the given MP material.
    Entry ids may carry a functional suffix (e.g. 'mp-2199-GGA')."""
    for c in report.get("candidates", []):
        eid = str(c.get("material_id", ""))
        if eid == mp_id or eid.startswith(mp_id + "-"):
            return c
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def find_file(name: str, roots: list[Path]) -> Path:
    hits = []
    for r in roots:
        hits += [p for p in r.rglob(name) if p.is_file()]
    hits = sorted(set(hits))
    if not hits:
        raise FileNotFoundError(f"{name} not found under {', '.join(map(str, roots))}")
    if len(hits) > 1:
        digests = {sha256_file(p) for p in hits}
        if len(digests) > 1:
            raise RuntimeError(f"{name}: {len(hits)} copies with different content: {hits}")
    return hits[0]


def g_els_path() -> Path:
    import pymatgen
    root = Path(pymatgen.__file__).resolve().parent
    hits = sorted(root.rglob("g_els.json"))
    if not hits:
        raise FileNotFoundError("g_els.json not found in the installed pymatgen")
    return hits[0]


def g_els_kJ(elements, temps) -> dict[str, np.ndarray]:
    """pymatgen elemental terms, linearly interpolated (as GibbsComputedStructureEntry does)."""
    raw = json.loads(g_els_path().read_text())
    out = {}
    for el in elements:
        pts = sorted((float(t), d[el]) for t, d in raw.items() if el in d)
        ts, vs = zip(*pts)
        out[el] = np.interp(temps, ts, np.asarray(vs) * EV_TO_KJ)
    return out


# ---------------------------------------------------------------------------
# CALPHAD side
# ---------------------------------------------------------------------------
def _condensed_phases(db, comps) -> list[str]:
    from pycalphad import variables as v  # noqa: F401  (import check)
    out = []
    for name, ph in db.phases.items():
        if any(w in name.upper() for w in EXCLUDED_PHASE_WORDS):
            continue
        species = {str(getattr(s, "name", s)).upper() for sub in ph.constituents for s in sub}
        if species & set(comps):
            out.append(name)
    return out


def element_gm_kJ(db, el: str, temps):
    """GM of pure element `el` at equilibrium in `db` [kJ/mol] and the phase at each T."""
    from pycalphad import equilibrium, variables as v
    EL = el.upper()
    comps = [EL, "VA"]
    fixed = ELEMENT_PHASES.get(el)
    phases = [p for p in (fixed or _condensed_phases(db, comps)) if p in db.phases]
    if not phases:
        raise ValueError(f"no usable phase for {el} (wanted {fixed})")
    eq = equilibrium(db, comps, phases, {v.T: list(temps), v.P: 101325, v.N: 1})
    gm = np.asarray(eq.GM.values).reshape(-1)[: len(temps)] / 1000.0
    names = []
    for i in range(len(temps)):
        ph = [str(p) for p in np.asarray(eq.Phase.isel(T=i).values).ravel() if str(p)]
        names.append("+".join(sorted(set(ph))))
    return gm, names


def compound_calphad(db, comp: dict, temps) -> dict:
    """dG_CALPHAD per grid point of one compound, with the phase check."""
    from pycalphad import equilibrium, variables as v
    els = list(comp["x"])
    comps = sorted(e.upper() for e in els) + ["VA"]
    phases = _condensed_phases(db, set(comps))
    second = els[1]
    eq = equilibrium(db, comps, phases,
                     {v.X(second.upper()): comp["x"][second], v.T: list(temps), v.P: 101325, v.N: 1})
    gm_comp = np.asarray(eq.GM.values).reshape(-1)[: len(temps)] / 1000.0
    el_gm, el_phase = {}, {}
    for el in els:
        el_gm[el], el_phase[el] = element_gm_kJ(db, el, temps)
    rows = []
    for i, T in enumerate(temps):
        names = np.asarray(eq.Phase.isel(T=i).values).ravel()
        fracs = np.asarray(eq.NP.isel(T=i).values).ravel()
        present = sorted({str(n) for n in names if str(n)})
        frac = phase_fraction(names, fracs, comp["phase"])
        ok = frac >= PHASE_FRACTION_MIN
        dg = gm_comp[i] - sum(comp["x"][el] * el_gm[el][i] for el in els)
        rows.append({"T": float(T), "phases": present, "expected_fraction": round(frac, 6),
                     "retained": bool(ok), "dG_calphad_kJ": float(dg),
                     "element_phase": {el: el_phase[el][i] for el in els},
                     "element_gm_kJ": {el: float(el_gm[el][i]) for el in els}})
    return {"rows": rows, "n_retained": sum(r["retained"] for r in rows)}


def check_calphad(roots: list[Path]) -> dict:
    """CALPHAD side for all compounds + reference tables (no SISSO)."""
    from pycalphad import Database
    warnings.filterwarnings("ignore")
    elements = sorted({el for c in COMPOUNDS for el in c["x"]})
    gels = g_els_kJ(elements, GRID)
    unary = Database(str(find_file(UNARY_TDB, roots)))
    unary_gm = {el: element_gm_kJ(unary, el, GRID)[0] for el in elements}
    out = {"grid": GRID, "compounds": {}, "phase_fraction_min": PHASE_FRACTION_MIN}
    for comp in COMPOUNDS:
        path = find_file(comp["tdb"], roots)
        res = compound_calphad(Database(str(path)), comp, GRID)
        for r in res["rows"]:
            # reference noise actually used: g_els - GM_eq(element) in THIS TDB, and TDB vs unary50
            r["g_els_minus_gm_tdb_kJ"] = {el: float(gels[el][GRID.index(r["T"])] - r["element_gm_kJ"][el])
                                          for el in comp["x"]}
            r["gm_tdb_minus_unary50_kJ"] = {el: float(r["element_gm_kJ"][el] - unary_gm[el][GRID.index(r["T"])])
                                            for el in comp["x"]}
        res["tdb_path"] = str(path)
        res["dropped"] = res["n_retained"] < MIN_POINTS
        out["compounds"][comp["name"]] = res
    return out


# ---------------------------------------------------------------------------
# SISSO side + study
# ---------------------------------------------------------------------------
def sisso_dgf(comp: dict, temps) -> tuple[dict[float, float], str]:
    sys.path.insert(0, str(HERE))
    from dft_sisso_predictor import predict_sisso_formation_gibbs
    rep = predict_sisso_formation_gibbs(comp["formula"], list(temps), nearest_prototype=False)
    cand = pick_sisso_candidate(rep, comp["mp_id"])
    if cand is None:
        raise RuntimeError(f"{comp['name']}: {comp['mp_id']} not among the SISSO candidates "
                           f"{[c.get('material_id') for c in rep.get('candidates', [])]}")
    vals = {float(T): cand["dGf_sisso_kJ_mol_atom"].get(str(float(T))) for T in temps}
    return vals, str(cand["material_id"])


def run_study(roots: list[Path]) -> dict:
    cal = check_calphad(roots)
    residuals, table, excluded = {}, {}, {}
    for comp in COMPOUNDS:
        c = cal["compounds"][comp["name"]]
        if c["dropped"]:
            excluded[comp["name"]] = f"{c['n_retained']} retained grid points (< {MIN_POINTS})"
            continue
        temps = [r["T"] for r in c["rows"] if r["retained"]]
        sisso, entry_id = sisso_dgf(comp, temps)
        pts = {}
        for r in c["rows"]:
            if not r["retained"]:
                continue
            s = sisso.get(r["T"])
            if s is None:
                continue
            pts[r["T"]] = s - r["dG_calphad_kJ"]
            r.update(dG_sisso_kJ=s, residual_kJ=pts[r["T"]])
        c["sisso_entry_id"] = entry_id
        if len(pts) < MIN_POINTS:
            excluded[comp["name"]] = f"{len(pts)} points with a SISSO value (< {MIN_POINTS})"
            continue
        residuals[comp["name"]] = pts
        table[comp["name"]] = c
    primary = evaluate(residuals)
    no_drop = {k: v for k, v in residuals.items() if k != SENSITIVITY_DROP}
    magnetic = {c["name"] for c in COMPOUNDS if c["magnetic"]}
    slopes = primary["slopes_J_mol_atom_K"]
    return {
        "calphad": cal, "excluded": excluded,
        "residuals_kJ": {c: {str(T): r for T, r in p.items()} for c, p in residuals.items()},
        "primary": primary,
        "secondary": {
            f"without_{SENSITIVITY_DROP}": evaluate(no_drop) if len(no_drop) >= 2 else None,
            "leave_one_out": leave_one_out(residuals),
            "upto_1300K": evaluate(restrict(residuals, 1300.0)) if len(restrict(residuals, 1300.0)) >= 2 else None,
            "residual_800K_kJ": {c: p.get(800.0) for c, p in residuals.items()},
            "mean_slope_magnetic": float(np.mean([s for c, s in slopes.items() if c in magnetic] or [np.nan])),
            "mean_slope_non_magnetic": float(np.mean([s for c, s in slopes.items() if c not in magnetic] or [np.nan])),
        },
    }


# ---------------------------------------------------------------------------
# Freeze manifest
# ---------------------------------------------------------------------------
def versions() -> dict:
    import importlib.metadata as md
    out = {"python": sys.version.split()[0]}
    for pkg in ("pymatgen", "pycalphad", "mp-api", "numpy"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def manifest_files(roots, note: Path | None) -> dict[str, Path]:
    files = {"script": Path(__file__).resolve(), "g_els.json": g_els_path(), UNARY_TDB: find_file(UNARY_TDB, roots)}
    for c in COMPOUNDS:
        files[c["tdb"]] = find_file(c["tdb"], roots)
    for dep in ("dft_sisso_predictor.py", "prototype_match.py"):
        files[dep] = HERE / dep
    if note:
        files["note"] = note.resolve()
    return files


def write_manifest(out: Path, roots, note: Path | None) -> dict:
    files = manifest_files(roots, note)
    data = {"files": {k: {"path": str(p), "sha256": sha256_file(p)} for k, p in files.items()},
            "versions": versions(), "settings": {
                "grid": GRID, "T0": T0, "phase_fraction_min": PHASE_FRACTION_MIN, "min_points": MIN_POINTS,
                "mae_gain_min": MAE_GAIN_MIN, "decision_rule": DECISION_RULE,
                "element_phases": ELEMENT_PHASES, "compounds": COMPOUNDS}}
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def verify_manifest(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    bad = []
    for key, f in data["files"].items():
        p = Path(f["path"])
        if not p.exists():
            bad.append(f"{key}: missing ({p})")
        elif sha256_file(p) != f["sha256"]:
            bad.append(f"{key}: changed since the freeze ({p})")
    return bad


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def markdown_report(res: dict) -> str:
    p = res["primary"]
    lines = ["# SISSO temperature calibration — results", "",
             f"Decision rule {p['rule']}: correction **{'adopted' if p['correction_adopted'] else 'not adopted'}**.",
             f"- Condition 1: {p['condition_1']['text']} → {'pass' if p['condition_1']['pass'] else 'fail'}",
             f"- Condition 2: {p['condition_2']['text']} → {'pass' if p['condition_2']['pass'] else 'fail'}",
             f"- alpha = {p['alpha_J_mol_atom_K']:+.2f} J/mol-atom/K (scatter SD {p['slope_scatter_sd']:.2f}, "
             f"n = {p['n_compounds']})", "",
             "| Compound | Points | Slope (J/mol-atom/K) | MAE before (kJ) | MAE after (kJ) |",
             "|---|---:|---:|---:|---:|"]
    for c, s in p["slopes_J_mol_atom_K"].items():
        n = len(res["residuals_kJ"][c])
        lines.append(f"| {c} | {n} | {s:+.2f} | {p['mae_before_kJ'][c]:.3f} | {p['mae_after_kJ'][c]:.3f} |")
    if res["excluded"]:
        lines += ["", "Excluded: " + "; ".join(f"{k} ({v})" for k, v in res["excluded"].items())]
    lines += ["", "Residuals (kJ/mol-atom):", "",
              "| Compound | " + " | ".join(f"{int(T)} K" for T in GRID) + " |",
              "|---|" + "|".join(["---:"] * len(GRID)) + "|"]
    for c, pts in res["residuals_kJ"].items():
        lines.append(f"| {c} | " + " | ".join(
            f"{pts[str(T)]:+.2f}" if str(T) in pts else "—" for T in GRID) + " |")
    lines += ["", "Secondary analyses (do not change the decision) are in the JSON file."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-calphad", action="store_true")
    mode.add_argument("--run", action="store_true")
    ap.add_argument("--manifest", type=Path, help="write (without --run) or verify (with --run)")
    ap.add_argument("--note", type=Path, help="pre-registration note (hashed)")
    ap.add_argument("--note-sha256", help="expected SHA-256 of --note (required with --run)")
    ap.add_argument("--roots", type=Path, nargs="+", default=[REPO_ROOT], help="where to look for TDB files")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "stage_five" / "results" / "sisso_t_calibration")
    args = ap.parse_args(argv)

    if args.manifest and not args.run:
        data = write_manifest(args.manifest, args.roots, args.note)
        print(f"Manifest written: {args.manifest} ({len(data['files'])} files)")
        if args.note:
            print(f"Note SHA-256: {data['files']['note']['sha256']}")
        if not args.check_calphad:
            return 0

    if args.check_calphad:
        res = check_calphad(args.roots)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        path = args.out.with_name(args.out.name + "_calphad_check.json")
        path.write_text(json.dumps(res, indent=2))
        for name, c in res["compounds"].items():
            kept = [int(r["T"]) for r in c["rows"] if r["retained"]]
            print(f"{name:7s} {Path(c['tdb_path']).name:22s} retained {c['n_retained']}/8 {kept}"
                  + ("  -> DROPPED" if c["dropped"] else ""))
        print(f"Details: {path}")
        return 0

    # --run
    if not (args.note and args.note_sha256 and args.manifest):
        ap.error("--run needs --note, --note-sha256 and --manifest")
    if sha256_file(args.note) != args.note_sha256.lower():
        print("Refusing to run: the note does not match --note-sha256.")
        return 2
    bad = verify_manifest(args.manifest)
    if bad:
        print("Refusing to run: files changed since the freeze:\n  " + "\n  ".join(bad))
        return 2
    res = run_study(args.roots)
    res["note_sha256"] = args.note_sha256.lower()
    res["manifest"] = str(args.manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(res, indent=2, default=float))
    args.out.with_suffix(".md").write_text(markdown_report(res))
    print(markdown_report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
