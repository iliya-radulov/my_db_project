"""check_binaries.py — standalone-compute, 3rd-gen screen, and numeric unary
consistency for the La-Fe-Si binary collection (Track A lessons 1 & 2)."""
import sys, os, re, glob, warnings
warnings.filterwarnings('ignore')
import sympy
from pycalphad import Database, calculate
T = sympy.Symbol('T')
BINDIR = sys.argv[1]
files = sorted(glob.glob(os.path.join(BINDIR, 'FeLa-*.tdb')) +
               glob.glob(os.path.join(BINDIR, 'LaSi-*.tdb')) +
               glob.glob(os.path.join(BINDIR, 'FeSi-*.tdb')))
unary = {}
print(f"{'file':20s} {'elems':12s} {'phases':3s} compute 3rdgen  GHSERLA/FE/SI(1500K)")
for f in files:
    name = os.path.basename(f)
    txt = open(f, encoding='utf-8', errors='replace').read()
    gen3 = 'yes' if re.search(r'EINSTEIN|GEIN', txt, re.I) else 'no'
    try:
        db = Database(f)
        els = sorted(e for e in db.elements if e not in ('/-', 'VA'))
        # standalone compute: GM of first non-trivial phase
        ok = 'ok'
        try:
            ph = [p for p in db.phases if 'LIQ' in p.upper()] or list(db.phases)[:1]
            calculate(db, els + ['VA'], ph[0], T=1500, P=101325, output='GM')
        except Exception as e:
            ok = 'FAIL'
        vals = {}
        for u in ('GHSERLA', 'GHSERFE', 'GHSERSI'):
            s = db.symbols.get(u)
            if s is not None:
                vals[u] = round(float(sympy.sympify(s).xreplace({T: 1500})), 1)
                unary.setdefault(u, {})[name] = vals[u]
        vstr = ' '.join(f"{u[-2:]}:{vals.get(u,'--')}" for u in ('GHSERLA','GHSERFE','GHSERSI'))
        print(f"{name:20s} {','.join(els):12s} {len(db.phases):3d} {ok:7s} {gen3:6s}  {vstr}")
    except Exception as e:
        print(f"{name:20s} PARSE FAIL: {str(e)[:40]}")
print("\nUnary consistency across files (distinct values per function at 1500K):")
for u, d in unary.items():
    vals = sorted(set(d.values()))
    print(f"  {u}: {len(vals)} distinct value(s) -> {vals}")
    if len(vals) > 1:
        for v in vals:
            print(f"     {v}: {[n for n,x in d.items() if x==v]}")
