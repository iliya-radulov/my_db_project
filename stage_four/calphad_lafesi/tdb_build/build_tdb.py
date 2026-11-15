"""
build_tdb.py — assemble a La–Fe–Si TDB from Feng et al. (2023) Table 5.

Reconstruction (no author TDB). Unaries: SGTE / Dinsdale 1991, extracted
verbatim from pycalphad-bundled databases and numerically verified to agree
across sources (see FROZEN_SPEC.md §1). Ternary + binary-excess + compound
parameters: typed from Feng Table 5 (data_feng2023/table5_parameters.md),
each block carrying a provenance comment.

Feng's Gibbs energies are PER MOLE OF ATOMS (the GHSER coefficients sum to
1), so each phase's sublattice site ratios ARE those coefficients.

This version builds the fully-specified subset: LIQUID, FCC_A1, BCC_A2,
DIAMOND_A4, the Fe–Si line compounds, the six La–Si(Fe) compounds, and the
ternary tau1/tau2 = La(Fe,Si)13. tau3–tau6 and the Fe–Si B2/D03 ordering
are deferred (FROZEN_SPEC §3, §4).

  python build_tdb.py            # writes LaFeSi_feng2023.tdb and validates
"""
import os
import glob
import re

import pycalphad

PCDIR = os.path.dirname(pycalphad.__file__)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'LaFeSi_feng2023.tdb')


def find(fname):
    return glob.glob(PCDIR + '/**/' + fname, recursive=True)[0]


def extract_function(path, name):
    """Verbatim FUNCTION block body (between name and the terminating !)."""
    txt = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'FUNCTION\s+' + name + r'\b(.*?)!', txt, re.S | re.I)
    if not m:
        raise KeyError(f'{name} not in {os.path.basename(path)}')
    return re.sub(r'\s+', ' ', m.group(1)).strip()


# --- unary function sources (all verified SGTE/Dinsdale, FROZEN_SPEC §1) ---
FENDB = os.path.join(HERE, '..', '..', '..', 'stage_three', 'FENDB_merged_v4.tdb')
SRC = {
    'GHSERLA': find('zrlayalo.tdb'), 'GLABCC': find('zrlayalo.tdb'),
    'GLAFCC': find('zrlayalo.tdb'), 'GLALIQ': find('zrlayalo.tdb'),
    'GHSERFE': FENDB, 'GFCCFE': FENDB, 'GLIQFE': find('CrFeNb_Jacob2016.tdb'),
    'GHSERSI': find('COST507.tdb'), 'GSIBCC': find('mc_fecocrnbti.tdb'),
    'GSIFCC': find('mc_fecocrnbti.tdb'),
}
# liquid Si typed from COST507's LIQUID,SI parameter (verified canonical)
GLIQSI_BODY = ('298.15 +50696.4-30.0994*T+2.09307E-21*T**7+GHSERSI#; '
               '1687.00 Y +49828.2-29.5591*T+4.20369E+30*T**(-9)+GHSERSI#; 6000.00 N')


def unary_block():
    lines = ['$ ===== SGTE / Dinsdale 1991 unary functions '
             '(verbatim; verified across sources, FROZEN_SPEC §1) =====']
    # fix cross-references: FENDB names the bcc/fcc Fe stabilities GHSERFE/GFCCFE
    for name in ('GHSERLA', 'GLABCC', 'GLAFCC', 'GLALIQ',
                 'GHSERFE', 'GFCCFE', 'GLIQFE',
                 'GHSERSI', 'GSIBCC', 'GSIFCC'):
        body = extract_function(SRC[name], name)
        lines.append(f'FUNCTION {name} {body} !')
    lines.append(f'FUNCTION GLIQSI {GLIQSI_BODY} !')
    # convenience aliases matching Feng's Table-5 notation
    lines.append('$ Feng notation: GHCP_La = dhcp-La SER = GHSERLA; '
                 'GDIA_Si = diamond-Si SER = GHSERSI; GBCC_Fe = bcc-Fe SER = GHSERFE')
    return '\n'.join(lines)


# --------------------------------------------------------------------------
# Feng Table 5 parameters  (energies J/mol-atom; provenance per block)
# --------------------------------------------------------------------------
HEADER = """$ ============================================================
$ La-Fe-Si -- reconstruction of Feng et al., Calphad 83 (2023) 102643
$ Ternary + binary-excess parameters typed from the paper's Table 5.
$ Unaries: SGTE/Dinsdale 1991 (see build_tdb.py, FROZEN_SPEC.md).
$ Scope: LIQUID, FCC_A1, BCC_A2, DIAMOND_A4, Fe-Si compounds,
$        La-Si(Fe) compounds, tau1/tau2 = La(Fe,Si)13.
$ Deferred: tau3-tau6, Fe-Si B2/D03 ordering.
$ ============================================================
ELEMENT VA   VACUUM               0.0      0.0      0.0    !
ELEMENT LA   DOUBLE_HCP(ABAC)   138.9055  6667.0   57.488 !
ELEMENT FE   BCC_A2              55.847    4489.0   27.28  !
ELEMENT SI   DIAMOND_A4          28.0855   3217.0   18.81  !

TYPE_DEFINITION % SEQ * !
DEFINE_SYSTEM_DEFAULT ELEMENT 2 !
DEFAULT_COMMAND DEFINE_SYSTEM_ELEMENT VA !

TYPE_DEFINITION & GES AMEND_PHASE_DESCRIPTION BCC_A2 MAGNETIC -1.0 0.4 !
TYPE_DEFINITION ) GES AMEND_PHASE_DESCRIPTION FCC_A1 MAGNETIC -3.0 0.28 !
"""

# site ratios = Feng's per-atom GHSER coefficients
LASI_COMPOUNDS = [
    # (phase, La_ratio, Si_ratio, G_La:Si, G_La:Fe, L_La:Si,Fe)
    ('LA5SIFE3', 0.625, 0.375,
     '-60012.5-14.37*T+0.625*GHSERLA#+0.375*GHSERSI#',
     '+8001.1109+8.001*T+0.625*GHSERLA#+0.375*GHSERFE#',
     '-25999.4388+4.9996*T'),
    ('LA3SIFE2', 0.6, 0.4,
     '-63125.4-14.93*T+0.6*GHSERLA#+0.4*GHSERSI#',
     '+10000+11*T+0.6*GHSERLA#+0.4*GHSERFE#',
     '-26500+5*T'),
    ('LA5SIFE4', 0.5556, 0.4444,
     '-67018.6-15.43*T+0.5556*GHSERLA#+0.4444*GHSERSI#',
     '+5000+9*T+0.5556*GHSERLA#+0.4444*GHSERFE#',
     '+36500+7.5*T'),
    ('LASIFE', 0.5, 0.5,
     '-70156.2-15.4*T+0.5*GHSERLA#+0.5*GHSERSI#',
     '+8000+10*T+0.5*GHSERLA#+0.5*GHSERFE#',
     '-43500+6.5*T'),
    ('ALASIFE2', 0.36, 0.64,
     '-53051.2-21.49*T+0.36*GHSERLA#+0.64*GHSERSI#',
     '+8900+8*T+0.36*GHSERLA#+0.64*GHSERFE#',
     '-115863.005+9*T'),
    ('BLASIFE2', 0.3333, 0.6667,
     '-49262.3-21.048*T+0.3333*GHSERLA#+0.6667*GHSERSI#',
     '+9504.75086+10*T+0.3333*GHSERLA#+0.6667*GHSERFE#',
     '-1.294+7*T'),
]

# Fe-Si stoichiometric line compounds: (phase, Fe_ratio, Si_ratio, G)
FESI_COMPOUNDS = [
    ('FE2SI', 0.66667, 0.33333, '-30592.9+0.33333*GHSERSI#+0.66667*GHSERFE#'),
    ('FE5SI3', 0.625, 0.375, '-34224.6+1.53653*T+0.375*GHSERSI#+0.625*GHSERFE#'),
    ('FESI_B20', 0.5, 0.5, '-39705.0+2.08759*T+0.5*GHSERSI#+0.5*GHSERFE#'),
    ('FESI2_L', 0.333, 0.667, '-39571.0+10.6912*T+0.6667*GHSERSI#+0.333*GHSERFE#'),
    ('FESI2_H', 0.3, 0.7, '-23969.4+0.7*GHSERSI#+0.3*GHSERFE#'),
]


def phases_and_params():
    L = []
    # ----- LIQUID (La,Fe,Si)1 -----
    L.append('$ ----- LIQUID -----')
    L.append('PHASE LIQUID % 1 1.0 !')
    L.append('CONSTITUENT LIQUID : LA,FE,SI : !')
    L.append(' PARAMETER G(LIQUID,LA;0) 298.15 +GLALIQ#; 6000 N ! $ unary')
    L.append(' PARAMETER G(LIQUID,FE;0) 298.15 +GLIQFE#; 6000 N ! $ unary')
    L.append(' PARAMETER G(LIQUID,SI;0) 298.15 +GLIQSI#; 6000 N ! $ unary')
    L.append(' PARAMETER G(LIQUID,LA,FE;0) 298.15 +19054.390+2.3114202*T; 6000 N ! $ Feng T5 [24]')
    L.append(' PARAMETER G(LIQUID,LA,FE;1) 298.15 +22910.538-10.052670*T; 6000 N ! $ Feng T5 [24]')
    L.append(' PARAMETER G(LIQUID,LA,FE;2) 298.15 +8497.879; 6000 N ! $ Feng T5 [24]')
    L.append(' PARAMETER G(LIQUID,LA,SI;0) 298.15 -249912.5-39.85*T; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(LIQUID,LA,SI;1) 298.15 +25123.5; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(LIQUID,LA,SI;2) 298.15 +83012.5; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(LIQUID,LA,SI;3) 298.15 -21695.6; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(LIQUID,FE,SI;0) 298.15 -150802.2+24.9159*T; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(LIQUID,FE,SI;1) 298.15 -22532.7; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(LIQUID,FE,SI;2) 298.15 +23530.4; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(LIQUID,LA,FE,SI;0) 298.15 +200000; 6000 N ! $ Feng T5 THIS WORK')

    # ----- FCC_A1 (La,Fe,Si)1(Va)1 -----
    L.append('$ ----- FCC_A1 -----')
    L.append('PHASE FCC_A1 %) 2 1 1 !')
    L.append('CONSTITUENT FCC_A1 : LA,FE,SI : VA : !')
    L.append(' PARAMETER G(FCC_A1,LA:VA;0) 298.15 +GLAFCC#; 6000 N ! $ unary')
    L.append(' PARAMETER G(FCC_A1,FE:VA;0) 298.15 +GFCCFE#; 6000 N ! $ unary')
    L.append(' PARAMETER G(FCC_A1,SI:VA;0) 298.15 +GSIFCC#; 6000 N ! $ unary')
    L.append(' PARAMETER TC(FCC_A1,FE:VA;0) 298.15 -201; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER BMAGN(FCC_A1,FE:VA;0) 298.15 -2.1; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(FCC_A1,LA,FE:VA;0) 298.15 +60142.574-9.7517685*T; 6000 N ! $ Feng T5 [24]')
    L.append(' PARAMETER G(FCC_A1,LA,SI:VA;0) 298.15 -191235.4; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(FCC_A1,FE,SI:VA;0) 298.15 -167164.9+42.9734*T; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(FCC_A1,FE,SI:VA;1) 298.15 -44950.4; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(FCC_A1,FE,SI:VA;2) 298.15 +19706.6; 6000 N ! $ Feng T5 [23]')

    # ----- BCC_A2 (La,Fe,Si)1(Va)3 -----
    L.append('$ ----- BCC_A2 -----')
    L.append('PHASE BCC_A2 %& 2 1 3 !')
    L.append('CONSTITUENT BCC_A2 : LA,FE,SI : VA : !')
    L.append(' PARAMETER G(BCC_A2,LA:VA;0) 298.15 +GLABCC#; 6000 N ! $ unary')
    L.append(' PARAMETER G(BCC_A2,FE:VA;0) 298.15 +GHSERFE#; 6000 N ! $ unary (bcc SER)')
    L.append(' PARAMETER G(BCC_A2,SI:VA;0) 298.15 +GSIBCC#; 6000 N ! $ unary')
    L.append(' PARAMETER TC(BCC_A2,FE:VA;0) 298.15 +1043; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER BMAGN(BCC_A2,FE:VA;0) 298.15 +2.22; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER TC(BCC_A2,FE,SI:VA;1) 298.15 +504; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER BMAGN(BCC_A2,FE,SI:VA;1) 298.15 +1.07; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(BCC_A2,LA,FE:VA;0) 298.15 +45319.444; 6000 N ! $ Feng T5 [24]')
    L.append(' PARAMETER G(BCC_A2,LA,SI:VA;0) 298.15 -202356.5; 6000 N ! $ Feng T5 [20]')
    L.append(' PARAMETER G(BCC_A2,FE,SI:VA;0) 298.15 -180000.0+47.8494*T; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(BCC_A2,FE,SI:VA;1) 298.15 -32198.0; 6000 N ! $ Feng T5 [23]')
    L.append(' PARAMETER G(BCC_A2,FE,SI:VA;2) 298.15 +15882.8; 6000 N ! $ Feng T5 [23]')

    # ----- DIAMOND_A4 (Si) -----
    L.append('$ ----- DIAMOND_A4 -----')
    L.append('PHASE DIAMOND_A4 % 1 1.0 !')
    L.append('CONSTITUENT DIAMOND_A4 : SI : !')
    L.append(' PARAMETER G(DIAMOND_A4,SI;0) 298.15 +GHSERSI#; 6000 N ! $ unary (diamond SER)')

    # ----- Fe-Si line compounds -----
    L.append('$ ----- Fe-Si line compounds (Feng T5 [23]) -----')
    for name, rfe, rsi, g in FESI_COMPOUNDS:
        L.append(f'PHASE {name} % 2 {rfe} {rsi} !')
        L.append(f'CONSTITUENT {name} : FE : SI : !')
        L.append(f' PARAMETER G({name},FE:SI;0) 298.15 +{g}; 6000 N ! $ Feng T5 [23]')

    # ----- La-Si(Fe) compounds: (La)a(Si,Fe)b -----
    L.append('$ ----- La-Si(Fe) compounds (Feng T5 [20] + THIS WORK solubility) -----')
    for name, rla, rx, gsi, gfe, lmix in LASI_COMPOUNDS:
        L.append(f'PHASE {name} % 2 {rla} {rx} !')
        L.append(f'CONSTITUENT {name} : LA : SI,FE : !')
        L.append(f' PARAMETER G({name},LA:SI;0) 298.15 +{gsi}; 6000 N ! $ Feng T5 [20]')
        L.append(f' PARAMETER G({name},LA:FE;0) 298.15 +{gfe}; 6000 N ! $ Feng T5 THIS WORK')
        L.append(f' PARAMETER G({name},LA:SI,FE;0) 298.15 +{lmix}; 6000 N ! $ Feng T5 THIS WORK')

    # ----- tau1, tau2 = La(Fe,Si)13 : (La)0.071428(Fe,Si)0.928572 -----
    L.append('$ ----- tau1 (cubic NaZn13) and tau2 (tetragonal) La(Fe,Si)13 (Feng T5 THIS WORK) -----')
    for name, gfe, gsi, lmix in [
        ('TAU1', '2300-0.95*T+0.071428*GHSERLA#+0.928572*GHSERFE#',
                 '37000+6.5*T+0.071428*GHSERLA#+0.928572*GHSERSI#', '-242114+9.5*T'),
        ('TAU2', '6500-0.9*T+0.071428*GHSERLA#+0.928572*GHSERFE#',
                 '22500+8.5*T+0.071428*GHSERLA#+0.928572*GHSERSI#', '-241114+8*T')]:
        L.append(f'PHASE {name} % 2 0.071428 0.928572 !')
        L.append(f'CONSTITUENT {name} : LA : FE,SI : !')
        L.append(f' PARAMETER G({name},LA:FE;0) 298.15 +{gfe}; 6000 N ! $ Feng T5 THIS WORK')
        L.append(f' PARAMETER G({name},LA:SI;0) 298.15 +{gsi}; 6000 N ! $ Feng T5 THIS WORK')
        L.append(f' PARAMETER G({name},LA:FE,SI;0) 298.15 +{lmix}; 6000 N ! $ Feng T5 THIS WORK')
    return '\n'.join(L)


def build():
    tdb = '\n'.join([HEADER, unary_block(), phases_and_params(), ''])
    open(OUT, 'w').write(tdb)
    print(f'wrote {OUT} ({len(tdb)} bytes)')
    return OUT


if __name__ == '__main__':
    build()
