import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from pycalphad import Database, equilibrium, variables as v
comps=['LA','FE','SI','VA']
def run(dbf,phs,x,T):
    c={v.T:T,v.P:101325,v.N:1,v.X('LA'):1/(13+1),v.X('SI'):x/14}
    # La(Fe13-x Six): La 1, total 14 atoms
    eq=equilibrium(dbf,comps,phs,c)
    g=float(eq.GM.values.squeeze())
    ph=eq.Phase.values.squeeze().ravel(); npv=eq.NP.values.squeeze().ravel()
    sets=[(str(p),float(n)) for p,n in zip(ph,npv) if str(p) and n>1e-4]
    # Si content of bcc-type phase in the assemblage
    xsi=None
    for i,(p,n) in enumerate(zip(ph,npv)):
        if str(p) in ('BCC_A2','A2_BCC','B2_BCC','BCC_4SL') and n>1e-4:
            xsi=float(eq.X.sel(component='SI').values.squeeze().ravel()[i])
    return g,sets,xsi
rows=[]
d0=Database('merged_12Ohn.tdb'); d1=Database('merged_12Ohn_ordered.tdb')
for x in (1.2,1.4,1.6,1.8,2.0):
    for TC in (1050,1150,1200):
        T=TC+273.15
        res={}
        for lab,dbf in (('no',d0),('ord',d1)):
            allp=list(dbf.phases.keys()); nop=[p for p in allp if p not in ('TAU1','TAU2')]
            g1,_,_=run(dbf,allp,x,T); g0,s0,xs=run(dbf,nop,x,T)
            res[lab]=(g0-g1,s0,xs)
        rows.append(dict(x=x,T_C=TC,D_no=res['no'][0],D_ord=res['ord'][0],dD=res['ord'][0]-res['no'][0],
                         bcc_xSi_no=res['no'][2],bcc_xSi_ord=res['ord'][2],sets_ord='+'.join(p for p,_ in res['ord'][1])))
df=pd.DataFrame(rows); pd.set_option('display.width',250); print(df.round(3).to_string())
df.to_csv('D_ordering_effect.csv',index=False)
