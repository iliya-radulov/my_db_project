"""
tag_language.py — add the metadata field "lang" ("ru" or "en") to every chunk of the rebuilt index.

Needed by the bilingual retrieval of synthesis_rag.py (24 Oct 2026): besides the four nearest
passages, the advisor takes the nearest passage written in the OTHER language, found with the
same query but restricted to chunks of that language (ChromaDB `where={"lang": ...}`).

A chunk is "ru" if it has more Cyrillic than Latin letters, else "en".
Only metadata is changed: ChromaDB merges the new field into each chunk's existing metadata and
does not touch documents or embeddings (checked on chromadb 1.5.9). Already tagged chunks are
skipped, so the script can be re-run safely.

Usage (stage_three/, RAG venv):
    python tag_language.py            # dry run: counts per collection, nothing written
    python tag_language.py --write    # write the tags, then verify ru + en = all chunks
Optional: --collections NAME ...      (default: every collection whose name contains "_v2")
"""
import argparse
from pathlib import Path

import chromadb

HERE = Path(__file__).resolve().parent
PAGE, BATCH = 5000, 500          # reads in pages (SQL-variable limit), writes in small batches


def lang_of(text: str) -> str:
    cyr = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    lat = sum(1 for c in text if c.isascii() and c.isalpha())
    return "ru" if cyr > lat else "en"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--chroma", type=Path, default=HERE / "chroma_db")
    ap.add_argument("--collections", nargs="*")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=str(args.chroma))
    names = sorted(c if isinstance(c, str) else c.name for c in client.list_collections())
    names = args.collections or [n for n in names if "_v2" in n]
    print(("WRITING" if args.write else "DRY RUN (nothing written)") + f" — {len(names)} collections\n")
    ok_all = True
    for name in names:
        col = client.get_collection(name)
        total = col.count()
        todo, counts, already = [], {"ru": 0, "en": 0}, 0
        for off in range(0, total, PAGE):
            r = col.get(limit=PAGE, offset=off, include=["documents", "metadatas"])
            for i, doc, meta in zip(r["ids"], r["documents"], r["metadatas"]):
                lang = lang_of(doc or "")
                counts[lang] += 1
                if (meta or {}).get("lang") == lang:
                    already += 1
                else:
                    todo.append((i, lang))
        print(f"{name:28s} {total:6d} chunks: {counts['ru']:5d} ru, {counts['en']:6d} en "
              f"({100 * counts['ru'] / max(1, total):.1f} % ru); to write {len(todo)}, already tagged {already}")
        if not args.write:
            continue
        for b in range(0, len(todo), BATCH):
            part = todo[b:b + BATCH]
            col.update(ids=[i for i, _ in part], metadatas=[{"lang": l} for _, l in part])
        n_ru = len(col.get(where={"lang": "ru"}, include=[])["ids"])
        n_en = len(col.get(where={"lang": "en"}, include=[])["ids"])
        ok = n_ru == counts["ru"] and n_en == counts["en"] and n_ru + n_en == total
        ok_all &= ok
        print(f"{'':28s} check: {n_ru} ru + {n_en} en = {n_ru + n_en} of {total} -> {'OK' if ok else 'MISMATCH'}")
    if args.write:
        print("\nRESULT:", "all chunks tagged" if ok_all else "PROBLEMS — see above")


if __name__ == "__main__":
    main()
