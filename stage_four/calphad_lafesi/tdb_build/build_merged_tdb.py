"""
build_merged_tdb.py — FULL MERGED build: real binary TDBs + Feng ternary.

Merges three binary TDB files (Fe-La, La-Si, Fe-Si) from the Track A SGTE
collection into one La-Fe-Si database, then injects Feng et al. (2023)
Table 5 ternary parameters (tau1/tau2 = La(Fe,Si)13 and the ternary liquid
interaction). The binary backbone is the real research files, not Feng's
Table-5 restatement — so this is the reconstruction on actual binaries, and
swapping the inputs gives the WP4 uncertainty band.

Faithful combo = Feng's cited binaries: FeLa-23Su (Su), LaSi-10Zho (Zhou),
FeSi-17Cui (Cui). Fe-Si is merged DISORDERED (BCC_A2 + line compounds):
Feng themselves treated Fe-Si as A2 for the ternary and added B2/D03
separately (paper p.9), so Cui's 4SL ordering phases are left out of the
ternary merge.

  python build_merged_tdb.py FeLa-23Su LaSi-10Zho FeSi-17Cui [out.tdb]
"""
raise SystemExit(
    "DEPRECATED (21 Nov 2026): this builder drops the pure-element end-member terms of the solution phases and gives wrong "
    "driving forces (+84.7 kJ/mol-atom instead of 1.76-5.56). Use ../build_merged_tdb_fixed.py (needs SGTE_BINARY_DIR). "
    "See tdb_build/RESULTS_MERGED.md.")

import os
import sys
import copy

from pycalphad import Database

COLL = '/home/user/projects_documentation/AlloyDB/Data/tdb/sgte_binary'
HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_PHASES = {'A2_BCC', 'B2_BCC', 'BCC_4SL'}      # Cui ordering: added separately, as Feng did

# Feng Table 5 ternary additions (tau1/tau2 model (La)0.071428(Fe,Si)0.928572)
FENG_TERNARY = """
$ ===== Feng et al. (2023) Table 5 -- ternary additions on the merged binaries =====
 PARAMETER G(LIQUID,LA,FE,SI;0) 298.15 +200000; 6000 N ! $ Feng T5 THIS WORK

PHASE TAU1 % 2 0.071428 0.928572 !
CONSTITUENT TAU1 : LA : FE,SI : !
 PARAMETER G(TAU1,LA:FE;0) 298.15 +2300-0.95*T+0.071428*GHSERLA#+0.928572*GHSERFE#; 6000 N ! $ Feng T5
 PARAMETER G(TAU1,LA:SI;0) 298.15 +37000+6.5*T+0.071428*GHSERLA#+0.928572*GHSERSI#; 6000 N ! $ Feng T5
 PARAMETER G(TAU1,LA:FE,SI;0) 298.15 -242114+9.5*T; 6000 N ! $ Feng T5

PHASE TAU2 % 2 0.071428 0.928572 !
CONSTITUENT TAU2 : LA : FE,SI : !
 PARAMETER G(TAU2,LA:FE;0) 298.15 +6500-0.9*T+0.071428*GHSERLA#+0.928572*GHSERFE#; 6000 N ! $ Feng T5
 PARAMETER G(TAU2,LA:SI;0) 298.15 +22500+8.5*T+0.071428*GHSERLA#+0.928572*GHSERSI#; 6000 N ! $ Feng T5
 PARAMETER G(TAU2,LA:FE,SI;0) 298.15 -241114+8*T; 6000 N ! $ Feng T5
"""


def merge_binaries(paths):
    """Object-level merge: union elements/symbols/phases/parameters.
    Shared solution phases get their constituent sets unioned per sublattice."""
    merged = Database()
    merged.elements = set()
    for path in paths:
        db = Database(path)
        merged.elements |= set(db.elements)
        # symbols (unary functions): dedup by name; verified consistent upstream
        for name, expr in db.symbols.items():
            merged.symbols.setdefault(name, expr)
        # phases
        for pname, phase in db.phases.items():
            if pname in SKIP_PHASES:
                continue
            if pname not in merged.phases:
                merged.phases[pname] = copy.deepcopy(phase)
            else:
                # union constituents per sublattice
                old = merged.phases[pname]
                if len(old.constituents) == len(phase.constituents):
                    old.constituents = tuple(
                        frozenset(a | b) for a, b in zip(old.constituents, phase.constituents))
        # parameters: union (skip ones for skipped phases)
        for p in db._parameters.all():
            if p['phase_name'] in SKIP_PHASES:
                continue
            merged._parameters.insert(dict(p))
    return merged


def build(fela, lasi, fesi, out=None):
    paths = [os.path.join(COLL, f + '.tdb') for f in (fela, lasi, fesi)]
    merged = merge_binaries(paths)
    backbone = merged.to_string(fmt='tdb')
    tdb_text = backbone + '\n' + FENG_TERNARY + '\n'
    out = out or os.path.join(HERE, f'merged_{fela}_{lasi}_{fesi}.tdb')
    open(out, 'w').write(tdb_text)
    # reload to confirm it parses with the ternary
    db = Database(out)
    return out, db


if __name__ == '__main__':
    args = sys.argv[1:]
    fela, lasi, fesi = (args + ['FeLa-23Su', 'LaSi-10Zho', 'FeSi-17Cui'])[:3]
    out = args[3] if len(args) > 3 else None
    path, db = build(fela, lasi, fesi, out)
    print(f'wrote {path}')
    print(f'elements: {sorted(e for e in db.elements if e not in ("VA", "/-"))}')
    print(f'{len(db.phases)} phases: {sorted(db.phases)}')
