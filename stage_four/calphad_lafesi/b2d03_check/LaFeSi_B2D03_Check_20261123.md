# La–Fe–Si: B2/D0₃ ordering check (23 Nov 2026)

Environment: pycalphad 0.11.2, numpy 2.5.3, Python 3.13. Inputs: FeSi-12Ohn.tdb, FeLa-23Su.tdb, LaSi-10Zho.tdb (user's SGTE binary collection); builder build_merged_tdb_fixed.py (sha256 a8cef9fe…8ad4, both copies identical), run with the three files above (SGTE_BINARY_DIR set).

## Files in the folder b2d03_check (sha256 in b2d03_hashes.txt)
- 38865d71904c3e64  D_ordering_effect.csv
- 77b7926cc43f4926  FeSi-12Ohn_pycalphad_VA3.tdb
- 3386890603e8887a  add_order.py
- 1b3c762b894229b8  d_ordering_effect.py
- f3229d93ed9b04e3  d_point.py
- 1aa10c438753450d  fesi_order_check.py
- 41b778abd0391537  table6_check.py
(The merged and ordered TDB files are not distributed; the scripts recreate them.)

## What was done
1. Reproduced the merged build: D at La(Fe11.5Si1.5), 1373 K: FeSi-12Ohn 1760.3, FeSi-17Cui 2068.9 J/mol-atom (ledger: 1762 and 2069). The 15 conditions of D_self.csv are reproduced to about 1 J/mol-atom by the 12Ohn merge (e.g. 1120.7 / 1554.7 / 2697.1 vs 1120.7 / 1554.8 / 2697.7).
2. Table 5 Fe–Si bcc parameters are Ohnuma 2012 (= FeSi-12Ohn): L0 −180000+47.8494T, L1 −32198, L2 +15882.8, Tc 504, β 1.07 match exactly. Table 5 minus FeSi-17Cui at 1373 K: −202, −422, −614, −658, −623 J/mol-atom at x(Si) = 0.02, 0.05, 0.10, 0.15, 0.20; this explains the 203–662 J/mol-atom difference of draft §2.1 (comparison with the Cui and Jung file, not a refit).
3. D0₃ energies not valued in Table 5: GB32FESI = 0.0 in 12Ohn; ΔG(D0₃, FeSi₃) = GBFE3SI (−3350) in 12Ohn but GBFESI3 = 0.0 in 17Cui. (My statement in chat that the two are equal holds for 12Ohn only.) Matters only on the Si-rich side.
4. pycalphad refuses the 4SL phase of the file (vacancy ratio 1 against 3 of the disordered A2). Workaround: ratio 3 in a copy (FeSi-12Ohn_pycalphad_VA3.tdb, one line changed). Ordering contribution to Gm(bcc) vs A2 at 1323–1473 K: 0 for x(Si) up to 0.15; at 0.20: −108.9 / −78.7 / −53.0 / −32.1 (2SL) at 1323 / 1373 / 1423 / 1473 K; 4SL gives −108.8 / −78.7 / 0 / 0 (difference not explained).
5. Ordered phases (A2_BCC, B2_BCC, BCC_4SL, no La) added to the merged 12Ohn build (add_order.py).
6. D with and without ordering at the 15 conditions (D_ordering_effect.csv): identical at 14, +3.7 J/mol-atom at x = 1.4, 1200 °C (assemblage differs: LaSi2 + fcc with the ordered phases present vs bcc without; not followed up). Si content of the bcc phase in the competing assemblage: 3.7–8.2 at.% (none at x = 1.2: fcc).
7. Table 6, 1373 K (table6_check.py): #19 La4Fe73Si23 no ordering: A2 + τ2; with: B2 + τ2 (experiment τ2 + B2; Feng τ2 + B2). #20 La3Fe71Si26: no ordering A2 + τ2; with: BCC_4SL (site fractions Fe/Si: 0.976/0.024, 0.976/0.024, 0.31/0.69, 0.80/0.20, i.e. sublattices 3 and 4 differ) + τ2 (experiment D0₃ + τ2; Feng τ2 + B2). #12 La2Fe66Si32: no ordering A2 0.115 + Fe2Si 0.605 + τ2 0.28; with: B2 0.672 + Fe2Si 0.048 + τ2 0.28 (experiment Fe2Si + τ2; Feng Fe2Si + τ2 + D0₃).

## Caveats
- Three single compositions, not the 21-alloy benchmark (needs τ3–τ6).
- 2SL and 4SL models differ at ≥ 1423 K at 20 at.% Si.
- Registered ρ not recomputed. D unchanged within 3.7 J/mol-atom.
- mc_fe files (MatCalc 2.062: no La–Si, no 1:13 phases, 2SL B2 only; the "2.059.pycalphad" upload is a saved GitHub page; the fecocrnbti file is a cut-down subset) cannot serve as a base.
- Stray file: my first builder run wrote merged_FeLa-23Su_LaSi-10Zho_FeSi-17Cui.tdb into the uploads folder; moved to my working directory.
