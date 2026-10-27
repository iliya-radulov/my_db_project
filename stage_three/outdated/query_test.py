import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("powder_metallurgy")

query = "what are the main parameters controlling mechanical alloying?"

results = collection.query(
    query_texts=[query],
    n_results=3
)

for i, doc in enumerate(results["documents"][0]):
    print(f"\n--- Chunk {i+1} ---")
    print(doc[:500])
