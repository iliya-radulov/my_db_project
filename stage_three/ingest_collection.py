"""
ingest_collection.py

Index a folder of PDFs into a named ChromaDB collection.
Usage: python3 ingest_collection.py <folder> <collection_name>

Example:
  python3 ingest_collection.py ~/Desktop/new_books/phase_rag phase_stability
  python3 ingest_collection.py ~/Desktop/new_books/synthesis synthesis
  python3 ingest_collection.py ~/Desktop/new_books/magnetic magnetic
"""

import sys
import os
from pathlib import Path
from pypdf import PdfReader
import chromadb

# ── Config ────────────────────────────────────────────────────────────
CHUNK_SIZE   = 400   # words — smaller than before for better precision
CHUNK_OVERLAP = 50   # words overlap between chunks
SKIP_CHUNKS  = 3     # skip front matter

# ── Args ──────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("Usage: python3 ingest_collection.py <folder> <collection_name>")
    sys.exit(1)

folder     = Path(sys.argv[1]).expanduser()
collection_name = sys.argv[2]

if not folder.exists():
    print(f"Folder not found: {folder}")
    sys.exit(1)

# ── ChromaDB ──────────────────────────────────────────────────────────
CHROMA_PATH = Path(__file__).resolve().parent / "chroma_db"
client      = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection  = client.get_or_create_collection(collection_name)

print(f"Collection: {collection_name}")
print(f"Folder:     {folder}")
print(f"Already indexed: {collection.count()} chunks")

# ── Find PDFs ─────────────────────────────────────────────────────────
pdfs = sorted(folder.glob("*.pdf"))
print(f"Found {len(pdfs)} PDF files\n")

# ── Index each PDF ────────────────────────────────────────────────────
total_new = 0

for pdf_path in pdfs:
    # Check if already indexed (by filename prefix)
    safe_name = pdf_path.stem[:40].replace(" ", "_").replace("/", "_")
    prefix    = f"{safe_name}-"

    # Quick check — skip if chunks with this prefix exist
    existing = collection.get(where={"source": pdf_path.name})
    if existing and existing["ids"]:
        print(f"  SKIP (already indexed): {pdf_path.name[:60]}")
        continue

    print(f"  Indexing: {pdf_path.name[:70]}")

    try:
        reader = PdfReader(str(pdf_path))
        print(f"    Pages: {len(reader.pages)}")

        # Extract all words
        words = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                words.extend(text.split())

        if len(words) < 100:
            print(f"    SKIP — too little text ({len(words)} words)")
            continue

        # Chunk with overlap
        chunks = []
        step = CHUNK_SIZE - CHUNK_OVERLAP
        for i in range(0, len(words), step):
            chunk = " ".join(words[i:i + CHUNK_SIZE])
            if len(chunk.strip()) > 50:
                chunks.append(chunk)

        # Skip front matter
        chunks = chunks[SKIP_CHUNKS:]
        print(f"    Chunks: {len(chunks)}")

        # Store in ChromaDB with metadata
        for i, chunk in enumerate(chunks):
            chunk_id = f"{safe_name}-{i}"
            collection.add(
                documents=[chunk],
                ids=[chunk_id],
                metadatas=[{"source": pdf_path.name, "chunk": i}]
            )
            if i % 100 == 0 and i > 0:
                print(f"    Stored {i}/{len(chunks)} chunks...")

        total_new += len(chunks)
        print(f"    Done! {len(chunks)} chunks added")

    except Exception as e:
        print(f"    ERROR: {e}")

print(f"\nFinished! {total_new} new chunks added")
print(f"Collection '{collection_name}' now has {collection.count()} chunks")
