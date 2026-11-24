import numpy as np, warnings
warnings.filterwarnings('ignore')
from pycalphad import Database, equilibrium, variables as v
dbf=Database('FeSi-12Ohn_pycalphad_VA3.tdb')
comps=['FE','SI','VA']
def gm(phases,x,T):
    eq=equilibrium(dbf,comps,phases,{v.X('SI'):x,v.T:T,v.P:101325,v.N:1},output='GM')
    return float(eq.GM.values.squeeze())
def stable(phases,x,T):
    eq=equilibrium(dbf,comps,phases,{v.X('SI'):x,v.T:T,v.P:101325,v.N:1})
    ph=[str(p) for p in eq.Phase.values.squeeze().ravel() if str(p)]
    return ph
print('Gm(A2) vs ordered bcc models (J/mol-atom); difference = ordering contribution')
for T in (1323,1373,1423,1473):
    for x in (0.04,0.06,0.08,0.10,0.12,0.15,0.20):
        a=gm(['A2_BCC'],x,T); b=gm(['A2_BCC','B2_BCC'],x,T); c=gm(['A2_BCC','BCC_4SL'],x,T)
        print(f'T={T} x_Si={x:.2f}  A2={a:10.1f}  2SL-A2={b-a:8.1f}  4SL-A2={c-a:8.1f}')
