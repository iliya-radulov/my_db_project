> **SUPERSEDED (21 Nov 2026) — the driving-force results below are wrong; do not use them.**
> The merged build behind this note had lost the pure-element end-member terms of the solution phases (and had further defects:
> missing species union, duplicated end-members summed by pycalphad, Fe-substitution terms not scaled per formula unit; see the fix
> comments in `../build_merged_tdb_fixed.py`). With τ1/τ2 suspended the "competing equilibrium" was pure bcc about 64 kJ/mol-atom above the
> mixture of the pure elements, which is impossible; hence the +84.7 kJ/mol-atom driving force, the "band 2064 J/mol-atom",
> "the spread is entirely Fe–Si-driven" and the "faithfulness proof" are all void. The proof compared ΔG_f(τ1), a quantity that does
> not depend on the solution-phase references, so it could not detect the defect; the check that does is the physical bound
> (no equilibrium above the pure-element mixture).
>
> **Corrected values** (committed builder `../build_merged_tdb_fixed.py`, `SGTE_BINARY_DIR` set, La(Fe11.5Si1.5), 1373 K, driving force
> D = G(τ1/τ2 suspended) − G(all)): over the 20 binary combinations **D = 1.76–5.56 kJ/mol-atom (mean 3.71)**; the **La–Si file is the main source of
> the spread** (LaSi-10Zho 1.76–2.08, LaSi-20Xu 4.99–5.56), the Fe–Si file moves D by up to 0.5 kJ (0.32 kJ with LaSi-10Zho), the Fe–La file by at most 0.07 kJ. The Feng-cited
> combination (FeLa-23Su + LaSi-10Zho + FeSi-17Cui) gives 2.07 kJ with competing bcc 0.802 + α-LaSi2 0.198; the combination
> FeLa-23Su + LaSi-10Zho + FeSi-12Ohn gives 1.76 kJ and reproduces the self-contained Table-5 descriptor of the paper draft.
> The formation energy ΔG_f(τ1) = −20992.6 J/mol-atom (1373 K) and its binary-independence are unaffected.
> The τ1/τ2 window and its (flat) temperature dependence are in `../refit_tau12/RESULTS.md` (Addenda D, D.1, E).
> The old builder `build_merged_tdb.py` and its users `wp4_band.py`, `wp4_probe.py` now stop with a pointer to the fixed builder.
> The text below is kept unchanged for the record.

# Full merged build — results

`build_merged_tdb.py` merges three real binary TDBs from the Track A SGTE
collection (`projects_documentation/AlloyDB/Data/tdb/sgte_binary/`) into one
La–Fe–Si database and injects Feng's τ1/τ2 + ternary liquid term.
`wp4_band.py` runs it over all 20 binary combinations.

## Pre-merge checks (Track A lessons)
- **Standalone compute (lesson 1):** all 9 binaries load and compute at
  1373 K. FeSi-23Wit (the flagged Witusiewicz file) computes fine.
- **3rd-gen screen (lesson 2):** all 2nd-generation (no Einstein terms,
  GHSER from 298.15), including the 2020s files FeLa-23Su, LaSi-20Xu,
  FeSi-23Wit.
- **Unary consistency (numeric, not text):** GHSERLA/FE/SI identical across
  all binaries where they overlap, and identical to the self-contained
  build's SGTE source.

## Merge
Shared solution phases (LIQUID, FCC_A1, BCC_A2, …) get their constituents
unioned to (La,Fe,Si); binary interactions and compounds carry over. Cui's
Fe–Si 4-sublattice ordering (A2_BCC/B2_BCC/BCC_4SL) is left out of the
ternary merge — Feng themselves treated Fe–Si as disordered A2 and added
B2/D03 separately (paper p.9). Result: 19 phases, parses and computes.

## The faithfulness proof
The faithful combo (Feng's cited **FeLa-23Su + LaSi-10Zho + FeSi-17Cui**)
reproduces the self-contained Feng-Table-5 build to **< 0.2 J/mol-atom**:

| | self-contained (Table 5) | merged (real binaries) |
|---|---|---|
| ΔG_f(τ1) at 1173 K | −20616.3 | −20616.3 |
| ΔG_f(τ1) at 1373 K | −20992.7 | −20992.6 |
| τ1/τ2 window | 0.10–0.23 / ≥0.27 | identical |

This is the Lindahl criterion: the merge of a set of binaries reproduces an
assessment to < 0.2 J/mol **because the binaries match**. It confirms, two
independent ways, that Feng's Table 5 faithfully restated its binaries and
that our reconstruction is faithful.

## WP4 descriptor and uncertainty band

**Descriptor 1 — ΔG_f(τ1) vs SER elements: binary-independent.** τ1's
energy is Feng's fixed ternary parameters + unaries; the binaries never
enter it. All 20 combinations give −20992.6 J/mol-atom (band = 0). Clean
result: the formation energy of τ1 carries no binary uncertainty.

**Descriptor 2 — τ1 formation driving force** G(competing, τ1/τ2
suspended) − G(τ1): binary-sensitive, the physically meaningful quantity
for whether annealing yields single-phase τ1.

| | driving force [J/mol-atom] | competing assemblage |
|---|---|---|
| 16 of 20 combinations | **+84703** | αFe (BCC_A2) |
| 4 combinations (FeSi-23Wit) | **+82639** | αFe + Fe₂Si |

- τ1 single-phase at the frozen point in **all 20** combinations — the τ1
  window is robust to the binary choice.
- **Band = 2064 J/mol-atom** (~2.5 %), mean 84290 ± 826.
- **The spread is entirely Fe–Si-driven.** The La–Fe (09Pov vs 23Su) and
  La–Si (10Zho vs 20Xu) choices make **zero** difference to the Fe-rich τ1
  descriptor — at this composition the competitor is Fe-based, so only the
  Fe–Si binary matters.
- **FeSi-23Wit (Witusiewicz) is the single outlier**, exactly as flagged:
  its "comprehensive/non-standard" lineage stabilises Fe₂Si as a competitor
  and lowers the driving force by ~2 kJ. An honest, informative band from
  one identifiable assessment, not noise.

## Caveat
With τ1/τ2 suspended, the competing equilibrium at this Fe-rich point is
reported as αFe (± Fe₂Si) with the La-bearing phase below the 0.01 NP
threshold (La is nearly insoluble in αFe; the small La-rich remainder sits
in a trace silicide/liquid). The driving-force magnitude is dominated by
the Fe-rich competitor and the FeSi-23Wit split is robust; the exact
La-partitioning of the trace is not resolved here.
