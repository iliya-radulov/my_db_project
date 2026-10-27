"""
check_embed.py — were any chunks of the bge-m3 collections cut when they were embedded?
(read-only, a few minutes on the GPU)

phase_stability_bge and synthesis_bge were embedded by the first re-index run, before the
context length was set to 8,192 tokens explicitly. If Ollama's default then cut long chunks,
their stored vectors differ from vectors of the full text. This script takes the chunks most
likely to have been cut (most tokens: longest, Cyrillic-heavy), embeds them again with the full
context, and compares with the stored vectors. magnetic_bge (embedded after the fix) is the control.

Verdict per collection: cosine similarity >= 0.999 for every checked chunk = nothing was cut.

Usage (stage_three/, RAG venv active, Ollama running):
    python check_embed.py                    # 40 chunks per collection
    python check_embed.py --n 100
"""
import argparse
import re
from pathlib import Path

import chromadb
import numpy as np
import ollama

HERE = Path(__file__).resolve().parent
CYR = re.compile("[Ѐ-ӿ]")
PAGE = 5000


def est_tokens(text: str) -> float:
    """Rough token estimate: Cyrillic needs about twice as many tokens per character."""
    cyr = len(CYR.findall(text))
    return (len(text) - cyr) / 4.0 + cyr / 2.0


def all_docs(col):
    ids, docs, offset = [], [], 0
    while True:
        r = col.get(include=["documents"], limit=PAGE, offset=offset)
        ids += r["ids"]
        docs += r["documents"]
        if len(r["ids"]) < PAGE:
            return ids, docs
        offset += PAGE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collections", nargs="*",
                    default=["phase_stability_bge", "synthesis_bge", "magnetic_bge"])
    ap.add_argument("--n", type=int, default=40, help="chunks checked per collection")
    ap.add_argument("--model", default="bge-m3")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--chroma", type=Path, default=HERE / "chroma_db")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=str(args.chroma))
    oc = ollama.Client()
    for name in args.collections:
        col = client.get_collection(name)
        ids, docs = all_docs(col)
        order = sorted(range(len(ids)), key=lambda i: -est_tokens(docs[i]))[: args.n]
        sel_ids = [ids[i] for i in order]
        stored = col.get(ids=sel_ids, include=["embeddings", "documents"])
        by_id = {i: (np.asarray(e, dtype=float), d)
                 for i, e, d in zip(stored["ids"], stored["embeddings"], stored["documents"])}
        sims, max_tok, errors = [], 0, []
        # same options as rag_reindex.py: an embedding model must take the whole input in one
        # batch, so num_batch has to be as large as num_ctx (Ollama's default batch is 512 tokens)
        opts = {"num_ctx": args.num_ctx, "num_batch": args.num_ctx}
        for cid in sel_ids:
            vec, doc = by_id[cid]
            try:
                r = oc.embed(model=args.model, input=[doc], truncate=False, options=opts)
            except Exception as e:                       # report and go on with the next chunk
                errors.append(f"{cid}: {e}")
                continue
            new = np.asarray(r["embeddings"][0], dtype=float)
            max_tok = max(max_tok, int(r.get("prompt_eval_count") or 0))
            sims.append(float(vec @ new / (np.linalg.norm(vec) * np.linalg.norm(new))))
        worst = min(sims) if sims else float("nan")
        verdict = "nothing was cut" if sims and worst >= 0.999 else "SOME CHUNKS DIFFER - possibly cut"
        print(f"{name:22s} {len(ids):6d} chunks, checked the {len(sel_ids)} longest: "
              f"lowest cosine {worst:.5f}, longest chunk {max_tok} tokens -> {verdict}", flush=True)
        for e in errors[:5]:
            print(f"    could not embed {e[:160]}")
        if errors:
            print(f"    ({len(errors)} chunks could not be embedded)")


if __name__ == "__main__":
    main()
