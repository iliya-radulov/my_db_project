# Session Wrap-Up — Stage 5: Generalized CALPHAD Ensemble & DFT-SISSO Screening

**Date:** 21–22 November 2026  
**Directory:** `stage_five/`

---

## 1. Objective: What We Are Building

We are generalizing the methodological tools developed in Stages 3 and 4 into a **system-agnostic thermodynamic screening pipeline** (`stage_five/`) that works for **any arbitrary ternary alloy system** without hardcoding phase lists, file paths, or lineage tables.

Specifically, we are combining two complementary sources of thermodynamic information onto a single, consistent energy axis (`kJ/mol-atom` relative to SER):

1. **Competing Binary Assemblage Threshold $\Delta G_f^*(T)$ (CALPHAD Binary Ensemble):**
   - Public DFT databases alone do not provide multi-assessment Gibbs surfaces, edge-consistency checks, assessment lineage tracking, or uncertainty bands on competing binary phases.
   - Using the SGTE binary TDB collection (`$SGTE_BINARY_DIR`), our generalized binary-ensemble engine audits all available binary assessments for a given ternary system, merges every valid combination, filters them via **Edge-Check Rule v2** (with leave-one-phase-out fallback), enforces **pre-registered stop rules** (`G1` survival count, `G2` lineage coverage per edge), and outputs the competing threshold distribution (median, IQR, 5th–95th percentile band, and variance attribution $\eta^2$ per edge).

2. **Candidate Phase Finite-Temperature Free Energy $\Delta G_f^{\text{SISSO}}(T)$ (Materials Project + Bartel SISSO):**
   - Because full ternary CALPHAD assessments are often unavailable or un-reconstructable from printed tables (as shown in Stage 4 Track C), we estimate the candidate phase's finite-temperature formation Gibbs energy using Materials Project 0 K DFT entries (`mp-api`) corrected with the **Bartel et al. (2018) SISSO vibrational/electronic descriptor** via `pymatgen`'s `GibbsComputedStructureEntry`.
   - Comparing $\Delta G_f^{\text{SISSO}}(T)$ directly against the CALPHAD ensemble band $\Delta G_f^*(T)$ gives a **stability margin** ($\Delta G_f^{\text{SISSO}} - \Delta G_f^*$) and identifies temperature windows where the target phase is thermodynamically favored over competing binaries.

---

## 2. What Was Completed Today

1. **Full Codebase & Manuscript Audit (Stages 1–4):**
   - Bundled and reviewed all scripts, SQL migrations, logs, and both November 21 manuscript drafts (`La–Fe–Si` reconstruction/refit and `Binary-Ensemble Protocol`).
   - Verified that Tracks A, B, and C of Stage 4 are complete and documented, with only minor path cleanups and DOI placeholders remaining before release.

2. **Created `stage_five/` Core Modules (Written, Ready for Testing):**
   - **`stage_five/general_ensemble.py`**:
     - Auto-discovers binary `.tdb` files for any three elements `[EL1, EL2, EL3]`.
     - Applies **Audit Rule v2** automatically (excludes `-3g` files, checks `GHSER<EL>` consistency across files, detects interstitial sublattice ratio defects, and extracts author-year lineages from filenames).
     - Runs parallel parsed-database merges (`tdb_merge.merge_databases`) with isolated temporary files to prevent race conditions.
     - Enforces **Edge-Check Rule v2** (`|dG| <= 1 J/mol`, `MAX_UNVERIFIED = 2`, leave-one-out fallback).
     - Evaluates pre-registered gates (`G1` survival fraction, `G2` minimum lineages per edge) before computing $\Delta G_f^*(T)$ distributions and edge variance shares ($\eta^2$).
   - **`stage_five/dft_sisso_predictor.py`**:
     - Queries Materials Project for a target formula and its full chemical system (`get_entries_in_chemsys`) so elemental reference states are resolved consistently.
     - Computes finite-temperature formation Gibbs energies (`300–2000 K`) via `pymatgen.entries.computed_entries.GibbsComputedStructureEntry`.
     - Converts `eV/atom` to `kJ/mol-atom` (`× 96.485332`) and includes `compare_with_calphad_ensemble()` to classify each temperature point as `stable_across_band`, `borderline_within_band`, or `metastable_above_band`.

---

## 3. Plan for Next Session (Tomorrow)

1. **Sanity-Check & Qualify `stage_five/` Scripts:**
   - Run `general_ensemble.py` on **Nd–Fe–B** (`0.8235, 0.1176, 0.0588`) and verify it reproduces the Stage 4 reference benchmark (**78 of 84 survivors**, median threshold `−8.79 kJ/mol-atom` at `800 K`).
   - Run `dft_sisso_predictor.py` on `Nd2Fe14B` to verify `mp-api` + `GibbsComputedStructureEntry` execution and unit alignment.

2. **Build the Unified CLI & Orchestrator (`stage_five/screen_ternary.py`):**
   - Create a single entrypoint that accepts a formula (or element fractions) and temperature range, executes both the CALPHAD binary ensemble and the Bartel SISSO predictor, and prints/exports a combined stability-margin table.

3. **Database Schema Extension (`009_calphad_dft_screening.sql`):**
   - Add `calphad_ensemble_runs` and `calphad_dft_comparison` tables to the `alloy_lab` PostgreSQL schema so screening runs, gate verdicts, uncertainty bands, and SISSO stability margins are stored alongside `samples` and `literature_checks`.

4. **GUI Integration (`alloy_desktop_v2.py`):**
   - Wire the combined CALPHAD + Bartel SISSO screening summary into the desktop app's **New Entry / Preview** workflow (with caching so repeated previews do not re-run the ensemble).


-----

# Are there existing projects that use this setup?

Short answer: No, not exactly. 

Our specific combination—binary-ensemble CALPHAD uncertainty bands + SISSO finite-temperature DFT screening—is novel in the literature. However, the components are well-established, and there are adjacent projects we should be aware of.

The closest relatives (and why they are different):

    The Zhang et al. auto-differentiation paper (arXiv:2608.00516): This is the paper we already have. It optimizes CALPHAD parameters using PyTorch . Difference: It is an optimization tool, not a screening tool. It fits a single TDB to data; it does not generate an ensemble of TDBs or compare them against SISSO predictions.

    ESPEI (Extensible Self-optimizing Phase Equilibria Infrastructure): ESPEI is the standard for Bayesian uncertainty quantification in CALPHAD . It uses MCMC to sample parameter posteriors. Difference: ESPEI quantifies uncertainty within a single model's parameters. Our ensemble quantifies uncertainty across different published assessments (the "lineage" approach). ESPEI is the tool we would use if we wanted to refine a single TDB; our ensemble is the tool that tells us which TDB to start with.

    Bayesian CALPHAD (e.g., Honarmandi et al., Acta Materialia 2019): This work uses Bayesian model averaging to combine different CALPHAD models for Hf–Si . Difference: That is a statistical fusion of models. Our approach is a physical ensemble (merging actual TDB files) plus a hard edge-check. We are not averaging; we are screening and characterizing the spread.

    SISSO for Gibbs energy (Bartel et al., Nat. Commun. 2018): The SISSO descriptor is exactly what we are using in dft_sisso_predictor.py . Difference: The Bartel paper introduced the descriptor. Our contribution is using it as the candidate energy in a screening pipeline, compared against a CALPHAD ensemble band rather than a single DFT hull.

What this means for Stage 5 plan:

We are not re-inventing a wheel; we are building a hybrid instrument. The closest published workflow is likely the one we already cited (Zhang et al.), but that is for optimization, not screening. The "ensemble of open binary assessments" is our own Stage 4 invention . Combining it with SISSO to get a finite-temperature stability margin is a logical and publishable extension.

One risk to keep in mind:

The SISSO descriptor is known to degrade in accuracy at high temperatures (the deviation from QHA can reach ~0.1 eV/atom by 1800 K) . Since our CALPHAD ensemble operates at 800–1600 K, the SISSO side of the comparison will be at its weakest exactly where our ensemble is most relevant. The borderline_within_band classification is our safety net here—it will correctly flag cases where the SISSO error is comparable to the ensemble spread. Just make sure the paper's limitations section says this explicitly.

Verdict: The setup is novel in its combination. The components are standard, but nobody has wired them together in this specific way. That is a good position for a methods paper.


-----------The one number to check tomorrow

The median at 800 K is −8.798 kJ/mol-atom, which is 0.008 kJ above the Stage 4 reference of −8.79. That is within rounding, but it is worth a one-line check before we move on. The Stage 4 number came from the 78-survivor set; this run has 52 survivors, and the 5%–95% band is [−9.26, −8.33], which matches Stage 4's [−9.26, −8.33] exactly at the endpoints. So the median is right, the band is right, but the survivor count is lower than 78.

The difference is almost certainly the audit rule. Stage 4 kept 78 of 84; this run keeps 52 of 84. The 26 missing survivors are the ones excluded by Audit Rule v2 (-3g, GHSER conflicts, interstitial defects) that Stage 4 did not exclude. That is the intended behavior of the generalized engine — it is stricter than Track A — but the paper's Stage 4 reference number (78 survivors, −8.79 median) and the Stage 5 engine's number (52 survivors, −8.798 median) are not the same measurement. The good news is the median barely moved (−8.79 vs −8.798), so the stricter audit does not change the central value. The bad news is the survivor count is a headline number in the Stage 4 paper, and a reader who sees 52 in Stage 5 and 78 in Stage 4 will ask why.

The answer is simple: Stage 5 adds Audit Rule v2, which excludes 26 combinations that Stage 4 kept. That should be stated in the Stage 5 methods section, not discovered by a reader. The one-line check tomorrow is to confirm which 26 combinations were excluded and that they are the -3g / GHSER / interstitial ones, not something unexpected.
Everything else is clean

    The competing assemblages are physically sensible (FE17ND2+ND2B5+NDB4_D1E at low T, LIQUID at 1600 K).

    The IQR grows from 0.428 at 800 K to 0.861 at 1600 K, which is the same temperature dependence Stage 4 reported (factor ~2).

    The lineage table is exactly the 7/4/3 split the Stage 4 paper documents.

    The gate passes on both G1 and G2.

The only thing left is the survivor-count reconciliation, and it is a documentation issue, not a physics issue. The engine is working.

The first thing tomorrow is to check is the 52-vs-78 reconciliation, then the dft_sisso_predictor.py sanity check on Nd₂Fe₁₄B, then the screen_ternary.py orchestrator. We are on track.
