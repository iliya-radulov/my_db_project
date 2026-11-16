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
import os
import sys
import copy

from pycalphad import Database

COLL = os.environ.get('SGTE_BINARY_DIR', '/home/user/projects_documentation/AlloyDB/Data/tdb/sgte_binary')
HERE = os.path.dirname(os.path.abspath(__file__))
CONFLICTS = []          # filled by merge_binaries: duplicates whose expressions differ (first kept)
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


# ---- Feng Table 5: La-Si compounds with Fe solubility (THIS WORK parameters) --------------------
# Zhou 2010 compounds are defined per FORMULA UNIT (e.g. LA5SI3_D8L = La5Si3, G = 5*GHSERLA+3*GHSERSI),
# Table 5 gives energies per MOLE OF ATOMS. Each Table-5 value is therefore multiplied by the number
# of atoms per formula unit (n). Mapping: (phase in the Zhou binary) -> (Feng compound, n, La frac, Fe-ref, G(La:Fe) const+T, L const+T)
FE_SUBST = {
 'LA5SI3_D8L': ('La5(Si,Fe)3',        8, 0.625,  ( 8001.1109,   8.001),  (-25999.4388, 4.9996)),
 'LA3SI2_D5A': ('La3(Si,Fe)2',        5, 0.6,    (10000.0,     11.0),    (-26500.0,     5.0)),
 'LA5SI4':     ('La5(Si,Fe)4',        9, 0.5556, ( 5000.0,      9.0),    ( 36500.0,     7.5)),
 'LASI_B27':   ('La(Si,Fe)',          2, 0.5,    ( 8000.0,     10.0),    (-43500.0,     6.5)),
 'LASI2_X':    ('alpha-La(Si,Fe)2',   1, 0.36,   ( 8900.0,      8.0),    (-115863.005,  9.0)),
 'LASI2_CC':   ('beta-La(Si,Fe)2',    3, 0.3333, ( 9504.75086, 10.0),    (-1.294,       7.0)),
}

def fe_substitution_text(merged_phases):
    """Parameter lines for the Fe-substituted La-Si compounds actually present in the merge."""
    out = ["$ ===== Feng et al. (2023) Table 5 -- Fe solubility of the La-Si compounds (per formula unit = n x per-atom value) ====="]
    for ph, (name, n, xla, (g0, g1), (l0, l1)) in FE_SUBST.items():
        if ph not in merged_phases:
            continue
        nla, nfe = n * xla, n * (1 - xla)     # La and Fe(Si) atoms per formula unit
        out.append(f" PARAMETER G({ph},LA:FE;0) 298.15 {n*g0:+.6f}{n*g1:+.6f}*T+{nla:.6f}*GHSERLA#+{nfe:.6f}*GHSERFE#; 6000 N ! $ Feng T5 THIS WORK ({name})")
        out.append(f" PARAMETER L({ph},LA:SI,FE;0) 298.15 {n*l0:+.6f}{n*l1:+.6f}*T; 6000 N ! $ Feng T5 THIS WORK ({name})")
    return "\n".join(out) + "\n"

def add_fe_to_constituents(merged):
    from pycalphad import variables as _v
    fe = _v.Species('FE')
    for ph in FE_SUBST:
        if ph in merged.phases:
            c = merged.phases[ph].constituents
            merged.phases[ph].constituents = (c[0], frozenset(set(c[1]) | {fe}))


def merge_binaries(paths):
    """Object-level merge: union elements/symbols/phases/parameters.
    Shared solution phases get their constituent sets unioned per sublattice."""
    merged = Database()
    merged.elements = set()
    seen = {}
    CONFLICTS.clear()
    for path in paths:
        db = Database(path)
        merged.elements |= set(db.elements)
        merged.species |= set(db.species)      # FIX: the writer groups parameters by species; an empty set writes none
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
            # FIX 2: the same parameter (typically a pure-element endmember such as G(BCC_A2,FE:VA))
            # appears in several binaries; pycalphad SUMS duplicates, which doubled the unary energies.
            # Keep the first occurrence; record whether the duplicate differs numerically (conflict).
            key = (p['phase_name'], p['parameter_type'], str(p['constituent_array']),
                   p['parameter_order'], str(p.get('diffusing_species')))
            if key in seen:
                if str(seen[key]['parameter']) != str(p['parameter']):
                    CONFLICTS.append((os.path.basename(path), key[:4], str(p['parameter'])[:60]))
                continue
            seen[key] = p
            merged._parameters.insert(dict(p))
    return merged


def build(fela, lasi, fesi, out=None, fe_subst=True):
    paths = [os.path.join(COLL, f + '.tdb') for f in (fela, lasi, fesi)]
    merged = merge_binaries(paths)
    if fe_subst:
        add_fe_to_constituents(merged)
    backbone = merged.to_string(fmt='tdb')
    tdb_text = backbone + '\n' + FENG_TERNARY + '\n' + (fe_substitution_text(merged.phases) if fe_subst else '')
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
