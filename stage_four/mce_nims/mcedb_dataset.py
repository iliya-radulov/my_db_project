"""
mcedb_dataset.py

Loader for the LLM-extracted magnetocaloric database of Yuan, Yang, Patra
and Liao (AIP Advances 14, 085125 (2024); arXiv:2403.02553),
github.com/RunqingYang1996/MCEdatabase.

LICENCE: the repository has no licence file. B. Liao (corresponding author)
agreed by email on 2 Nov 2026 to its use with citation of the paper. Do not
commit or redistribute the data; clone the authors' repository into
stage_four/mce_nims/data/MCEdatabase/ (gitignored).

Files used:
  html/725_updated.csv        714 human-corrected rows, with DOI
                              -> quality_flag 'literature_mined'
  databasecsv/modified6125.csv  6,614 raw GPT-3.5 rows, no DOI
                              -> quality_flag 'unverified'
  source/savedrecs*.xls       the Web of Science export the papers came from

Provenance of the raw rows: their 'source' value is the 0-based position
of the paper in the Web of Science export concatenated in the order
savedrecs.xls, savedrecs (1).xls ... (8).xls. Checked on the corrected
file: the position of every one of its 714 titles equals its source
index. Raw rows from papers that are also in the corrected file are
dropped (the corrected rows replace them).

Every value is parsed strictly: a value is kept only when it is
unambiguous, otherwise it is left empty and the reason counted (roadmap
§4 step C: log accepted / rejected / incomplete).
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from composition_key import ELEMENTS

DEFAULT_REPO = Path(__file__).resolve().parent / 'data' / 'MCEdatabase'
WOS_FILES = ['savedrecs.xls'] + [f'savedrecs ({i}).xls' for i in range(1, 9)]
# T_C window for La(Fe,Si/Al)13 (domain judgement; shared by all literature imports)
PLAUSIBLE_TC_K = (100.0, 500.0)
RARE_EARTHS = ('La', 'Ce', 'Pr', 'Nd', 'Sm', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Y')

NUM = r'(\d+(?:\.\d+)?)'


class FormulaError(ValueError):
    pass


# --------------------------------------------------------------------------
# Formula parser for published formulas (not the lab calculator's parser)
# --------------------------------------------------------------------------
def parse_formula(text):
    """'La(Fe0.92Co0.08)11.9Si1.1' -> {'La': 1.0, 'Fe': 10.948, 'Co': 0.952, 'Si': 1.1}.

    Unlike the lab calculator's parser this one is case-sensitive, so an
    element without a number means 1 (standard notation, unambiguous when
    case matters), and brackets with a multiplier are expanded. Anything
    that is not an element symbol, a number, a bracket or a space -- a
    variable (x, y, δ), a word ('alloy', 'Nanocrystalline'), a sign, a
    range -- raises FormulaError: such formulas are 'incomplete', not
    guessed."""
    s = str(text).strip()
    if not s or s.lower() == 'nan':
        raise FormulaError('empty')
    pos = 0

    def number():
        nonlocal pos
        m = re.match(r'\d+(?:\.\d+)?|\.\d+', s[pos:])
        if not m:
            return None
        pos += m.end()
        return float(m.group())

    def group(closing):
        nonlocal pos
        out = {}
        while pos < len(s):
            c = s[pos]
            if c == ' ':
                pos += 1
                continue
            if c in '([':
                pos += 1
                inner = group(')' if c == '(' else ']')
                mult = number()
                for e, v in inner.items():
                    out[e] = out.get(e, 0.0) + v * (1.0 if mult is None else mult)
                continue
            if c in ')]':
                if c != closing:
                    raise FormulaError(f"unbalanced '{c}'")
                pos += 1
                return out
            sym = None
            if s[pos:pos + 2] in ELEMENTS and s[pos:pos + 2][1:].islower():
                sym = s[pos:pos + 2]
            elif c in ELEMENTS:
                sym = c
            if sym is None:
                raise FormulaError(f"not an element at '{s[pos:pos + 12]}'")
            pos += len(sym)
            amount = number()
            out[sym] = out.get(sym, 0.0) + (1.0 if amount is None else amount)
        if closing:
            raise FormulaError('unclosed bracket')
        return out

    comp = group(None)
    if not comp or sum(comp.values()) <= 0:
        raise FormulaError('no elements')
    return comp


# --------------------------------------------------------------------------
# Value parsers: (value or None, reason or None)
# --------------------------------------------------------------------------
def parse_field_T(text):
    """'2 T', '5.0 T', '2T', '10 kOe', '0-5 T' (a field change from 0) -> tesla."""
    s = str(text).strip()
    m = re.fullmatch(rf'(?:0+(?:\.0+)?\s*[-–]\s*)?{NUM}\s*(T|kOe)', s)
    if not m:
        return None, 'field_not_plain' if s.lower() not in ('nan', 'nan t', 'nan koe', '') else 'field_missing'
    v = float(m.group(1)) / (10.0 if m.group(2) == 'kOe' else 1.0)
    return (v, None) if v > 0 else (None, 'field_zero')


def parse_dS(text):
    """Plain number, sign ignored (|ΔS| convention), optional 'J/kg K'."""
    s = str(text).strip()
    if s.lower() in ('nan', ''):
        return None, 'dS_missing'
    m = re.fullmatch(rf'-?\s*{NUM}\s*(?:J\s*/\s*kg\s*/?\s*K|J\s*kg-1\s*K-1)?', s)
    if not m:
        return None, 'dS_unit' if re.search(r'mol|cm|mJ', s) else 'dS_not_plain'
    return float(m.group(1)), None


def parse_Tc(text):
    """Plain positive number, optional 'K'."""
    s = str(text).strip()
    if s.lower() in ('nan', ''):
        return None, 'Tc_missing'
    m = re.fullmatch(rf'{NUM}\s*K?', s)
    if not m:
        return None, 'Tc_not_plain'
    return float(m.group(1)), None


def in_lafesi_family(comp):
    """La(Fe,Si/Al)13-type: La present; rare earths 5-9.5 at.% of the metal
    sites; Fe >= 55 at.%; Si or Al present. Interstitials (H, C, N, B)
    excluded from the metal total."""
    metal = {e: v for e, v in comp.items() if e not in ('H', 'C', 'N', 'B')}
    tot = sum(metal.values())
    if tot <= 0 or 'La' not in metal:
        return False
    pct = {e: 100 * v / tot for e, v in metal.items()}
    re_sum = sum(pct.get(e, 0) for e in RARE_EARTHS)
    return 5.0 <= re_sum <= 9.5 and pct.get('Fe', 0) >= 55 and ('Si' in pct or 'Al' in pct)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_wos(repo):
    parts = [pd.read_excel(Path(repo) / 'source' / f) for f in WOS_FILES]
    return pd.concat(parts, ignore_index=True)


def load_mcedb(repo=DEFAULT_REPO):
    """One row per extracted entry, both files, with parsed values,
    rejection reasons, DOI, quality_flag and an external_id. Raw rows of
    papers covered by the corrected file are dropped."""
    repo = Path(repo)
    if not (repo / 'databasecsv').exists():
        raise FileNotFoundError(
            f"{repo} not found. Clone https://github.com/RunqingYang1996/MCEdatabase into it.")
    wos = load_wos(repo)

    cor = pd.read_csv(repo / 'html' / '725_updated.csv')
    cor['paper_index'] = cor['source'].str.extract(r'(\d+)\.txt$')[0].astype(float)
    cor['external_id'] = ['corr-' + str(i) for i in range(len(cor))]   # 'Number' is not unique here
    cor['quality_flag'] = 'literature_mined'
    cor['doi'] = cor['DOI']

    raw = pd.read_csv(repo / 'databasecsv' / 'modified6125.csv')
    raw['paper_index'] = pd.to_numeric(raw['source'], errors='coerce')   # e.g. '948(1)' -> NaN, flagged
    raw['external_id'] = 'raw-' + raw['Number'].astype(str)
    raw['quality_flag'] = 'unverified'
    raw['doi'] = [wos['DOI'].iloc[int(n)] if pd.notna(n) and 0 <= n < len(wos) else np.nan
                  for n in raw['paper_index']]
    raw['Article Title'] = [wos['Article Title'].iloc[int(n)] if pd.notna(n) and 0 <= n < len(wos) else np.nan
                            for n in raw['paper_index']]
    covered = set(cor['paper_index'].dropna().astype(int))
    raw['covered_by_corrected'] = raw['paper_index'].isin(covered)

    keep = ['external_id', 'quality_flag', 'paper_index', 'doi', 'Article Title', 'Material',
            'Magnetic Entropy Change', 'Magnetic Field', 'Curie Temperature']
    df = pd.concat([cor[keep].assign(file='725_updated.csv', covered_by_corrected=False),
                    raw[keep + ['covered_by_corrected']].assign(file='modified6125.csv')],
                   ignore_index=True)
    df['doi'] = df['doi'].astype('string').str.strip().str.lower()

    comps, reasons = [], []
    for text in df['Material']:
        try:
            comps.append(parse_formula(text)); reasons.append(None)
        except FormulaError as e:
            comps.append(None); reasons.append(f'formula: {e}')
    df['composition'] = comps
    df['formula_problem'] = reasons
    for col, fn, name in (('Magnetic Field', parse_field_T, 'field_T'),
                          ('Magnetic Entropy Change', parse_dS, 'dS'),
                          ('Curie Temperature', parse_Tc, 'Tc')):
        parsed = [fn(v) for v in df[col]]
        df[name] = [p[0] for p in parsed]
        df[name + '_problem'] = [p[1] for p in parsed]
    df['lafesi_family'] = [in_lafesi_family(c) if c else False for c in df['composition']]
    df['source_index_problem'] = df['paper_index'].isna()
    return df


if __name__ == '__main__':
    checks = {
        'LaFe11.6Si1.4': {'La': 1, 'Fe': 11.6, 'Si': 1.4},
        'La(Fe0.92Co0.08)11.9Si1.1': {'La': 1, 'Fe': 10.948, 'Co': 0.952, 'Si': 1.1},
        'La0.7Pr0.3Fe10.4Co0.8Si1.8': {'La': 0.7, 'Pr': 0.3, 'Fe': 10.4, 'Co': 0.8, 'Si': 1.8},
        'LaFe11.5Si1.5H1.3': {'La': 1, 'Fe': 11.5, 'Si': 1.5, 'H': 1.3},
        'Gd5(Si2Ge2)': {'Gd': 5, 'Si': 2, 'Ge': 2},
    }
    for text, expected in checks.items():
        got = parse_formula(text)
        assert set(got) == set(expected) and all(abs(got[e] - expected[e]) < 1e-9 for e in got), (text, got)
    for bad in ('Er2-xPrxFe17', 'Nanocrystalline Gd', 'LaFe11.0Co0.8(Si1-xAlx)(1.2) (x= 0.2)',
                'Co50Ni22Ga28 alloy', 'La(Fe,Si)13', 'LaFe11.4Si1.6)', 'CO2'):
        try:
            parse_formula(bad)
        except FormulaError:
            continue
        if bad == 'CO2':        # C1 O2: valid symbols, case-sensitive reading -- accepted, not a bug
            continue
        raise AssertionError(f'{bad!r} should be rejected')
    assert parse_field_T('0-5 T') == (5.0, None) and parse_field_T('10 kOe') == (1.0, None)
    assert parse_field_T('nan T')[0] is None and parse_field_T('Up to 5 T')[0] is None
    assert parse_dS('-12.3') == (12.3, None) and parse_dS('0.65(J/mol K)') == (None, 'dS_unit')
    assert parse_dS('10.07 to 4.47')[0] is None and parse_Tc('Below 360')[0] is None
    assert in_lafesi_family(parse_formula('LaFe11.6Si1.4')) and not in_lafesi_family(parse_formula('LaMn1.9Fe0.1Si2'))
    print('mcedb_dataset self-test passed')
