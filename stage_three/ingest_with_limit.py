"""
ingest_with_limit.py — run ingest_collection.py unchanged, with pypdf's parsing limit raised.

pypdf 6.x stops parsing a page whose content stream needs more than 2,000,000 parsing
steps ("Reached maximum number of tokens per stream") — a protection against malicious
PDFs. Very large books (e.g. the 2,787-page Encyclopedia of Condensed Matter Physics)
exceed it. For our own, trusted books we raise the limit; everything else is identical.

Usage (stage_three/, RAG venv):  python ingest_with_limit.py <folder> <collection_name>
"""
import runpy
import sys
from pathlib import Path

import pypdf

LIMIT = 50_000_000
try:
    pypdf.overwrite_configuration(stream_parsing_work_maximum_count=LIMIT)
except AttributeError:
    sys.exit(f"pypdf {pypdf.__version__} has no overwrite_configuration — please tell Claude the version")
print(f"pypdf {pypdf.__version__}: stream parsing limit raised to {LIMIT:,}")

script = Path(__file__).resolve().parent / "ingest_collection.py"
sys.argv = [str(script)] + sys.argv[1:]
runpy.run_path(str(script), run_name="__main__")
