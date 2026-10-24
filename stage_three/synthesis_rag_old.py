"""
synthesis_rag.py

Composition-aware RAG for synthesis route guidance.
Importable from the main app — returns structured dicts,
never prints directly.

Usage from alloy_desktop_v2.py:
    from stage_three.synthesis_rag import query_synthesis
    result = query_synthesis(
        system_name="Mn-Al-C",
        suggested_routes=["mechanical alloying"],
        composition={"Mn": 0.47, "Al": 0.52, "C": 0.01}
    )
    print(result["answer"])
"""

import os
from pathlib import Path
import chromadb
import ollama

# ── Paths ────────────────────────────────────────────────────────────
# Absolute path so this works when imported from any directory
_STAGE_THREE_DIR = Path(__file__).resolve().parent
_CHROMA_PATH = str(_STAGE_THREE_DIR / "chroma_db")
_COLLECTION_NAME = "powder_metallurgy"
_MODEL = "qwen2.5:14b"

# ── ChromaDB client (lazy init) ───────────────────────────────────────
_client = None
_collection = None

def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=_CHROMA_PATH)
        _collection = _client.get_or_create_collection(_COLLECTION_NAME)
    return _collection

# ── Query builder ─────────────────────────────────────────────────────

def _build_query(system_name, suggested_routes, composition):
    """
    Builds a composition-aware query from alloy info.
    More specific than a generic question — includes the
    actual system name and relevant processing routes.
    """
    routes_str = " and ".join(suggested_routes) if suggested_routes else "common metallurgical routes"

    # Add composition context for key elements
    comp_hints = []
    for el, frac in sorted(composition.items(), key=lambda x: -x[1]):
        if frac > 0.05:   # only major elements
            comp_hints.append(f"{el} ({frac*100:.0f} at%)")
    comp_str = ", ".join(comp_hints) if comp_hints else ""

    query = (
        f"What synthesis parameters and conditions are recommended "
        f"for {system_name} alloy"
        f"{' (' + comp_str + ')' if comp_str else ''} "
        f"prepared by {routes_str}? "
        f"Include temperatures, atmosphere, milling parameters, "
        f"and any known challenges for this system."
    )
    return query

# ── System prompt ─────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a materials science assistant specializing in
alloy synthesis and processing. Answer based ONLY on the provided context.
If the context does not contain enough information about this specific
system, say so clearly and note what general principles apply.
Do not invent data, temperatures, or literature references."""

# ── Main entry point ──────────────────────────────────────────────────

def query_synthesis(system_name, suggested_routes, composition,
                    n_chunks=4, model=_MODEL):
    """
    Query the synthesis literature RAG for a specific alloy system.

    Args:
        system_name:      str  e.g. "Mn-Al-C"
        suggested_routes: list e.g. ["mechanical alloying", "arc melting"]
        composition:      dict e.g. {"Mn": 0.47, "Al": 0.52, "C": 0.01}
        n_chunks:         int  number of context chunks to retrieve
        model:            str  ollama model name

    Returns:
        {
            "answer":    str   — LLM answer
            "query":     str   — the query that was sent
            "chunks":    list  — retrieved context chunks (raw text)
            "sources":   list  — first 200 chars of each chunk
            "success":   bool
            "error":     str or None
        }
    """
    try:
        collection = _get_collection()
        n_indexed = collection.count()

        if n_indexed == 0:
            return {
                "answer": "No literature has been indexed yet. Add PDFs using ingest.py first.",
                "query": "", "chunks": [], "sources": [],
                "success": False, "error": "empty collection",
            }

        query = _build_query(system_name, suggested_routes, composition)

        results = collection.query(
            query_texts=[query],
            n_results=min(n_chunks, n_indexed),
        )

        chunks = results["documents"][0]
        context = "\n\n".join(chunks)

        prompt = f"""{_SYSTEM_PROMPT}

Context:
{context}

Question: {query}

Answer:"""

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        answer = response["message"]["content"]

        return {
            "answer":  answer,
            "query":   query,
            "chunks":  chunks,
            "sources": [c[:200] + "..." for c in chunks],
            "success": True,
            "error":   None,
        }

    except Exception as e:
        return {
            "answer":  f"RAG query failed: {e}",
            "query":   "",
            "chunks":  [],
            "sources": [],
            "success": False,
            "error":   str(e),
        }


# ── Entry point ──────────────────────────────────────────────────────
# When called with a JSON argument → subprocess mode (used by main app)
# When called with no argument → interactive CLI test

if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1:
        # Subprocess mode — return pure JSON only
        data = json.loads(sys.argv[1])
        result = query_synthesis(
            system_name=data["system_name"],
            suggested_routes=data["suggested_routes"],
            composition=data["composition"],
        )
        print(json.dumps(result))
    else:
        # Interactive CLI test
        result = query_synthesis(
            system_name="Mn-Al-C",
            suggested_routes=["mechanical alloying"],
            composition={"Mn": 0.47, "Al": 0.52, "C": 0.01},
        )
        print(f"\nQuery: {result['query']}\n")
        print(f"--- Answer ---\n{result['answer']}")
        print(f"\n--- Sources ---")
        for i, s in enumerate(result["sources"], 1):
            print(f"\nChunk {i}: {s}")
