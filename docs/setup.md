# Setup

## Stack

- **PostgreSQL**, running in Docker (container name `postgres`).
- **Metabase**, also in Docker, pointed at a `metabase` database inside the
  same Postgres instance (not the default embedded H2 database — worth
  remembering, since it's easy to assume Metabase's internal data lives
  somewhere else).
- **Python venv** per project directory. Two exist side by side:
  `my_db_project` (the main application) and, earlier on,
  `my_lookup_project` (used to prototype the literature-database lookups
  before folding them into the main project).

## Project layout (post-Stage-1 reorganization)

After Stage 1 was functionally complete, the flat file layout was
reorganized into a proper folder structure. A full project backup
(`my_db_project_backup_<date>`) was taken immediately before starting —
worth doing before any reorganization like this.

```
my_db_project/
├── alloy_desktop_complete.py   # stable GUI entry point — the one that works
├── alloy_desktop_v2.py         # Stage 2 sandbox/testing, NOT the stable app
├── db_config.py, .env, .gitignore
├── data/
├── stage_one/
│   ├── alloy/          # core logic: calculator, db interface, screening, CLI entry
│   ├── integrations/   # per-instrument DB integration (xrd/vsm/sem)
│   ├── lookup/         # the three literature-database clients + dedup
│   ├── parsers/        # the actual file-format parsers
│   ├── tools/          # data sorter, test interface, plot_v1.py (see note below)
│   └── outdated/       # every earlier iteration, archived rather than deleted
├── stage_two/
│   └── tools/          # plotting/analysis tooling under active development —
│                        # not yet documented here, see the Stage 2 project
└── stage_three/         # reserved, empty for now
```

**Versioning convention**: every active file under `stage_one/` was reset
to `_v1` on reorganization — this marks "the Stage 1 stable version,"
not "the first version ever written" (most of these went through several
named iterations first; see each component's page in this `docs/` folder
for that history, still preserved in `stage_one/outdated/`). Going
forward, a higher version number on a given file (e.g. `_v2`) signals
active Stage 2 development on that specific piece, while `_v1` remains
the known-working Stage 1 baseline. The same idea applies to the GUI at
the top level: `alloy_desktop_complete.py` is the stable one,
`alloy_desktop_v2.py` is where Stage 2 GUI work happens — don't confuse
the two, and don't edit `_complete.py` while experimenting.

**Note on `stage_one/tools/plot_v1.py`**: the unified XRD/VSM/SEM
plotting module was originally built during Stage 1, but conceptually
belongs to the ongoing plotting/analysis tooling work now happening in
`stage_two/tools/` (as `plot_xrd_v2.py`). To keep the stable Stage 1 app
from depending on code inside `stage_two/` (which will keep changing), a
dedicated copy was kept at `stage_one/tools/plot_v1.py`, and
`alloy_desktop_complete.py` imports from there specifically. The two
copies are expected to diverge over time — this is intentional, not
duplication to clean up later.

**Cross-folder imports — confirmed working approach**: files across
`stage_one/alloy/`, `stage_one/lookup/`, `stage_one/integrations/`, and
`stage_one/tools/` reference each other using package-relative imports
(e.g. `from stage_one.lookup.mp_lookup_v1 import lookup`). This works
correctly for `alloy_desktop_complete.py` itself, since it sits at the
project root and Python adds the script's own directory (the root) to
its search path automatically. It does **not** work automatically for
entry-point scripts that sit *inside* a nested folder, like
`stage_one/alloy/alloy_entry_full_v1.py` — running that one directly
(`python stage_one/alloy/alloy_entry_full_v1.py`) only puts
`stage_one/alloy/` itself on the path, not the project root, so the
`stage_one.*` imports fail with `ModuleNotFoundError`. Two working fixes,
either is fine:
- Run as a module from the project root: `python -m
  stage_one.alloy.alloy_entry_full_v1`
- Or add this at the top of the entry-point file, before its `stage_one`
  imports, so it works regardless of how/where it's launched:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
  ```

`__init__.py` files were not strictly required for any of this (Python 3
treats plain folders as namespace packages automatically), though adding
them is a reasonable future cleanup for clarity. The `sys.path.insert`
fix was applied consistently to every affected script inside nested
`stage_one/` folders (`alloy_entry_full_v1.py`, `xrd_integration_v1.py`,
`vsm_integration_v1.py`), so all of them run correctly via direct path
invocation, not just via `-m`.

## Credentials: the `.env` migration

The Postgres password was originally hardcoded in plaintext in
`db_config.py`. This was found (and initially only half-fixed — a
commented-out copy of the password was missed by a first grep pass) and
properly resolved:

1. `pip install python-dotenv`
2. A `.env` file at the project root:
   ```
   POSTGRES_PASSWORD=...
   POSTGRES_USER=postgres
   POSTGRES_DB=alloy_lab
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```
3. `.gitignore` created **before** the repo's first commit (`.env`,
   `venv/`, `__pycache__/`, `*.pyc`, `*.backup`, `*.messy`, `.DS_Store`),
   so the password never entered git history at all — the best possible
   timing, since the project hadn't been pushed anywhere yet.
4. `db_config.py` rewritten to read from environment variables via
   `os.environ`, using `os.environ['POSTGRES_PASSWORD']` (no default) so
   a missing `.env` fails loudly rather than silently connecting with a
   wrong/empty password.

The Materials Project API key is kept **outside the project directory
entirely** (in a separate `back_up/API/` folder), read via a small
`get_api_key()` helper — deliberately not even inside the project's own
`.env`, for extra separation.

## Going public: the `data/` folder incident

Before the repository was made public, a real problem surfaced that's
worth documenting precisely, since it's a genuinely easy mistake to
repeat. `data/` **was** already listed in `.gitignore` — but ~1446 files
under it (raw XRD/VSM/SEM data, and, more seriously, unpublished
manuscript drafts, a copyrighted publisher PDF, and internal institutional
documents) were still fully tracked in git, because they had been
committed **before** the `.gitignore` rule was added.

**The lesson, stated plainly: adding a path to `.gitignore` only stops
new files from being tracked — it does nothing for files already
committed.** `git rm -r --cached data/` would have stopped tracking going
forward, but the files would still be recoverable from every earlier
commit. The actual fix needed history rewriting:

```bash
pip install git-filter-repo
git clone <repo-url> repo-cleanup   # a FRESH clone, not the working copy --
                                     # this only touches git history, never
                                     # your real files on disk
cd repo-cleanup
git filter-repo --path data --path stage_two --path stage_three --invert-paths
git remote add origin <repo-url>    # filter-repo removes the remote as a
                                     # safety check -- re-add it deliberately
git push origin --force --all
git push origin --force --tags
```

Verified afterward with `git log --all -- data/` returning nothing, and
`.git` shrinking from 792 MB to 1.1 MB. The repository was kept **private**
for the entire cleanup window, only flipped back to public once the
history rewrite was confirmed clean — a mistake like this is only a
near-miss if caught before wide exposure, not after.

## Known gotcha: matching venvs to scripts

Several packages (`optimade[http-client]` for OQMD/Alexandria, `aflow`,
`customtkinter`, `psycopg2-binary`) were originally installed and tested
in whichever venv happened to be active for prototyping
(`my_lookup_project`), then needed a separate `pip install` when the same
script was later imported into the main project's venv
(`my_db_project`). Easy to lose track of which venv has which package —
worth checking `pip list` in the *actual* venv about to run a script
before assuming a dependency is present.

## Metabase

Runs at `http://localhost:3000`. Connected to the `alloy_lab` Postgres
database for browsing/dashboards. A separate troubleshooting session
resolved a login/container-instability issue — root cause turned out to
be a combination of a stale-but-still-valid browser session cookie and
some Docker container/port-mapping confusion (a leftover container from
a port mixup), not any actual data loss. Two follow-ups from that session
worth keeping in mind:
- Set a memorable Metabase account password (Account settings → Password)
  rather than relying on the session cookie indefinitely.
- Consider `restart: unless-stopped` on the Postgres/Metabase containers
  so a host restart doesn't silently take them down.

## Quick reference

```bash
# Start everything
cd /Users/r/Documents/Projects/my_db_project
source venv/bin/activate
docker start postgres

# Run the desktop GUI
python alloy_desktop_complete.py

# Run the CLI workflow (works directly -- alloy_entry_full_v1.py has a
# sys.path.insert at its top that adds the project root, see Project
# Layout above for why that's needed)
python stage_one/alloy/alloy_entry_full_v1.py

# Direct DB access
docker exec -it postgres psql -U postgres -d alloy_lab

# Verify no plaintext password anywhere before committing
grep -rn "<old password>" *.py
```
