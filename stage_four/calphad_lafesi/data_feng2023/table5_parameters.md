# Table 5 — thermodynamic parameters of the La–Fe–Si system

> **Re-checked against the PDF on 16 Nov 2026** (pages 7-9, page images; see `WP4b_Step2_Transcription_Check_20261116.md`). Three sign errors in tau4-tau6 corrected below (marked CORRECTED); everything else matched as printed. Note: the printed positive signs of G(tau4,La:Fe:Fe) and G(tau5,La:Fe:Si) are as printed, not verified for physical sense; flag, do not fix.

Transcribed from Feng et al., Calphad 83 (2023) 102643, Table 5 (© Elsevier).
Energies in J/mol, T in K. `(cid:0)` in the PDF text layer = minus sign;
values cross-checked against the page images. Ref tags: [20] Zhou 2010
(La–Si), [23] Cui 2017 (Fe–Si), [24] Su 2022 (La–Fe).

Unary reference functions (SGTE, Dinsdale 1991): GHSERLA, GHSERFE,
GHSERSI, and the lattice-stability terms `GHCP_La` (written `Gd_La^dhcp`,
the dhcp La reference), `GDIA_Si`, `GBCC_Fe` used in the compound
energies below.

## Liquid  —  model (La,Fe,Si)1, Redlich–Kister
```
0 L(La,Fe) =  19054.390 + 2.3114202*T      [24]
1 L(La,Fe) =  22910.538 - 10.052670*T      [24]
2 L(La,Fe) =  +8497.879                     [24]
0 L(La,Si) = -249912.5 - 39.85*T            [20]
1 L(La,Si) =  25123.5                        [20]
2 L(La,Si) =  83012.5                        [20]
3 L(La,Si) = -21695.6                        [20]
0 L(Fe,Si) = -150802.2 + 24.9159*T          [23]
1 L(Fe,Si) = -22532.7                        [23]
2 L(Fe,Si) = +23530.4                        [23]
0 L(La,Fe,Si) = 200000                       THIS WORK
```

## FCC_A1  —  (La,Fe,Si)1(Va)1
```
0 L(La,Fe) = +60142.574 - 9.7517685*T       [24]
0 L(La,Si) = -191235.4                        [20]
0 L(Fe,Si) = -167164.9 + 42.9734*T           [23]
1 L(Fe,Si) = -44950.4                          [23]
2 L(Fe,Si) = +19706.6                          [23]
TC(Fe:Va) = -201 ; BMAGN(Fe:Va) = -2.1        [23]
```

## BCC_A2  —  (La,Fe,Si)1(Va)3
```
0 L(La,Fe) = +45319.444                        [24]
0 L(La,Si) = -202356.5                          [20]
0 L(Fe,Si) = -180000.0 + 47.8494*T             [23]
1 L(Fe,Si) = -32198.0                            [23]
2 L(Fe,Si) = +15882.8                            [23]
TC(Fe:Va) = 1043 ; BMAGN(Fe:Va) = 2.22          [23]
TC1(Fe,Si) = 504 ; BMAGN1(Fe,Si) = 1.07         [23]
```

## Fe–Si ordering (from Cui 2017 [23]) — affects only the Fe-rich corner
```
BCC_B2 (Fe,Si)(Fe,Si)(Va)3:
  G(Fe:Si) = G(Si:Fe) = -10672.1 ; G(Fe:Fe) = G(Si:Si) = 0
  0L(Fe:Fe,Si)=0L(Si:Fe,Si)=0L(Fe,Si:Fe)=0L(Fe,Si:Si)=10672.1
  dTc = -200 ; dBmagn = -0.4
D03 (Fe,Si)(Fe,Si)(Fe,Si)(Fe,Si)... second-order; from B2:
  dGB_Fe2Si = -10672.1 ; dGD03_Fe3Si = -3350 ; dTc_D03 = 65 ; dBmagn = 0.2
  (full endmember/interaction set in the PDF; reconstruct from Cui 2017)
```

## Fe–Si line compounds (from [23]) — relative to GBCC_Fe, GDIA_Si
```
Fe2Si   = -30592.9 + 0.33333*GDIA_Si + 0.66667*GBCC_Fe
Fe5Si3  = -34224.6 + 1.53653*T + 0.375*GDIA_Si + 0.625*GBCC_Fe
FeSi    = -39705.0 + 2.08759*T + 0.5*GDIA_Si + 0.5*GBCC_Fe
LT-FeSi2= -39571.0 + 10.6912*T + 0.6667*GDIA_Si + 0.333*GBCC_Fe
HT-FeSi2= -23969.4 + 0.7*GDIA_Si + 0.3*GBCC_Fe
```

## La–Si compounds with Fe solubility — model La_a(Si,Fe)_b
Endmember `:Si` from Zhou 2010 [20]; endmember `:Fe` and the mixing
parameter `L` are THIS WORK. `GHCP_La` = dhcp-La reference.
```
La5(Si,Fe)3  G(La:Si) = -60012.5 - 14.37*T + 0.625*GHCP_La + 0.375*GDIA_Si   [20]
             G(La:Fe) = +8001.1109 + 8.001*T + 0.625*GHCP_La + 0.375*GBCC_Fe  THIS WORK
             L(La:Si,Fe) = -25999.4388 + 4.9996*T                              THIS WORK
La3(Si,Fe)2  G(La:Si) = -63125.4 - 14.93*T + 0.6*GHCP_La + 0.4*GDIA_Si         [20]
             G(La:Fe) = 10000 + 11*T + 0.6*GHCP_La + 0.4*GBCC_Fe               THIS WORK
             L(La:Si,Fe) = -26500 + 5*T                                        THIS WORK
La5(Si,Fe)4  G(La:Si) = -67018.6 - 15.43*T + 0.5556*GHCP_La + 0.4444*GDIA_Si   [20]
             G(La:Fe) = +5000 + 9*T + 0.5556*GHCP_La + 0.4444*GBCC_Fe          THIS WORK
             L(La:Si,Fe) = +36500 + 7.5*T                                      THIS WORK
La(Si,Fe)    G(La:Si) = -70156.2 - 15.4*T + 0.5*GHCP_La + 0.5*GDIA_Si          [20]
             G(La:Fe) = +8000 + 10*T + 0.5*GHCP_La + 0.5*GBCC_Fe               THIS WORK
             L(La:Si,Fe) = -43500 + 6.5*T                                      THIS WORK
alpha-La(Si,Fe)2  G(La:Si) = -53051.2 - 21.49*T + 0.36*GHCP_La + 0.64*GDIA_Si  [20]
             G(La:Fe) = +8900 + 8*T + 0.36*GHCP_La + 0.64*GBCC_Fe              THIS WORK
             L(La:Si,Fe) = -115863.005 + 9*T                                   THIS WORK
beta-La(Si,Fe)2   G(La:Si) = -49262.3 - 21.048*T + 0.3333*GHCP_La + 0.6667*GDIA_Si [20]
             G(La:Fe) = +9504.75086 + 10*T + 0.3333*GHCP_La + 0.6667*GBCC_Fe   THIS WORK
             L(La:Si,Fe) = -1.294 + 7*T                                        THIS WORK
```

## La–Fe–Si ternary compounds (ALL THIS WORK)

### tau1, tau2 — La(Fe,Si)13, model (La)_0.071428 (Fe,Si)_0.928572
(site fractions 1/14 La, 13/14 (Fe,Si); = (La)1(Fe,Si)13 normalised)
```
tau1  G(La:Fe) = 2300 - 0.95*T  + 0.071428*GHCP_La + 0.928572*GBCC_Fe
      G(La:Si) = 37000 + 6.5*T  + 0.071428*GHCP_La + 0.928572*GDIA_Si
      L(La:Si,Fe) = -242114 + 9.5*T
tau2  G(La:Fe) = 6500 - 0.9*T   + 0.071428*GHCP_La + 0.928572*GBCC_Fe
      G(La:Si) = 22500 + 8.5*T  + 0.071428*GHCP_La + 0.928572*GDIA_Si
      L(La:Si,Fe) = -241114 + 8*T
```

### tau3–tau6 — model (La)(Si,Fe)(Si,Fe), four endmembers + mixing
(paper's eq. 8; the three-sublattice compound with neutralisation
variables Y_II, Y_III. All interaction L's equal, as noted.)
```
tau3 (La3Fe2Si8)   G(La:Fe:Si) = -55000 - 11.2*T
                   G(La:Si:Fe) = -43004.3 - 10*T
                   G(La:Fe:Fe) = 10001 + 8.0032*T
                   G(La:Si:Si) = 45000 - 9*T
                   L(La:Si,Fe:Si,Fe) = -136160.007 + 5*T
                   L(La:Si,Fe:Si)=L(La:Si,Fe:Fe)=L(La:Si:Si,Fe)=L(La:Fe:Si,Fe)=L(La:Si,Fe:Si,Fe)
tau4 (LaFeSi2)     G(La:Fe:Si) = -53021.2027 - 16*T
                   G(La:Si:Fe) = -32022.4058 - 10.01*T
                   G(La:Fe:Fe) = +10001 - 5.002*T      [CORRECTED 16 Nov 2026: printed +10001 (page 9); earlier transcription had -10001]
                   G(La:Si:Si) = -40016.0024 - 8.0032*T
                   L(La:Si,Fe:Si,Fe) = -171189.014 + 10*T  (and equalities as tau3)
tau5 (LaFeSi)      G(La:Fe:Si) = +48500 - 13.6*T       [CORRECTED 16 Nov 2026: printed +48500 (page 9); earlier transcription had -48500]
                   G(La:Si:Fe) = -20002 - 5.005*T
                   G(La:Fe:Fe) = 15000 + 15*T
                   G(La:Si:Si) = 8000.800 - 17.50175*T
                   L(La:Si,Fe:Si,Fe) = -13000 + 5*T  (and equalities)
tau6 (La3Fe2Si8*)  G(La:Fe:Si) = -67855 - 11*T
                   G(La:Si:Fe) = 20004 + 10*T
                   G(La:Fe:Fe) = 20008.012 - 15*T
                   G(La:Si:Si) = -49009 - 20*T
                   L(La:Si,Fe:Si,Fe) = -65006.5 + 10*T  (and equalities)   [CORRECTED 16 Nov 2026: printed -65006.5 (page 9); earlier transcription had +65006.5]
```

## Phase name map (Feng 2023 → Niitsu 2012, our registry)
| Feng | Niitsu/registry | identity |
|---|---|---|
| tau1 | tau1 | cubic La(Fe,Si)13 (NaZn13) — the magnetocaloric phase |
| tau2 | tau2 | tetragonal La(Fe,Si)13 (Ce2Ni17Si9) |
| tau3 | — | LaFe2Si2-region ternary (Feng's labelling differs from Niitsu's) |
| tau4 | LaFeSi2 | CeNiSi2-type |
| tau5 | LaFeSi | Cu2Sb-type |
| tau6 | La3Fe2Si8 | AlB2-type region |
| B2, D03 | — | Fe–Si ordered phases (Fe-rich corner only) |

Note: Feng's τ3–τ6 numbering is NOT the same as Niitsu's τ1/τ2 — only
τ1 and τ2 (the two La(Fe,Si)13 structures) carry across directly. The
registry's `phase_registry.csv` keeps the identities; this map is the
bridge for the audit overlay.
