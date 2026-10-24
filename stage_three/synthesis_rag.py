"""
synthesis_rag.py — composition-aware literature guidance (Stage 3 RAG advisor).

Used two ways:
  * by alloy_desktop_v2.py as a subprocess: one JSON argument in, one JSON object on stdout;
  * by rag_benchmark.py, which imports retrieve(), generate(), PROMPT and the settings from
    here — so the benchmark tests exactly the retrieval, prompt and model settings the app uses.

Changes on 23 Oct 2026 (the version of 20 Sep queried a collection that no longer existed):
  - collection synthesis_bge (bge-m3 embeddings), opened with get_collection: a missing
    collection is now an error, not a silently created empty one;
  - the prompt is the one the benchmark evaluated (rag_benchmark.py PROMPT);
  - temperature 0, and the context window is set explicitly (NUM_CTX). Ollama's default
    (4,096 tokens) silently cut the longest prompts to about half — the beginning, with the
    instruction and the best-ranked passage, was lost;
  - "sources" are the book file names from the chunk metadata (was: first 200 characters);
  - "prompt_tokens" reports how many prompt tokens the model actually read.

Changes on 24 Oct 2026 (bilingual retrieval):
  - collection synthesis_v2_bge (the rebuilt index);
  - a test showed that an English question practically never retrieves a Russian passage:
    the 7 Russian-source benchmark questions found their passage 5 of 7 times when asked in
    Russian and 0 of 7 times when asked in English (same-language texts lie closer together
    in the embedding space, and English books cover most topics). The advisor's queries are
    English, so the Russian books were effectively unreachable;
  - first attempt (rejected): translate the query with the local model. Qwen2.5-14B drifted into
    Chinese in 5 of 44 benchmark questions even with a checked, retried prompt, and mistranslated
    terms in others ("caloric" -> "тепловой", "bulk" -> "блочном", "sintered" -> "сшитых");
  - second attempt (kept as the mechanism, not enough on its own): every chunk carries its
    language in the metadata (tag_language.py), and the extra passage is searched only among
    chunks of the other language. With the English question itself this found the Russian
    gold passage for only 1 of the 7 questions (2 within the two nearest Russian chunks);
  - now: the extra passage is searched among Russian chunks with a RUSSIAN query built from a
    fixed template (build_query_ru, route names from ROUTES_RU) — no model translation. With a
    correct Russian query the gold passage is the nearest Russian chunk for 5 of the 7
    questions. The model reads N_CHUNKS + N_OTHER = 5 passages; the first four are unchanged,
    so nothing found before can be lost; the question to the model stays English;
  - the result also contains "other_language", "other_query" and, per passage, "via".

Usage from alloy_desktop_v2.py (subprocess, RAG venv):
    python synthesis_rag.py '{"system_name": "Mn-Al-C", "suggested_routes": ["mechanical alloying"],
                              "composition": {"Mn": 0.47, "Al": 0.52, "C": 0.01}}'
Interactive test (no argument):
    python synthesis_rag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb

# ── Settings (shared with rag_benchmark.py) ──────────────────────────────────
STAGE_THREE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = STAGE_THREE_DIR / "chroma_db"
COLLECTIONS = ["synthesis_v2_bge"]      # searched together; results merged by distance
MODEL = "qwen2.5:14b"
N_CHUNKS = 4                         # passages for the query as asked
N_OTHER = 1                          # + nearest passage in the other language (0 = off)
NUM_CTX = 16384                      # tokens; the longest benchmark prompt is ~4,800
MAX_CTX = 32768                      # Qwen2.5-14B's own limit
TEMPERATURE = 0

PROMPT = """You are a materials science assistant.
Answer the question based ONLY on the provided context.
If the context does not contain enough information, say so clearly.
Do not invent data, parameters, or references.

Context:
{context}

Question: {question}

Answer:"""

# ── Collections (opened once per process) ────────────────────────────────────
_client = None
_collections: dict[str, object] = {}


def get_collections(names=None, chroma_path=CHROMA_PATH) -> list:
    """Open the named collections; raise with a clear message if one does not exist."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(chroma_path))
    out = []
    for name in names or COLLECTIONS:
        if name not in _collections:
            existing = [c if isinstance(c, str) else c.name for c in _client.list_collections()]
            if name not in existing:
                raise RuntimeError(f"collection '{name}' not found in {chroma_path} "
                                   f"(existing: {', '.join(sorted(existing))})")
            # no embedding_function argument: the one stored with the collection is used
            _collections[name] = _client.get_collection(name)
            if N_OTHER > 0:
                require_language_tags([_collections[name]])
        out.append(_collections[name])
    return out


def require_language_tags(collections: list) -> None:
    """Bilingual retrieval filters on the metadata field "lang"; without it, the filter would
    silently find nothing. Raise instead."""
    for col in collections:
        r = col.get(limit=1, include=["metadatas"])
        if r["ids"] and "lang" not in (r["metadatas"][0] or {}):
            raise RuntimeError(f"collection '{col.name}' has no language tags — run tag_language.py --write")


# ── Retrieval and generation (rag_benchmark.py imports these) ────────────────
def retrieve(collections: list, query: str, k: int, where: dict | None = None) -> list[dict]:
    """Top-k chunks over all given collections, merged by distance (smaller = closer).
    *where* restricts the search by metadata, e.g. {"lang": "ru"}."""
    hits = []
    for col in collections:
        n = min(k, col.count())
        if n == 0:
            continue
        r = col.query(query_texts=[query], n_results=n, where=where,
                      include=["documents", "metadatas", "distances"])
        for i, d, m, dist in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
            hits.append({"key": (col.name, i), "doc": d, "source": (m or {}).get("source", ""),
                         "distance": float(dist), "collection": col.name})
    hits.sort(key=lambda h: h["distance"])
    return hits[:k]


def generate(model: str, question: str, chunks: list[str]) -> tuple[str, int]:
    """Answer from the chunks. Returns (answer, number of prompt tokens the model read)."""
    import ollama
    prompt = PROMPT.format(context="\n\n".join(chunks), question=question)
    # Conservative size check (about 2 characters per token, the Cyrillic worst case):
    # widen the window rather than let Ollama cut the prompt without an error.
    num_ctx = NUM_CTX
    while len(prompt) // 2 + 1024 > num_ctx and num_ctx < MAX_CTX:
        num_ctx *= 2
    if len(prompt) // 2 + 1024 > num_ctx:
        raise RuntimeError(f"prompt of {len(prompt)} characters may not fit the {num_ctx}-token context")
    resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}],
                       options={"temperature": TEMPERATURE, "num_ctx": num_ctx})
    return resp["message"]["content"].strip(), int(resp.get("prompt_eval_count") or 0)


def query_language(text: str) -> str:
    """'Russian' if most letters are Cyrillic, else 'English' (the corpus's two languages)."""
    cyr, lat = _letters(text)
    return "Russian" if cyr > lat else "English"


def _letters(text: str) -> tuple[int, int]:
    cyr = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    lat = sum(1 for c in text if c.isascii() and c.isalpha())
    return cyr, lat


def retrieve_bilingual(collections: list, query: str, k: int, n_first: int = N_CHUNKS,
                       n_other: int = N_OTHER, other_query: str | None = None) -> tuple[list[dict], str | None]:
    """Ranked passages: the n_first nearest to the query, then the n_other nearest among chunks
    written in the other language (metadata filter), searched with *other_query* (the query in
    that language) if given, else with the query itself; then the remaining passages of both
    lists alternately (for ranking only). Returns (passages, other language code or None)."""
    primary = retrieve(collections, query, k)
    if n_other <= 0:
        return primary, None
    other = "ru" if query_language(query) == "English" else "en"
    secondary = retrieve(collections, other_query or query, k, where={"lang": other})
    out, seen = [], set()

    def add(h, via):
        if h["key"] not in seen:
            seen.add(h["key"])
            out.append(dict(h, via=via))
            return True
        return False

    for h in primary[:n_first]:
        add(h, "query")
    added = 0
    for h in secondary:
        if added >= n_other:
            break
        added += add(h, "other-language")
    rest_p = [h for h in primary[n_first:] if h["key"] not in seen]
    rest_s = [h for h in secondary if h["key"] not in seen]
    for i in range(max(len(rest_p), len(rest_s))):
        if i < len(rest_p):
            add(rest_p[i], "query")
        if i < len(rest_s):
            add(rest_s[i], "other-language")
    return out[:k], other


# ── Composition-aware query (unchanged from the 20 Sep version) ──────────────
def build_query(system_name, suggested_routes, composition) -> str:
    routes_str = " and ".join(suggested_routes) if suggested_routes else "common metallurgical routes"
    comp_hints = [f"{el} ({frac * 100:.0f} at%)"
                  for el, frac in sorted(composition.items(), key=lambda x: -x[1]) if frac > 0.05]
    comp_str = ", ".join(comp_hints)
    return (f"What synthesis parameters and conditions are recommended "
            f"for {system_name} alloy"
            f"{' (' + comp_str + ')' if comp_str else ''} "
            f"prepared by {routes_str}? "
            f"Include temperatures, atmosphere, milling parameters, "
            f"and any known challenges for this system.")


# Russian version of the same template (24 Oct 2026). Route names as the screening writes them
# (stage_two/alloy/alloy_screening_v2.py, lines 403-423, the first seven entries); a route missing
# here is quoted in English inside the Russian sentence and reported.
ROUTES_RU = {
    "mechanical alloying (ball milling)": "механическим легированием (размолом в шаровой мельнице)",
    "powder sintering": "спеканием порошков",
    "diffusion bonding": "диффузионной сваркой",
    "arc/induction melting (monitor mass loss)": "дуговой или индукционной плавкой (с контролем потери массы)",
    "literature precedent check": "с проверкой по литературным данным",
    "small-scale test melt": "пробной плавкой малого объёма",
    "arc/induction melting": "дуговой или индукционной плавкой",
    # general names (interactive test, other callers)
    "mechanical alloying": "механическим легированием",
    "ball milling": "размолом в шаровой мельнице",
    "high-energy ball milling": "высокоэнергетическим размолом в шаровой мельнице",
    "arc melting": "дуговой плавкой",
    "induction melting": "индукционной плавкой",
    "melt spinning": "спиннингованием расплава",
    "rapid solidification": "быстрой закалкой из расплава",
    "powder metallurgy": "методами порошковой металлургии",
    "sintering": "спеканием",
    "hot pressing": "горячим прессованием",
    "spark plasma sintering": "искровым плазменным спеканием",
    "solid-state reaction": "твердофазным синтезом",
    "annealing": "отжигом",
    "common metallurgical routes": "обычными металлургическими методами",
}


def build_query_ru(system_name, suggested_routes, composition) -> tuple[str, list[str]]:
    """The query of build_query() in Russian, from a fixed template. Returns (query, unknown routes)."""
    routes = list(suggested_routes) or ["common metallurgical routes"]
    unknown = [r for r in routes if r.strip().lower() not in ROUTES_RU]
    routes_ru = " и ".join(ROUTES_RU.get(r.strip().lower(), f"методом «{r}»") for r in routes)
    comp_hints = [f"{el} ({frac * 100:.0f} ат.%)"
                  for el, frac in sorted(composition.items(), key=lambda x: -x[1]) if frac > 0.05]
    comp_str = ", ".join(comp_hints)
    query = (f"Какие параметры и условия синтеза рекомендуются для сплава {system_name}"
             f"{' (' + comp_str + ')' if comp_str else ''}, получаемого {routes_ru}? "
             f"Укажите температуры, атмосферу, параметры помола и известные трудности для этой системы.")
    return query, unknown


# ── Main entry point ─────────────────────────────────────────────────────────
def query_synthesis(system_name, suggested_routes, composition, n_chunks=N_CHUNKS, model=MODEL) -> dict:
    """
    Returns {
        "answer":        str   — the model's answer (or an error message)
        "query":         str   — the query that was sent
        "chunks":        list  — the retrieved passages (full text)
        "other_language": str  — language of the extra passage ("ru"/"en", or None)
        "other_query":   str   — the Russian query used for it (fixed template)
        "sources":       list  — book file name of each passage, best first
        "distances":     list  — distance of each passage (smaller = closer)
        "via":           list  — "query" or "other-language" for each passage
        "collections":   list  — collections searched
        "model":         str
        "prompt_tokens": int   — prompt tokens the model read
        "success":       bool
        "error":         str or None
    }
    """
    result = {"answer": "", "query": "", "other_language": None, "other_query": None,
              "chunks": [], "sources": [],
              "distances": [], "via": [],
              "collections": list(COLLECTIONS), "model": model, "prompt_tokens": 0,
              "success": False, "error": None}
    try:
        query = build_query(system_name, suggested_routes, composition)
        result["query"] = query
        query_ru, unknown_routes = build_query_ru(system_name, suggested_routes, composition)
        hits, other = retrieve_bilingual(get_collections(), query, n_chunks + N_OTHER,
                                         n_first=n_chunks, other_query=query_ru)
        result.update(other_language=other, other_query=query_ru)
        if unknown_routes:
            result["error"] = f"route(s) without a Russian name in ROUTES_RU: {', '.join(unknown_routes)}"
        hits = hits[:n_chunks + N_OTHER]
        if not hits:
            raise RuntimeError("no passages retrieved (empty collections?)")
        chunks = [h["doc"] for h in hits]
        answer, ptok = generate(model, query, chunks)
        result.update(answer=answer, chunks=chunks, prompt_tokens=ptok, success=True,
                      sources=[h["source"] for h in hits],
                      distances=[round(h["distance"], 4) for h in hits],
                      via=[h.get("via", "query") for h in hits])
    except Exception as e:
        result.update(answer=f"RAG query failed: {e}", error=str(e))
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Subprocess mode — the JSON object is the only thing written to stdout
        data = json.loads(sys.argv[1])
        print(json.dumps(query_synthesis(
            system_name=data["system_name"],
            suggested_routes=data.get("suggested_routes") or [],
            composition=data["composition"])))
    else:
        r = query_synthesis("Mn-Al-C", ["mechanical alloying"], {"Mn": 0.47, "Al": 0.52, "C": 0.01})
        print(f"\nQuery: {r['query']}\nRussian query (extra passage among {r['other_language']}-language "
              f"chunks): {r['other_query']}\n")
        if r["error"]:
            print(f"Note: {r['error']}\n")
        print(f"--- Answer ({r['model']}, {r['prompt_tokens']} prompt tokens read) ---\n{r['answer']}")
        print("\n--- Sources ---")
        for i, (s, d, via) in enumerate(zip(r["sources"], r["distances"], r["via"]), 1):
            print(f"{i}. {s}  (d={d}{', other language' if via == 'other-language' else ''})")
        if not r["success"]:
            sys.exit(1)
