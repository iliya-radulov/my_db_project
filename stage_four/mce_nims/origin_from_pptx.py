"""
origin_from_pptx.py

Extracts the worksheet data of Origin graphs embedded in a PowerPoint file,
without Origin (and without Windows).

An Origin graph pasted into PowerPoint is stored as an OLE object
(ppt/embeddings/oleObjectN.bin, ProgID 'Origin50.Graph') whose 'Contents'
stream is a complete Origin project ('CPYA ...' header), including every
dataset the graph plots. That stream is a sequence of blocks
[int32 size]['\\n'][payload]['\\n']; a dataset is a 146-byte header block
with the column's short name at offset 88 (e.g. 'Ni01_C190' = book Ni01,
column C190), followed by a block of values. Values are float64, stored
either as plain 8 bytes or as a 2-byte flag + 8 bytes; the layout is
detected per column. This covers the numeric columns; text columns, long
names and units are not decoded -- identify columns from the slide.

Checked against independent values: the Ni series' Tc, |ΔS| and ΔTad
read this way agree with the values NIMS took from the published paper.

Usage:
  python origin_from_pptx.py slides.pptx out_dir/
writes out_dir/slideNN_oleObjectM.csv (one file per embedded graph, one
column per dataset, shorter columns padded with empty cells) and prints
a summary.
"""
import re
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
import olefile
import pandas as pd

HEADER_SIZE = 146
NAME_OFFSET = 88
MISSING = -1.23456789e-300           # Origin's missing-value marker


def _blocks(data):
    p = data.find(b'\n') + 1          # skip the 'CPYA ...' header line
    while p + 5 <= len(data):
        size = struct.unpack('<i', data[p:p + 4])[0]
        if data[p + 4:p + 5] != b'\n' or size < 0 or p + 5 + size > len(data):
            return
        yield p + 5, size
        p += 5 + size + (1 if size > 0 else 0)


def _decode_values(raw):
    """Try the two value layouts; keep the one that gives sensible numbers."""
    best = None
    for width, offset in ((8, 0), (10, 2)):
        if not raw or len(raw) % width:
            continue
        arr = (np.frombuffer(raw, np.uint8).reshape(-1, width)[:, offset:offset + 8]
               .copy().view('<f8').ravel())
        score = (np.isfinite(arr) & (np.abs(arr) < 1e12)).mean()
        if best is None or score > best[0]:
            best = (score, arr)
    if best is None or best[0] < 0.9:
        return None
    arr = best[1].copy()
    arr[(np.abs(arr) > 1e12) | np.isclose(arr, MISSING, rtol=0, atol=1e-310)] = np.nan
    return arr


def origin_datasets(contents):
    """{dataset name: values} from one Origin 'Contents' stream."""
    blocks = list(_blocks(contents))
    out = {}
    for k, (start, size) in enumerate(blocks[:-1]):
        if size != HEADER_SIZE:
            continue
        name = contents[start + NAME_OFFSET:start + NAME_OFFSET + 25].split(b'\0')[0]
        if not re.fullmatch(rb'[A-Za-z0-9_@.\-]+_[A-Za-z0-9]+', name or b'-'):
            continue
        data_start, data_size = blocks[k + 1]
        values = _decode_values(contents[data_start:data_start + data_size])
        if values is not None:
            out[name.decode()] = values
    return out


def _embedding_slides(pptx):
    """{'oleObject5.bin': [14], ...} from the slide relationship files."""
    slides = {}
    for name in pptx.namelist():
        m = re.fullmatch(r'ppt/slides/_rels/slide(\d+)\.xml\.rels', name)
        if not m:
            continue
        for target in re.findall(r'Target="\.\./embeddings/([^"]+)"', pptx.read(name).decode('utf-8')):
            slides.setdefault(target, []).append(int(m.group(1)))
    return slides


def extract(pptx_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    with zipfile.ZipFile(pptx_path) as pptx:
        slides = _embedding_slides(pptx)
        for name in sorted((n for n in pptx.namelist() if n.startswith('ppt/embeddings/')),
                           key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]):
            raw = pptx.read(name)
            if not olefile.isOleFile(raw):
                continue
            ole = olefile.OleFileIO(raw)
            if not ole.exists('Contents'):
                continue
            contents = ole.openstream('Contents').read()
            if not contents.startswith(b'CPYA'):
                continue
            ds = origin_datasets(contents)
            if not ds:
                continue
            obj = Path(name).stem
            slide = '-'.join(str(s) for s in slides.get(Path(name).name, [])) or 'unknown'
            n = max(len(v) for v in ds.values())
            table = pd.DataFrame({k: np.pad(v, (0, n - len(v)), constant_values=np.nan) for k, v in ds.items()})
            table = table.dropna(how='all')
            path = out_dir / f"slide{slide}_{obj}.csv"
            table.to_csv(path, index=False)
            summary.append((slide, obj, len(ds), len(table), path.name))
    return summary


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    for slide, obj, n_cols, n_rows, fname in extract(sys.argv[1], sys.argv[2]):
        print(f"slide {slide:>5}  {obj:14s} {n_cols:3d} columns, {n_rows:5d} rows -> {fname}")
