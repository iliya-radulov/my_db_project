import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
import os

# --- Config ---
PDF_PATH = "/home/iliya-radulov/Documents/PM/M. Sherif El-Eskandarany - Mechanical Alloying, Second Edition_ Nanotechnology, Materials Science and Powder Metallurgy (2015, William Andrew) [10.1016_B978-1-4557-7752-5.00001-2].pdf"
COLLECTION_NAME = "powder_metallurgy"
CHUNK_SIZE = 800  # words per chunk

# --- Init ChromaDB ---
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(COLLECTION_NAME)

# Add this before get_or_create_collection
#client.delete_collection(COLLECTION_NAME)

# --- Read PDF ---
print("Reading PDF...")
reader = PdfReader(PDF_PATH)
print(f"Pages: {len(reader.pages)}")

# --- Chunk and store ---
words = []
for page in reader.pages:
    text = page.extract_text()
    if text:
        words.extend(text.split())

chunks = [" ".join(words[i:i+CHUNK_SIZE]) 
          for i in range(0, len(words), CHUNK_SIZE)]

# Skip first 5 chunks (front matter)
chunks = chunks[5:]
print(f"Chunks after skipping front matter: {len(chunks)}")

# --- Add to ChromaDB ---
for i, chunk in enumerate(chunks):
    collection.add(
        documents=[chunk],
        ids=[f"el-eskandarany-{i}"]
    )
    if i % 50 == 0:
        print(f"  stored chunk {i}/{len(chunks)}")

print("Done. Collection ready.")
