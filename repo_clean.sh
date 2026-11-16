#!/usr/bin/env bash
# repo_clean.sh (16 Nov 2026) - untrack derived/paper-derived/co-author files in the PUBLIC repo. Local files are NOT deleted (git rm --cached).
# Usage:  bash repo_clean.sh        -> dry run (prints what would be untracked)
#         bash repo_clean.sh apply  -> does it (then you review `git status` and commit yourself)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
MODE=${1:-dry}
# 1. .gitignore additions (D10: reports -> doc repo; outputs/derived/paper tables -> data/ or ignored)
read -r -d '' ADD <<'EOF' || true

# --- added 16 Nov 2026 (Layer 2 cleaning, D10) ---
*.pkl
*.zip
stage_three/cache/
stage_three/stage4_step1/diagnostics/*.zip
stage_three/stage4_step1/results_v2/merged_tdbs/
stage_three/stage4_step1/results_v2/*.csv
stage_three/FENDB_merged_v4.tdb
stage_four/calphad_lafesi/tdb_build/*.tdb
stage_four/mce_nims/test_set_edx.csv
stage_four/mce_nims/SNAPSHOT_v1.pdf
stage_three/stage4_step1/backup/
stage_three/rag_benchmark_questions*.csv
EOF
# 2. tracked files to untrack
LIST=$( { git ls-files | grep -E '\.(pkl|zip)$' ; git ls-files | grep -E '\.tdb$'
  git ls-files | grep -E '^stage_four/calphad_lafesi/data_(feng2023|niitsu2012)/.*\.csv$'   # .md stay tracked (D12 exception)
  git ls-files | grep -E '^stage_four/mce_nims/(test_set_edx\.csv|SNAPSHOT_v1\.pdf)$'
  git ls-files | grep -E '^stage_three/stage4_step1/(backup/|results_v2/[^/]*\.csv$)'
  git ls-files | grep -E '^stage_three/(rag_benchmark_questions.*\.csv|results_v2_run.*\.log|advisor_app/grid_lookup_selfcheck\.log)$' ; } | sort -u )
echo "files to untrack: $(echo "$LIST" | grep -c .)"; echo "$LIST" | sed -E 's#(.*)/[^/]*$#\1#' | sort | uniq -c | sort -rn | head -20
if [ "$MODE" != apply ]; then echo "(dry run - nothing changed)"; exit 0; fi
# only append patterns not already present (you changed .gitignore yourself)
printf '%s\n' "$ADD" | while IFS= read -r l; do [ -z "$l" ] || [[ "$l" == \#* ]] || grep -qxF "$l" .gitignore || echo "$l" >> .gitignore; done
echo "$LIST" | xargs -d '\n' git rm --cached -q --
# 3. private-network details in tracked text (README, SNAPSHOT_v1.tex)
sed -i -E 's/192\.168\.[0-9]+\.[0-9]+/<server-ip>/g' README.md stage_four/mce_nims/SNAPSHOT_v1.tex
echo "done. Review: git status --short | head -50 ; then commit."
