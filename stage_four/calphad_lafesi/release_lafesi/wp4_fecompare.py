import warnings,sys,numpy as np;warnings.filterwarnings("ignore")
sys.path.insert(0,'/home/claude')
import build_merged_tdb_fixed as B
from pycalphad import Database,calculate,equilibrium,variables as v
fdb=Database('/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/tdb_build/LaFeSi_feng2023.tdb')
out,db=B.build('FeLa-23Su','LaSi-10Zho','FeSi-17Cui',out='/tmp/faith_fe.tdb')
print("phases with Fe on 2nd sublattice:",[p for p in B.FE_SUBST if p in db.phases and 'FE' in {s.name for s in db.phases[p].constituents[1]}])
feng={'LA5SI3_D8L':'LA5SIFE3','LA3SI2_D5A':'LA3SIFE2','LA5SI4':'LA5SIFE4','LASI_B27':'LASIFE','LASI2_X':'ALASIFE2','LASI2_CC':'BLASIFE2'}
T=1373.0
print("A) per-atom G at site fractions (La:Si,Fe) = (1, 1-x, x), merged minus Feng, J/mol-atom, T=1373")
for ph,fn in feng.items():
    r=[]
    for x in (0.0,0.2,1.0):
        pt=np.array([[1.0,1-x,x]])
        m=float(calculate(db,['LA','SI','FE','VA'],ph,T=T,P=101325,points=pt).GM.squeeze())
        f=float(calculate(fdb,['LA','SI','FE','VA'],fn,T=T,P=101325,points=pt).GM.squeeze())
        r.append(m-f)
    print(f"   {ph:11s} x_Fe=0: {r[0]:+7.1f}   0.2: {r[1]:+7.1f}   1.0: {r[2]:+7.1f}")
X={v.X('LA'):1/14,v.X('SI'):1.5/14,v.T:T,v.P:101325,v.N:1}
def run(d,ph):
    eq=equilibrium(d,['LA','FE','SI','VA'],ph,X,calc_opts={'pdens':2000})
    return float(np.array(eq.GM).ravel()[0]),[(str(p),round(float(n),3)) for p,n in zip(np.array(eq.Phase).ravel(),np.array(eq.NP).ravel()) if str(p) not in('','nan') and not np.isnan(n) and n>0.005]
for name,d in (("merged+Fe-subst",db),("self-contained ",fdb)):
    ap=list(d.phases); a=run(d,ap); c=run(d,[p for p in ap if p not in('TAU1','TAU2')])
    print(f"B) {name}: tau1 {a[0]:.0f} {a[1]} | compete {c[0]:.0f} {c[1]} | driving force {c[0]-a[0]:.0f} J/mol-atom")
