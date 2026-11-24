import warnings; warnings.filterwarnings('ignore')
import numpy as np
from pycalphad import Database, equilibrium, variables as v
alloys={12:(2,66,32),19:(4,73,23),20:(3,71,26)}
exp={12:'Fe2Si + tau2',19:'tau2 + B2',20:'D03 + tau2'}
feng={12:'Fe2Si + tau2 + D03',19:'tau2 + B2',20:'tau2 + B2'}
def phases_of(dbf,names,x,T=1373.0):
    comps=['LA','FE','SI','VA']
    cond={v.T:T,v.P:101325,v.N:1,v.X('LA'):x[0]/100,v.X('SI'):x[2]/100}
    eq=equilibrium(dbf,comps,names,cond)
    ph=eq.Phase.values.squeeze().ravel(); npv=eq.NP.values.squeeze().ravel()
    return sorted([(str(p),round(float(n),3)) for p,n in zip(ph,npv) if str(p) and n>1e-3])
for label,path in (('no ordering (merged 12Ohn)','merged_12Ohn.tdb'),('with Ohnuma B2/D03','merged_12Ohn_ordered.tdb')):
    dbf=Database(path); names=list(dbf.phases.keys())
    print('==',label)
    for k,x in alloys.items():
        print(f'  #{k} La{x[0]}Fe{x[1]}Si{x[2]}  exp: {exp[k]:14s} Feng calc: {feng[k]:20s} ->', phases_of(dbf,names,x))
