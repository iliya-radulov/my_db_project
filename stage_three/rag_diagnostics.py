"""
rag_diagnostics.py — read-only health check of the Stage 3 ChromaDB store.

Measures, per collection:
  1. size: chunks, distinct source books, chunks per book
  2. embedding coverage: how much of each chunk the embedding model actually sees.
     ChromaDB's default embedding (all-MiniLM-L6-v2, used because ingest_collection.py
     sets no embedding function) truncates every chunk to 256 tokens. A 400-word chunk
     is usually longer than that, so the end of each chunk never influences retrieval.
  3. language / OCR quality: share of chunks that are mostly Cyrillic (the default
     model is English-only) and share that look like OCR garbage.
  4. (optional) books in the source folders that have NO chunks in the collection —
     e.g. scanned PDFs without OCR, or files whose first 40 name characters collide
     with another file (ingest_collection.py builds chunk IDs from stem[:40], and
     ChromaDB silently ignores a second chunk with an existing ID).

Nothing is written to the database. Results are printed and saved as JSON.

Usage (on the ML desktop, inside the stage_three RAG venv):
    python rag_diagnostics.py
    python rag_diagnostics.py --books ~/Desktop/new_books/phase_rag=phase_stability \
                              --books ~/Desktop/new_books/synthesis=synthesis \
                              --books ~/Desktop/new_books/magnetic=magnetic
Options:
    --chroma PATH      ChromaDB folder (default: chroma_db next to this script)
    --sample N         chunks per collection to tokenize (default 1000)
    --tokenizer PATH   tokenizer.json (default: ChromaDB's cached all-MiniLM-L6-v2)
    --out FILE         JSON output (default: rag_diagnostics.json)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import chromadb

DEFAULT_TOKENIZER = (Path.home() / ".cache" / "chroma" / "onnx_models"
                     / "all-MiniLM-L6-v2" / "onnx" / "tokenizer.json")
MAX_TOKENS = 256                      # ChromaDB default embedding truncation ([CLS] + 254 + [SEP])
CYR = re.compile(r"[Ѐ-ӿ]")
LAT = re.compile(r"[A-Za-z]")


def load_tokenizer(path: Path):
    if not path.exists():
        print(f"  [tokenizer] not found at {path} — skipping token statistics")
        return None
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(path))
    tok.no_truncation()
    tok.no_padding()
    return tok


def coverage(tok, text: str) -> tuple[int, float]:
    """Return (content tokens in chunk, fraction of the chunk's words beyond the 256-token cut)."""
    enc = tok.encode(text)                     # [CLS] t1 … tn [SEP]
    if len(enc.ids) <= MAX_TOKENS:
        return len(enc.ids) - 2, 0.0
    cut_char = enc.offsets[MAX_TOKENS - 1][0]  # first character that is not embedded
    words_total = len(text.split())
    words_seen = len(text[:cut_char].split())
    return len(enc.ids) - 2, 1.0 - words_seen / max(words_total, 1)


def text_profile(text: str) -> tuple[bool, bool]:
    """(mostly Cyrillic, looks like OCR garbage)."""
    cyr, lat = len(CYR.findall(text)), len(LAT.findall(text))
    letters = cyr + lat
    mostly_cyr = letters > 0 and cyr / letters > 0.5
    alpha = sum(ch.isalpha() for ch in text) / max(len(text), 1)
    return mostly_cyr, alpha < 0.55


def missing_books(collection, folder: Path) -> dict:
    pdfs = sorted(folder.expanduser().glob("*.pdf"))
    metas = collection.get(include=["metadatas"])["metadatas"]
    indexed = {m.get("source") for m in metas if m}
    missing = [p.name for p in pdfs if p.name not in indexed]
    prefixes = defaultdict(list)
    for p in pdfs:
        prefixes[p.stem[:40].replace(" ", "_").replace("/", "_")].append(p.name)
    collisions = {k: v for k, v in prefixes.items() if len(v) > 1}
    return {"folder": str(folder), "pdfs_in_folder": len(pdfs),
            "pdfs_without_chunks": missing, "id_prefix_collisions": collisions}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chroma", type=Path, default=Path(__file__).resolve().parent / "chroma_db")
    ap.add_argument("--sample", type=int, default=1000)
    ap.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    ap.add_argument("--books", action="append", default=[], help="FOLDER=COLLECTION, may be repeated")
    ap.add_argument("--out", type=Path, default=Path("rag_diagnostics.json"))
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=str(args.chroma))
    tok = load_tokenizer(args.tokenizer)
    random.seed(0)
    report = {"chroma_path": str(args.chroma), "collections": {}}

    print(f"ChromaDB: {args.chroma}\n")
    for col in client.list_collections():
        name = col if isinstance(col, str) else col.name
        c = client.get_collection(name)
        meta = c.get(include=["metadatas"])
        ids, metas = meta["ids"], meta["metadatas"]
        per_src = Counter((m or {}).get("source", "<no source>") for m in metas)
        r = {"chunks": len(ids), "sources": len(per_src),
             "chunks_per_source_median": st.median(per_src.values()) if per_src else 0,
             "chunks_per_source_max": max(per_src.values()) if per_src else 0}

        sample_ids = random.sample(ids, min(args.sample, len(ids)))
        docs = c.get(ids=sample_ids, include=["documents"])["documents"] if sample_ids else []
        prof = [text_profile(d) for d in docs]
        r["sampled"] = len(docs)
        r["share_mostly_cyrillic"] = round(sum(p[0] for p in prof) / max(len(prof), 1), 3)
        r["share_ocr_garbage"] = round(sum(p[1] for p in prof) / max(len(prof), 1), 3)
        r["words_per_chunk_median"] = st.median(len(d.split()) for d in docs) if docs else 0

        if tok and docs:
            cov = [coverage(tok, d) for d in docs]
            ntok = [n for n, _ in cov]
            r["tokens_per_chunk_median"] = st.median(ntok)
            r["share_chunks_truncated"] = round(sum(n > MAX_TOKENS - 2 for n in ntok) / len(ntok), 3)
            r["share_of_text_not_embedded_mean"] = round(st.mean(f for _, f in cov), 3)

        report["collections"][name] = r
        print(f"[{name}]")
        for k, v in r.items():
            print(f"  {k:34s} {v}")
        print()

    for spec in args.books:
        folder, _, cname = spec.partition("=")
        try:
            res = missing_books(client.get_collection(cname), Path(folder))
        except Exception as e:
            res = {"error": str(e)}
        report.setdefault("books", {})[cname + " ← " + folder] = res
        print(f"[books → {cname}]  {res.get('pdfs_in_folder', '?')} PDFs in {folder}")
        for n in res.get("pdfs_without_chunks", []):
            print(f"  no chunks: {n}")
        for k, v in res.get("id_prefix_collisions", {}).items():
            print(f"  ID prefix collision '{k}': {v}")
        if "error" in res:
            print(f"  error: {res['error']}")
        print()

    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved → {args.out}")


if __name__ == "__main__":
    main()
