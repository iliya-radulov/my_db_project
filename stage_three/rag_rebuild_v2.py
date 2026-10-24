"""
rag_rebuild_v2.py — rebuild the book index from the PDFs, without the known defects.

Builds, for each topic, TWO new collections from the SAME chunks:
    <base>_v2       embedded by ChromaDB's default model (all-MiniLM-L6-v2), as the original index
    <base>_v2_bge   embedded by bge-m3 via Ollama
so that the benchmark can compare the two models on identical chunks again.

Chunking is exactly that of ingest_collection.py (pypdf text, 400 words, 50 overlap, chunks of
<= 50 characters dropped, first 3 chunks skipped, books with < 100 words skipped). Changed:
  - unique chunk IDs: first 40 characters of the name + 8-character hash of the FULL file name
    + chunk number (the old IDs used only the first 40 characters, and 4,011 chunks were lost);
  - pypdf's parsing limit raised for our own books (the encyclopedia exceeded it);
  - bge-m3 with truncate=False: a text that does not fit raises an error instead of being cut
    silently (the old re-index embedded only ~2,048 tokens of long chunks). Long chunks are
    embedded one at a time, and the model's token count is recorded for them;
  - every collection is checked against the number of chunks produced, and the longest chunks
    of each bge-m3 collection are re-embedded at the end and compared with what was stored.
The old collections are not touched.

Usage (stage_three/, RAG venv active, Ollama running):
    python rag_rebuild_v2.py                       # all three topics, both models (~1 h)
    python rag_rebuild_v2.py --topics phase        # one topic first, as a test (~5 min)
Resumable: books already complete in both collections are skipped on a re-run.
Results: rag_rebuild_v2_summary.json, and the printed summary at the end.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from pathlib import Path

import chromadb
import numpy as np

HERE = Path(__file__).resolve().parent
TOPICS = {                              # folder name -> base collection name
    "phase": "phase_stability",
    "synthesis": "synthesis",
    "magnetic": "magnetic",
}
CHUNK_SIZE, CHUNK_OVERLAP, SKIP_CHUNKS = 400, 50, 3     # as in ingest_collection.py
CYR = re.compile("[Ѐ-ӿ]")


def est_tokens(text: str) -> float:
    """Rough token estimate (Cyrillic needs about twice as many tokens per character)."""
    c = len(CYR.findall(text))
    return (len(text) - c) / 4.0 + c / 2.0


def chunk_id(file_name: str, i: int) -> str:
    stem = Path(file_name).stem
    safe = stem[:40].replace(" ", "_").replace("/", "_")
    h = hashlib.sha1(file_name.encode("utf-8")).hexdigest()[:8]
    return f"{safe}-{h}-{i}"


def extract_chunks(pdf: Path) -> tuple[list[str], int, int]:
    """Same text extraction and chunking as ingest_collection.py. Returns (chunks, pages, words)."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    words = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            words.extend(text.split())
    if len(words) < 100:
        return [], len(reader.pages), len(words)
    chunks, step = [], CHUNK_SIZE - CHUNK_OVERLAP
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)
    return chunks[SKIP_CHUNKS:], len(reader.pages), len(words)


class BgeEmbedder:
    """bge-m3 via Ollama, never truncating silently."""

    def __init__(self, model: str, num_ctx: int, single_above: float):
        import ollama
        self.ollama = ollama
        self.client = ollama.Client()
        self.model = model
        # an embedding model must take the whole text in one batch, so num_batch = num_ctx
        self.opts = {"num_ctx": num_ctx, "num_batch": num_ctx}
        self.single_above = single_above
        self.shortened: set[str] = set()
        self.tokens: dict[str, int] = {}

    def _too_long(self, err) -> bool:
        return "context length" in str(err)

    def one(self, cid: str, text: str):
        cut = text
        while True:
            try:
                r = self.client.embed(model=self.model, input=[cut], truncate=False, options=self.opts)
                if cut is not text:
                    self.shortened.add(cid)
                self.tokens[cid] = int(r.get("prompt_eval_count") or 0)
                return r["embeddings"][0]
            except self.ollama.ResponseError as e:
                if not self._too_long(e) or len(cut) < 200:
                    raise
                cut = cut[: len(cut) // 2]        # only if > num_ctx tokens; reported as shortened

    def fresh(self, text: str):
        """Embedding of the full text for the end check (None if it does not fit)."""
        try:
            r = self.client.embed(model=self.model, input=[text], truncate=False, options=self.opts)
            return r["embeddings"][0]
        except self.ollama.ResponseError:
            return None

    def many(self, ids: list[str], texts: list[str]):
        out = [None] * len(texts)
        short = [k for k, t in enumerate(texts) if est_tokens(t) <= self.single_above]
        if short:
            try:
                r = self.client.embed(model=self.model, input=[texts[k] for k in short],
                                      truncate=False, options=self.opts)
                for k, e in zip(short, r["embeddings"]):
                    out[k] = e
            except self.ollama.ResponseError as e:
                if not self._too_long(e):
                    raise
        for k, t in enumerate(texts):
            if out[k] is None:
                out[k] = self.one(ids[k], t)
        return out


def present(col, source: str) -> int:
    return len(col.get(where={"source": source}, include=[])["ids"])


def cos(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books-root", type=Path, default=Path("~/Desktop/new_books").expanduser())
    ap.add_argument("--topics", nargs="*", default=list(TOPICS))
    ap.add_argument("--set", default="_v2", help="suffix of the new collection names")
    ap.add_argument("--model", default="bge-m3")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--single-above", type=float, default=1000,
                    help="estimated tokens above which a chunk is embedded on its own")
    ap.add_argument("--check-n", type=int, default=20, help="longest chunks re-checked at the end")
    ap.add_argument("--chroma", type=Path, default=HERE / "chroma_db")
    args = ap.parse_args()

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    import pypdf
    try:
        pypdf.overwrite_configuration(stream_parsing_work_maximum_count=50_000_000)
    except AttributeError:
        print(f"note: pypdf {pypdf.__version__} has no parsing limit to raise")

    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    client = chromadb.PersistentClient(path=str(args.chroma))
    emb = BgeEmbedder(args.model, args.num_ctx, args.single_above)
    summary_path = HERE / "rag_rebuild_v2_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    for topic in args.topics:
        base = TOPICS[topic]
        folder = args.books_root / topic
        pdfs = sorted(folder.glob("*.pdf"))
        col_m = client.get_or_create_collection(base + args.set)                       # MiniLM (default)
        col_b = client.get_or_create_collection(base + args.set + "_bge",
                                                embedding_function=OllamaEmbeddingFunction(model_name=args.model))
        print(f"\n=== {topic}: {len(pdfs)} PDFs -> {col_m.name}, {col_b.name}", flush=True)
        books = summary.get(topic, {}).get("books", {})
        t0, all_ids = time.time(), set()
        for pdf in pdfs:
            name = pdf.name
            done = books.get(name, {})
            n_known = done.get("chunks")
            if n_known is not None and present(col_m, name) == n_known and present(col_b, name) == n_known:
                all_ids.update(chunk_id(name, i) for i in range(n_known))
                continue
            try:
                chunks, pages, words = extract_chunks(pdf)
            except Exception as e:
                books[name] = {"status": f"ERROR: {e}"[:300], "chunks": 0}
                print(f"  ERROR  {name[:70]}: {e}", flush=True)
                continue
            if not chunks:
                books[name] = {"status": "too little text", "pages": pages, "words": words, "chunks": 0}
                print(f"  SKIP   {name[:70]} — {words} words (no text layer?)", flush=True)
                continue
            ids = [chunk_id(name, i) for i in range(len(chunks))]
            dup = all_ids.intersection(ids)
            if dup or len(set(ids)) != len(ids):
                raise SystemExit(f"duplicate chunk IDs for {name}: {sorted(dup)[:3]} — stopping")
            all_ids.update(ids)
            metas = [{"source": name, "chunk": i} for i in range(len(chunks))]
            for col in (col_m, col_b):                      # remove a partial earlier attempt
                old = col.get(where={"source": name}, include=[])["ids"]
                if old:
                    col.delete(ids=old)
            for s in range(0, len(chunks), 256):
                col_m.add(ids=ids[s:s + 256], documents=chunks[s:s + 256], metadatas=metas[s:s + 256])
            for s in range(0, len(chunks), args.batch):
                sl = slice(s, s + args.batch)
                col_b.add(ids=ids[sl], documents=chunks[sl], metadatas=metas[sl],
                          embeddings=emb.many(ids[sl], chunks[sl]))
            tk = [emb.tokens[c] for c in ids if c in emb.tokens]
            books[name] = {"status": "ok", "pages": pages, "words": words, "chunks": len(chunks),
                           "tokens_measured": len(tk), "over_2048_tokens": sum(t > 2048 for t in tk),
                           "max_tokens": max(tk) if tk else None,
                           "shortened": sorted(emb.shortened.intersection(ids))}
            summary[topic] = {"books": books}
            summary_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
            print(f"  ok     {name[:70]}: {len(chunks)} chunks  ({(time.time() - t0) / 60:.1f} min)", flush=True)

        expected = sum(b.get("chunks", 0) for b in books.values())
        n_m, n_b = col_m.count(), col_b.count()
        # end check: re-embed the longest chunks one at a time and compare with the stored vectors
        g_ids, g_docs, off = [], [], 0
        while True:                                   # paged: large get() calls fail in ChromaDB
            r = col_b.get(include=["documents"], limit=5000, offset=off)
            g_ids += r["ids"]; g_docs += r["documents"]
            if len(r["ids"]) < 5000:
                break
            off += 5000
        order = sorted(range(len(g_ids)), key=lambda i: -est_tokens(g_docs[i]))[: args.check_n]
        sel = [g_ids[i] for i in order]
        stored = col_b.get(ids=sel, include=["embeddings", "documents"])
        fresh = [(v, emb.fresh(d)) for v, d in zip(stored["embeddings"], stored["documents"])]
        sims = [cos(v, f) if f is not None else 0.0 for v, f in fresh]
        okb = [b for b in books.values() if b.get("status") == "ok"]
        maxes = [b["max_tokens"] for b in okb if b.get("max_tokens")]
        summary[topic] = {
            "books": books,
            "books_indexed": sum(b.get("status") == "ok" for b in books.values()),
            "books_without_chunks": sorted(k for k, b in books.items() if b.get("status") != "ok"),
            "chunks_expected": expected, "chunks_minilm": n_m, "chunks_bge": n_b,
            "end_check_lowest_cosine": round(min(sims), 6) if sims else None,
            "chunks_measured_tokens": sum(b.get("tokens_measured", 0) for b in okb),
            "chunks_over_2048_tokens": sum(b.get("over_2048_tokens", 0) for b in okb),
            "longest_chunk_tokens": max(maxes) if maxes else None,
            "shortened_for_embedding": [c for b in okb for c in b.get("shortened", [])],
        }
        summary_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
        s = summary[topic]
        ok = (n_m == expected and n_b == expected and not s["shortened_for_embedding"]
              and (not sims or min(sims) >= 0.999))
        print(f"--- {topic}: {s['books_indexed']} books, {expected} chunks expected; "
              f"stored MiniLM {n_m}, bge-m3 {n_b}; end check lowest cosine {s['end_check_lowest_cosine']}; "
              f"{s['chunks_over_2048_tokens']} chunks > 2048 tokens (longest {s['longest_chunk_tokens']}); "
              f"shortened {len(s['shortened_for_embedding'])} -> {'OK' if ok else 'CHECK!'}", flush=True)
        if s["books_without_chunks"]:
            print(f"    books without chunks: {', '.join(x[:50] for x in s['books_without_chunks'])}")

    print(f"\nSummary written to {summary_path.name}")


if __name__ == "__main__":
    main()
