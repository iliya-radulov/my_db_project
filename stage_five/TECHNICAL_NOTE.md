# Stage 5 screening tool: CALPHAD binary-ensemble threshold with an optional DFT + SISSO overlay

Technical note, contract version 1.0, 24 November 2026
Iliya A. Radulov, Claude (Anthropic)
Code: https://github.com/iliya-radulov/my_db_project (`stage_five/`), release tag `v5.0-stage5`.
Earlier release of the project: Stage 4 Track A, DOI 10.5281/zenodo.24039719.

## 1. Purpose

Stage 5 answers one screening question for a ternary composition: *is a candidate phase predicted to be more
stable than the best combination of the three binary systems at that composition?* The competing side comes from
an ensemble of open binary CALPHAD assessments, so it carries an assessment-scatter band, not a single number. The
candidate side comes from a Materials Project 0 K entry with a Bartel SISSO finite-temperature correction. This note
fixes what each number means, how the labels are assigned, how nearest prototypes are treated and what the tool does
not claim, so that results produced now stay interpretable when the tool is extended. The meaning of every stored
value is the contract in `stage_five/CONTRACT.md`; this note summarises it.

## 2. Pipeline

1. **Audit.** For the three binary edges of the ternary, every open assessment (TDB file) is checked: third-generation
   (`-3g`) files, files that do not parse, files whose unary GHSER functions conflict with the others, and files with an
   interstitial-site defect (site ratios of an ordered phase disagree with its disordered part) are excluded; every
   decision is written to the audit log of the report.
2. **Merge and edge check.** One file per edge makes a combination (e.g. 3 × 7 × 4 = 84 for Nd–Fe–B). The three files
   are merged in the order of the element list (edges 1–2, 1–3, 2–3); on conflicting parameters the first file wins,
   so the order is part of the specification. A combination is kept only if the merged database reproduces each of its
   own binary assessments at the stored reference points (Edge-Check Rule v2: |ΔG| ≤ 1 J mol⁻¹, at most two
   unverifiable points, leave-one-phase-out fallback).
3. **Threshold.** For each surviving combination, ΔG_f*(T) = G_comp(x, T) − Σ xᵢ GHSERᵢ(T) in kJ mol⁻¹ atom⁻¹: the
   equilibrium energy of the binary phases at the target composition x (no ternary phase), relative to the SGTE element
   references. Over the survivors: median, 5th and 95th percentile (the band), survivor count, lineage coverage.
   Temperatures: 800, 1000, 1100, 1200, 1300, 1375, 1450, 1600 K.
4. **Gates.** G1: at least 25 % of the combinations survive. G2: at least two surviving lineages per edge. These are
   engineering defaults, not pre-registered values. A failed gate marks the result `ensemble_unreliable`.
5. **Candidate side (optional).** Materials Project entries are filtered (§4); each gets ΔG_f^SISSO(T) from the phase
   diagram built with `GibbsComputedStructureEntry`, in kJ mol⁻¹ atom⁻¹ (eV/atom × 96.485), relative to the pymatgen
   element references. If this step fails the CALPHAD result is kept and labelled `sisso_unavailable`.
6. **Comparison, windows, storage.** Classification (§3), the stability window (most negative margin, temperature runs
   with ΔG_f^SISSO ≤ p95 and < p05, class changes), and storage in PostgreSQL (`calphad_ensemble_runs`,
   `calphad_dft_comparison`, `calphad_run_samples`).

## 3. Locked decisions and labels

1. **Prototype margin at the prototype's own composition.** A nearest prototype is compared with the threshold
   re-evaluated at *its* composition on the surviving combinations (the edge check does not depend on composition).
2. **SISSO is a soft, secondary axis.** Classes come from the CALPHAD band only; the SISSO margin and its value on
   the SER axis of the CALPHAD side are reported as approximate extra fields and never change a class.
3. **Label set.** `stable_across_band` (ΔG_f^SISSO < p05), `borderline_within_band` (p05 ≤ ΔG_f^SISSO ≤ p95),
   `metastable_above_band` (> p95), `ensemble_unreliable`, `sisso_unavailable`, `no_dft_entry`,
   `prototype_indicative_only`. A database view exposes the column names of the original plan.
4. **Edge comparison, not half-width.** The rule compares ΔG_f^SISSO with the percentile edges.
5. **Numbers in the methods text** (grid, band widths) are those of the frozen reports (§5).

The margin is ΔΔG = ΔG_f^SISSO − ΔG_f*,median; negative means the candidate lies below the competing binaries.
`borderline_within_band` is the honest answer when the candidate's offset is smaller than the assessment scatter.

## 4. Prototype handling and display

An `exact_match` has the target composition (distance ≤ 5·10⁻⁴). A `nearest_prototype` must contain the minority
element(s) of the target within 0.03 (elements below 3 at.% are dopants and never anchors; the smallest remaining
element anchors only if it is at most 25 at.%) and lie within a composition distance of 0.16. Optionally (opt-in),
elements that share a crystallographic site are grouped (`FE,SI`), so that La(Fe,Si)₁₃ prototypes are found across the
series. Ranking: exact before nearest, then 0 K hull energy, then low-temperature ΔG_f^SISSO, then distance; at most
three prototypes are kept. A nearest prototype never receives a stability class at the target: its row is
`prototype_indicative_only` (`comparable = FALSE`) and carries `verdict_at_prototype`, the class against the band at the
prototype's composition.

Display rules: the provenance label shows the match type and Δx, for example `mp-… (LaFe9Si4, nearest_prototype
Δx=0.001 (grouped), Euclid 0.252)`. With site groups the grouped distance only says that the site totals agree; the
Euclidean distance is shown next to it whenever they differ by more than 0.005. A `‡` marks values that refer to the
prototype's own composition. The table never shows a target-composition margin next to a prototype that has a matched
check.

## 5. Results from the frozen runs

**Table 1.** CALPHAD binary-ensemble thresholds at 800 K, kJ mol⁻¹ atom⁻¹ relative to SER (reports in
`stage_five/results/`; width = p95 − p05).

| System (target) | Merge priority | Survivors | Gates | ΔG_f*(800 K) median [p05, p95] | Width 800 K (range over grid) | SISSO overlay |
|---|---|---|---|---|---|---|
| Nd₂Fe₁₄B (Fe 0.824, Nd 0.118, B 0.059) | Fe–Nd > B–Fe > B–Nd | 78/84 (93 %) | pass | −8.79 [−9.20, −8.40] | 0.80 (0.67–2.00) | not run in the frozen table |
| Al₁₆Fe₅Mn₅ (Al 0.615, Fe 0.192, Mn 0.192) | Al–Fe > Al–Mn > Fe–Mn | 313/594 (53 %) | pass | −25.51 [−26.52, −24.06] | 2.46 (0.44–2.46) | not run in the frozen table |
| La₇.₁Fe₈₂.₁Si₁₀.₈ (Fe 0.821, Si 0.108, La 0.071) | Fe–Si > Fe–La > La–Si | 16/20 (80 %) | pass | −17.78 [−19.00, −16.47] | 2.53 (2.53–3.60) | run on the desktop; see Table 2 |

The merge order matters: Nd–Fe–B gives 78/84 survivors in the order above and 52/84 on the same data in alphabetical
order (the first file wins on conflicts). In Al–Fe–Mn two third-generation FeMn files are excluded by the audit and
FeMn-89Lee fails the edge check in every combination; in Fe–La–Si FeSi-91Lac-LB fails it in all four of its
combinations.

**Table 2.** La₇.₁Fe₈₂.₁Si₁₀.₈ with the SISSO overlay (desktop run of 24 November 2026, database run 11, nearest
prototypes with site group Fe,Si; values at 800 K unless stated; the numbers are taken from the application output, the
JSON export of this run is listed under planned items).

| Prototype (Materials Project entry) | Euclidean distance to target | ΔG_f^SISSO | band at the prototype's composition, median [p05, p95] | margin | class at the prototype |
|---|---|---|---|---|---|
| LaFe₉Si₄ (mp-662529) | 0.252 | −37.68 | −33.13 [−35.06, −31.21] | −4.55 | stable_across_band to 1300 K; borderline_within_band from 1375 K |
| LaFe₈Si₅ (mp-1211378) | 0.353 | −41.92 | −36.38 [−38.50, −34.27] | −5.54 | stable_across_band to 1450 K; borderline at 1600 K |
| LaFe₈Si₅ (mp-1223067) | 0.353 | −41.04 | −36.38 [−38.50, −34.27] | −4.66 | stable_across_band to 1375 K; borderline from 1450 K |

Reading: at its own Si-rich composition the La(Fe,Si)₁₃-type structure lies 4–6 kJ mol⁻¹ atom⁻¹ below the competing
binaries and moves into the band (class `borderline_within_band`) at 1375–1600 K. This is evidence about the structure type; it is **not** a
verdict on the target composition, which is 0.25–0.35 away. Without the site group the closest entry is LaFe₉
(ΔG_f^SISSO = +14.5 kJ mol⁻¹ atom⁻¹ at 800 K, band at its composition −1.77, margin +16.3: `metastable_above_band`),
a high-energy entry that is not a useful stand-in. The margins of 4–6 kJ mol⁻¹ atom⁻¹ are of the size of the usual
SISSO error and of the band width (about 4 kJ mol⁻¹ atom⁻¹ here), which is why SISSO stays secondary.

## 6. Limitations

* **Binary competitors only.** The candidate energy is a DFT value and already contains the candidate's own ternary
  interactions; what is missing are ternary competing phases and ternary terms of the competing assemblage. The
  comparison is a necessary, not a sufficient, screen.
* **SISSO is approximate.** Its model error is not part of the class and is usually larger than the band. For
  Nd₂Fe₁₄B the difference ΔG_f^SISSO − ΔG_f* grows with temperature by about +15 J mol⁻¹ atom⁻¹ K⁻¹ (23 November run, not
  part of the frozen files), which would correspond to an implausible formation entropy; the cause is untested and
  nothing in the code compensates for it. The reference-axis correction explains only about 1.6 of the 5.8 kJ mol⁻¹
  atom⁻¹ margin at 800 K in that case.
* **A prototype is not the target.** Prototype rows are indicative; the class at the prototype describes the structure
  type at its composition.
* **The band depends on specification choices:** the merge order, the gate defaults, and the open assessments that
  exist. Edges with two lineages (Fe–La, La–Si in Fe–La–Si) give a band that may not represent the true assessment
  scatter; a zero-width matched band (all survivors share one assessment on the relevant edge) means "no scatter
  available", not "high confidence".
* **Magnetic and polymorph state of the Materials Project entry** is not controlled; entries with the same
  composition differ by about 1 kJ mol⁻¹ atom⁻¹ (LaFe₈Si₅ above).
* The temperature range is 800–1600 K; statements for higher temperatures are not made.

## 7. Reproducibility

* **Code and version.** Tag `v5.0-stage5`; engine rules version `stage5-engine/edge-rule-v2/fix1-2026-11-23`;
  contract 1.0 (`stage_five/CONTRACT.md`).
* **Frozen reports.** `stage_five/results/ensemble_B-Fe-Nd_Nd2Fe14B.json`, `ensemble_Al-Fe-Mn_Al16Fe5Mn5.json`,
  `ensemble_Fe-La-Si_La7.1Fe82.1Si10.8.json`, with SHA-256 in `results/SHA256SUMS`; each report stores its
  specification hash, the hash of the accepted TDB files, the merge order and every combination's result.
  The table and notes are generated from these files only (`methods_table.py`).
* **Reproduction.** On 24 Nov 2026 the current code (after the contract changes; Python 3.13, pycalphad 0.11.2) re-ran all three ensembles from scratch and compared them with the frozen files. The same combinations survive (16/20, 78/84, 313/594), the specification hashes and the hashes of the accepted TDB collection are identical, and the largest differences of the bands (median, 5 %, 95 %, minimum, maximum at every temperature) and of every per-combination threshold are below 10⁻⁵ kJ mol⁻¹ atom⁻¹ (printed as 0.00000). Run times with four workers: 159 s (Fe–La–Si), 228 s (Nd–Fe–B), 4125 s (Al–Fe–Mn).
* **Database.** Migrations 009–012 in `stage_five/` (tables, prototype provenance, secondary fields with the view
  `v_stage5_screening`, run–sample links with `v_stage5_sample_runs`).
* **Tests.** `pytest stage_five/tests` (76 tests, 6 skipped without tkinter; the full ensembles run with
  `RUN_SLOW=1` and `SGTE_BINARY_DIR` set; the window tests run under a virtual display).
* **Environment of the frozen reports.** pycalphad 0.11.2; the SISSO side uses pymatgen's
  `GibbsComputedStructureEntry` and the Materials Project API (versions of the desktop installation are recorded
  with the release).

## 8. Versioning and planned items

This is version 1.0. Planned, not part of it: export of the Fe–La–Si desktop run as JSON next to the frozen reports,
SISSO overlays for the other two systems (needs a Materials Project key), a temperature-dependent SISSO calibration
study (needs a validation set), and any rule that promotes a nearest prototype to a verdict. Each becomes a new
version with a changelog entry in `CONTRACT.md`; results are always labelled with the version that produced them.

## References

1. C. J. Bartel et al., Physical descriptor for the Gibbs energy of inorganic crystalline solids and
   temperature-dependent materials chemistry, Nat. Commun. 9, 4168 (2018).
2. R. Otis and Z.-K. Liu, pycalphad: CALPHAD-based computational thermodynamics in Python, J. Open Res. Softw. 5, 1 (2017).
3. A. T. Dinsdale, SGTE data for pure elements, Calphad 15, 317 (1991).
4. A. Jain et al., Commentary: The Materials Project: a materials genome approach to accelerating materials
   innovation, APL Mater. 1, 011002 (2013).
5. S. P. Ong et al., Python Materials Genomics (pymatgen): a robust, open-source Python library for materials
   analysis, Comput. Mater. Sci. 68, 314 (2013).

(Reference details to be checked against the publishers' records before deposit.)
