"""
alloy_screening.py
Quick composition screening using VEC, δ, and ΔH_mix
No external dependencies - uses only element property tables.

ΔH_mix table source: Takeuchi & Inoue, Mater. Trans. JIM 41 (2000) 1372
and the companion classification paper, Takeuchi & Inoue, Mater. Trans.
46 (2005) 2817. Values are the post-metallisation ΔH_AB^mix in kJ/mol
for equiatomic binary liquid A-B, as tabulated by those papers.

CONVENTION: ΔH_mix here is stored as the Takeuchi ΔH_AB^mix. The
regular-solution interaction parameter is Ω_ij = 4 * ΔH_AB^mix, and
that factor is applied inside calculate_mixing_enthalpy. Do NOT
pre-multiply the table values by 4.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ---------------------------------------------------------------------------
# Element properties
# ---------------------------------------------------------------------------
# Complete ELEMENT_PROPERTIES - includes all elements with data
# valence electrons, atomic radius (Å), electronegativity (Pauling),
# melting point (melt_K) and boiling point (boil_K), both in Kelvin.
# melt_K/boil_K source: Reade.com reference table, spot-checked against
# known CRC/NIST values (Fe, Cu, W, Al, Zn, Mg all matched exactly).
# None = no stable value at 1 atm (e.g. He does not solidify at 1 atm).
# NOTE: As has an INVERTED melt/boil relationship (melt_K=1090 > boil_K=887)
# -- this is real physics, not a data error: As sublimes directly at 1 atm
# and only shows a true liquid phase under ~3.6 MPa pressure. At (astatine)
# is also inverted in the source table, but At's properties are poorly
# known (only ever produced in trace/synthetic quantities). Any synthesis-
# route logic comparing melt/boil across elements must special-case these
# two rather than assume boil_K > melt_K always holds.
ELEMENT_PROPERTIES = {
    # Period 1
    'H': {'valence': 1, 'radius': 0.53, 'en': 2.20, 'melt_K': 14.01, 'boil_K': 20.28},
    'He': {'valence': 2, 'radius': 0.31, 'en': 4.16, 'melt_K': None, 'boil_K': 4.22},
    # Period 2
    'Li': {'valence': 1, 'radius': 1.52, 'en': 0.98, 'melt_K': 453.69, 'boil_K': 1615},
    'Be': {'valence': 2, 'radius': 1.12, 'en': 1.57, 'melt_K': 1560, 'boil_K': 2743},
    'B': {'valence': 3, 'radius': 0.87, 'en': 2.04, 'melt_K': 2348, 'boil_K': 4273},
    'C': {'valence': 4, 'radius': 0.77, 'en': 2.55, 'melt_K': 3823, 'boil_K': 4300},
    'N': {'valence': 5, 'radius': 0.75, 'en': 3.04, 'melt_K': 63.05, 'boil_K': 77.36},
    'O': {'valence': 6, 'radius': 0.73, 'en': 3.44, 'melt_K': 54.8, 'boil_K': 90.2},
    'F': {'valence': 7, 'radius': 0.71, 'en': 3.98, 'melt_K': 53.5, 'boil_K': 85.03},
    'Ne': {'valence': 8, 'radius': 0.69, 'en': 4.79, 'melt_K': 24.56, 'boil_K': 27.07},
    # Period 3
    'Na': {'valence': 1, 'radius': 1.86, 'en': 0.93, 'melt_K': 370.87, 'boil_K': 1156},
    'Mg': {'valence': 2, 'radius': 1.60, 'en': 1.31, 'melt_K': 923, 'boil_K': 1363},
    'Al': {'valence': 3, 'radius': 1.43, 'en': 1.61, 'melt_K': 933.47, 'boil_K': 2792},
    'Si': {'valence': 4, 'radius': 1.17, 'en': 1.90, 'melt_K': 1687, 'boil_K': 3173},
    'P': {'valence': 5, 'radius': 1.10, 'en': 2.19, 'melt_K': 317.3, 'boil_K': 553.6},
    'S': {'valence': 6, 'radius': 1.04, 'en': 2.58, 'melt_K': 388.36, 'boil_K': 717.87},
    'Cl': {'valence': 7, 'radius': 0.99, 'en': 3.16, 'melt_K': 171.6, 'boil_K': 239.11},
    'Ar': {'valence': 8, 'radius': 0.98, 'en': 3.24, 'melt_K': 83.8, 'boil_K': 87.3},
    # Period 4
    'K': {'valence': 1, 'radius': 2.27, 'en': 0.82, 'melt_K': 336.53, 'boil_K': 1032},
    'Ca': {'valence': 2, 'radius': 1.97, 'en': 1.00, 'melt_K': 1115, 'boil_K': 1757},
    'Sc': {'valence': 3, 'radius': 1.62, 'en': 1.36, 'melt_K': 1814, 'boil_K': 3103},
    'Ti': {'valence': 4, 'radius': 1.47, 'en': 1.54, 'melt_K': 1941, 'boil_K': 3560},
    'V': {'valence': 5, 'radius': 1.35, 'en': 1.63, 'melt_K': 2183, 'boil_K': 3680},
    'Cr': {'valence': 6, 'radius': 1.28, 'en': 1.66, 'melt_K': 2180, 'boil_K': 2944},
    'Mn': {'valence': 7, 'radius': 1.27, 'en': 1.55, 'melt_K': 1519, 'boil_K': 2334},
    'Fe': {'valence': 8, 'radius': 1.26, 'en': 1.83, 'melt_K': 1811, 'boil_K': 3134},
    'Co': {'valence': 9, 'radius': 1.25, 'en': 1.88, 'melt_K': 1768, 'boil_K': 3200},
    'Ni': {'valence': 10, 'radius': 1.24, 'en': 1.91, 'melt_K': 1728, 'boil_K': 3186},
    'Cu': {'valence': 11, 'radius': 1.28, 'en': 1.90, 'melt_K': 1357.77, 'boil_K': 2835},
    'Zn': {'valence': 12, 'radius': 1.33, 'en': 1.65, 'melt_K': 692.68, 'boil_K': 1180},
    'Ga': {'valence': 3, 'radius': 1.36, 'en': 1.81, 'melt_K': 302.91, 'boil_K': 2477},
    'Ge': {'valence': 4, 'radius': 1.22, 'en': 2.01, 'melt_K': 1211.4, 'boil_K': 3093},
    'As': {'valence': 5, 'radius': 1.21, 'en': 2.18, 'melt_K': 1090, 'boil_K': 887},
    'Se': {'valence': 6, 'radius': 1.17, 'en': 2.55, 'melt_K': 494, 'boil_K': 958},
    'Br': {'valence': 7, 'radius': 1.14, 'en': 2.96, 'melt_K': 265.8, 'boil_K': 332},
    'Kr': {'valence': 8, 'radius': 1.12, 'en': 3.00, 'melt_K': 115.79, 'boil_K': 119.93},
    # Period 5
    'Rb': {'valence': 1, 'radius': 2.48, 'en': 0.82, 'melt_K': 312.46, 'boil_K': 961},
    'Sr': {'valence': 2, 'radius': 2.15, 'en': 0.95, 'melt_K': 1050, 'boil_K': 1655},
    'Y': {'valence': 3, 'radius': 1.80, 'en': 1.22, 'melt_K': 1799, 'boil_K': 3618},
    'Zr': {'valence': 4, 'radius': 1.60, 'en': 1.33, 'melt_K': 2128, 'boil_K': 4682},
    'Nb': {'valence': 5, 'radius': 1.46, 'en': 1.60, 'melt_K': 2750, 'boil_K': 5017},
    'Mo': {'valence': 6, 'radius': 1.39, 'en': 2.16, 'melt_K': 2896, 'boil_K': 4912},
    'Tc': {'valence': 7, 'radius': 1.36, 'en': 1.90, 'melt_K': 2430, 'boil_K': 4538},
    'Ru': {'valence': 8, 'radius': 1.34, 'en': 2.20, 'melt_K': 2607, 'boil_K': 4423},
    'Rh': {'valence': 9, 'radius': 1.34, 'en': 2.28, 'melt_K': 2237, 'boil_K': 3968},
    'Pd': {'valence': 10, 'radius': 1.37, 'en': 2.20, 'melt_K': 1828.05, 'boil_K': 3236},
    'Ag': {'valence': 11, 'radius': 1.44, 'en': 1.93, 'melt_K': 1234.93, 'boil_K': 2435},
    'Cd': {'valence': 12, 'radius': 1.49, 'en': 1.69, 'melt_K': 594.22, 'boil_K': 1040},
    'In': {'valence': 3, 'radius': 1.63, 'en': 1.78, 'melt_K': 429.75, 'boil_K': 2345},
    'Sn': {'valence': 4, 'radius': 1.40, 'en': 1.96, 'melt_K': 505.08, 'boil_K': 2875},
    'Sb': {'valence': 5, 'radius': 1.40, 'en': 2.05, 'melt_K': 903.78, 'boil_K': 1860},
    'Te': {'valence': 6, 'radius': 1.37, 'en': 2.10, 'melt_K': 722.66, 'boil_K': 1261},
    'I': {'valence': 7, 'radius': 1.33, 'en': 2.66, 'melt_K': 386.85, 'boil_K': 457.4},
    'Xe': {'valence': 8, 'radius': 1.31, 'en': 2.60, 'melt_K': 161.3, 'boil_K': 165.1},
    # Period 6 (Lanthanides)
    'Cs': {'valence': 1, 'radius': 2.65, 'en': 0.79, 'melt_K': 301.59, 'boil_K': 944},
    'Ba': {'valence': 2, 'radius': 2.22, 'en': 0.89, 'melt_K': 1000, 'boil_K': 2143},
    'La': {'valence': 3, 'radius': 1.87, 'en': 1.10, 'melt_K': 1193, 'boil_K': 3737},
    'Ce': {'valence': 3, 'radius': 1.82, 'en': 1.12, 'melt_K': 1071, 'boil_K': 3633},
    'Pr': {'valence': 3, 'radius': 1.82, 'en': 1.13, 'melt_K': 1204, 'boil_K': 3563},
    'Nd': {'valence': 3, 'radius': 1.82, 'en': 1.14, 'melt_K': 1294, 'boil_K': 3373},
    'Pm': {'valence': 3, 'radius': 1.81, 'en': 1.13, 'melt_K': 1373, 'boil_K': 3273},
    'Sm': {'valence': 3, 'radius': 1.80, 'en': 1.17, 'melt_K': 1345, 'boil_K': 2076},
    'Eu': {'valence': 2, 'radius': 1.80, 'en': 1.20, 'melt_K': 1095, 'boil_K': 1800},
    'Gd': {'valence': 3, 'radius': 1.79, 'en': 1.20, 'melt_K': 1586, 'boil_K': 3523},
    'Tb': {'valence': 3, 'radius': 1.77, 'en': 1.10, 'melt_K': 1629, 'boil_K': 3503},
    'Dy': {'valence': 3, 'radius': 1.77, 'en': 1.22, 'melt_K': 1685, 'boil_K': 2840},
    'Ho': {'valence': 3, 'radius': 1.77, 'en': 1.23, 'melt_K': 1747, 'boil_K': 2973},
    'Er': {'valence': 3, 'radius': 1.76, 'en': 1.24, 'melt_K': 1770, 'boil_K': 3141},
    'Tm': {'valence': 3, 'radius': 1.75, 'en': 1.25, 'melt_K': 1818, 'boil_K': 2223},
    'Yb': {'valence': 2, 'radius': 1.74, 'en': 1.10, 'melt_K': 1092, 'boil_K': 1469},
    'Lu': {'valence': 3, 'radius': 1.73, 'en': 1.27, 'melt_K': 1936, 'boil_K': 3675},
    # Period 6 (Transition metals)
    'Hf': {'valence': 4, 'radius': 1.59, 'en': 1.30, 'melt_K': 2506, 'boil_K': 4876},
    'Ta': {'valence': 5, 'radius': 1.46, 'en': 1.50, 'melt_K': 3290, 'boil_K': 5731},
    'W': {'valence': 6, 'radius': 1.39, 'en': 2.36, 'melt_K': 3695, 'boil_K': 5828},
    'Re': {'valence': 7, 'radius': 1.37, 'en': 1.90, 'melt_K': 3459, 'boil_K': 5869},
    'Os': {'valence': 8, 'radius': 1.35, 'en': 2.20, 'melt_K': 3306, 'boil_K': 5285},
    'Ir': {'valence': 9, 'radius': 1.36, 'en': 2.20, 'melt_K': 2739, 'boil_K': 4701},
    'Pt': {'valence': 10, 'radius': 1.39, 'en': 2.28, 'melt_K': 2041.4, 'boil_K': 4098},
    'Au': {'valence': 11, 'radius': 1.44, 'en': 2.54, 'melt_K': 1337.33, 'boil_K': 3129},
    'Hg': {'valence': 12, 'radius': 1.50, 'en': 2.00, 'melt_K': 234.32, 'boil_K': 629.88},
    'Tl': {'valence': 3, 'radius': 1.71, 'en': 1.80, 'melt_K': 577, 'boil_K': 1746},
    'Pb': {'valence': 4, 'radius': 1.75, 'en': 2.33, 'melt_K': 600.61, 'boil_K': 2022},
    'Bi': {'valence': 5, 'radius': 1.55, 'en': 2.02, 'melt_K': 544.4, 'boil_K': 1837},
    'Po': {'valence': 6, 'radius': 1.53, 'en': 2.00, 'melt_K': 528, 'boil_K': 1235},
    'At': {'valence': 7, 'radius': 1.50, 'en': 2.20, 'melt_K': 575, 'boil_K': 623},
    'Rn': {'valence': 8, 'radius': 1.48, 'en': 2.60, 'melt_K': 202, 'boil_K': 211.3},
    # Period 7 (Actinides)
    'Fr': {'valence': 1, 'radius': 2.70, 'en': 0.70, 'melt_K': 294, 'boil_K': 923},
    'Ra': {'valence': 2, 'radius': 2.23, 'en': 0.90, 'melt_K': 973, 'boil_K': 2010},
    'Ac': {'valence': 3, 'radius': 1.95, 'en': 1.10, 'melt_K': 1323, 'boil_K': 3473},
    'Th': {'valence': 4, 'radius': 1.80, 'en': 1.30, 'melt_K': 2023, 'boil_K': 5093},
    'Pa': {'valence': 5, 'radius': 1.61, 'en': 1.50, 'melt_K': 1845, 'boil_K': 4273},
    'U': {'valence': 6, 'radius': 1.54, 'en': 1.38, 'melt_K': 1408, 'boil_K': 4200},
    'Np': {'valence': 6, 'radius': 1.55, 'en': 1.36, 'melt_K': 917, 'boil_K': 4273},
    'Pu': {'valence': 6, 'radius': 1.53, 'en': 1.28, 'melt_K': 913, 'boil_K': 3505},
    'Am': {'valence': 3, 'radius': 1.52, 'en': 1.13, 'melt_K': 1449, 'boil_K': 2284},
    'Cm': {'valence': 3, 'radius': 1.50, 'en': 1.28, 'melt_K': 1618, 'boil_K': 3383},
    'Bk': {'valence': 3, 'radius': 1.48, 'en': 1.30, 'melt_K': 1323, 'boil_K': None},
    'Cf': {'valence': 3, 'radius': 1.47, 'en': 1.30, 'melt_K': 1173, 'boil_K': None},
    'Es': {'valence': 3, 'radius': 1.45, 'en': 1.30, 'melt_K': 1133, 'boil_K': None},
    'Fm': {'valence': 3, 'radius': 1.44, 'en': 1.30, 'melt_K': 1800, 'boil_K': None},
    'Md': {'valence': 3, 'radius': 1.43, 'en': 1.30, 'melt_K': 1100, 'boil_K': None},
    'No': {'valence': 3, 'radius': 1.42, 'en': 1.30, 'melt_K': 1100, 'boil_K': None},
    'Lr': {'valence': 3, 'radius': 1.41, 'en': 1.30, 'melt_K': 1900, 'boil_K': None},
}

# ---------------------------------------------------------------------------
# Pairwise mixing enthalpy table
# Values are ΔH_AB^mix (kJ/mol) for equiatomic binary liquid A-B, from
# Takeuchi & Inoue, Mater. Trans. JIM 41 (2000) 1372 / Mater. Trans. 46
# (2005) 2817. Symmetric: (A,B) and (B,A) are the same value. The
# regular-solution interaction parameter Ω = 4·ΔH is applied later.
#
# Every entry was cross-checked (2026-10) against matminer's machine-
# readable transcription of the same Takeuchi & Inoue 2005 table
# (matminer/utils/data_files/MiedemaLiquidDeltaHf.tsv). That check found
# 16 wrong values in the previous version of this table (all C pairs set
# to 0, B-Zr, Cu-Mn and Cu-V with flipped signs, Ag-Fe, Ag-La, Au-La,
# Cr-P, La-Mn, Ga-Si), which are corrected here.
# ---------------------------------------------------------------------------
PAIRWISE_DELTA_H = {
    ('Ag', 'Al'): -4,     ('Ag', 'La'): -30,
    ('Ag', 'Cu'): 2,      ('Ag', 'Fe'): 28,   ('Ag', 'Mg'): -10,
    ('Al', 'B'): 0,       ('Al', 'Ca'): -20,  ('Al', 'Ce'): -38,
    ('Al', 'Co'): -19,    ('Al', 'Cr'): -10,  ('Al', 'Cu'): -1,
    ('Al', 'Fe'): -11,    ('Al', 'Ga'): 1,    ('Al', 'La'): -38,
    ('Al', 'Mg'): -2,     ('Al', 'Mn'): -19,  ('Al', 'Mo'): -5,
    ('Al', 'Nb'): -18,    ('Al', 'Ni'): -22,  ('Al', 'Si'): -19,
    ('Al', 'Zr'): -44,
    ('Au', 'Cu'): -9,     ('Au', 'La'): -73,
    ('B', 'Co'): -24,     ('B', 'Cr'): -31,   ('B', 'Cu'): 0,
    ('B', 'Fe'): -26,     ('B', 'Ni'): -24,   ('B', 'Zr'): -71,
    ('C', 'Co'): -42,     ('C', 'Cr'): -61,   ('C', 'Fe'): -50,
    ('C', 'Mo'): -67,     ('C', 'Ni'): -39,   ('C', 'Si'): -39,
    ('C', 'W'): -60,
    ('Ca', 'Cu'): -13,    ('Ca', 'Mg'): -6,   ('Ca', 'Zn'): -22,
    ('Co', 'Cr'): -4,     ('Co', 'Fe'): -1,   ('Co', 'Hf'): -35,
    ('Co', 'Mn'): -5,     ('Co', 'Mo'): -5,   ('Co', 'Nb'): -25,
    ('Co', 'Ni'): 0,      ('Co', 'P'): -35.5, ('Co', 'Pd'): -1,
    ('Co', 'Si'): -38,    ('Co', 'Ti'): -28,  ('Co', 'V'): -14,
    ('Co', 'W'): -1,      ('Co', 'Y'): -22,   ('Co', 'Zr'): -41,
    ('Cr', 'Fe'): -1,     ('Cr', 'Ge'): -18.5,('Cr', 'Mo'): 0,
    ('Cr', 'Ni'): -7,     ('Cr', 'P'): -49.5, ('Cr', 'Pd'): -15,
    ('Cr', 'Si'): -37,    ('Cr', 'Zr'): -12,
    ('Cu', 'Fe'): 13,     ('Cu', 'Hf'): -17,  ('Cu', 'La'): -21,
    ('Cu', 'Mg'): -3,     ('Cu', 'Mn'): 4,    ('Cu', 'Nb'): 3,
    ('Cu', 'Ni'): 4,      ('Cu', 'P'): -17.5, ('Cu', 'Si'): -19,
    ('Cu', 'Ti'): -9,     ('Cu', 'V'): 5,     ('Cu', 'Y'): -22,
    ('Cu', 'Zr'): -23,
    ('Fe', 'Ga'): -2,     ('Fe', 'Ge'): -15.5,('Fe', 'Hf'): -21,
    ('Fe', 'La'): 5,      ('Fe', 'Ni'): -2,   ('Fe', 'P'): -39.5,
    ('Fe', 'Si'): -35,    ('Fe', 'Zr'): -25,
    ('Ga', 'Mg'): -4,
    ('Hf', 'Ni'): -42,
    ('La', 'Mn'): 3,      ('La', 'Ni'): -27,  ('La', 'Zn'): -31,
    ('Mg', 'Ni'): -4,     ('Mg', 'Zn'): -4,
    ('Mn', 'Ni'): -8,     ('Mn', 'Si'): -45,  ('Mn', 'Zr'): -15,
    ('Mo', 'Ni'): -7,     ('Mo', 'Si'): -35,
    ('Nb', 'Ni'): -30,    ('Nb', 'Ti'): 2,    ('Nb', 'Zr'): 4,
    ('Ni', 'Si'): -40,    ('Ni', 'Ti'): -35,  ('Ni', 'Y'): -31,
    ('Ni', 'Zr'): -49,
    ('P', 'Pd'): -36.5,   ('Pd', 'Si'): -55,
    ('Si', 'Ti'): -66,    ('Si', 'Zr'): -84,
    ('Ti', 'Zr'): 0,
    ('V', 'Zr'): -4,      ('W', 'Zr'): -9,
    # --- Lanthanide pairs (previously flagged low confidence; now confirmed
    #     against the Takeuchi & Inoue 2005 table, see header note) ---
    ('Fe', 'Nd'): 1,
    ('Nd', 'Co'): -20,
    ('Nd', 'B'): -49,
    ('Nd', 'Al'): -38,
    ('Nd', 'Si'): -73,
    ('La', 'Si'): -73,
    ('Ga', 'Si'): -17,
    # --- Pairs added for the alloy families in active use (Mn-Fe-P-Si,
    #     La-Fe-Co-Si, Nd-Fe-Ga, Cantor/HEA-type), same source ---
    ('Fe', 'Mn'): 0,      ('Mn', 'P'): -57.5, ('P', 'Si'): -25.5,
    ('Co', 'La'): -17,    ('Ga', 'Nd'): -40,  ('Co', 'Ga'): -11,
    ('Ga', 'La'): -41,    ('Co', 'Cu'): 6,    ('Cr', 'Cu'): 12,
    ('Cr', 'Mn'): 2,      ('Al', 'Ti'): -30,  ('Fe', 'Ti'): -17,
    ('Cr', 'Ti'): -7,     ('Al', 'V'): -16,   ('Fe', 'V'): -7,
    ('Cr', 'V'): -2,      ('Ni', 'V'): -18,   ('Fe', 'Nb'): -16,
    ('Fe', 'Mo'): -2,     ('Cr', 'Nb'): -7,   ('Co', 'Ge'): -21.5,
    ('Ge', 'Mn'): -31.5,
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class IncompleteElementDataError(ValueError):
    """Raised when the composition contains elements missing from
    ELEMENT_PROPERTIES. VEC/delta would otherwise be silently computed
    from an incomplete subset of the composition -- wrong, with no
    indication anything was skipped."""
    def __init__(self, missing_elements):
        self.missing_elements = missing_elements
        msg = (f"ELEMENT_PROPERTIES has no data for: {', '.join(missing_elements)}. "
               f"VEC/delta cannot be reliably computed without it -- "
               f"add these elements to ELEMENT_PROPERTIES, or exclude them from screening.")
        super().__init__(msg)


class IncompletePairDataError(ValueError):
    """Raised when calculate_mixing_enthalpy encounters a pair of elements
    that are both present in ELEMENT_PROPERTIES but whose ΔH_mix value is
    not in PAIRWISE_DELTA_H. The pair-level analogue of
    IncompleteElementDataError: silently defaulting to 0 would produce a
    plausible-looking but wrong ΔH_mix."""
    def __init__(self, missing_pairs):
        self.missing_pairs = missing_pairs
        pairs_str = ", ".join(f"{a}-{b}" for a, b in missing_pairs)
        msg = (f"PAIRWISE_DELTA_H has no entry for: {pairs_str}. "
               f"Delta_H_mix cannot be reliably computed without it -- "
               f"add these pairs to PAIRWISE_DELTA_H, or exclude them from screening.")
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Core calculators
# ---------------------------------------------------------------------------
def _check_elements(composition_at_frac):
    """Raise IncompleteElementDataError if any element in the composition
    is missing from ELEMENT_PROPERTIES."""
    missing = [e for e in composition_at_frac.keys() if e not in ELEMENT_PROPERTIES]
    if missing:
        raise IncompleteElementDataError(missing)


def calculate_vec(composition_at_frac):
    """Valence Electron Concentration (VEC)."""
    _check_elements(composition_at_frac)
    return sum(fraction * ELEMENT_PROPERTIES[e]['valence']
               for e, fraction in composition_at_frac.items())


def calculate_delta(composition_at_frac):
    """Atomic size mismatch δ."""
    _check_elements(composition_at_frac)
    avg_radius = sum(fraction * ELEMENT_PROPERTIES[e]['radius']
                     for e, fraction in composition_at_frac.items())
    delta_sq = sum(fraction * (1 - ELEMENT_PROPERTIES[e]['radius'] / avg_radius) ** 2
                   for e, fraction in composition_at_frac.items())
    return delta_sq ** 0.5


def calculate_mixing_enthalpy(composition_at_frac):
    """
    Mixing enthalpy (kJ/mol) using the Takeuchi-Inoue regular-solution form:

        ΔH_mix = Σ_{i<j} Ω_ij · c_i · c_j,   with Ω_ij = 4 · ΔH_AB^mix

    The 4× factor is the Takeuchi convention (Mater. Trans. JIM 41 (2000)
    eq. 1) and makes the output directly comparable to the tabulated
    ΔH^chem values in that paper (average -33 kJ/mol, GFA threshold
    -15 kJ/mol).

    Raises IncompleteElementDataError if any element is unknown, and
    IncompletePairDataError if any pair is missing from the table.
    """
    _check_elements(composition_at_frac)

    elements = list(composition_at_frac.keys())
    fractions = [composition_at_frac[e] for e in elements]

    # Pass 1: verify every pair is present, collect missing ones.
    missing_pairs = []
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            if (a, b) not in PAIRWISE_DELTA_H and (b, a) not in PAIRWISE_DELTA_H:
                missing_pairs.append((a, b))
    if missing_pairs:
        raise IncompletePairDataError(missing_pairs)

    # Pass 2: sum. Ω = 4·ΔH applied here, not stored in the table.
    delta_h = 0.0
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            dh = PAIRWISE_DELTA_H.get((a, b), PAIRWISE_DELTA_H.get((b, a)))
            delta_h += 4.0 * fractions[i] * fractions[j] * dh
    return delta_h


# ---------------------------------------------------------------------------
# Synthesis feasibility
# ---------------------------------------------------------------------------
def check_synthesis_feasibility(composition_at_frac, hard_block_margin_K=125, caution_zone_K=300):
    """
    Composition-only feasibility check for melt-based synthesis (arc/induction
    melting), using ONLY melt_K/boil_K -- no crystal structure or DFT needed,
    same input shape as calculate_vec/calculate_delta.

    Physical logic (the hard-block rule IS physically grounded, not a
    heuristic):
      - Homogenizing a melt requires heating to at least the HIGHEST melting
        point among constituents.
      - boil_K is treated as "the temperature at which this element is lost
        to vapor at 1 atm" -- true boiling point for most elements, but for
        As (and similarly At) this is really a sublimation point, since
        those elements have no stable liquid phase at 1 atm. Using boil_K
        directly still gives the physically correct comparison either way.
      - If the required melt temperature is at or above the most volatile
        constituent's vapor-loss point (minus a safety margin), that
        element WILL be lost before/as the alloy homogenizes in an open
        melt -- this is a hard physical block, not a judgment call.

    hard_block_margin_K: subtracted from the boiling point before the hard-
    block comparison. Default 125 K is conservative in the safe direction --
    vacuum/inert-atmosphere furnaces used in practice generally LOWER the
    effective boiling point further, not raise it, so real risk starts
    before the naive 1-atm boil_K value is reached.

    caution_zone_K: width of the "genuinely uncertain" zone above the hard-
    block threshold. This width is a practical, ADJUSTABLE heuristic (unlike
    the hard-block rule itself) -- a strongly negative Delta_H_mix can
    suppress a volatile element's effective vapor pressure once alloyed,
    which this composition-only check cannot quantify. Cases in this zone
    are deliberately flagged rather than given a false-confidence route
    suggestion; see calculate_mixing_enthalpy for the complementary check
    worth consulting manually.

    Returns a dict with 'status' in {'ok', 'caution', 'blocked', 'unknown'},
    the limiting elements/temperatures, a human-readable message, and
    suggested_routes.
    """
    _check_elements(composition_at_frac)

    elements = list(composition_at_frac.keys())
    missing_data = sorted({
        e for e in elements
        if ELEMENT_PROPERTIES[e].get('melt_K') is None or ELEMENT_PROPERTIES[e].get('boil_K') is None
    })
    if missing_data:
        return {
            'status': 'unknown',
            'limiting_melt_element': None, 'limiting_melt_K': None,
            'limiting_boil_element': None, 'limiting_boil_K': None,
            'margin_K': None,
            'message': (f"Cannot evaluate melt/boil feasibility -- missing melt_K/boil_K "
                        f"data for: {', '.join(missing_data)}."),
            'suggested_routes': [],
        }

    limiting_melt_element = max(elements, key=lambda e: ELEMENT_PROPERTIES[e]['melt_K'])
    limiting_melt_K = ELEMENT_PROPERTIES[limiting_melt_element]['melt_K']
    limiting_boil_element = min(elements, key=lambda e: ELEMENT_PROPERTIES[e]['boil_K'])
    limiting_boil_K = ELEMENT_PROPERTIES[limiting_boil_element]['boil_K']
    margin_K = limiting_boil_K - limiting_melt_K

    if margin_K <= hard_block_margin_K:
        status = 'blocked'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, at or above "
            f"{limiting_boil_element}'s vapor-loss point ({limiting_boil_K:.0f} K, "
            f"hard-block margin {hard_block_margin_K} K). {limiting_boil_element} would be "
            f"lost to vapor before/as the alloy homogenizes in an open melt -- this is a "
            f"physical block, not a soft warning."
        )
        suggested_routes = ['mechanical alloying (ball milling)', 'powder sintering', 'diffusion bonding']
    elif margin_K <= hard_block_margin_K + caution_zone_K:
        status = 'caution'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, only "
            f"{margin_K:.0f} K below {limiting_boil_element}'s vapor-loss point "
            f"({limiting_boil_K:.0f} K). Pure-element numbers alone aren't sufficient to call "
            f"this either way -- a strongly negative Delta_H_mix can suppress "
            f"{limiting_boil_element}'s effective vapor pressure once alloyed. Check "
            f"calculate_mixing_enthalpy(), search for literature precedent, or run a small "
            f"test melt before committing a full batch."
        )
        suggested_routes = ['arc/induction melting (monitor mass loss)', 'literature precedent check', 'small-scale test melt']
    else:
        status = 'ok'
        message = (
            f"Melting {limiting_melt_element} requires {limiting_melt_K:.0f} K, comfortably "
            f"below {limiting_boil_element}'s vapor-loss point ({limiting_boil_K:.0f} K, "
            f"margin {margin_K:.0f} K). No melt-based volatility concern from composition alone."
        )
        suggested_routes = ['arc/induction melting']

    return {
        'status': status,
        'limiting_melt_element': limiting_melt_element,
        'limiting_melt_K': limiting_melt_K,
        'limiting_boil_element': limiting_boil_element,
        'limiting_boil_K': limiting_boil_K,
        'margin_K': margin_K,
        'message': message,
        'suggested_routes': suggested_routes,
    }


# ---------------------------------------------------------------------------
# Top-level screening
# ---------------------------------------------------------------------------
def screen_composition(composition_at_frac):
    """Run all screening calculations on a composition."""
    return {
        'VEC': calculate_vec(composition_at_frac),
        'delta': calculate_delta(composition_at_frac),
        'Delta_H_mix': calculate_mixing_enthalpy(composition_at_frac),
        'synthesis_feasibility': check_synthesis_feasibility(composition_at_frac),
    }


def interpret_screening(results):
    """Basic interpretation of screening results."""
    vec = results['VEC']
    delta = results['delta']
    delta_h = results['Delta_H_mix']

    print("\n📊 Screening Interpretation:")
    print("-" * 40)

    # VEC thresholds from Guo et al., J. Appl. Phys. 109 (2011) 103505:
    # VEC >= 8.0 -> FCC, VEC < 6.87 -> BCC, in between -> FCC + BCC.
    # These apply to alloys that do form a solid solution.
    if vec >= 8.0:
        print(f"VEC = {vec:.2f} → FCC favoured (if a solid solution forms)")
    elif vec >= 6.87:
        print(f"VEC = {vec:.2f} → Mixed FCC + BCC (if a solid solution forms)")
    else:
        print(f"VEC = {vec:.2f} → BCC favoured (if a solid solution forms)")

    # calculate_delta() returns a fraction; the Yang & Zhang (2012)
    # solid-solution criterion is delta <= 6.6 %.
    delta_pct = delta * 100
    if delta_pct <= 6.6:
        print(f"δ = {delta_pct:.2f} % → Small atomic mismatch: solid solution likely")
    else:
        print(f"δ = {delta_pct:.2f} % → Large atomic mismatch: intermetallic likely")

    # Thresholds here follow Takeuchi-Inoue convention, where the
    # regular-solution form is used (Ω = 4·ΔH).
    if delta_h < -20:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Strong compound formation likely")
    elif delta_h < -5:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Moderate compound formation likely")
    else:
        print(f"ΔH_mix = {delta_h:.1f} kJ/mol → Weak compound formation")

    synth = results.get('synthesis_feasibility')
    if synth:
        status_icon = {'ok': '✅', 'caution': '⚠️', 'blocked': '🚫', 'unknown': '❓'}.get(synth['status'], '')
        print(f"\n{status_icon} Synthesis feasibility [{synth['status']}]: {synth['message']}")
        if synth['suggested_routes']:
            print(f"   Suggested routes: {', '.join(synth['suggested_routes'])}")


# ---------------------------------------------------------------------------
# Self-tests: anchor values from Takeuchi & Inoue (2005) text and Table 1.
# These check that the table was entered correctly, and that the Ω=4·ΔH
# convention is applied consistently.
# ---------------------------------------------------------------------------
def _self_test():
    """Verify the pairwise table against known anchor values. Raises
    AssertionError on mismatch."""
    anchors = {
        ('Zr', 'Ni'): -49,
        ('Mg', 'Zn'): -4,
        ('Mg', 'Cu'): -3,
        ('Nb', 'Sn'): None,   # Sn-Nb not in our table; skip
        ('Nb', 'Ta'): None,   # Ta pairs not tabulated here; skip
        ('Ti', 'Zr'): 0,
        ('Ni', 'Pd'): None,   # not in our table
        ('Fe', 'B'): -26,
        ('Fe', 'P'): -39.5,
        ('Cu', 'Fe'): 13,
        ('Cu', 'Ni'): 4,
        ('Fe', 'Si'): -35,
        ('Si', 'Zr'): -84,
        ('Si', 'Ti'): -66,
        ('Co', 'Si'): -38,
        ('Cr', 'Si'): -37,
        ('Ni', 'Al'): -22,
        ('La', 'Fe'): 5,
        ('Fe', 'C'): -50,
        ('Zr', 'B'): -71,
        ('Cu', 'Mn'): 4,
        ('Cu', 'V'): 5,
        ('Fe', 'Nd'): 1,
    }
    failures = []
    for (a, b), expected in anchors.items():
        if expected is None:
            continue
        got = PAIRWISE_DELTA_H.get((a, b), PAIRWISE_DELTA_H.get((b, a)))
        if got != expected:
            failures.append(f"  {a}-{b}: expected {expected}, got {got}")
    if failures:
        raise AssertionError("Pairwise table anchor mismatches:\n" + "\n".join(failures))
    print("✅ Pairwise table anchors verified.")

    # Convention check: a 50/50 binary should give ΔH_mix = Ω/4 · 1 · 1 = ΔH_AB.
    # i.e. for an equiatomic binary, the regular-solution form with Ω=4ΔH
    # reduces to exactly ΔH_AB^mix. Test against Fe-B = -26.
    fe_b_50_50 = {'Fe': 0.5, 'B': 0.5}
    dh = calculate_mixing_enthalpy(fe_b_50_50)
    assert abs(dh - (-26.0)) < 1e-9, f"Convention check failed: Fe0.5B0.5 gave {dh}, expected -26"
    print("✅ Ω = 4·ΔH convention verified (Fe0.5B0.5 → -26 kJ/mol).")


if __name__ == "__main__":
    _self_test()

    print("\n" + "=" * 50)
    print("Testing NdFeB composition (Fe 0.65, Nd 0.30, Co 0.05):")
    test_composition = {'Fe': 0.65, 'Nd': 0.30, 'Co': 0.05}
    try:
        results = screen_composition(test_composition)
        for key, value in results.items():
            print(f"  {key}: {value}")
        interpret_screening(results)
    except (IncompleteElementDataError, IncompletePairDataError) as e:
        print(f"⚠️  Screening aborted: {e}")

    print("\n" + "=" * 50)
    print("Testing Fe2P composition (Fe 0.667, P 0.333):")
    test_fe2p = {'Fe': 0.667, 'P': 0.333}
    try:
        results = screen_composition(test_fe2p)
        for key, value in results.items():
            print(f"  {key}: {value}")
        interpret_screening(results)
    except (IncompleteElementDataError, IncompletePairDataError) as e:
        print(f"⚠️  Screening aborted: {e}")

    print("\n" + "=" * 50)
    print("Testing a composition with all pairs present (Fe-Nd-Co-B):")
    # Fe-Nd, Fe-Co, Nd-Co are present; Fe-B present; Nd-B present;
    # Co-B present. This should succeed.
    test_with_b = {'Fe': 0.60, 'Nd': 0.20, 'Co': 0.10, 'B': 0.10}
    try:
        results = screen_composition(test_with_b)
        print(f"  ΔH_mix = {results['Delta_H_mix']:.2f} kJ/mol")
    except IncompletePairDataError as e:
        print(f"⚠️  Pair missing (unexpected here): {e}")

    print("\n" + "=" * 50)
    print("Testing a composition with a known-missing pair (Fe-Nd-Ti):")
    # Fe-Nd present, Fe-Ti present, Nd-Ti NOT present → should raise.
    test_missing_pair = {'Fe': 0.60, 'Nd': 0.30, 'Ti': 0.10}
    try:
        results = screen_composition(test_missing_pair)
        print(f"  ΔH_mix = {results['Delta_H_mix']:.2f} kJ/mol (unexpected — pair was found)")
    except IncompletePairDataError as e:
        print(f"✅ Expected IncompletePairDataError caught: {e}")