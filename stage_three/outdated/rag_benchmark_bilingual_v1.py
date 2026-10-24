"""
rag_benchmark.py — retrieval (and optional answer) benchmark for the Stage 3 RAG advisor.

For every question in rag_benchmark_questions.csv:
  1. find the GOLD chunk(s): chunks of the named book that contain the copied gold phrase
     (matching ignores case, line-break hyphenation, ligatures and spacing);
  2. run retrieval and record the rank of the first gold chunk;
  3. (MiniLM only) record whether the gold phrase lies in the part of the chunk that the
     embedding model actually sees (first 256 tokens) — tests the truncation finding;
  4. (--generate) ask the LLM with the top-4 chunks and write a grading sheet: you mark
     correct / faithful / refused by hand.
Retrieval, prompt, model settings and generation are imported from synthesis_rag.py, the code
the desktop app runs, so the benchmark evaluates the app's own settings. Only the query differs:
here the question as written, in the app a query built from the composition.

Metrics: hit@1, hit@3, hit@5, hit@10 and MRR, overall and by language, collection and
"phrase in embedded part / in cut-off tail".

Usage (ML desktop, stage_three RAG venv, script next to chroma_db/):
    python rag_benchmark.py --tag minilm_baseline
    python rag_benchmark.py --tag minilm_baseline --generate          # + answers to grade
    python rag_benchmark.py --tag minilm_all --route all              # no collection routing
    python rag_benchmark.py --tag bge --suffix _bge                    # re-indexed collections
    python rag_benchmark.py --tag v2_bge --set _v2 --suffix _bge       # rebuilt set (rag_rebuild_v2.py)
Options:
    --questions FILE   (default rag_benchmark_questions.csv)
    --chroma PATH      (default chroma_db next to this script)
    --k N              retrieved chunks to score (default 10)
    --embed SPEC       auto (default: the function each collection was indexed with),
                       default, ollama:<model>, or hash (offline test only)
    --collections ...  benchmark collections (default phase_stability synthesis magnetic)
    --exclude NAMES    collections never searched (default powder_metallurgy)
The `collection` column may be left empty: the script then finds the book's collection itself.
Rows without a gold phrase yet (empty or starting with '<') are skipped, so the file can be
filled in gradually. The book name is matched loosely (case, punctuation and '_' ignored).
When a phrase is not found, the run prints hints: the longest part of the phrase that the
book does contain, and any other book/collection where the whole phrase occurs.
    --model NAME       LLM for --generate (default: synthesis_rag.MODEL), temperature 0,
                       context window synthesis_rag.NUM_CTX (the prompt tokens read are recorded)
Outputs: benchmark_runs/<tag>/results.csv, summary.json, and with --generate answers.md + grading.csv
    --context          also write contexts.md (the full text of the top-4 chunks per question);
                       re-running a tag with only --context checks that the ranks are reproduced
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics as st
import unicodedata
from collections import defaultdict
from pathlib import Path

import chromadb

HERE = Path(__file__).resolve().parent
DEFAULT_TOKENIZER = (Path.home() / ".cache" / "chroma" / "onnx_models"
                     / "all-MiniLM-L6-v2" / "onnx" / "tokenizer.json")
MAX_TOKENS = 256
KS = (1, 3, 5, 10)
# Shared with the app: number of passages, prompt, model settings, retrieval, generation
from synthesis_rag import (N_CHUNKS as N_CONTEXT, N_OTHER, NUM_CTX, MODEL, PROMPT,  # noqa: E402
                           retrieve, retrieve_bilingual, generate)
REFUSAL = re.compile(r"(does not contain|do not contain|not enough information|insufficient"
                     r"|no information|cannot be determined|not (?:specified|mentioned|provided))",
                     re.I)
NUM = re.compile(r"\d+(?:[.,]\d+)?")


# ── text normalisation for phrase matching ───────────────────────────────────
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)          # "magne- tic" → "magnetic"
    return re.sub(r"\s+", " ", s).strip().lower()


# ── embedding functions ──────────────────────────────────────────────────────
class HashEF(chromadb.EmbeddingFunction):
    """Bag-of-words hashing embedding. OFFLINE TESTING ONLY — never for real results."""
    def __init__(self, dim: int = 512):
        self.dim = dim
    def __call__(self, input):
        out = []
        for text in input:
            v = [0.0] * self.dim
            for w in re.findall(r"\w+", text.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out
    @staticmethod
    def name() -> str:
        return "hash_test"
    def get_config(self):
        return {"dim": self.dim}
    @staticmethod
    def build_from_config(config):
        return HashEF(**config)


def make_ef(spec: str):
    if spec == "auto":
        return None
    if spec == "default":
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        return DefaultEmbeddingFunction()
    if spec.startswith("ollama:"):
        from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
        return OllamaEmbeddingFunction(model_name=spec.split(":", 1)[1])
    if spec == "hash":
        return HashEF()
    raise SystemExit(f"Unknown --embed '{spec}'")


def open_collection(client, name, ef):
    if ef is None:
        return client.get_collection(name)
    return client.get_collection(name, embedding_function=ef)


# ── truncation check (MiniLM only) ───────────────────────────────────────────
def load_tokenizer(path: Path):
    if not path.exists():
        return None
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(path))
    tok.no_truncation()
    tok.no_padding()
    return tok


def phrase_in_embedded_part(tok, doc: str, phrase: str):
    """True if the gold phrase ends before the 256-token cut (approximate, by word position)."""
    if tok is None:
        return None
    nd, nphr = norm(doc), norm(phrase)
    pos = nd.find(nphr)
    if pos < 0:
        return None
    end_ratio = len(nd[:pos + len(nphr)].split()) / max(len(nd.split()), 1)
    enc = tok.encode(doc)                      # [CLS] t1 … tn [SEP]
    if len(enc.ids) <= MAX_TOKENS:
        return True
    cut_char = enc.offsets[MAX_TOKENS - 1][0]  # first token beyond [CLS] + 254 kept tokens
    seen_ratio = len(doc[:cut_char].split()) / max(len(doc.split()), 1)
    return end_ratio <= seen_ratio


# ── gold chunks ──────────────────────────────────────────────────────────────
PAGE = 5000      # ChromaDB fails on very large get() calls ("too many SQL variables") → page


def get_all(col, include, **kw):
    out = {"ids": [], **{k: [] for k in include}}
    offset = 0
    while True:
        r = col.get(include=include, limit=PAGE, offset=offset, **kw)
        out["ids"] += r["ids"]
        for k in include:
            out[k] += r[k]
        if len(r["ids"]) < PAGE:
            return out
        offset += len(r["ids"])


def src_key(s: str) -> str:
    """File-name comparison ignores case, punctuation, underscores and '.pdf'."""
    return " ".join(re.findall(r"[^\W_]+", norm(s).removesuffix(".pdf")))


CYR = re.compile(r"[а-яё]", re.I)


class GoldFinder:
    def __init__(self):
        self._sources: dict[str, list[str]] = {}

    def sources(self, col) -> list[str]:
        if col.name not in self._sources:
            metas = get_all(col, ["metadatas"])["metadatas"]
            self._sources[col.name] = sorted({(m or {}).get("source", "") for m in metas} - {""})
        return self._sources[col.name]

    def match_sources(self, col, source_spec: str) -> list[str]:
        """Books whose file name contains source_spec (or, failing that, all of its words)."""
        want = src_key(source_spec)
        if not want:
            return []
        keys = {s: src_key(s) for s in self.sources(col)}
        hit = [s for s, k in keys.items() if want in k]
        if not hit:
            words = set(want.split())
            hit = [s for s, k in keys.items() if words <= set(k.split())]
        return hit

    def find(self, col, source_spec: str, phrase: str):
        """Return (status, gold_ids, matched_sources, {id: doc})."""
        nphr = norm(phrase)
        if not nphr:
            return "no_gold_phrase", [], [], {}
        if source_spec.strip():
            cands = self.match_sources(col, source_spec)
            if not cands:
                return "source_not_indexed", [], [], {}
            got = get_all(col, ["documents"], where={"source": {"$in": cands}})
        else:
            cands = []
            got = get_all(col, ["documents"])
        gold = {i: d for i, d in zip(got["ids"], got["documents"]) if nphr in norm(d)}
        if not gold:
            return "phrase_not_found", [], cands, {}
        return "ok", list(gold), cands, gold

    # ── hints for the check run ──────────────────────────────────────────────
    @staticmethod
    def search_phrase(col, phrase: str) -> dict[str, str]:
        """Chunks anywhere in the collection that contain the phrase → {id: source}.
        Candidates come from ChromaDB's text search on the phrase's longest words."""
        nphr = norm(phrase)
        words = sorted(set(re.findall(r"[^\W\d_]{6,}", phrase)), key=len, reverse=True)[:3]
        found = {}
        for w in words:
            got = get_all(col, ["documents", "metadatas"], where_document={"$contains": w})
            for i, d, m in zip(got["ids"], got["documents"], got["metadatas"]):
                if nphr in norm(d):
                    found[i] = (m or {}).get("source", "")
        return found

    @staticmethod
    def longest_run(col, sources: list[str], phrase: str) -> tuple[int, int, str]:
        """Longest run of consecutive phrase words that does occur in these books' chunks."""
        docs = get_all(col, ["documents"], where={"source": {"$in": sources}})["documents"]
        text = " | ".join(norm(d) for d in docs)
        w = norm(phrase).split()
        best, i, j = (0, ""), 0, 0
        while i < len(w):
            j = max(j, i)
            while j < len(w) and " ".join(w[i:j + 1]) in text:
                j += 1
            if j - i > best[0]:
                best = (j - i, " ".join(w[i:j]))
            i += 1
        return best[0], len(w), best[1]


# ── retrieval ────────────────────────────────────────────────────────────────
# ── summary ──────────────────────────────────────────────────────────────────
def metrics(rows):
    if not rows:
        return {"n": 0}
    out = {"n": len(rows)}
    for k in KS:
        out[f"hit@{k}"] = round(sum(r[f"hit@{k}"] for r in rows) / len(rows), 3)
    out["MRR"] = round(st.mean(r["mrr"] for r in rows), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--questions", type=Path, default=Path("rag_benchmark_questions.csv"))
    ap.add_argument("--chroma", type=Path, default=HERE / "chroma_db")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--set", default="", help="collection set, e.g. _v2 (names: base + set + suffix)")
    ap.add_argument("--route", choices=["given", "all"], default="given")
    ap.add_argument("--collections", nargs="*", default=["phase_stability", "synthesis", "magnetic"],
                    help="benchmark collections (base names, without suffix)")
    ap.add_argument("--exclude", nargs="*", default=["powder_metallurgy"])
    ap.add_argument("--embed", default="auto")
    ap.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--context", action="store_true",
                    help="write contexts.md: full text of the chunks given to the model (no LLM call)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--outdir", type=Path, default=Path("benchmark_runs"))
    ap.add_argument("--bilingual", action="store_true",
                    help="retrieval as the advisor does it since 24 Oct: the query plus its translation "
                         f"into the other corpus language; the model gets {N_CONTEXT} + {N_OTHER} passages")
    args = ap.parse_args()
    n_ctx = N_CONTEXT + (N_OTHER if args.bilingual else 0)

    # The CSV may come back from a spreadsheet program with ';' or tab as separator
    # (e.g. LibreOffice with a German locale) — use whichever the header line uses.
    with open(args.questions, encoding="utf-8-sig", newline="") as f:
        header = f.readline()
        f.seek(0)
        sep = max([",", ";", "\t"], key=header.count)
        qs = [{(k or "").strip(): (v or "") for k, v in r.items()}
              for r in csv.DictReader(f, delimiter=sep)]
    if "gold_phrase" not in (qs[0] if qs else {}):
        raise SystemExit(f"{args.questions}: no 'gold_phrase' column — header read as {header.strip()!r}")

    def unfinished(r):
        q, ph = (r.get("question") or "").strip(), (r.get("gold_phrase") or "").strip()
        if not q or q.startswith("<"):
            return True
        return (r.get("kind") or "").strip() != "out_of_corpus" and (not ph or ph.startswith("<"))
    skipped = [r["id"] for r in qs if unfinished(r)]
    qs = [r for r in qs if not unfinished(r)]
    if skipped:
        print(f"Skipping {len(skipped)} unfinished rows (no question or no gold phrase yet): {', '.join(skipped)}")

    client = chromadb.PersistentClient(path=str(args.chroma))
    ef = make_ef(args.embed)
    all_names = [c if isinstance(c, str) else c.name for c in client.list_collections()]
    cache = {}
    def col(name):
        if name not in cache:
            cache[name] = open_collection(client, name, ef)
        return cache[name]

    # the benchmark collections (with the suffix applied); --route all searches all of them
    sfx = args.set + args.suffix                    # e.g. "_v2" + "_bge"
    route_all = [c + sfx for c in args.collections
                 if c not in args.exclude and c + sfx in all_names]
    missing = [c + sfx for c in args.collections if c + sfx not in all_names]
    if missing:
        print(f"Collections not found: {', '.join(missing)}")

    uses_minilm = args.embed in ("auto", "default") and not args.suffix
    # truncation check: automatic for MiniLM collections, or whenever a tokenizer is given explicitly
    tok = load_tokenizer(args.tokenizer) if (uses_minilm or args.tokenizer != DEFAULT_TOKENIZER) else None
    gf = GoldFinder()
    out_dir = args.outdir / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)

    def locate(source_spec: str) -> list[str]:
        """Benchmark collections that contain a book whose file name matches source_spec."""
        return [n for n in route_all if gf.match_sources(col(n), source_spec)]

    rows, answers, contexts = [], [], []
    for q in qs:
        qid, kind = q["id"], (q.get("kind") or "").strip()
        given = (q.get("collection") or "").strip()
        lang = (q.get("source_language") or "").strip() or \
            ("ru" if CYR.search(q.get("gold_phrase") or q["question"]) else "en")
        row = {"id": qid, "kind": kind, "language": lang,
               "collection": "", "status": "", "n_gold": 0, "rank": "", "mrr": 0.0,
               "in_embedded_part": "", "top1_source": "", "top1_distance": "", "hint": ""}
        hints = []
        if given and given + sfx not in all_names:
            hints.append(f"collection '{given}' does not exist — ignored")
            given = ""

        # which collection holds the answer: the one that has the book, else the given one
        found = locate(q.get("gold_source", "")) if kind != "out_of_corpus" else []
        if given and given + sfx in found:
            cname = given + sfx
        elif found:
            cname = found[0]
            if given:
                hints.append(f"book is in '{cname}', not in '{given}' — using '{cname}'")
        elif given:
            cname = given + sfx
        else:
            cname = ""
        if args.route == "all" or not cname:
            search = [col(n) for n in route_all]          # out-of-corpus without a collection: search all
        elif cname in all_names:
            search = [col(cname)]
        else:
            search = []
        row["collection"] = "ALL" if (args.route == "all" or not cname) else cname

        gold_keys, gold_docs = set(), {}
        if kind == "out_of_corpus":
            row["status"] = "out_of_corpus"
        elif not cname:
            row["status"] = "source_not_indexed"
        elif cname not in all_names:
            row["status"] = "collection_missing"
        else:
            gold_col = col(cname)
            status, ids, cands, docs = gf.find(gold_col, q.get("gold_source", ""), q.get("gold_phrase", ""))
            row["status"], row["n_gold"] = status, len(ids)
            gold_keys = {(gold_col.name, i) for i in ids}
            gold_docs = docs
            if status == "phrase_not_found" and cands:
                n, total, run = gf.longest_run(gold_col, cands, q["gold_phrase"])
                hints.append(f"in the book, the longest matching part is {n} of {total} words"
                             + (f": \"{run}\"" if run else ""))

        # phrase not where expected → look for it in every benchmark collection
        if row["status"] in ("source_not_indexed", "phrase_not_found", "collection_missing"):
            elsewhere = {}
            for n in route_all:
                for cid, s in gf.search_phrase(col(n), q.get("gold_phrase", "")).items():
                    elsewhere.setdefault((s, n), cid)
            for (s, n), cid in elsewhere.items():
                hints.append(f"phrase found in '{n}', book: {s}")
            if not elsewhere and row["status"] != "phrase_not_found":
                hints.append("phrase not found in any collection either")
        row["hint"] = " | ".join(hints)

        translated = None
        if args.bilingual:
            hits, translated = retrieve_bilingual(search, q["question"], args.k)
        else:
            hits = retrieve(search, q["question"], args.k)
        if hits:
            row["top1_source"], row["top1_distance"] = hits[0]["source"], round(hits[0]["distance"], 4)
        if row["status"] == "ok":
            rank = next((n for n, h in enumerate(hits, 1) if h["key"] in gold_keys), None)
            row["rank"] = rank or ""
            row["mrr"] = 1.0 / rank if rank else 0.0
            for k in KS:
                row[f"hit@{k}"] = int(bool(rank and rank <= k))
            if tok is not None:
                flags = [phrase_in_embedded_part(tok, d, q["gold_phrase"]) for d in gold_docs.values()]
                flags = [f for f in flags if f is not None]
                row["in_embedded_part"] = "yes" if any(flags) else ("no" if flags else "")
        rows.append(row)

        ctx = hits[:n_ctx]
        if args.generate or args.context:
            contexts.append({"q": q, "row": row, "ctx": ctx, "gold": gold_keys, "translated": translated})
        if args.generate:
            answer, prompt_tokens = generate(args.model, q["question"], [h["doc"] for h in ctx])
            ctx_norm, q_norm = norm(" ".join(h["doc"] for h in ctx)), norm(q["question"])
            # numbers that appear neither in the context nor in the question itself
            unsupported = sorted({n for n in NUM.findall(answer) if n not in ctx_norm and n not in q_norm})
            answers.append({"q": q, "row": row, "ctx": ctx, "gold": gold_keys, "answer": answer,
                            "refused_auto": "yes" if REFUSAL.search(answer) else "no",
                            "unsupported": unsupported, "prompt_tokens": prompt_tokens,
                            "translated": translated})
        print(f"  {qid}: {row['status']:<18} rank={row['rank'] or '-':<3} "
              f"embedded={row['in_embedded_part'] or '-'}", flush=True)
        if translated:
            print(f"        translated: {translated}", flush=True)
        for h in hints:
            print(f"        → {h}", flush=True)

    # ── a re-run must reproduce the earlier ranks (retrieval is deterministic) ──
    old_csv = out_dir / "results.csv"
    if old_csv.exists():
        with open(old_csv, encoding="utf-8", newline="") as f:
            old = {r["id"]: r.get("rank", "") for r in csv.DictReader(f)}
        diff = [r["id"] for r in rows if r["id"] in old and str(old[r["id"]]) != str(r["rank"])]
        print(f"\nSame ranks as the earlier run in {out_dir}: "
              + ("yes" if not diff else f"NO — differ for {', '.join(diff)}"))

    if contexts:
        with open(out_dir / "contexts.md", "w", encoding="utf-8") as f:
            f.write(f"# Context given to the model — {args.tag} (top {n_ctx} chunks per question"
                    f"{', bilingual retrieval' if args.bilingual else ''})\n\n")
            for c in contexts:
                q, row = c["q"], c["row"]
                f.write(f"## {q['id']} — {q['question']}\n\n")
                f.write(f"*gold:* {q.get('gold_source') or '-'} · *gold phrase:* {q.get('gold_phrase') or '-'} · "
                        f"*retrieval:* {row['status']}, rank {row['rank'] or '-'}\n\n")
                if c.get("translated"):
                    f.write(f"*translated query:* {c['translated']}\n\n")
                for n, h in enumerate(c["ctx"], 1):
                    mark = "  [GOLD]" if h["key"] in c["gold"] else ""
                    if h.get("via") == "translation":
                        mark += "  (via translation)"
                    f.write(f"### {n}. {h['source']} (d={h['distance']:.3f}){mark}\n\n```text\n{h['doc']}\n```\n\n")
                f.write("---\n\n")

    # ── write results ────────────────────────────────────────────────────────
    fields = ["id", "kind", "language", "collection", "status", "n_gold", "rank",
              *[f"hit@{k}" for k in KS], "mrr", "in_embedded_part", "top1_source", "top1_distance",
              "hint"]
    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    scored = [r for r in rows if r["status"] == "ok"]
    groups = defaultdict(list)
    for r in scored:
        groups[f"language={r['language'] or '?'}"].append(r)
        groups[f"collection={r['collection']}"].append(r)
        if r["in_embedded_part"]:
            groups[f"phrase_in_embedded_part={r['in_embedded_part']}"].append(r)
    summary = {
        "tag": args.tag, "k": args.k, "route": args.route, "suffix": args.suffix, "set": args.set,
        "embed": args.embed, "questions": len(rows), "bilingual": args.bilingual, "passages": n_ctx,
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
        "overall": metrics(scored),
        "groups": {g: metrics(v) for g, v in sorted(groups.items())},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.generate:
        with open(out_dir / "answers.md", "w", encoding="utf-8") as f:
            f.write(f"# Answers — {args.tag} (model {args.model}, temperature 0, context {NUM_CTX} tokens"
                    f"{', bilingual retrieval, ' + str(n_ctx) + ' passages' if args.bilingual else ''})\n\n")
            for a in answers:
                q, row = a["q"], a["row"]
                f.write(f"## {q['id']} — {q['question']}\n\n")
                f.write(f"*kind:* {row['kind'] or '-'} · *gold:* {q.get('gold_source') or '-'} · "
                        f"*retrieval:* {row['status']}, rank {row['rank'] or '-'}\n\n")
                if a.get("translated"):
                    f.write(f"*Translated query:* {a['translated']}\n\n")
                f.write("**Context given to the model:**\n\n")
                for n, h in enumerate(a["ctx"], 1):
                    mark = " **[GOLD]**" if h["key"] in a["gold"] else ""
                    if h.get("via") == "translation":
                        mark += " *(via translation)*"
                    f.write(f"{n}. {h['source']} (d={h['distance']:.3f}){mark}\n")
                f.write(f"\n*Prompt tokens read by the model:* {a['prompt_tokens']}\n")
                f.write(f"\n**Answer:**\n\n{a['answer']}\n\n")
                if a["unsupported"]:
                    f.write(f"*Numbers in the answer not found in the context:* {', '.join(a['unsupported'])}\n\n")
                f.write("---\n\n")
        with open(out_dir / "grading.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "kind", "retrieval_rank", "refused_auto", "numbers_not_in_context",
                        "correct (yes/partly/no)", "faithful (yes/no)", "refused (yes/no)", "comment",
                        "prompt_tokens"])
            for a in answers:
                w.writerow([a["q"]["id"], a["row"]["kind"], a["row"]["rank"], a["refused_auto"],
                            " ".join(a["unsupported"]), "", "", "", "", a["prompt_tokens"]])

    # ── print summary ────────────────────────────────────────────────────────
    print(f"\n=== {args.tag}  (route={args.route}, embed={args.embed}{', suffix=' + args.suffix if args.suffix else ''}) ===")
    print("status:", summary["status_counts"])
    o = summary["overall"]
    if o["n"]:
        print(f"overall  n={o['n']:<3} " + "  ".join(f"hit@{k}={o[f'hit@{k}']:.2f}" for k in KS) + f"  MRR={o['MRR']:.2f}")
        for g, m in summary["groups"].items():
            print(f"  {g:<34} n={m['n']:<3} hit@5={m['hit@5']:.2f}  MRR={m['MRR']:.2f}")
    print(f"\nSaved → {out_dir}/")


if __name__ == "__main__":
    main()
