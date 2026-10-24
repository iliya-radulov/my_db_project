"""
check_ctx.py — did Ollama read the whole benchmark prompt?  (read-only, about 2-4 minutes)

rag_benchmark.py --generate sends one prompt per question: instruction + the top-4 chunks +
the question, about 2,000-4,000 tokens. Ollama reads at most `num_ctx` tokens of a prompt;
the benchmark (and synthesis_rag.py) never set num_ctx, so the server default applied.
If the prompt is longer, Ollama cuts it without an error.

This script rebuilds every prompt from contexts.md and sends it twice, generating only one token:
  A) as the benchmark did:          options {"temperature": 0}
  B) with a large context window:   options {"temperature": 0, "num_ctx": 16384}
Ollama reports how many prompt tokens it read (prompt_eval_count). If A < B, the prompt was cut.

Usage (stage_three/, RAG venv active):
    python check_ctx.py                                   # benchmark_runs/bge/contexts.md
    python check_ctx.py benchmark_runs/minilm/contexts.md
"""
import re
import subprocess
import sys
from pathlib import Path

import ollama

MODEL = "qwen2.5:14b"
BIG = 16384
PROMPT = """You are a materials science assistant.
Answer the question based ONLY on the provided context.
If the context does not contain enough information, say so clearly.
Do not invent data, parameters, or references.

Context:
{context}

Question: {question}

Answer:"""


def load(path: Path) -> list[tuple[str, str, list[str]]]:
    """[(id, question, [chunk texts in rank order])] from a contexts.md written by rag_benchmark.py."""
    out = []
    for block in re.split(r"\n## ", path.read_text(encoding="utf-8"))[1:]:
        head = block.split("\n", 1)[0]
        qid, _, question = head.partition(" — ")
        chunks = re.findall(r"### \d+\. .*?\n\n```text\n(.*?)\n```", block, re.S)
        out.append((qid.strip(), question, chunks))
    return out


def tokens_read(prompt: str, options: dict) -> int:
    r = ollama.generate(model=MODEL, prompt=prompt, options={**options, "num_predict": 1})
    return int(r.get("prompt_eval_count") or 0)


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmark_runs/bge/contexts.md")
    items = load(path)
    print(f"{path}: {len(items)} prompts, model {MODEL}")
    prompts = [(q, PROMPT.format(context="\n\n".join(c), question=s)) for q, s, c in items]

    print("A) server default context ...", flush=True)
    a = {q: tokens_read(p, {"temperature": 0}) for q, p in prompts}
    try:
        print(subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout)
    except FileNotFoundError:
        pass
    print(f"B) num_ctx {BIG} ...", flush=True)
    b = {q: tokens_read(p, {"temperature": 0, "num_ctx": BIG}) for q, p in prompts}

    print(f"\n{'id':5} {'A read':>7} {'B read':>7}  cut")
    cut = 0
    for q, _ in prompts:
        lost = b[q] - a[q]
        flag = f"{lost} tokens ({lost / b[q]:.0%})" if lost > 50 else ""
        cut += bool(flag)
        print(f"{q:5} {a[q]:7d} {b[q]:7d}  {flag}")
    print(f"\nPrompts cut with the server default: {cut} of {len(prompts)}")
    print(f"Largest number of tokens read in A: {max(a.values())}  (≈ the default context length)")


if __name__ == "__main__":
    main()
