# Binary collection — validation (Track A lessons applied)

Source: `iliya-radulov/projects_documentation` → `AlloyDB/Data/tdb/sgte_binary/`.
The La–Fe–Si subset: 2 FeLa × 2 LaSi × 5 FeSi = **20 ternary combinations**.

## Feng's cited binaries are all present
Feng et al. (2023) optimised the ternary on: La–Si = Zhou 2010 [20],
Fe–Si = Cui 2017 [23], La–Fe = Su 2022 [24]. The collection has
**`LaSi-10Zho`, `FeSi-17Cui`, `FeLa-23Su`** — so a faithful merged
reconstruction (ternary params on the exact cited binaries) is possible,
not just the self-contained one.

## Lessons 1 & 2 — all pass (`check_binaries.py`)
- **Standalone compute:** all 9 binary files load and compute in pycalphad.
- **3rd-generation screen:** none use Einstein/3rd-gen unaries — including
  the 2020s files `FeLa-23Su`, `LaSi-20Xu`, `FeSi-23Wit`. All 2nd-gen SGTE.
- **Unary consistency (numeric, not text):** GHSERLA, GHSERFE, GHSERSI each
  take **one distinct value** across every file (−119873.4 / −80562.9 /
  −56966.0 at 1500 K), and match the self-contained TDB's unaries exactly.

## Faithfulness of the self-contained TDB vs the real cited binaries
Liquid Gibbs energy of mixing at x=0.5, 1873 K (`crosscheck_binaries.py`):

| system | real cited binary | my typed Feng T5 | Δ |
|---|---|---|---|
| La–Si (LaSi-10Zho) | −91932.3 | −91932.3 | **exact** |
| La–Fe (FeLa-23Su) | −4948.5 | −4948.5 | **exact** |
| Fe–Si (FeSi-17Cui) | −37367.1 | −36828.1 | −539 (1.4%) |

So the self-contained reconstruction is **exactly faithful for La–Si and
La–Fe**, and within 1.4% on the Fe–Si liquid (Feng's Table 5 slightly
rounds/simplifies Cui's Fe–Si liquid RK terms). The real `FeSi-17Cui` also
carries the full Fe–Si **B2/D03 ordering** (A2_BCC/B2_BCC/BCC_4SL) that the
self-contained build deferred.

## Next: merged reconstruction + WP4 band
- Merge Feng's 3 cited binaries + the typed ternary fragment → the exact
  faithful TDB, with B2/D03. Validate against the same acceptance test.
- WP4 uncertainty band: build all 20 merged ternaries (swap the binaries)
  and compute the τ1 formation driving force ΔG* at La(Fe11.5Si1.5),
  T_anneal — the honest band on the descriptor.
