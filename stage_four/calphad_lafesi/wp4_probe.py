import sys, warnings, numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0,'.')
from pycalphad import equilibrium, variables as v
from build_merged_tdb import build
_,db=build('FeLa-23Su','LaSi-10Zho','FeSi-17Cui',out='/tmp/faith.tdb')
print("phases:",sorted(db.phases))
X={v.X('LA'):1/14,v.X('SI'):1.5/14,v.T:1373,v.P:101325,v.N:1}
def run(phs,pd=2000):
    eq=equilibrium(db,['LA','FE','SI','VA'],phs,X,calc_opts={'pdens':pd})
    G=float(np.array(eq.GM).ravel()[0])
    ph=np.array(eq.Phase).ravel(); n=np.array(eq.NP).ravel()
    return G,[(str(p),round(float(x),4)) for p,x in zip(ph,n) if str(p) not in('','nan') and not np.isnan(x)]
allp=list(db.phases)
print("all  :",run(allp))
comp=[p for p in allp if p not in('TAU1','TAU2')]
for pd in (500,2000,8000): print("compete pdens",pd,run(comp,pd))
# La-bearing candidates
for drop in (None,):
    pass
print("---- G_SER and mixtures")
from pycalphad import calculate
def sym(name): return float(db.symbols[name].subs({v.T:1373.0}))
xs={'LA':1/14,'FE':11.5/14,'SI':1.5/14}
names={'LA':'GHSERLA','FE':'GHSERFE','SI':'GHSERSI'}
for e,n in names.items(): print(e,n,n in db.symbols, round(sym(n)) if n in db.symbols else None)
Gser=sum(xs[e]*sym(names[e]) for e in xs); print("G_SER(1373 K) =",round(Gser),"J/mol-atom")
print("dG_f(tau1) =",round(run(allp)[0]-Gser),"| dG(compete bcc-only result) =",round(-6728.49-Gser))
for phs in (['BCC_A2','DHCP'],['BCC_A2','LIQUID'],['BCC_A2','DHCP','LIQUID'],['BCC_A2','LA5SI3_D8L'],['BCC_A2','FCC_A1','DHCP','LIQUID','FE2SI','LASI_B27','LA5SI3_D8L']):
    print(phs,run(phs,2000))
print("---- hand-built two-phase state: (1/14) dhcp-La + (13/14) bcc(Fe,Si)")
from pycalphad import calculate
def gcalc(phase,comps,cond):
    r=calculate(db,comps,phase,T=1373,P=101325,pdens=50,**cond)
    return float(r.GM.min())
# pure La in dhcp
gL=float(calculate(db,['LA','VA'],'DHCP',T=1373,P=101325,pdens=10).GM.min())
print("G(dhcp, pure La) =",round(gL))
# bcc Fe-Si at x_Si = 1.5/13 (Fe0.885Si0.115)
xs=1.5/13
r=calculate(db,['FE','SI','VA'],'BCC_A2',T=1373,P=101325,pdens=2000)
import numpy as np
X=np.array(r.X.sel(component='SI')).ravel(); G=np.array(r.GM).ravel()
k=np.argmin(abs(X-xs)); print("bcc Fe-Si at xSi=%.3f: G=%.0f (grid x=%.3f)"%(xs,G[k],X[k]))
Gmix=(1/14)*gL+(13/14)*G[k]
print("hand-built mixture G =",round(Gmix),"J/mol-atom ;  equilibrium(competing) returned -6728")
