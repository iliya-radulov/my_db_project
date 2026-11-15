# Work log — Stage 4, Track C: CALPHAD audit of La–Fe–Si

*(started 14 November 2026)*

## 0. Status at a glance

| Item | State |
|---|---|
| Plan | reproduce the published La–Fe–Si assessment → audit it against Niitsu & Kainuma (2012) and our own data → use it for hypothesis tests → extend (ORCHID-SAGE style) |
| 2023 assessment paper (Feng et al., Calphad 83 (2023) 102643) | **received and fully transcribed** — all parameters, EPMA data and comparison captured (section 7) |
| TDB reconstruction (τ1/τ2 subset) | **built and validated** — acceptance test passed, WP4 descriptor computed (section 9) |
| Full merged build (real binaries) | **done** — 20-combination WP4 band; faithful combo matches self-contained to <0.2 J/mol (section 10) |
| Niitsu & Kainuma (2012) experimental data | transcribed, validated, ESPEI datasets generated (sections 2–3) |
| Computational leg | proven end-to-end: Setty et al. Mo–Si–Y–Hf TDB (Zenodo 20848011) downloaded and an isothermal section computed with pycalphad 0.11.2 (the Track A pin) in this environment |
| ESPEI | does not install on Python 3.13 (pins `emcee<3`, which no longer builds); fallback options in section 5 |
| Network | cloud environment `alloy-lab` created 14 Nov (zenodo.org, orchid-project.org allowed) |

## 1. Context

Fourth workflow of the project (Track A: Nd–Fe–B assessment ensemble in
`stage_three/stage4_step1/`; Track B: magnetocaloric literature layer in
`stage_four/mce_nims/`). Idea (I. Radulov, 14 Nov): do for La–Fe–Si what
Setty et al. did for Mo–Si–Y–Hf — a thermodynamic database built and
tested openly — as a small, concrete pilot of the ORCHID consortium's
"evidence → assessment → phase diagram" funnel (ORCHID-SAGE, Zenodo
24045969; orchid-calphad GitHub organization).

Key change of plan found on day 1: a published assessment already exists
("Thermodynamic assessment of La–Fe–Si systems", CALPHAD, ~2023,
built largely on Niitsu & Kainuma 2012). So the pilot starts as a
**reproduction + audit** (the MANIFESTO's subject), not a from-scratch
fit. The 2012 paper supplies the independent measuring stick either way.

## 2. Transcription of Niitsu & Kainuma (2012)

Method: numbers taken from the PDF's embedded text layer (pdfplumber),
not from page images; ambiguous glyphs resolved on 230–260 dpi crops.
Greek letters are mangled in the text layer — mapping established and
spot-checked against the crops: τ→"s", ε→"3", η→"h", β→"b", ζβ→"zb",
ζα→"zs"(subscript), α→"a", —→"e"/"d".

Transcribed: Tables 2–4 (tie-lines at 1173/1373/1573 K), Table 7
(τ₁/τ₂ pairs at 1273–1523 K), Table 8 (17 DSC reaction temperatures),
Table 6 (lattice parameters), plus the running-text facts
(`text_facts.csv`). 71 equilibria, 177 measured phase compositions.

Validation (all in `niitsu2012.py`, exit non-zero on failure):
1. row counts per table = paper (29/29/9/4; DSC 17) — **pass**
2. composition sanity (0–100, La+Si ≤ 100) — **pass**
3. τ₁/τ₂ La content = 7.14 ± 0.6 at.% (1/14 of 1:13 sites) — **pass**
4. DSC x ↔ Si(at.%) redundancy: Si = 13x/14 within 0.15 — **pass**
   (this also settled x = 0.224, which the text layer garbled)
5. τ₁/τ₂ composition ranges spanned by the tie-lines ⊆ the ranges stated
   in the paper's text (±0.02) — **pass** (e.g. 1373 K τ₁: endpoints give
   x = 0.096–0.229, text states 0.096–0.229)
6. mass balance (nominal inside the measured simplex, 2 at.% tolerance)
   — 12 rows flagged, kept as printed (section 3)
7. visual: `plot_tielines.py` reproduces the topology of the paper's
   Fig. 3(a)–(c) (checked side by side on 14 Nov)

## 3. Rows flagged by the mass-balance check

Interpretation, not correction — the CSV stays as printed:

- **T3 33.3/33.3 (10.5 at.% off) and T3 33.3/53.3 (11.2 at.% off): the two
  rows' results are almost certainly swapped in the paper.** Swapping them
  puts both nominals inside the other row's phase triangle (0.3 and
  ~1 at.%), and the swapped assignment matches the 1173 K result for the
  same 33.3/33.3 alloy (LaFeSi + LaFe₂Si₂ + La₅Si₄). Not corrected in the
  CSV; the ESPEI dataset comment carries the flag. Worth an email to the
  authors at some point.
- **T4 10.0/50.0 (12.6 at.% off):** τ₂ + LaFe₂Si₂ + Liq at 1573 K, but all
  three measured compositions are Si-poorer than the alloy. The liquid
  (quenched, 20 µm beam) is the likely culprit. Treat with care in any fit.
- The remaining ten (2.1–6.5 at.%, mostly ε/LaSi₂₋ₐ₂ two-phase rows and
  very short anneals): consistent with the paper's own caveats — nominal
  vs. actual composition differs because the La-oxidized outer region is
  excluded, and 0.13–3 day anneals may not be fully equilibrated. Normal
  experimental scatter for this system, valuable to know for weighting.

The check is exactly the kind of audit this track exists for: it found a
probable table swap in a well-cited experimental paper on day 1.

## 4. Decisions

| Date | Decision | Reason |
|---|---|---|
| 14 Nov | Track C starts as reproduction + audit of the 2023 assessment, not a from-scratch ESPEI fit | the assessment exists; auditing it is cheaper and is the project's actual research question |
| 14 Nov | Transcribe as printed; flag, never fix | provenance discipline (Track B rule); the flags are themselves results |
| 14 Nov | Phase labels: paper's labels canonicalized to ASCII; TDB/ESPEI names are placeholders in `phase_registry.csv` | the 2023 paper's phase models and names are not known yet; one mapping file to update |
| 14 Nov | CSVs committed (local `.gitignore` override of the repo-wide `*.csv` rule) | they are our transcription (source data of this stage), not redistributed third-party files |
| 14 Nov | ESPEI ZPF datasets generated now, even though the fit comes later | same datasets serve the audit (overlay + residuals) and any later re-optimization |
| 14 Nov | New cloud environment `alloy-lab` (zenodo.org, orchid-project.org) instead of widening the Default | the Zenodo records are material for this project only |

## 7. The 2023 assessment: Feng et al. (received)

The paper is **E. Feng, K. Huang, J. Wang et al., "Thermodynamic
assessment of La–Fe–Si systems", Calphad 83 (2023) 102643**
(doi:10.1016/j.calphad.2023.102643). It is a complete, self-contained
CALPHAD assessment of the 1373 K isothermal section — **all parameters
are in the paper (Table 5); no supplementary TDB is needed.** It builds on
the binaries La–Si (Zhou 2010), Fe–Si (Cui 2017), La–Fe (Su 2022) and
optimises the ternary τ phases plus a few binary-into-ternary solubility
terms, with Thermo-Calc's PARROT.

Captured in `data_feng2023/` (all transcribed from the PDF, as printed):
- `table5_parameters.md` — **every parameter**: Liquid, FCC_A1, BCC_A2,
  the Fe–Si B2/D03 ordering, the Fe–Si line compounds, the six
  La–Si(Fe) compounds, and the six ternary τ1–τ6 compounds with their
  sublattice models. Cross-checked against the page images (the PDF text
  layer scrambles subscripts and rotates page 9).
- `table4_epma.csv` — 21 alloys, 46 EPMA phase compositions, 1373 K /
  30 days. Validated: all sum to 100 at.% (one printed as 99.0, kept as
  printed — alloy 20 D03).
- `table6_comparison.csv` — Feng's own experiment-vs-calculation table.

**First result, from Feng's own Table 6: their assessment reproduces
their own experiment fully for only 11 of 21 alloys** (10 partial
mismatches at 1373 K — e.g. alloys 9, 11, 12 predict a different phase
count in the Fe-rich corner). So the published assessment is itself
imperfect in exactly the Fe-rich region the magnetocaloric τ1 phase lives
in. That is the audit's starting point, not a flaw we introduced.

### Phase-naming caveat (important)
Feng's τ1–τ6 are **not** Niitsu's τ1/τ2. Only τ1 and τ2 — the two
La(Fe,Si)13 structures (cubic NaZn13 and tetragonal Ce2Ni17Si9) — map
across directly. Feng's τ3–τ6 are the Si-rich/La-rich ternary compounds
that Niitsu names LaFe2Si2, LaFeSi2, LaFeSi, La3Fe2Si8. The map is in
`table5_parameters.md`; the audit overlay must use it, or τ-labels will
be compared wrongly.

## 8. TDB build plan (next session)

Building a working `.tdb` from Table 5 needs three things, in rising
difficulty:
1. **SGTE unary functions** (La, Fe, Si; Dinsdale 1991). Fe is in the
   repo's Nd–Fe–B TDBs (`stage_three/FENDB_merged_v4.tdb`, `GHSERFE`);
   Si and La must be added. Transcribe from SGTE, or source an unary TDB
   (check `orchid-data` on Zenodo first).
2. **The disordered + compound phases** — Liquid, FCC_A1, BCC_A2, the
   Fe–Si line compounds, the six La–Si(Fe) compounds, and τ1/τ2
   ((La)(Fe,Si) 1:13). These are straightforward PARAMETER statements.
   This subset already computes the **magnetocaloric-relevant** τ1
   single-phase window and the τ1/τ2/αFe equilibria — enough to overlay
   Niitsu's low-Si tie-lines and answer the annealing-window question.
3. **The hard parts** — the Fe–Si BCC_B2/D03 ordering (4-sublattice,
   Cui 2017) and the τ3–τ6 three-sublattice (La)(Si,Fe)(Si,Fe) model
   (Feng's eq. 8 with neutralisation variables). These matter for the
   full Si-rich section but are error-prone; build and validate them
   separately, against Feng's Fig. 5 topology and Table 4.

**Validation gate before any science:** the built TDB must reproduce
Feng's own Table 4 phase assemblages and Fig. 5 topology at 1373 K. Only
then overlay the Niitsu tie-lines and compute residuals. A subtly wrong
TDB is worse than none — do not shortcut this gate.

## 9. TDB reconstruction and WP4 descriptor (15 Nov)

Built `tdb_build/LaFeSi_feng2023.tdb` from Feng Table 5 + SGTE unaries
(Dinsdale 1991, verified identical across pycalphad-bundled sources). This
is the faithful reconstruction: the binary backbone is Feng's own Table 5,
so the ternary τ parameters sit on exactly the binaries they were fitted on
(Zhou/Cui/Su) — no hybrid. Pilot discipline followed: `FROZEN_SPEC.md`
(composition La(Fe11.5Si1.5) and the A1–A5 acceptance test) written before
any parameter was typed; every PARAMETER block carries a provenance comment.

**Acceptance test passed** (`tdb_build/RESULTS.md`): parses & computes (A1);
unaries SGTE-consistent numerically (A2); τ1 single-phase at the frozen 1:13
point (A3); τ1 correct in all 5 Feng Table-4 τ1 alloys with αFe where
reported (A4); τ1/τ2 window x≈0.10–0.23 / ≥0.27 matches the literature
0.096–0.229 / 0.266+ (A5).

**WP4 descriptor:** ΔG_f(τ1) at La(Fe11.5Si1.5) = **−20.99 kJ/mol-atom at
1373 K** (−20.6 at 1173 → −21.2 at 1473; ≈ −1.9 J/mol-atom·K). The Track B
physics descriptor is in hand.

Deferred (do not affect the Fe-rich τ1 descriptor): τ3–τ6 three-sublattice
compounds (need the site ratios from Feng's eq. 8, which the PDF text layer
garbled) and the Fe–Si B2/D03 ordering (Table 5 gives only its ΔG anchors).

Lessons carried / added:
- `calculate()` on a coarse internal grid missed τ1's ideal site occupancy
  and gave a wrong-sign ΔG_f (+23 kJ); the equilibrium GM is the right
  source (−21 kJ). Verify descriptors from equilibrium, not raw grids.
- The two Track A unary lessons held: numeric (not text) unary comparison
  (A2), and a 3rd-gen screen (no Einstein terms; all sources 2nd-gen).

### Next TDB layers
1. τ3–τ6 site ratios — re-read Feng eq. 8 from the PDF (page 5) carefully.
2. Fe–Si B2/D03 ordering from Cui 2017 (for the full Si-rich section).
3. WP4 uncertainty band — swap Feng's binaries for the Track A collection
   (needs the external `data/tdb/sgte_binary/` files; build script already
   accepts an external backbone).

## 10. Full merged build on the real binaries + WP4 band (15 Nov)

Binary collection obtained (`iliya-radulov/projects_documentation`,
`AlloyDB/Data/tdb/sgte_binary/`). Feng's exact cited binaries are all there:
**FeLa-23Su** (Su), **LaSi-10Zho** (Zhou), **FeSi-17Cui** (Cui) — so a
faithful merged build on real files is possible, plus the WP4 band over the
full 2 FeLa x 2 LaSi x 5 FeSi = 20 combinations.

`build_merged_tdb.py` merges three binary TDBs at the pycalphad
Database-object level (union constituents for shared solution phases; keep
binary compounds; drop Cui's 4SL ordering, as Feng did) and injects Feng's
τ1/τ2 + ternary liquid term. `wp4_band.py` runs the 20 combinations.
Pre-merge: all 9 binaries pass standalone-compute and the 3rd-gen screen;
unaries numerically identical across files.

**Faithfulness proof (the Lindahl criterion):** the faithful combo
reproduces the self-contained Feng-Table-5 build to **< 0.2 J/mol-atom**
(ΔG_f(τ1) −20992.6 vs −20992.7 at 1373 K; window identical). The merge of
the binaries reproduces the assessment because the binaries match — the
reconstruction is faithful, confirmed two ways.

**WP4 result (`RESULTS_MERGED.md`):**
- ΔG_f(τ1) vs elements is **binary-independent** (−20.99 kJ/mol-atom, band
  = 0): τ1's energy is Feng's fixed parameters, the binaries never enter it.
- The binary-sensitive descriptor is the **τ1 formation driving force**
  (G_compete − G_τ1): **+84.7 kJ/mol-atom for 16/20**, **+82.6 for the 4
  using FeSi-23Wit**. Band 2064 J/mol-atom (~2.5 %).
- τ1 single-phase at the frozen point in **all 20** combinations (robust
  window). The spread is **entirely Fe–Si-driven** — La–Fe and La–Si
  choices make zero difference at this Fe-rich composition — and
  **FeSi-23Wit (Witusiewicz) is the single outlier**, exactly as flagged
  (it stabilises Fe₂Si as a competitor).

Merged `.tdb` files are gitignored (derived from third-party binaries,
regenerable via the scripts).

## 11. tau3-tau6: not reconstructable from the paper (15 Nov)

Attempted to add Feng's tau3-tau6 (the Si-rich/La-rich ternary compounds).
**Finding: they cannot be faithfully reconstructed from Feng (2023).**
Table 5 omits the GHSER reference terms (tau1/tau2 print them, tau3-tau6 do
not) and the sublattice site ratios. Three reconstructions, each tested
against Feng's own Table 4 (eq. 8 model (La)x(Si,Fe)y(Si,Fe)z, site ratios
inferred from the Table-4 EPMA compositions): as-printed = never stable;
printed + site-weighted GHSER = too weak, never stable (tau1/tau2
preserved); site-count-scaled + GHSER = tau4 takes over the whole diagram.
None reproduces Feng's phase stabilities. Details and the recommendation
(request the authors' TDB) in `tdb_build/TAU36_RECONSTRUCTION.md`.

The production TDB keeps tau1/tau2 only (validated). `tau36_block.py` ships
the physically-sensible non-destructive hypothesis, flagged non-validated,
for correction once the authors' file is obtained. **No impact on the WP4
descriptor** (Fe-rich tau1 corner).

A reusable methodology write-up was committed to the projects_documentation
repo (`AlloyDB/Stage4/LaFeSi_CALPHAD_reconstruction_procedure.md`),
including the forward-looking "no ternary reference" route (merge binaries +
fit the ternary to experimental tie-lines with ESPEI).

Test-harness lesson added: a composition slip (passing the Fe at.% where Si
was meant) evaluates a different alloy and produces "impossible" assemblages
that look like a solver failure. Always echo the composition actually passed.

## 5. Next steps

1. **When the 2023 PDF arrives:** transcribe its parameter tables to a TDB
   (or take the supplementary TDB if one exists); recompute its diagrams;
   overlay these tie-lines; per-tie-line residuals; hold out what it did
   not fit (e.g. our Track B T_C layer, EDX samples).
2. Binary sub-systems: locate machine-readable TDBs for Fe–Si, La–Si,
   La–Fe matching the 2023 paper's choices (check `orchid-data` and the
   Track A SGTE collection first).
3. ESPEI runtime, when fitting starts: Python 3.11 venv (uv) or replace
   the MCMC step with a transparent scipy least-squares on pycalphad
   residuals (MANIFESTO-friendlier); decide then.
4. Possible DB layer later: a `phase_equilibria` literature table in
   `alloy_lab` (same provenance pattern as `mce_literature_records`) if
   more experimental papers get transcribed.
5. Side note for the paper: the suspected Table 3 row swap (section 3).

## 6. Reproducing everything

```bash
cd stage_four/calphad_lafesi
python niitsu2012.py              # validators; exit 0 = all pass
python niitsu2012.py --espei      # writes espei_datasets/*.json
python plot_tielines.py           # writes results/tielines_{1173,1373,1573}K.png
# compare the three PNGs with Fig. 3(a)-(c) of the paper
```
