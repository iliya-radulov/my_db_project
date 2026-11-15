"""crosscheck_binaries.py — compare the self-contained TDB's typed binary
parameters against the real cited binaries (faithfulness proof).
Usage: python crosscheck_binaries.py <binary_tdb_dir>"""
import sys, warnings; warnings.filterwarnings('ignore')
import numpy as np
from pycalphad import Database, calculate
BIN = sys.argv[1].rstrip('/') + '/'
mine = Database(sys.argv[2] if len(sys.argv) > 2 else
                __file__.rsplit('/tdb_build/', 1)[0] + '/tdb_build/LaFeSi_feng2023.tdb')

def gmix_liquid(db, elA, elB, T=1873):
    g = float(np.array(calculate(db, [elA, elB, 'VA'] if 'VA' in db.elements else [elA, elB],
              'LIQUID', T=T, P=101325, points=np.array([[0.5, 0.5]]), output='GM').GM).ravel()[0])
    gA = float(np.array(calculate(db, [elA, elB], 'LIQUID', T=T, P=101325,
              points=np.array([[1.0, 0.0]]), output='GM').GM).ravel()[0])
    gB = float(np.array(calculate(db, [elA, elB], 'LIQUID', T=T, P=101325,
              points=np.array([[0.0, 1.0]]), output='GM').GM).ravel()[0])
    return g - 0.5 * gA - 0.5 * gB

for sysname, (elA, elB, f) in {'Fe-Si': ('FE', 'SI', 'FeSi-17Cui.tdb'),
                               'La-Si': ('LA', 'SI', 'LaSi-10Zho.tdb'),
                               'La-Fe': ('LA', 'FE', 'FeLa-23Su.tdb')}.items():
    gr = gmix_liquid(Database(BIN + f), elA, elB)
    gm = gmix_liquid(mine, elA, elB)
    print(f"{sysname}: real[{f}]={gr:.1f}  mine={gm:.1f}  delta={gm-gr:+.1f} J/mol")
