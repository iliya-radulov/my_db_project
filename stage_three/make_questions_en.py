"""
make_questions_en.py — the 7 Russian-source benchmark questions, asked in English (24 Oct 2026).

Test: does bge-m3 find the Russian passages when the question is in English? (The advisor's own
queries are always English.) Reads YOUR current rag_benchmark_questions.csv and writes
rag_benchmark_questions_en.csv with only these 7 rows: same id, gold book and gold phrase
(still Russian), only the question text replaced. The original Russian wording goes into the new
column "question_other": with --bilingual, the extra passage is searched among Russian chunks
with it (as the advisor does with its Russian query template). Your original file is not changed.

Usage (stage_three/, RAG venv):
    python make_questions_en.py
    python rag_benchmark.py --tag v2_bge_en --set _v2 --suffix _bge --questions rag_benchmark_questions_en.csv --generate --context
Compare with the Russian versions in benchmark_runs/v2_bge/ (same index, same settings).
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "rag_benchmark_questions.csv", HERE / "rag_benchmark_questions_en.csv"

EN = {
    "q03": "What is magnetostriction related to?",
    "q08": "mechanical concept of the driving forces of sintering",
    "q16": "A small amount of extremely pure iron was made by Thompson and Cleaves",
    "q19": "the best crystalline soft magnetic materials.",
    "q21": "What are the conditions for the appearance of diffraction maxima related to?",
    "q26": "What do the optimal domain sizes in a sample correspond to?",
    "q36": "What does the cluster scheme of melting and crystallization describe?",
}

text = SRC.read_text(encoding="utf-8-sig")
header = text.splitlines()[0]
sep = ";" if header.count(";") > header.count(",") else ","
rows = list(csv.DictReader(text.splitlines(), delimiter=sep))
fields = list(rows[0].keys()) + ["question_other"]
out = []
for r in rows:
    if r["id"] in EN:
        print(f"{r['id']}: {r['question'].strip()}\n   -> {EN[r['id']]}")
        r["question_other"] = r["question"].strip()
        r["question"] = EN[r["id"]]
        r["notes"] = (r.get("notes") or "") + " [English version of the Russian question, 24 Oct 2026]"
        out.append(r)
missing = set(EN) - {r["id"] for r in out}
if missing:
    raise SystemExit(f"not found in {SRC.name}: {sorted(missing)}")
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, delimiter=sep)
    w.writeheader()
    w.writerows(out)
print(f"\nWritten: {OUT.name} ({len(out)} questions)")
