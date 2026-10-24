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
    in the embedding space). The advisor's queries are English, so the Russian books were
    effectively unreachable. Now the query is also translated into the corpus's other language
    (English <-> Russian, by the same local model, temperature 0), and the best passage for the
    translation that is not already among the N_CHUNKS passages is added (N_OTHER = 1):
    the model reads N_CHUNKS + N_OTHER = 5 passages. The four passages for the query as asked
    are unchanged, so nothing that was found before can be lost;
  - the result also contains "translated_query" and, per passage, "via" (query/translation);
  - the translation is checked before it is used: the first test of the plain prompt drifted into
    Chinese in mid-sentence ("механического合金化…") and then added a comment. The prompt is
    now written in the target language with one worked example, only the first paragraph is
    kept, and a translation with Chinese characters, the wrong script or an implausible length
    is rejected (one retry with a stricter prompt, then the advisor falls back to the query
    alone and says so).

Usage from alloy_desktop_v2.py (subprocess, RAG venv):
    python synthesis_rag.py '{"system_name": "Mn-Al-C", "suggested_routes": ["mechanical alloying"],
                              "composition": {"Mn": 0.47, "Al": 0.52, "C": 0.01}}'
Interactive test (no argument):
    python synthesis_rag.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import chromadb

# ── Settings (shared with rag_benchmark.py) ──────────────────────────────────
STAGE_THREE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = STAGE_THREE_DIR / "chroma_db"
COLLECTIONS = ["synthesis_v2_bge"]      # searched together; results merged by distance
MODEL = "qwen2.5:14b"
N_CHUNKS = 4                         # passages for the query as asked
N_OTHER = 1                          # + best new passage for the query translated (0 = off)
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

# Translation prompts: instruction in the target language + one worked example (see 24 Oct notes)
TRANSLATE = {
    "Russian": {
        "system": "Ты переводчик научных текстов по материаловедению. Отвечай только переводом "
                  "на русский язык, без пояснений. Химические формулы, символы элементов, числа и "
                  "единицы оставляй без изменений.",
        "user": "Переведи на русский язык:\n\n{text}",
        "example": ("What is the coercivity of hot-deformed Nd2Fe14B magnets (Nd 13 at%)?",
                    "Какова коэрцитивная сила горячедеформированных магнитов Nd2Fe14B (Nd 13 at%)?"),
        "strict": "Только русский язык. Никаких китайских иероглифов и комментариев.",
    },
    "English": {
        "system": "You translate materials-science texts. Reply only with the English translation, "
                  "without comments. Keep chemical formulas, element symbols, numbers and units unchanged.",
        "user": "Translate into English:\n\n{text}",
        "example": ("Какова коэрцитивная сила горячедеформированных магнитов Nd2Fe14B (Nd 13 at%)?",
                    "What is the coercivity of hot-deformed Nd2Fe14B magnets (Nd 13 at%)?"),
        "strict": "English only. No Chinese characters and no comments.",
    },
}
CJK = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")


class TranslationError(RuntimeError):
    pass


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
        out.append(_collections[name])
    return out


# ── Retrieval and generation (rag_benchmark.py imports these) ────────────────
def retrieve(collections: list, query: str, k: int) -> list[dict]:
    """Top-k chunks over all given collections, merged by distance (smaller = closer)."""
    hits = []
    for col in collections:
        n = min(k, col.count())
        if n == 0:
            continue
        r = col.query(query_texts=[query], n_results=n,
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


def check_translation(source: str, out: str, target: str) -> str | None:
    """Reason why *out* is not a usable translation of *source* into *target*, or None."""
    if not out:
        return "empty"
    if CJK.search(out):
        return "contains Chinese characters"
    cyr, lat = _letters(out)
    if target == "Russian" and cyr < 2 * lat:
        return f"not mainly Cyrillic ({cyr} Cyrillic, {lat} Latin letters)"
    if target == "English" and cyr > 0:
        return f"contains {cyr} Cyrillic letters"
    ratio = len(out) / max(1, len(source))
    if not 0.5 <= ratio <= 2.5:
        return f"implausible length ({ratio:.1f} x the original)"
    return None


def translate(text: str, target: str, model: str = MODEL) -> str:
    """Translate a query with the local model (temperature 0: the same query gives the same text).
    Raises TranslationError if no attempt passes check_translation()."""
    import ollama
    t = TRANSLATE[target]
    problems = []
    for attempt in (1, 2):
        system = t["system"] + (" " + t["strict"] if attempt == 2 else "")
        ex_q, ex_a = t["example"]
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": t["user"].format(text=ex_q)},
                    {"role": "assistant", "content": ex_a},
                    {"role": "user", "content": t["user"].format(text=text)}]
        resp = ollama.chat(model=model, messages=messages,
                           options={"temperature": TEMPERATURE, "num_ctx": 4096,
                                    "num_predict": max(64, len(text))})
        out = resp["message"]["content"].strip()
        out = re.split(r"\n\s*\n", out, maxsplit=1)[0].strip()      # first paragraph only
        for prefix in ("Translation:", "Перевод:"):
            if out.startswith(prefix):
                out = out[len(prefix):].strip()
        out = out.strip('"«»“”')
        why = check_translation(text, out, target)
        if why is None:
            return out
        problems.append(f"attempt {attempt}: {why}: {out[:80]!r}")
    raise TranslationError("; ".join(problems))


def retrieve_bilingual(collections: list, query: str, k: int, n_first: int = N_CHUNKS,
                       n_other: int = N_OTHER, model: str = MODEL) -> tuple[list[dict], str | None]:
    """Ranked passages for the query and for its translation into the corpus's other language.

    Order: the n_first best passages for the query as asked, then the n_other best passages for
    the translation that are not already listed, then the remaining passages of both lists
    alternately (for ranking only). Returns (passages, translated query or None)."""
    primary = retrieve(collections, query, k)
    if n_other <= 0:
        return primary, None
    target = "Russian" if query_language(query) == "English" else "English"
    translated = translate(query, target, model)
    secondary = retrieve(collections, translated, k)
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
        added += add(h, "translation")
    rest_p = [h for h in primary[n_first:] if h["key"] not in seen]
    rest_s = [h for h in secondary if h["key"] not in seen]
    for i in range(max(len(rest_p), len(rest_s))):
        if i < len(rest_p):
            add(rest_p[i], "query")
        if i < len(rest_s):
            add(rest_s[i], "translation")
    return out[:k], translated


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


# ── Main entry point ─────────────────────────────────────────────────────────
def query_synthesis(system_name, suggested_routes, composition, n_chunks=N_CHUNKS, model=MODEL) -> dict:
    """
    Returns {
        "answer":        str   — the model's answer (or an error message)
        "query":         str   — the query that was sent
        "chunks":        list  — the retrieved passages (full text)
        "translated_query": str — the query in the corpus's other language (or None)
        "sources":       list  — book file name of each passage, best first
        "distances":     list  — distance of each passage (smaller = closer)
        "via":           list  — "query" or "translation" for each passage
        "collections":   list  — collections searched
        "model":         str
        "prompt_tokens": int   — prompt tokens the model read
        "success":       bool
        "error":         str or None
    }
    """
    result = {"answer": "", "query": "", "translated_query": None, "chunks": [], "sources": [],
              "distances": [], "via": [],
              "collections": list(COLLECTIONS), "model": model, "prompt_tokens": 0,
              "success": False, "error": None}
    try:
        query = build_query(system_name, suggested_routes, composition)
        result["query"] = query
        cols = get_collections()
        try:
            hits, translated = retrieve_bilingual(cols, query, n_chunks + N_OTHER, n_first=n_chunks)
            result["translated_query"] = translated
        except TranslationError as e:                # translation failed: answer from the query alone
            hits = [dict(h, via="query") for h in retrieve(cols, query, n_chunks)]
            result["error"] = f"translation failed, monolingual retrieval used: {e}"
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
        print(f"\nQuery: {r['query']}\nTranslated: {r['translated_query']}\n")
        print(f"--- Answer ({r['model']}, {r['prompt_tokens']} prompt tokens read) ---\n{r['answer']}")
        print("\n--- Sources ---")
        for i, (s, d, via) in enumerate(zip(r["sources"], r["distances"], r["via"]), 1):
            print(f"{i}. {s}  (d={d}{', via translation' if via == 'translation' else ''})")
        if not r["success"]:
            sys.exit(1)
