#!/usr/bin/env python3
"""Build eqopt inputs for the tau1/tau2 refit (see FROZEN_SPEC.md).
Usage: python make_inputs.py BASELINE.tdb TIELINES.csv OUTDIR
BASELINE.tdb = pycalphad-written merged TDB. Writes OUTDIR/{param.tdb,
baseline_eq.tdb, train.csv, valid.csv, report.txt}."""
import re, sys, csv
from pathlib import Path

MAP = {'tau1': 'TAU1', 'tau2': 'TAU2', 'alphaFe': 'BCC_A2', 'gammaFe': 'FCC_A1',
       'epsilon': 'MSI_B20', 'eta': 'M5SI3_D88', 'beta': 'FE2SI',
       'zeta_alpha': 'FESI2_H', 'zeta_beta': 'FESI2_L', 'La5Si3': 'LA5SI3_D8L',
       'La5Si4': 'LA5SI4', 'La3Si2': 'LA3SI2_D5A', 'LaSi': 'LASI_B27',
       'Si': 'DIAMOND_A4', 'Liq': 'LIQUID'}
WITH_COMP = {'BCC_A2', 'FCC_A1', 'LIQUID', 'TAU1', 'TAU2'}
DROP = ('DHCP', 'HCP_A3')
# Addendum B: stoichiometric ternary compounds added to the TDB. name -> (La, Fe, Si) site counts
TERNARY = {'LAFE2SI2': (1, 2, 2), 'LAFESI': (1, 1, 1), 'LAFESI2': (1, 1, 2)}
TER_MAP = {'LaFe2Si2': 'LAFE2SI2', 'LaFeSi': 'LAFESI', 'LaFeSi2': 'LAFESI2'}
PRIOR_KJ_PER_ATOM = -30.0   # prior formation energy, frozen in Addendum B
TARGETS = [('TAU1', 'LA:FE;0'), ('TAU1', 'LA:SI;0'), ('TAU1', 'LA:FE,SI;0'),
           ('TAU2', 'LA:FE;0'), ('TAU2', 'LA:SI;0'), ('TAU2', 'LA:FE,SI;0')]

def normalise(text):
    text = re.sub(r';\s*,\s*N\s*!', '; 6000.0 N !', text)
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(r'(PHASE|CONSTITUENT)\s+(%s)\b' % '|'.join(DROP), s): continue
        if re.match(r'PARAMETER\s+\w+\((%s)[,)]' % '|'.join(DROP), s): continue
        out.append(ln)
    return '\n'.join(out) + '\n'

def parameterise(text, constants_only=False):
    """Add 1000*w + 10*v*T (w in kJ/mol, v in 10 J/mol/K) to the six TAU1/TAU2
    parameters. Plain symbols = trainable in eqopt (zero-initialised)."""
    names = []
    for ph, cons in TARGETS:
        tag = cons.replace(':', '').replace(',', '').replace(';0', '')
        wn, vn = f'w{ph[-1]}{tag}', f'v{ph[-1]}{tag}'
        pat = re.compile(r'(PARAMETER G\(%s,%s\)\s+298\.15\s+)([^;]*?)(\s*;)' % (ph, re.escape(cons)))
        text, c = pat.subn(lambda m: f'{m.group(1)}{m.group(2)}+1000*{wn}{"" if constants_only else f"+10*{vn}*T"}{m.group(3)}', text)
        assert c == 1, (ph, cons, c)
        names += [wn] if constants_only else [wn, vn]
    return text, names

def add_ternary(text):
    """Append three stoichiometric compounds, G = sum(GHSER) + n*(prior + 1000*w + 10*v*T)."""
    names = []
    for ph, (a, b, c) in TERNARY.items():
        n = a + b + c
        text += f'PHASE {ph} % 3 {a} {b} {c} !\nCONSTITUENT {ph} : LA : FE : SI : !\n'
        text += (f'PARAMETER G({ph},LA:FE:SI;0) 298.15 +{a}*GHSERLA#+{b}*GHSERFE#+{c}*GHSERSI#'
                 f'+{n}*({PRIOR_KJ_PER_ATOM*1000:.1f}+1000*w_{ph}+10*v_{ph}*T); 6000 N !\n')
        names += [f'w_{ph}', f'v_{ph}']
    return text, names

def main(tdb, ties, out, constants_only=False, ternary=False):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    base = normalise(Path(tdb).read_text())
    (out / 'baseline_eq.tdb').write_text(base)
    if ternary:
        base, tnames = add_ternary(base); MAP.update(TER_MAP); WITH_NO = True
        (out / 'baseline_eq.tdb').write_text(base)
    ptxt, names = parameterise(base, constants_only)
    if ternary: names += tnames
    (out / 'param.tdb').write_text(ptxt)
    rows = list(csv.DictReader(open(ties, encoding='utf-8')))
    tr, va, skipped = [], [], []
    for i, r in enumerate(rows):
        ph = [(r[f'phase{j}'], r[f'La{j}'], r[f'Si{j}']) for j in (1, 2, 3) if r[f'phase{j}']]
        if any(p not in MAP for p, _, _ in ph):
            skipped.append((i, r['table'], r['T_K'], [p for p, _, _ in ph if p not in MAP])); continue
        (va if r['T_K'] == '1373' else tr).append((i, r['T_K'], ph))
    def dump(lst, name):
        with open(out / name, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['eq_index', 'temperature', 'phase_name', 'x_FE', 'x_LA', 'x_SI'])
            for k, (i, T, ph) in enumerate(lst):
                for p, la, si in ph:
                    n = MAP[p]
                    if n in WITH_COMP:
                        la, si = float(la) / 100, float(si) / 100
                        w.writerow([k, float(T), n, round(1 - la - si, 6), la, si])
                    else: w.writerow([k, float(T), n, '', '', ''])
    dump(tr, 'train.csv'); dump(va, 'valid.csv')
    rep = [f'train equilibria {len(tr)}, validation(1373K) {len(va)}, excluded {len(skipped)}']
    rep += [f'  excluded row {i} table {t} {T}K unmapped {u}' for i, t, T, u in skipped]
    (out / 'report.txt').write_text('\n'.join(rep) + '\n'); print('\n'.join(rep))
    print('parameters:', names)

if __name__ == '__main__': main(*sys.argv[1:4], constants_only='--constants-only' in sys.argv, ternary='--ternary' in sys.argv)
