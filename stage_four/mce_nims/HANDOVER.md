# Hand-over: La(Fe,Si)₁₃ magnetocaloric workflow (state 3 Nov 2026)

Paste this into a new chat to continue the discussion. Details,
numbers and reasons are in `WORKLOG.md` (same folder); the governing plan
is the colleagues' `my_alloy_db_General_Road_Map_v2.md` (Plans C/D
complementary, A/B outdated).

## What the project is

Lab database (PostgreSQL, schema `alloy_lab`, on my own server) for alloy
work. Stages 1–2 (composition calculator, screening, literature checks)
are reviewed and merged. Stage 4 here is the **magnetocaloric
La(Fe,Si)₁₃ workflow**, kept separate from the Nd–Fe–B / CALPHAD work.
Idea (colleagues): train on heterogeneous literature data (NIMS), use
consistently measured series for testing and correction only.

## Data

| Source | Use | Licence | Records (La(Fe,Si/Al)₁₃) |
|---|---|---|---|
| NIMS La(Fe,Si)₁₃ dataset | training | CC BY 4.0 | 1,113 records, 1,539 points, 660 composition keys |
| GitHub MCE database (Yuan et al., AIP Adv. 2024) | checks, coverage | use with citation (B. Liao, email 2 Nov) | 202 (after the T_C plausibility filter) |
| Kelly & Cole 2025 Curie/Néel | checks, coverage | CC BY 4.0 | 100 |
| Court & Cole 2018 Curie/Néel | checks, coverage | CC BY 4.0 | 80 |
| Ni and Cr series (Moreno-Ramírez 2018, 2019) | held-out test, never trained on | own / co-authored | 12 points; EDX compositions committed |

Not used: Cole 2021 MCE set (no answer yet; skip unless she replies),
NEMAD (no per-row provenance; closed — maybe useful later for Nd–Fe–B).

## Database design (delivered as migrations + `SERVER_SETUP.md`)

- Literature in its own tables (`mce_literature_records`, `_points`),
  linked to own samples by a **composition key** (metals normalised to
  100 at.%, H/C/N/B as interstitials, 0.1 at.% resolution, e.g.
  `Fe81.4-La7.1-Si11.4+H3.6`).
- `quality_flag`: `experimental_literature` | `literature_mined` |
  `unverified` | `dft`. Duplicates rule: same source + id → update;
  same key from another source → keep both, report.
- Migrations 007 (literature tables) and 008 (checks/provenance on
  `literature_checks`).

## Main results

- Evaluation design matters most: a random split flatters (ΔS MAE 1.74
  vs 3.32 J/kg K with whole papers held out).
- Current model (rows without annealing data kept): T_tr, papers held
  out: gradient boosting 11.1 K, ridge 14.3 K; Ni+Cr test: ridge 7.5 K,
  GB 9.3 K. ΔS: GB 3.3 (papers), 3.2 J/kg K (test).
- Trees predict flat values along the Cr series; ridge follows the trend.
- Correction step on the consistent series: criterion met with the ridge
  base, not with GB; a straight line through the series' own points does
  as well; NIMS helps for the first 1–3 samples of a new series.
- EDX instead of nominal compositions in the test set: worse (training
  data are nominal) → nominal stays default.
- Adding the three text-mined sources to training: **no improvement**
  (pre-registered criterion not met for T_tr or ΔS) → train on NIMS only.
- Source agreement on T_C within 2 K: 64–79 % between pairs of sources.

## Open tasks

On the server (me):
1. Merge PR #8, then on the server run `SERVER_SETUP.md`: migrations
   007/008 and the four imports if not done yet; **re-run
   `import_mcedb.py`** (now 202 records, removes 7).

Science / next steps:
2. High-Mn series as an out-of-range test (data in the first stay report,
   not used yet).
3. A model that extrapolates along a substituent (linear term or
   physics-informed baseline), given the Cr result.
4. More consistently measured series (HZDR or own) for the correction step.
5. Hydrides: keep in training with H as a feature, or model separately?
6. Column labels in the extracted Origin tables (which Book = which x;
   unlabelled column on stay 2, slide 15).
7. Paper: the "lessons" table in `WORKLOG.md` §14 is the material for the
   data-quality / method section.

Waiting / postponed:
8. J. M. Cole's answer (Cole 2021 MCE set) — optional.
9. Origin-file extractor as a side project — postponed.
10. Nd–Fe–B workflow — separate, later (NEMAD API script kept for it).

Coding work → back to the Claude Code session on the repository
(`iliya-radulov/my_db_project`, folder `stage_four/mce_nims/`).
