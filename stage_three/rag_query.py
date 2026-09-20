import chromadb
import ollama

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("powder_metallurgy")

def ask(question):
    # Retrieve relevant chunks
    results = collection.query(
        query_texts=[question],
        n_results=4
    )
    context = "\n\n".join(results["documents"][0])

    # Build prompt
    prompt = f"""You are a materials science assistant specializing in powder metallurgy.
Answer the question based ONLY on the provided context.
If the context does not contain enough information, say so clearly.
Do not invent data, parameters, or references.

Context:
{context}

Question: {question}

Answer:"""

    # Call Qwen
    response = ollama.chat(
        model="qwen2.5:14b",
        messages=[{"role": "user", "content": prompt}]
    )
    
    print("\n--- Answer ---")
    print(response["message"]["content"])
    print("\n--- Sources (chunks used) ---")
    for i, doc in enumerate(results["documents"][0]):
        print(f"\nChunk {i+1}: {doc[:200]}...")

ask("What are the main parameters controlling mechanical alloying?")
