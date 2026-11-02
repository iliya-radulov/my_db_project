"""
nims_dataset.py

Loader for the NIMS La(Fe,Si)13 magnetocaloric dataset
(NIMS Materials Data Repository, doi:10.48505/nims.4909, file
1-13_dataset.xlsx; licence CC BY 4.0 -- cite the dataset when using it).

The file itself is not committed to this repository: put it in
stage_four/mce_nims/data/ (gitignored) or pass its path explicitly.

What this module takes care of, each found by opening the real file
rather than assumed from its description:

  - Headers are checked against EXPECTED_COLUMNS and the load fails
    loudly if one is missing or renamed. Some real headers are not what
    they look like: the entropy-change column is '|ΔSM|max (J/kg K) '
    (trailing space) and the density column is 'Density (g/cm3)'. A
    dict.get() with the "obvious" name silently returns None, i.e. an
    empty target column with no error.
  - Composition comes from the 24 metal element columns (at.%, summing to
    100 over the 1:13 metal sites). 'Composition in the article' is filled
    in for only about half the rows and often contains variables
    ('La(FexSi(1-x))13', '...Hy'), so it is kept as a note only.
  - H/C/N/B are separate columns in at.% relative to the metal total
    (H = 3.57 for y = 0.5 in La(Fe,Si)13Hy, i.e. y/14*100); they are not
    part of the 100 and are kept separately, otherwise a hydride looks
    identical to its parent alloy.
  - 'Article ID' and 'Article DOI' are only filled on the first row of
    each paper's block (some cells hold two DOIs on two lines); they are
    filled down here.
  - Field-dependent values are stored as list strings, e.g. HS = '[1, 2, 5]'
    with |ΔSM|max = '[10.5, 14.3, 19.4]'; expand_points() turns these into
    one row per (sample, field).
"""
from pathlib import Path
import re

import numpy as np
import pandas as pd

DATASET_DOI = "10.48505/nims.4909"
DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "1-13_dataset.xlsx"

METAL_ELEMENTS = ['Fe', 'Si', 'Al', 'Ga', 'Co', 'V', 'Cr', 'Ni', 'Cu', 'Nb', 'Mn',
                  'P', 'Zn', 'Ca', 'La', 'Nd', 'Ce', 'Pr', 'Dy', 'Ho', 'Gd', 'Y',
                  'Tb', 'Er']
# Interstitial header -> short name used everywhere else in this package.
INTERSTITIALS = {'H [or D]': 'H', 'C': 'C', 'N': 'N', 'B': 'B'}

# Exact header in the file -> short name. Load fails if any is missing.
EXPECTED_COLUMNS = {
    'Article ID': 'article_id',
    'Article DOI': 'doi',
    'Composition in the article': 'composition_text',
    'Composition details': 'composition_details',
    '1:13 Total': 'total_1_13',
    'Method': 'method',
    'Ann. Time (h)': 'anneal_time_h',
    'Ann. Temp. (K)': 'anneal_temp_K',
    'NaZn13 (%)': 'phase_1_13_pct',
    'α-Fe (%)': 'phase_alpha_fe_pct',
    'a@PM (Å)': 'a_pm_A',
    'Htr (T)': 'H_tr_T',
    'Ttr (K)': 'T_tr_K',
    'ΔThys (K)': 'T_hys_K',
    'HS (T)': 'H_S_T',
    '|ΔSM|max (J/kg K) ': 'dS_max',
    'T@|ΔSM|max (K)': 'T_at_dS_max_K',
    'ΔSM FWHM (K)': 'dS_fwhm_K',
    'Had (T)': 'H_ad_T',
    '|ΔTad|max (K)': 'dT_ad_max_K',
    'T@|ΔTad|max (K)': 'T_at_dT_ad_max_K',
    'Density (g/cm3)': 'density_g_cm3',
    'isoT/isoH [1/0]': 'isothermal_protocol',
    'COMMENTS': 'comments',
}

FIELD_LIST_COLUMNS = ['H_S_T', 'dS_max', 'T_at_dS_max_K', 'dS_fwhm_K',
                      'H_ad_T', 'dT_ad_max_K', 'T_at_dT_ad_max_K']


class NIMSFormatError(ValueError):
    """The file does not have the structure this loader was written for."""


def _parse_list(value, column, sample_id):
    """'[1, 2, 5]' -> [1.0, 2.0, 5.0]; a plain number -> [number]; empty -> [].
    Raises NIMSFormatError on anything else rather than guessing."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (int, float, np.integer, np.floating)):
        return [float(value)]
    text = str(value).strip()
    if not (text.startswith('[') and text.endswith(']')):
        try:
            return [float(text)]
        except ValueError:
            raise NIMSFormatError(f"sample {sample_id}, {column}: cannot read {value!r}")
    try:
        return [float(x) for x in text[1:-1].split(',') if x.strip()]
    except ValueError:
        raise NIMSFormatError(f"sample {sample_id}, {column}: cannot read {value!r}")


def family_label(row):
    """Substituent family, e.g. 'Si', 'Si+Co', 'Si+Mn+Ce': the non-zero metal
    elements other than La and Fe, in the column order of the file."""
    subs = [e for e in METAL_ELEMENTS if e not in ('Fe', 'La') and row[e] > 0]
    return '+'.join(subs) if subs else 'none'


def load_nims(path=DEFAULT_PATH):
    """Read and validate the file. Returns one row per NIMS sample (index =
    NIMS ID) with short column names, filled-down article/DOI, metal and
    interstitial composition columns, list columns parsed into Python lists,
    and derived 'family', 'has_interstitial' columns."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download 1-13_dataset.xlsx from "
            f"https://doi.org/{DATASET_DOI} and put it in {DEFAULT_PATH.parent}/")
    raw = pd.read_excel(path, index_col=0)
    if raw.index.name != 'ID':
        raise NIMSFormatError(f"first column should be 'ID', found {raw.index.name!r}")
    if not raw.index.is_unique:
        raise NIMSFormatError("NIMS IDs are not unique")

    needed = list(EXPECTED_COLUMNS) + METAL_ELEMENTS + list(INTERSTITIALS)
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise NIMSFormatError(f"columns missing or renamed in {path.name}: {missing}")

    df = raw[list(EXPECTED_COLUMNS)].rename(columns=EXPECTED_COLUMNS)
    for el in METAL_ELEMENTS:
        df[el] = raw[el].astype(float)
    for header, short in INTERSTITIALS.items():
        df[short] = raw[header].astype(float)

    metal_sum = df[METAL_ELEMENTS].sum(axis=1)
    bad = metal_sum[(metal_sum - 100).abs() > 0.05]
    if len(bad):
        raise NIMSFormatError(f"metal at.% does not sum to 100 for IDs {list(bad.index[:10])}")

    # Article ID / DOI only on the first row of each paper's block.
    df['article_id'] = df['article_id'].ffill()
    df['doi'] = df['doi'].ffill().astype(str).str.strip()
    df['doi_list'] = df['doi'].map(lambda s: [d.strip().lower() for d in re.split(r'[\n;]', s) if d.strip()])

    for col in FIELD_LIST_COLUMNS:
        df[col] = [_parse_list(v, col, i) for i, v in zip(df.index, df[col])]

    df['family'] = df.apply(family_label, axis=1)
    df['has_interstitial'] = (df[list(INTERSTITIALS.values())] > 0).any(axis=1)
    return df


def restore_T_tr(df, max_field_T=2.0):
    """Adds 'T_tr_restored_K' and 'T_tr_source'. Where the paper reports no
    transition temperature, take the peak temperature of the lowest-field
    ΔS (or ΔTad) curve, if that field is <= max_field_T -- the same idea as
    the NIMS scripts' restore_T_tr, done per row. If both peaks exist at the
    same lowest field, their mean is used.
    T_tr_source: 'reported' | 'dS_peak' | 'dTad_peak' | 'dS_dTad_mean' | None."""
    values, sources = [], []
    for _, r in df.iterrows():
        if pd.notna(r['T_tr_K']):
            values.append(r['T_tr_K']); sources.append('reported'); continue
        cands = []
        for field_col, t_col, name in (('H_S_T', 'T_at_dS_max_K', 'dS_peak'),
                                       ('H_ad_T', 'T_at_dT_ad_max_K', 'dTad_peak')):
            H, T = r[field_col], r[t_col]
            if H and T and len(H) == len(T) and min(H) <= max_field_T:
                k = int(np.argmin(H))
                cands.append((H[k], T[k], name))
        if not cands:
            values.append(np.nan); sources.append(None); continue
        h_min = min(c[0] for c in cands)
        at_min = [c for c in cands if c[0] == h_min]
        if len(at_min) == 2:
            values.append(round((at_min[0][1] + at_min[1][1]) / 2, 1)); sources.append('dS_dTad_mean')
        else:
            values.append(at_min[0][1]); sources.append(at_min[0][2])
    out = df.copy()
    out['T_tr_restored_K'] = values
    out['T_tr_source'] = sources
    return out


def expand_points(df, kind='dS'):
    """One row per (NIMS ID, field). kind='dS' uses H_S_T with dS_max,
    T_at_dS_max_K, dS_fwhm_K; kind='dTad' uses H_ad_T with dT_ad_max_K,
    T_at_dT_ad_max_K. List entries whose length does not match the field
    list are left empty (NaN) for that row and counted in the returned
    'length_mismatch' attribute, never silently re-paired."""
    if kind == 'dS':
        field, values = 'H_S_T', {'dS_max': 'dS_max', 'T_at_dS_max_K': 'T_peak_K', 'dS_fwhm_K': 'dS_fwhm_K'}
    elif kind == 'dTad':
        field, values = 'H_ad_T', {'dT_ad_max_K': 'dT_ad_max_K', 'T_at_dT_ad_max_K': 'T_peak_K'}
    else:
        raise ValueError("kind must be 'dS' or 'dTad'")

    rows, mismatched = [], []
    for nims_id, r in df.iterrows():
        H = r[field]
        for k, h in enumerate(H):
            point = {'nims_id': nims_id, 'field_T': h}
            for src, dst in values.items():
                lst = r[src]
                if len(lst) == len(H):
                    point[dst] = lst[k]
                else:
                    point[dst] = np.nan
                    if lst:
                        mismatched.append((nims_id, src))
            rows.append(point)
    points = pd.DataFrame(rows)
    points.attrs['length_mismatch'] = sorted(set(mismatched))
    return points


def apply_composition_overrides(df, path):
    """Replace the metal composition of selected samples with measured
    values, e.g. EDX of the 1:13 phase instead of the nominal composition.
    path: CSV with columns nims_id and edx_formula (published-formula
    notation, read by mcedb_dataset.parse_formula). The metal at.% are
    renormalised to 100; interstitial columns are left as they are.
    Returns a copy; raises on an unknown NIMS ID or element."""
    from mcedb_dataset import parse_formula
    overrides = pd.read_csv(path)
    out = df.copy()
    for _, o in overrides.iterrows():
        nid = int(o['nims_id'])
        if nid not in out.index:
            raise NIMSFormatError(f"override for unknown NIMS ID {nid}")
        comp = parse_formula(o['edx_formula'])
        unknown = [e for e in comp if e not in METAL_ELEMENTS]
        if unknown:
            raise NIMSFormatError(f"NIMS ID {nid}: elements {unknown} are not NIMS metal columns")
        total = sum(comp.values())
        for e in METAL_ELEMENTS:
            out.at[nid, e] = 100.0 * comp.get(e, 0.0) / total
    return out

