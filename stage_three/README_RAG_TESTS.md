# RAG tests — how to run them (19 Oct 2026)

Goal: measure how well the RAG advisor finds the right passage, fix the two problems found
on 6 Oct (MiniLM sees only the first 256 tokens of each chunk; it is English-only), and
measure again. The before/after numbers decide whether the RAG part goes into paper 3.

All scripts only **read** the existing collections. The re-index writes **new**
collections with the suffix `_bge`; the originals stay untouched.

## 0. Setup (ML desktop)

```bash
cd ~/Documents/github/active/my_db_project/stage_three
# copy the 4 files of this kit here, next to chroma_db/
source .venv/bin/activate
ollama pull bge-m3            # ~1.2 GB, for step 2
```

## 1. Diagnostics (a few minutes)

```bash
python rag_diagnostics.py --books ~/Desktop/new_books/<folder>=<collection>  # repeat --books per folder
```
Saves `rag_diagnostics.json`: chunks per collection, how much of each chunk MiniLM never
sees, share of Russian / garbled chunks, books with no chunks, 40-character name collisions.

## 2. Re-index with bge-m3 (runs in the background)

Quick speed test on the smallest collection first:
```bash
python rag_reindex.py --collections phase_stability
```
Then everything else in the background (resumable — just run it again if interrupted):
```bash
nohup python rag_reindex.py > reindex.log 2>&1 &
tail -f reindex.log
```
Same chunks, same IDs, only the embedding model changes → a clean comparison.

## 3. Write the questions (while step 2 runs)

Fill `rag_benchmark_questions.csv`, **20–30 questions**:

| column | what to put |
|---|---|
| `question` | as you would ask it |
| `collection` | `phase_stability`, `synthesis` or `magnetic` |
| `gold_source` | the PDF file name (a unique part of it is enough) |
| `gold_phrase` | **6–10 consecutive words copied from the PDF text** of the answering passage |
| `kind` | e.g. `phases`, `processing`, `magnetic`; **`out_of_corpus`** for questions the books cannot answer |
| `source_language` | `en` or `ru` |

Tips: copy the phrase from the *same* PDF that was indexed (for scanned books, the OCR'd
file, so OCR errors match); avoid formulas, sub/superscripts and phrases that cross a page
break. Include **a few Russian-only answers** and **3–5 out-of-corpus questions**.
Rows still starting with `<` are skipped.

Check the phrases before the real run:
```bash
python rag_benchmark.py --tag check
```
`phrase_not_found` → fix the phrase, or it is a real indexing loss (note it!).
`source_not_indexed` → that book is not in the collection (OCR or name collision).

## 4. Baseline run (MiniLM, current system)

```bash
python rag_benchmark.py --tag minilm --generate
```
Generation: qwen2.5:14b, temperature 0, top-4 chunks, prompt as in `rag_query.py`.

## 5. After the re-index (bge-m3)

```bash
python rag_benchmark.py --tag bge --suffix _bge --generate
```
Optional, both models without collection routing: add `--route all` with tags `minilm_all`, `bge_all`.

## 6. Grade the answers

For each run, fill `benchmark_runs/<tag>/grading.csv`: correct (yes/partly/no),
faithful to the retrieved text (yes/no), refused (yes/no, for out-of-corpus).
`answers.md` shows each answer with the context it got; numbers in an answer that do not
appear in that context are listed under it.

## 7. Send back

- `rag_diagnostics.json`
- the `benchmark_runs/` folder (zip)
- `stage_three/synthesis_rag.py` and the lines of `alloy_desktop_v2.py` that call it
