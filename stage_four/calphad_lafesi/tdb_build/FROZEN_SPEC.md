# Frozen build spec — La–Fe–Si TDB reconstruction (write-before-run)

*Frozen 15 November 2026, BEFORE any parameter was typed or any equilibrium
run. Pilot discipline (Track A rule): decide the target and the acceptance
test first, so a sign typo cannot quietly pass.*

## 1. What this is

A **reconstruction** (Lindahl-style, minus the author's file) of the
published assessment **Feng et al., Calphad 83 (2023) 102643**: the
ternary parameters typed from the paper's Table 5 onto a binary backbone.

**Faithfulness decision (the "whose binaries" question).** Feng's Table 5
*restates every binary parameter it used*, with ref tags:
La–Si = Zhou 2010 [20], Fe–Si = Cui 2017 [23], La–Fe = Su 2022 [24].
Therefore the faithful backbone is **Feng's own Table 5**, not an external
binary file — typing Table 5 in full reproduces exactly the description the
ternary τ parameters were fitted on. No hybrid risk. (The separate WP4
"swap the binaries, get an uncertainty band" experiment *does* need the
external binary collection; that is a later layer, see §5.)

**Unaries.** SGTE / Dinsdale 1991, taken from pycalphad's bundled
`zrlayalo.tdb` (La), `COST507.tdb` (Si) and the repo's `FENDB_merged_v4.tdb`
(Fe). GHSERLA cross-checked identical between `zrlayalo.tdb` and
`mc_fecocrnbti.tdb`; **La SER = DOUBLE_HCP (dhcp)**, matching Feng's
`GHCP_La` reference term.

## 2. Frozen composition (the WP4 descriptor point)

The 1:13 point, written down first:

```
La(Fe11.5Si1.5)      total 14 atoms, ratio 1 La : 13 (Fe,Si)
  x_La = 1/14    = 0.071429
  x_Fe = 11.5/14 = 0.821429
  x_Si = 1.5/14  = 0.107143
  (Si fraction of the 13 (Fe,Si) sites: x = 1.5/13 = 0.1154)
```

Primary temperature **T_anneal = 1373 K** (Niitsu: τ1 single-phase forms
completely in 5 days at 1373 K; Feng's section is at 1373 K). The WP4
descriptor is ΔG_f(τ1, T_anneal) at this composition; the band comes from
the binary-swap experiment (§5), not needed for the faithful build.

## 3. Scope of this TDB (and documented omission)

Built from Feng Table 5:
- Solution phases LIQUID, FCC_A1, BCC_A2 (with the ternary interaction terms)
- Fe–Si line compounds (Fe2Si, Fe5Si3, FeSi, LT/HT-FeSi2)
- La–Si(Fe) compounds (La5(Si,Fe)3, La3(Si,Fe)2, La5(Si,Fe)4, La(Si,Fe),
  α- and β-La(Si,Fe)2)
- Ternary τ1, τ2 = La(Fe,Si)13 (cubic NaZn13 / tetragonal), model
  (La)(Fe,Si) at 1:13
- Ternary τ3–τ6, model (La)(Si,Fe)(Si,Fe)

**Omitted, on purpose, this version:** the Fe–Si BCC_B2 / D03 ordering
(Cui 2017 4-sublattice). Feng's Table 5 gives only the ΔG anchors for it,
not the full endmember set. B2/D03 matter only in the Fe-rich corner
(Feng alloys #19, #20). Fe–Si there is represented as disordered BCC_A2.
This is a stated limitation, not a silent one: those two alloys are
excluded from the acceptance test below.

## 4. Acceptance test (decided now, before typing)

The build is **accepted** only if all of:

- **A1 — parses & computes.** pycalphad loads the TDB; every phase returns
  finite Gibbs energy over 1000–1700 K; no missing GHSER references.
- **A2 — unary consistency.** GHSERLA, GHSERFE, GHSERSI in the built TDB
  match the SGTE source numerically (not by text) at 300/1000/1700 K.
- **A3 — τ1 is stable at the frozen point.** At La(Fe11.5Si1.5), 1373 K,
  the cubic 1:13 phase τ1 is present in the computed equilibrium.
- **A4 — reproduces Feng's Table 4 (Fe-rich, B2/D03-free subset).** For
  Feng alloys #10, #11, #13, #17, #21 (the τ1-bearing ones), the computed
  stable phase set contains the τ1/τ2/τ3 or αFe phases Feng reports.
  Target: ≥ 4 of 5 qualitatively correct.
- **A5 — τ1 window overlaps the literature.** Along La(Fe1-xSix)13 at
  1373 K, the τ1 single-phase (or τ1-dominant) range overlaps the
  Feng/Niitsu stated 0.096–0.229 in x.

If A1–A3 pass but A4/A5 only partly: **accepted as "computes, partial
match"** — still usable for the WP4 ΔG_f descriptor (A1–A3), with the
phase-boundary caveats logged. A sign typo that breaks A4/A5 while A1–A3
pass is exactly what the per-block provenance comments (§below) are for.

## 5. Later layer — WP4 uncertainty band (needs the external binaries)

Swapping Feng's cited binaries for the other members of the Track A
collection (2 FeLa × 3 LaSi × 5 FeSi) gives the honest uncertainty band on
ΔG_f(τ1, T_anneal). That needs the actual binary TDB files (local
`data/tdb/sgte_binary/`, not in this cloud env). Deferred; the build script
is written to accept an external binary backbone so this is a drop-in later.

## 6. Provenance rule while typing

Every PARAMETER block in the TDB carries a comment: `$ Feng2023 Table5
<phase> <ref>` and any deviation (unit note, suspected typo, correction).
The τ3–τ6 three-sublattice model and the 1:13 site ratio are documented at
the phase definition.
