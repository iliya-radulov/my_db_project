#!/usr/bin/env python3
"""Dark-phase area fraction from BSE micrographs of La1.07Fe13-xSix (pilot, 13 Nov 2026).

Usage: python3 analyze_dark_phase.py <data_root> <out_dir>
Finds TIFs by name: 'NNNNCSi<x>.TIF' = temperature series (12 h, 2000x, 15 kV, 1424x968)
                    'SiXXh<t>_B2000/B2K.TIF' = time series (1100 C, 2000x, 30 kV, 712x484)
Method (identical for every image):
  1. 8-bit grey image, Gaussian smoothing sigma = 1.2 px; data bar and everything below it masked.
  2. Matrix grey level = histogram mode of the smoothed image; matrix noise sigma_s = MAD of
     smoothed pixels within +-10 grey levels of the mode.
  3. Pores = smoothed < 0.45 * mode (dilated 3 px), excluded from the dark phase.
  4. Dark phase = smoothed < mode - k*sigma_s (not pore), opened once; area fraction reported
     for k = 3, 4, 6, 8. k=4 is the nominal value, the k range is the threshold uncertainty.
"Dark phase" is not identified as alpha-Fe (EDX not available for these fields).
"""
import csv, os, re, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

KS = (3, 4, 6, 8)
FLAGS = {}   # no file is excluded; see the pilot record for the 1150 C / x = 1.6 discussion
root, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

def parse(path):
    n = os.path.basename(path)
    m = re.match(r'(\d{4})CSi(\d),?(\d?)\.TIF$', n, re.I)
    if m:
        x = float(m.group(2) + ('.' + m.group(3) if m.group(3) else ''))
        return dict(series='temperature', x=x, T_C=int(m.group(1)), t_h=12)
    m = re.match(r'Si(\d\d)h(\d+)_B(2000|2K)\.TIF$', n, re.I)
    if m:
        return dict(series='time', x=int(m.group(1)) / 10, T_C=1100, t_h=int(m.group(2)))
    return None

rows = []
for dp, _d, fs in os.walk(root):
    for f in sorted(fs):
        p = os.path.join(dp, f)
        meta = parse(p)
        if not meta or '__MACOSX' in p:
            continue
        a = np.array(Image.open(p).convert('L')).astype(float)
        H = a.shape[0]
        valid = np.ones(a.shape, bool)
        valid[int(H * 0.873) - 6:, :] = False          # data bar + below
        s = ndi.gaussian_filter(a, 1.2)
        v = s[valid]
        hist, edges = np.histogram(v, bins=256, range=(0, 256))
        mode = edges[np.argmax(hist)] + 0.5
        w = v[np.abs(v - mode) < 10]
        sig = 1.4826 * np.median(np.abs(w - np.median(w)))
        pore = ndi.binary_dilation(s < mode * 0.45, iterations=3)
        rec = dict(meta, file=f, flag=FLAGS.get(f, ''), px=f'{a.shape[1]}x{a.shape[0]}', matrix_grey=round(mode, 1),
                   sigma_s=round(sig, 2), pore_pct=round(100 * (pore & valid).sum() / valid.sum(), 2))
        for k in KS:
            dark = ndi.binary_opening((s < mode - k * sig) & valid & ~pore, iterations=1)
            _, n = ndi.label(dark)
            rec[f'area_pct_k{k}'] = round(100 * dark.sum() / valid.sum(), 2)
            rec[f'n_k{k}'] = n
        rows.append(rec)
rows.sort(key=lambda r: (r['series'], r['x'], r['T_C'], r['t_h']))
with open(os.path.join(out, 'dark_phase_results.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows), 'images ->', os.path.join(out, 'dark_phase_results.csv'))
