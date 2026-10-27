"""
rag_reindex.py — re-embed the EXISTING chunks with another embedding model.

Copies every chunk (same text, same ID, same metadata) of each source collection into a
new collection <name><suffix>, embedded with an Ollama model (default bge-m3). Because the
chunks are identical, a benchmark comparison between e.g. `synthesis` and `synthesis_bge`
isolates the effect of the embedding model alone.

Long chunks: Ollama is asked for the model's full context (num_ctx 8192). If a batch is
still rejected ("input length exceeds the context length"), its chunks are embedded one by
one, and a chunk that is still too long is shortened FOR EMBEDDING ONLY (halved until it
fits). The stored text is always the complete chunk. The number of shortened chunks is
reported per collection.

The source collections are only read. Re-running resumes: chunks already present in the
target are skipped.

Before starting:  ollama pull bge-m3
Usage (ML desktop, stage_three RAG venv, script next to chroma_db/):
    python rag_reindex.py                         # all collections except powder_metallurgy
    python rag_reindex.py --collections phase_stability      # one collection
Options:
    --model NAME     Ollama embedding model (default bge-m3)
    --num-ctx N      context window requested from Ollama (default 8192)
    --suffix S       target name suffix (default _bge)
    --batch N        chunks per request (default 32)
    --chroma PATH    ChromaDB folder (default chroma_db next to this script)
    --embed hash     offline test only (no Ollama)
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import chromadb

from rag_benchmark import HashEF       # offline test embedding

HERE = Path(__file__).resolve().parent


class OllamaEmbedder:
    """bge-m3 via Ollama with the full context window and a per-chunk fallback."""

    def __init__(self, model: str, num_ctx: int):
        import ollama
        self.ollama = ollama
        self.client = ollama.Client()
        self.model = model
        self.options = {"num_ctx": num_ctx, "num_batch": num_ctx}
        self.shortened = 0

    def _embed(self, texts):
        r = self.client.embed(model=self.model, input=texts, truncate=True, options=self.options)
        return list(r["embeddings"])

    @staticmethod
    def _too_long(err) -> bool:
        return "context length" in str(err)

    def __call__(self, texts):
        try:
            return self._embed(texts)
        except self.ollama.ResponseError as e:
            if not self._too_long(e):
                raise
        vectors = []
        for text in texts:                      # one by one; shorten only what must be shortened
            cut = text
            while True:
                try:
                    vectors.append(self._embed([cut])[0])
                    break
                except self.ollama.ResponseError as e:
                    if not self._too_long(e) or len(cut) < 200:
                        raise
                    cut = cut[: len(cut) // 2]
            if cut is not text:
                self.shortened += 1
        return vectors


class HashEmbedder:
    shortened = 0
    def __init__(self):
        self.ef = HashEF()
    def __call__(self, texts):
        return self.ef(texts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collections", nargs="*")
    ap.add_argument("--exclude", nargs="*", default=["powder_metallurgy"])
    ap.add_argument("--model", default="bge-m3")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--suffix", default="_bge")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--chroma", type=Path, default=HERE / "chroma_db")
    ap.add_argument("--embed", default=None, help="'hash' for offline tests")
    args = ap.parse_args()

    if args.embed == "hash":
        embedder, query_ef = HashEmbedder(), HashEF()
    else:
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
        embedder = OllamaEmbedder(args.model, args.num_ctx)
        # stored with the collection, so queries (rag_benchmark.py --embed auto) use the same model
        query_ef = OllamaEmbeddingFunction(model_name=args.model)

    client = chromadb.PersistentClient(path=str(args.chroma))
    names = [c if isinstance(c, str) else c.name for c in client.list_collections()]
    sources = args.collections or [n for n in names
                                   if n not in args.exclude and not n.endswith(args.suffix)]

    for name in sources:
        if name not in names:
            print(f"[{name}] does not exist — skipped")
            continue
        src = client.get_collection(name)
        dst = client.get_or_create_collection(name + args.suffix, embedding_function=query_ef)
        total, done_before = src.count(), dst.count()
        print(f"[{name}] → [{dst.name}]  {total} chunks, {done_before} already done", flush=True)

        t0, added, offset, short0 = time.time(), 0, 0, embedder.shortened
        while offset < total:
            page = src.get(limit=args.batch, offset=offset, include=["documents", "metadatas"])
            offset += len(page["ids"])
            if not page["ids"]:
                break
            have = set(dst.get(ids=page["ids"], include=[])["ids"]) if done_before else set()
            keep = [i for i, cid in enumerate(page["ids"]) if cid not in have]
            if keep:
                docs = [page["documents"][i] for i in keep]
                dst.add(ids=[page["ids"][i] for i in keep], documents=docs,
                        metadatas=[page["metadatas"][i] for i in keep],
                        embeddings=embedder(docs))
                added += len(keep)
            if added and (offset // args.batch) % 20 == 0:
                rate = added / (time.time() - t0)
                eta = (total - offset) / rate / 60 if rate else 0
                print(f"    {offset}/{total}  {rate:.1f} chunks/s  ETA {eta:.0f} min", flush=True)
        print(f"  done: {added} added, {dst.count()} in {dst.name}, "
              f"{embedder.shortened - short0} shortened for embedding "
              f"({(time.time() - t0) / 60:.1f} min)", flush=True)
        if dst.count() != total:
            print(f"  WARNING: {dst.name} has {dst.count()} chunks, source has {total}")


if __name__ == "__main__":
    main()
