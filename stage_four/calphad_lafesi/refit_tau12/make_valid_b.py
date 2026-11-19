#!/usr/bin/env python3
"""(Added after the freeze; script helper, no rule change.) Make a fixed-parameter TDB for held-out
evaluation from a numeric TDB: adds one dummy trainable symbol zz (coefficient 0) because eqopt needs >= 1 symbol.
Usage: python make_valid_b.py IN.tdb OUT.tdb"""
import sys, re
t = open(sys.argv[1]).read(); done = False; out = []
for ln in t.splitlines():
    if not done and ln.lstrip().startswith('PARAMETER G(TAU1,LA:FE;0)'):
        ln = ln.replace('; 6000', ' + 0*zz; 6000', 1); done = True
    out.append(ln)
assert done; open(sys.argv[2], 'w').write('\n'.join(out) + '\n')
