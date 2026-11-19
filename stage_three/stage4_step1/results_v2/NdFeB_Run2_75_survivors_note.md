# Note: the Nd–Fe–B "75 survivors" run (27 Oct 2026) — result file not retained

**What it was.** Run 2 of the Nd–Fe–B edge check on 27 Oct 2026 returned 75 of 84 surviving combinations instead of the released 78 of 84. The cause was a race condition: a fixed merged-TDB filename was shared by 8 parallel workers, so a worker could read a file written by another. The run was therefore invalid, not a result about Nd–Fe–B. The code was changed afterwards (unique merged filename per combination) and the published count is **78/84**. The episode is recorded in the daylog of 27 Oct 2026 and reported in the paper as a finding (silent failure of the parallel merge step).

**What exists.** The released results (78/84) and the fixed code. **The CSV of the 75-survivor run was not kept** (the run was judged invalid at the time and the file was not archived); it cannot be reconstructed without deliberately reintroducing the bug, which was judged not worthwhile.

**How to read the numbers.** 78/84 is the Nd–Fe–B survival count of the final protocol. 75/84 appears only in the daylog and paper text as the symptom of the race condition. It is not comparable to the 78/84 and not related to the separate Al–Fe–Mn pycalphad 0.11.2 / 0.12.0 difference (78/144 vs 75/144, caused by ordered/disordered label ties).

*(19 Nov 2026. Edit the details against the daylog if its wording differs.)*
