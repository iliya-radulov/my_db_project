# Audit rule v2 for the TDB collection (18 Nov 2026)

Closes the Layer 2 carry-over "audit rule v2" (Layer 2 wrap-up §5; Al–Fe–Mn record §8.4; Audit Addendum §2.3). Script: `audit_inventory_v2.py` (standard library only, deterministic, 2 s for the whole collection). Run: `python audit_inventory_v2.py --tdb-dir tdb/sgte_binary --out audit_v2`. The rule v1 script itself was not in the session, so v2 is a new standalone script, not an edit; it does not read the inventory CSV.

## What v2 does (all read from the TDB text)
1. **target_kind** per system: `ternary-only` (absent from the binaries by design) or `binary-borne` (target phase name must be defined by `PHASE` lines on the edges). Replaces the CSV `ternary_phases` column.
2. **Unary incompatibility**: (a) `FUNCTION GHSER<EL>` and (b) every pure-element G parameter, normalised numerically (number-format-insensitive), compared (i) with the most common definition in the collection (informational) and (ii) **within each system**: the same (phase, element) end-member defined with different expressions by files of that system is listed in `unary_conflicts_by_system.csv`.
3. **Interstitial site-ratio defect** of ordered phases (BCC_4SL/FCC_4SL/B2_BCC/L12_FCC) against their `DIS_PART` (the check pycalphad enforces).
4. **Order–disorder descriptions** per file (bcc: BCC_4SL/B2_BCC/BCC_B2; fcc: FCC_4SL/L12_FCC); `multi_order` if two or more of the same lattice.
Outputs: `files.csv` (one row per file), `systems.csv`, `unary_deviations.csv`, `unary_conflicts_by_system.csv`, `summary.txt`.

## Validation against known results (2773 files parsed, 0 parse failures)
- File and combination counts per system equal rule v1 and the pilots: Nd–Fe–B 84, Al–Fe–Mn 792 raw, Cr–Fe–Ni 588, La–Fe–Si 20, Ni–Mn–Sn 154 (7 × 11 × 2).
- **Binary-borne target by direct parsing** reproduces the 12 Nov addendum: Al–Fe–Mn γ-brass defined in AlFe 7 files (4 usable + 3 excluded by model) and AlMn 9, **FeMn 0**; Cr–Fe–Ni σ in CrFe 7 of 7, CrNi 2 of 7, FeNi 0.
- **Interstitial-ratio defect** flags exactly AlMn-12Dju, AlMn-18Zhe, AlMn-18Zhe-mod (the three files that failed 0/9 in pycalphad on 14 Nov), plus two new files: **FeSi-12Ohn and FeSi-17Cui** (BCC_4SL ratio 1 vs A2_BCC ratio 3). A first version also flagged sigma phases (CoCr-16Li, CrRe-10Pal) and was corrected to the order–disorder families only.
- **Within-system unary conflicts** for Ni–Mn–Sn list `G(FCC_A1,SN:VA)` with variants 8/5 (the five files with the 91Din value: MnSn-01Mie, MnSn-04Liu, NiSn-03Mie, NiSn-05Liu, NiSn-99Gho) — i.e. the conflict behind 112 of the 130 edge-check failures would have been visible before the run.

## Limits (state in the README)
- A flag is a hint for file selection, not evidence: a conflicting unary can be irrelevant. Nd–Fe–B shows a conflict in G(FCC_A1,B:VA) (3 of 7 Fe–B files) and still survives at 93 %, because fcc B does not compete. Relevance needs the merge/edge check.
- `ghser_deviates` against the collection mode also flags old second-generation files, so it is not a third-generation test by itself; the third-generation list stays name-based (`-3g`) plus the numerical flags.
- Text parsing handles the TDB command syntax of this collection (comments `$`, commands ending `!`); an exotic syntax would be missed, not mis-parsed silently: parse failures are reported.
- Not yet checked: whether FeSi-17Cui (used in the La–Fe–Si reconstruction, WP4b) is affected in practice; pycalphad refuses the file only when BCC_4SL is active. To be looked at if La–Fe–Si is revisited.
- Rule v2 is fixed here before further use; changes after seeing results are sensitivity results.
