# τ3–τ6 reconstruction attempt — finding

**Result: τ3–τ6 cannot be faithfully reconstructed from Feng et al. (2023)
as published.** The production TDB keeps τ1/τ2 only (validated); τ3–τ6 are
documented here and shipped as a flagged, non-validated experiment
(`tau36_block.py`).

## What the paper gives, and what it omits

Eq. 8 defines the model **(La)ₓ(Si,Fe)_y(Si,Fe)_z** with four endmembers
(La:Si:Si, La:Fe:Fe, La:Si:Fe, La:Fe:Si) and reciprocal interactions, per
mole of atoms. Table 5 lists the four endmember "G" values and the
interaction L for each of τ3–τ6, e.g. τ3:
```
G(La:Fe:Si) = -55000 - 11.2*T
G(La:Si:Fe) = -43004.3 - 10*T
G(La:Fe:Fe) = 10001 + 8.0032*T
G(La:Si:Si) = 45000 - 9*T
L(La:Si,Fe:Si,Fe) = -136160.007 + 5*T   (all partial L's equal)
```

**Two things needed to build the phase are not in the paper:**
1. **The GHSER reference terms.** τ1/τ2 print them explicitly
   (`+0.071428·GHSERLA + 0.928572·GHSERFE`); τ3–τ6 print none. Without a
   reference the endmember energy has no absolute level.
2. **The site ratios x, y, z.** Eq. 8 names them but Table 5 does not give
   their values. They were inferred from the Table 4 EPMA compositions:
   τ3 (1,2,2) = LaFe₂Si₂, τ4 (1,1,2) = LaFeSi₂, τ5 (1,1,1) = LaFeSi, τ6
   (1,2,2) [τ6 is not in Table 4 — guess].

## Three reconstructions tested, all against Feng's own Table 4

The acceptance test: do τ3/τ4/τ5 appear in the Table-4 alloys where Feng
reports them, at 1373 K, without breaking the validated τ1/τ2 build?

| hypothesis for the endmember | τ3–τ6 behaviour |
|---|---|
| **A. as printed** (no GHSER) | non-competitive — never stable anywhere |
| **B. printed + site-weighted GHSER** (physically sensible; τ3 ΔG_f ≈ −11 kJ/mol-atom) | too weak — never stable; τ1/τ2 preserved |
| **E. (x+y+z)·printed + GHSER** (τ3 alone looked right) | τ4 super-stable, takes over the whole diagram including the τ1/τ2 window |

None reproduces Feng's Fig. 5 / Table 4 phase stabilities. B is
non-destructive (τ1/τ2 still correct) but leaves τ3–τ6 inert; A and E are
wrong. The published parameters are insufficient to pin the τ3–τ6 energies
to the level that makes them stable where Feng shows them.

## Conclusion and recommendation

This is the τ3–τ6 analogue of the suspected Table-3 row swap (WORKLOG §3):
the acceptance test surfaces that the published assessment is **not
reproducible for τ3–τ6 from the paper alone**. To complete them faithfully,
obtain the authors' actual TDB — the paper's Data Availability says "Data
will be made available on request" (corresponding authors huangkl0916,
qingry96, luzhao_gx). With their file, `tau36_block.py` can be corrected in
minutes (the site ratios and the GHSER convention are the only unknowns).

`tau36_block.py` ships hypothesis **B** (physically sensible, non-destructive)
so the phase definitions and the inferred site ratios are preserved for that
correction; it is **not** part of the production build and must not be used
for phase-stability work until validated.

## Impact on the WP4 work: none

τ3–τ6 are the Si-rich/La-rich ternary compounds. The magnetocaloric τ1
phase and its descriptor live in the Fe-rich corner, where τ1/τ2 + the
binary backbone are fully validated. The WP4 descriptor and the uncertainty
band are unaffected.


## Update 16 Nov 2026 — rerun with corrected Table 5 signs

An independent check of Table 5 against the PDF found three sign errors in the earlier
transcription (tau4 G(La:Fe:Fe) = +10001-5.002T; tau5 G(La:Fe:Si) = +48500-13.6T;
tau6 L = -65006.5+10T). They are corrected in table5_parameters.md and tau36_block.py.
Rerun (tau36_rerun.py, 21 alloys, 1373 K, hypotheses A/B/E, old vs corrected signs):
the conclusion does not change. A and B never make tau3-tau6 stable (identical to the run
without them; 5/21 exact phase-set matches vs experiment); E lets tau4 take over the
diagram (0/21). The missing piece is the reference/scaling (GHSER terms, site ratios),
not the signs. tau3-tau6 stay excluded from the WP4b descriptor.
Record: WP4b_Step3_Tau36_Rerun_20261116.md (private documentation repo).