# Stage 5 frozen ensemble reports and methods table (23 Nov 2026)

The three CALPHAD binary-ensemble reports behind `methods_table_800K.md` / `.tsv`. They are
frozen: the table is generated from these files only, and `SHA256SUMS` fixes their content.

| file | system, target | merge priority | survivors | 800 K ΔG_f* median [5 %, 95 %] |
|---|---|---|---|---|
| `ensemble_B-Fe-Nd_Nd2Fe14B.json` | Nd2Fe14B | FE-ND > B-FE > B-ND | 78 / 84 | −8.79 [−9.20, −8.40] |
| `ensemble_Al-Fe-Mn_Al16Fe5Mn5.json` | Al16Fe5Mn5 (0.6154, 0.1923, 0.1923) | AL-FE > AL-MN > FE-MN | 313 / 594 | −25.51 [−26.52, −24.06] |
| `ensemble_Fe-La-Si_La7.1Fe82.1Si10.8.json` | La7.1Fe82.1Si10.8 | FE-SI > FE-LA > LA-SI | 16 / 20 | −17.78 [−19.00, −16.47] |

**Code:** `stage_five/general_ensemble.py` as of commit `1fe56e9` (master after PR #28; the engine file is
unchanged since). pycalphad 0.11.2. Binary files: the SGTE binary collection (`SGTE_BINARY_DIR`); the hash of the
accepted files is stored in each report (`tdb_collection_sha256`), the specification hash in `spec_sha256`,
the rules version in `engine_rules_version`.

**Commands** (from the repository root, `SGTE_BINARY_DIR` set, 3 workers):

```bash
python stage_five/general_ensemble.py --elements FE ND B  --comp 0.8235 0.1176 0.0588 --workers 3 --out ensemble_B-Fe-Nd_Nd2Fe14B.json
python stage_five/general_ensemble.py --elements AL FE MN --comp 0.6154 0.1923 0.1923 --workers 3 --out ensemble_Al-Fe-Mn_Al16Fe5Mn5.json
python stage_five/general_ensemble.py --elements FE SI LA --comp 0.821 0.108 0.071   --workers 3 --out ensemble_Fe-La-Si_La7.1Fe82.1Si10.8.json
python stage_five/methods_table.py --system "B-Fe-Nd (Nd2Fe14B)=ensemble_B-Fe-Nd_Nd2Fe14B.json" \
    --system "Al-Fe-Mn (Al16Fe5Mn5)=ensemble_Al-Fe-Mn_Al16Fe5Mn5.json" \
    --system "Fe-La-Si (La7.1Fe82.1Si10.8)=ensemble_Fe-La-Si_La7.1Fe82.1Si10.8.json" \
    --temp 800 --out methods_table_800K.md --tsv methods_table_800K.tsv
```

## Notes on the numbers
- **Merge priority matters.** The first file wins on conflicting parameters. Nd–Fe–B with the alphabetical edge order
  (B-Fe, B-Nd, Fe-Nd) gives 52 / 84 on the same data; with the order above 78 / 84 (the Stage 4 reference). Fe–La–Si
  gives the same 16 / 20 and the same band with FE-LA first (checked, not committed).
- **Fe–La–Si:** FeSi-91Lac-LB fails the edge check in all 4 of its combinations (rule v2); Track C's older
  20-combination band (`wp4b_descriptor.py band`) included it without an edge check.
- **Al–Fe–Mn:** two third-generation FeMn files are excluded by the audit; FeMn-89Lee fails the edge check in every
  combination. The same engine run on the 61.6/19.2/19.2 at.% composition stored in the server database gives the
  same survivor count (313 / 594) and a median of −25.503 (here −25.510 for 0.6154/0.1923/0.1923).
- The Nd₂Fe₁₄B entry of the server database (run 1, 52 / 84) was made with the earlier alphabetical edge order and
  is superseded by the 78 / 84 report.
- The SISSO columns of the table say "not run": no Materials Project key was available. They are filled from a SISSO
  report with `methods_table.py --system "LABEL=ensemble.json,sisso.json"`; nearest-prototype rows are marked †
  (indicative, not a stability verdict).
