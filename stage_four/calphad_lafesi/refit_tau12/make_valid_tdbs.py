#!/usr/bin/env python3
"""Make fixed-parameter TDBs for held-out evaluation. Reads param.tdb (symbols),
baseline_eq.tdb and the fitted optimized.tdb; writes valid_base.tdb and
valid_fit.tdb in which the 12 corrections are numeric constants plus ONE
dummy trainable symbol (zz, coefficient 0) because eqopt requires >=1 symbol.
Usage: python make_valid_tdbs.py DIR"""
import re, sys
from pathlib import Path
d = Path(sys.argv[1])
def terms(expr):
    """-> (constant, T coefficient) of the non-GHSER terms"""
    import sympy
    expr = re.sub(r'[+-]?\s*[\d.]+\s*\*\s*GHSER\w+#?', '', expr)
    e = sympy.expand(sympy.sympify(expr.replace(' ', '')))
    T = sympy.Symbol('T')
    return float(e.coeff(T, 0)), float(e.coeff(T, 1))
def tauparams(path):
    out = {}
    for ln in Path(path).read_text().splitlines():
        m = re.match(r'\s*PARAMETER G\((TAU[12]),(LA:[A-Z,]+;0)\)\s+298\.15\s+([^;]*);', ln)
        if m: out[(m.group(1), m.group(2))] = m.group(3)
    return out
base = tauparams(d / 'baseline_eq.tdb'); fit = tauparams(d / 'out_train/optimized.tdb')
assert len(base) == len(fit) == 6
delta = {}
for k in base:
    (cb, tb), (cf, tf) = terms(base[k]), terms(fit[k])
    delta[k] = (cf - cb, tf - tb)
    print(k, 'dconst %.1f J/mol  dT %.4f J/mol/K' % delta[k])
def build(corr):
    txt = (d / 'param.tdb').read_text()
    for (ph, cons), (w, v) in corr.items():
        tag = cons.replace(':', '').replace(',', '').replace(';0', '')
        n = f'{ph[-1]}{tag}'
        txt = txt.replace(f'+1000*w{n}+10*v{n}*T', f'+({w:.6f})+({v:.8f})*T')
    # dummy symbol on the first TAU1 parameter
    txt = txt.replace('+(', '+0*zz+(', 1)
    assert 'w1LAFE' not in txt
    return txt
(d / 'valid_base.tdb').write_text(build({k: (0.0, 0.0) for k in base}))
(d / 'valid_fit.tdb').write_text(build(delta))
