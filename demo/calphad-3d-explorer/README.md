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
| Solidus, solvus, valleys, invariant points | Derived from the T₀ surface and the change of the most stable solid | From the equilibrium calculation |
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

## Later: connection to the Stage 5 code (planned, not started)

Keep this front-end; replace `src/calphad/solver.ts` by results from pycalphad (the engine and TDB files Stage 5 already uses): a small Python backend computes isothermal sections and the liquidus surface for a ternary, cached, and the 3D scene draws them. Estimated 3–5 days plus about a day of checking against published diagrams.
