# Work log — Stage 4, Track C: CALPHAD audit of La–Fe–Si

*(started 14 November 2026)*

## 0. Status at a glance

| Item | State |
|---|---|
| Plan | reproduce the published La–Fe–Si assessment → audit it against Niitsu & Kainuma (2012) and our own data → use it for hypothesis tests → extend (ORCHID-SAGE style) |
| 2023 assessment paper (CALPHAD journal, S0364591623001153) | **waiting for the PDF** (I. Radulov, via institution) |
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
