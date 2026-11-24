import sys,warnings; warnings.filterwarnings('ignore')
import numpy as np
from pycalphad import Database, equilibrium, variables as v
def D(tdbpath,T=1373.0,xsi_over=1.5,extra=()):
    dbf=Database(tdbpath); comps=['LA','FE','SI','VA']
    allp=[p for p in dbf.phases.keys()]
    p_all=[p for p in allp]; p_no=[p for p in allp if p not in ('TAU1','TAU2')]
    n=13+1 # La + Fe(13-x) + Si x   -> per 14 atoms
    xla=1/14; xsi=xsi_over/14
    cond={v.T:T,v.P:101325,v.N:1,v.X('LA'):xla,v.X('SI'):xsi}
    g1=float(equilibrium(dbf,comps,p_all,cond,output='GM').GM.values.squeeze())
    g0=float(equilibrium(dbf,comps,p_no,cond,output='GM').GM.values.squeeze())
    return g0-g1
if __name__=='__main__':
    for f in sys.argv[1:]: print(f, round(D(f),1))
