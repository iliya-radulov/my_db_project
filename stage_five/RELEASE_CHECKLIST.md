# Release checklist: Stage 5 contract 1.0 (tag `v5.0-stage5`)

Nothing here is done by the tooling; each step is yours to run. The release publishes a snapshot (GitHub release;
Zenodo archives it if the Zenodo–GitHub link is on for the repository, as for the earlier releases).

1. **Merge** the Stage 5 PRs (tabs, freeze) and pull: `git checkout master && git pull`.
2. **Optional, recommended: export the Fe–La–Si desktop run** as a frozen file (needs `MP_API_KEY`, `SGTE_BINARY_DIR`)
   and rebuild the table; commands are at the end of `results/README.md`. Add the new file to `results/SHA256SUMS`
   (`sha256sum results/*.json > results/SHA256SUMS`). The note (Table 2) currently quotes this run from the
   application output (database run 11).
3. **Record the desktop environment** for the SISSO side and paste the output into §7 of `TECHNICAL_NOTE.md`:
   `pip show pymatgen mp-api pycalphad | grep -E "Name|Version"`.
4. **Check the tests** once more: `pytest stage_five/tests -q` (and, with `SGTE_BINARY_DIR` set, `RUN_SLOW=1`).
5. **Set the release date** in `CITATION.cff` (`date-released`) to the day of publication; the `version` is already
   `v5.0-stage5`. The `doi:` line still holds the Track A record; after the release you may replace it by the
   concept DOI that Zenodo shows for the whole series.
6. **Tag and release:**
   ```bash
   git tag -a v5.0-stage5 -m "Stage 5 screening, contract 1.0"
   git push origin v5.0-stage5
   ```
   then publish a GitHub release for that tag (title "Stage 5 screening, contract 1.0"; description: the first
   paragraph of the technical note and the link to `stage_five/CONTRACT.md`).
7. **After Zenodo has archived it:** copy the new DOI into the note header and `CITATION.cff` in a follow-up commit
   (the archived snapshot keeps the text without the DOI; that is normal). The PDF of the note
   (`TECHNICAL_NOTE.pdf`) is part of the archived repository snapshot; upload it to the Zenodo record as an
   additional file if you want it listed separately.
8. **Server:** migrations 009–012 are applied (`\dt alloy_lab.calphad*`, `\dv alloy_lab.v_stage5*`).
