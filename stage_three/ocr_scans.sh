#!/usr/bin/env bash
# ocr_scans.sh — OCR the 8 scanned books of the `magnetic` folder that have no text layer.
#
# Reads from  ~/Desktop/new_books/magnetic/   (originals are never changed)
# Writes to   ~/Desktop/new_books/ocr_done/   (same file names)
# Russian books: -l rus+eng (English terms and formulas inside); Bozorth: -l eng.
# Resumable: books already in ocr_done/ are skipped. After each book, the number of
# words pypdf can now extract from the first 20 pages is printed as a quick check.
#
# Usage (stage_three/, RAG venv active):  nohup bash ocr_scans.sh > logs/ocr_scans.log 2>&1 &

set -u
IN="$HOME/Desktop/new_books/magnetic"
OUT="$HOME/Desktop/new_books/ocr_done"
JOBS=8
mkdir -p "$OUT"

BOOKS=(
  "R_M_Bozorth_American_Society_for_Metals_et_al.pdf"
  "Nagaev E.L. -- Magnetiki so slozhnymi obmennymi vzaimodejstviyami.pdf"
  "Turov E.A_Fizicheskie svojstva magnitouporyadochennyh kristallov.pdf"
  "Uajt R. Kvantovaja teorija magnetizma.pdf"
  "Vonsovskij S.V. Magnetizm.pdf"
  "Ашкрофт Н., Мермин Н. Физика твердого тела (том 1).pdf"
  "Ашкрофт Н., Мермин Н. Физика твердого тела (том 2).pdf"
  "Барьяхтар_В.Г.,_Иванов_Б.А._В_мире_магнитных_доменов._.pdf"
)

echo "OCR start $(date '+%F %T') — $(ocrmypdf --version 2>/dev/null || echo 'ocrmypdf NOT FOUND')"
for f in "${BOOKS[@]}"; do
  src="$IN/$f"; dst="$OUT/$f"
  if [ ! -f "$src" ]; then echo "MISSING: $f"; continue; fi
  if [ -s "$dst" ]; then echo "already done: $f"; continue; fi
  case "$f" in R_M_Bozorth*) lang="eng" ;; *) lang="rus+eng" ;; esac
  echo "---- $(date '+%T')  $f  (language $lang)"
  if ocrmypdf --skip-text --jobs "$JOBS" --output-type pdf -l "$lang" "$src" "$dst"; then
    python3 - "$dst" <<'PY'
import sys
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
n = sum(len((p.extract_text() or "").split()) for p in r.pages[:20])
print(f"     OK: {len(r.pages)} pages, {n} words in the first 20 pages")
PY
  else
    echo "     FAILED: $f"
    rm -f "$dst"
  fi
done
echo "OCR end $(date '+%F %T')"
ls -la "$OUT"
