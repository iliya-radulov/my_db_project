"""
Tests for vsm_mass_extractor.extract_mass_from_filename.

Run with:  python3 test_vsm_mass_extractor.py   (or pytest)

Covers the filename conventions seen in real data: underscore, point and
comma as decimal separator, an optional 'm' prefix, upper-case extensions,
and the documented ambiguous 'm4_140mg' case (behaviour kept).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vsm_mass_extractor import extract_mass_from_filename

# (filename, expected mass in mg or None)
CASES = [
    ('20230630_SPS_sample1_50mg.dat', 50.0),
    ('x_50_35mg.dat', 50.35),
    ('sample_m29_07_foo.dat', 29.07),
    ('20230312_Ref_m4_140mg_x.dat', 140.0),          # documented ambiguous case, kept
    ('20230312_TT_small_95.98mg.dat', 95.98),        # was read as 98 mg
    ('20240812_CoFeSi_InductionMolten_m11,819mg.dat', 11.819),
    ('20240813_FM11177_CoFeSi_SuctionCasting_m23,660mg.dat', 23.660),
    ('20240814_FM11178_Fe2Si_Inductionmolten_m23.147mg_.dat', 23.147),
    ('20240827_Mn0.95FeP0.56Si0.39B0.05_BM10h_1100C_xh_32.306mg.dar.DAT', 32.306),
    ('20240828_Fe2Si_SUCTIONCAST_22.205mg.DAT', 22.205),
    ('20240908_Fe5Si3_Ind.Molten_13.878mg.dat', 13.878),
    ('a_50MG.dat', 50.0),
    ('sample1.50mg.dat', None),                      # ambiguous: no mass, not a wrong one
    ('20240910_Fe5Si3_SuctionCasting.dat', None),
]


def test_filename_masses():
    for name, expected in CASES:
        got, _ = extract_mass_from_filename(name)
        if expected is None:
            assert got is None, (name, got)
        else:
            assert got is not None and abs(got - expected) < 1e-9, (name, got, expected)


if __name__ == '__main__':
    test_filename_masses()
    print(f'{len(CASES)} filename cases OK')
