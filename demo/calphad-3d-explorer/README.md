# CALPHAD 3D Phase Explorer (demo)

Interactive 3D view of a ternary system: composition triangle × temperature, with surfaces, an isothermal slice, invariant points and a Gibbs-energy probe. Built-in systems: Sn–Ag–Cu, Al–Mg–Si, Fe–Cr–Ni; your own `.TDB` files can be imported.

Generated in Google AI Studio (Nov 2026) and cleaned up for this repository. **It is a qualitative demo, kept here as the front-end skeleton for a later connection to the Stage 5 CALPHAD code.** Do not use its numbers.

## Run

```bash
cd demo/calphad-3d-explorer
npm install
npm run dev        # http://localhost:3000
npm run build      # static build in dist/
```

No API key or server is needed; everything runs in the browser.

## What the numbers are — and are not

| Item | In this demo | Correct CALPHAD treatment |
|---|---|---|
| "Liquidus" surface | **T₀ surface**: temperature where the liquid and the most stable solid have equal Gibbs energy *at the same composition* | Common-tangent / lower-convex-hull construction; gives two-phase regions. Temperatures can differ by tens to hundreds of K. |
| Solidus and solvus surfaces | **Not computed**: drawn by rule-of-thumb shapes (a solidus placed a fixed fraction above an assumed eutectic floor, a power-law "solvus dome") | From the equilibrium calculation |
| Valleys, invariant points | From changes of the most stable solid on the T₀ surface | From the equilibrium calculation |
| Compounds | Parabola around the formula composition (curvature 32 000 J/mol by default) plus ¼ of the ideal mixing entropy | Line compound (or sublattice model) |
| Models | One substitutional lattice per phase, Redlich–Kister + Muggianu; site ratios of compound end-members are used to convert to per-atom energies | Full compound-energy formalism: sublattices, vacancies, ordering, magnetic contribution |
| Built-in systems | Hand-made parameters, linear in T, illustrative only (e.g. the Sn–Ag–Cu ternary eutectic comes out at 420 K; the real one is about 490 K / 217 °C) | Published assessments |
| Imported `.TDB` | Functions and parameters read; missing liquid functions are **estimated** from a built-in table of melting points and enthalpies of fusion, a missing `GHSER` function becomes 0 | — |

The app shows a "Qualitative demo" line under the title, and lists every estimate the importer had to make for an imported file.

## Changes from the AI Studio export

- Removed the unused Gemini / AI Studio parts: `@google/genai`, `express`, `dotenv`, `metadata.json`, `.env.example`, the AI-Studio-specific Vite settings.
- Removed `bun.lock` and a pinned `esbuild` that conflicted with Vite 8 under npm; `package-lock.json` added.
- `npm run dev` listens on localhost only (was all network interfaces).
- Visible "Qualitative demo" label; surface toggles renamed "Liquidus (T₀)" and "Solidus (approx.)"; probe hint no longer says "CALPHAD equilibria".
- Imported systems record where data was invented (`buildNotes`), shown in the header.

## Computed datasets from real TDB files

The explorer can show real equilibria computed with pycalphad instead of the toy solver.

**1. Compute a dataset** (Python, from the repository root; `datasets/` is git-ignored, the file is regenerated from the TDB and the command):

```bash
pip install -r demo/calphad-3d-explorer/tools/requirements.txt
python demo/calphad-3d-explorer/tools/export_ternary.py \
    --tdb stage_four/calphad_lafesi/refit_tau12/results_addD/paperbuild_FeLa-23Su_LaSi-10Zho_FeSi-12Ohn.tdb \
    --elements FE LA SI --tmin 800 --tmax 2600 --dt 10 --grid 30 --workers 4 \
    --out demo/calphad-3d-explorer/datasets/lafesi_paperbuild.json
python -m pytest demo/calphad-3d-explorer/tools/test_export_ternary.py
```

Per composition (triangular grid) and temperature: equilibrium phases and fractions, molar Gibbs energy. Corners and edges are computed as pure-element and binary systems, so the triangle edges are exactly the binary diagrams (a ternary calculation needs X > 0 for every element, and in La–Fe–Si even 1e-4 La precipitates TAU1/TAU2 on the Fe–Si edge and moves the liquidus by up to ~250 K). Results that are not the minimum are rejected: an equilibrium G(T) is concave, so a point more than 200 J/mol above the chord of its temperature neighbours is a solver failure (seen in La–Fe at 1070 K: "all liquid", 5.6 kJ/mol too high); such points are stored as missing and counted separately. Per composition: liquidus and solidus (from the liquid fraction; resolution = temperature step), primary phase, solid assemblage below the solidus. Provenance in the file: TDB name, path and SHA-256, script SHA-256, package versions, command line, grid, number of points where pycalphad did not converge (stored as missing, not filled). Choose `--tmax` above the highest liquidus: in the paper-build La–Fe–Si file, LaSi₂ (`LASI2_X`) and TAU1 are still solid at 2000 K over a large part of the triangle, so 2600 K is used above (grid 30, 10 K steps: about 80 s on 4 cores).

**2. Load it** with the *Load dataset* button. With a dataset:

- liquidus and solidus surfaces, valleys and the primary-phase colouring come from the computed grid;
- the isothermal slice is coloured by the actual equilibrium phase set at the nearest grid point and temperature (stripes = two or more phases, grey = not converged);
- the probe shows the computed phases, fractions and molar Gibbs energy at the nearest grid point and temperature (chemical potentials are not stored);
- invariant-point markers are only grid extrema ("lowest liquidus"), not identified invariant reactions;
- the header shows the TDB file, its SHA-256, the pycalphad version, the resolution and how many points did not converge or lie outside the temperature range (drawn at the range edge);
- the interaction slider is disabled (the equilibria come from the TDB as it is); the data tab shows the dataset provenance.

**3. Check the mapping** (TypeScript, from `demo/calphad-3d-explorer`): `npx tsx tools/check_viewer_mapping.ts datasets/<file>.json` compares the probe at grid-node compositions with the stored states (paper-build La–Fe–Si, 2600 K: 355 checks, 0 mismatches).

**4. Check the dataset against the model and reference data** (`tools/check_dataset.py`):

```bash
python demo/calphad-3d-explorer/tools/check_dataset.py \
    --dataset demo/calphad-3d-explorer/datasets/lafesi_paperbuild.json \
    --tdb stage_four/calphad_lafesi/refit_tau12/results_addD/paperbuild_FeLa-23Su_LaSi-10Zho_FeSi-12Ohn.tdb \
    [--refs my_reference_points.csv] --workers 4 --out demo/calphad-3d-explorer/datasets/lafesi_paperbuild_check
```

Two kinds of check, reported separately:

- **A. Pipeline (pass/fail):** TDB hash; corners and every edge point against an independent pure-element / binary calculation from the same TDB (coarse scan, then 1 K steps), for liquidus, solidus and primary phase, tolerance = step + 2 K. Exit code 1 if the hash, a corner or an edge liquidus fails.
- **B. Model vs reference data (comparison only):** pure-element melting points against the SGTE unary values; optional sourced reference points from a CSV (`tools/reference_points_TEMPLATE.csv`: liquidus/solidus at a composition, or the phase set at a composition and temperature, each with tolerance and source).

Paper-build La–Fe–Si (grid 30, 800–2600 K, 10 K): **A passes** — hash yes, corners 3/3, edge liquidus 87/87, solidus 86/87, primary phase 86/87 (the two differences are within one or two grid steps: two solids appearing within one 10 K step at Fe–Si x(Si) = 0.30, and a rejected neighbour point at La-rich Fe–La). 160 of 89 776 points did not converge, 17 were rejected as not the minimum. B: Fe 1811 / La 1194 / Si 1688 K against SGTE 1811 / 1193 / 1687 K. No reference points yet: they need sourced values (e.g. from the La–Fe–Si paper), which is why the template contains none.

## Status of the connection to the real pipeline

- Step 1, pycalphad export (`tools/export_ternary.py`): done.
- Step 2, loading datasets in the explorer: done.
- Step 3, checks: done for the pipeline (A); the comparison with sourced La–Fe–Si reference points (B2) waits for the values.
- Later: link datasets to the project database (dataset hash, TDB hash), and decide which files are shown for the hand-in.
