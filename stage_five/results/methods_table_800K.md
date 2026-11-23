Stage 5 screening at 800 K. ΔG in kJ/mol-atom relative to SER.

| System | Target (atomic fractions) | Merge priority | Survivors | Gates | ΔG_f*(T) median [5%, 95%] kJ/mol-atom | Competing assemblage | SISSO entry (provenance) | ΔG_f^SISSO(T) kJ/mol-atom | Margin kJ/mol-atom | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| B-Fe-Nd (Nd2Fe14B) | FE 0.824, ND 0.118, B 0.059 | FE-ND > B-FE > B-ND | 78/84 (93 %) | PASS (G1 ok, G2 ok; lineages/edge 3/7/4) | -8.79 [-9.20, -8.40] | FE17ND2+ND2B5+NDB4_D1E | not run (needs a SISSO report / MP_API_KEY) | — | — | — |
| Al-Fe-Mn (Al16Fe5Mn5) | AL 0.615, FE 0.192, MN 0.192 | AL-FE > AL-MN > FE-MN | 313/594 (53 %) | PASS (G1 ok, G2 ok; lineages/edge 10/8/4) | -25.51 [-26.52, -24.06] | AL5FE2+BCC_A2 | not run (needs a SISSO report / MP_API_KEY) | — | — | — |
| Fe-La-Si (La7.1Fe82.1Si10.8) | FE 0.821, SI 0.108, LA 0.071 | FE-SI > FE-LA > LA-SI | 16/20 (80 %) | PASS (G1 ok, G2 ok; lineages/edge 4/2/2) | -17.78 [-19.00, -16.47] | BCC_A2+LA5SI4 | not run (needs a SISSO report / MP_API_KEY) | — | — | — |

Notes
- ΔG_f*: distribution over the surviving combinations of the open binary assessments (competing-assemblage energy at the target composition, binaries only, no ternary phase).
- Merge priority: the first file wins on conflicting parameters, so the edge order can change the survivor count; the order is part of the specification.
- Gate parameters are Stage-5 engineering defaults unless registered otherwise (preregistered=False).
- SISSO model error included in the verdict: 0 kJ/mol-atom (none: the CALPHAD band alone is far narrower than the SISSO error).

Per-system provenance (frozen reports): specification hash, hash of the accepted TDB files, engine rules version
- B-Fe-Nd (Nd2Fe14B): spec 316cc2dbc860, TDB collection 0fd3094fd0f3, stage5-engine/edge-rule-v2/fix1-2026-11-23
- Al-Fe-Mn (Al16Fe5Mn5): spec a414f295c1a6, TDB collection 1c921de583c0, stage5-engine/edge-rule-v2/fix1-2026-11-23
- Fe-La-Si (La7.1Fe82.1Si10.8): spec f69a41acac84, TDB collection 262b28f17c5a, stage5-engine/edge-rule-v2/fix1-2026-11-23
- Al-Fe-Mn (Al16Fe5Mn5): audit-excluded files: FeMn-19Big-3g.tdb, FeMn-23Wal-3g.tdb; files that fail the edge check in every combination: FeMn-89Lee.tdb
- Fe-La-Si (La7.1Fe82.1Si10.8): audit-excluded files: none; files that fail the edge check in every combination: FeSi-91Lac-LB.tdb
