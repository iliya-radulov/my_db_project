import warnings,sys,numpy as np;warnings.filterwarnings("ignore")
sys.path.insert(0,'/home/claude')
import build_merged_tdb_fixed as B
from pycalphad import Database,calculate,variables as v
fdb=Database('/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/tdb_build/LaFeSi_feng2023.tdb')
out,db=B.build('FeLa-23Su','LaSi-10Zho','FeSi-17Cui',out='/tmp/faith_fe.tdb')
cui=Database(B.COLL+'/FeSi-17Cui.tdb')
print("Fe-Si bcc (BCC_A2, disordered) G per atom, J/mol-atom at 1373 K")
print(f"{'x_Si':>6} {'merged':>10} {'Cui disord':>11} {'Feng T5':>10}  merged-Feng   merged-Cui")
for x in (0.02,0.05,0.10,0.15,0.20):
    pt=np.array([[1-x,x,1.0]])    # sublattice 1 sorted (FE,SI), sublattice 2 VA
    g=lambda d: float(calculate(d,['FE','SI','VA'],'BCC_A2',T=1373.0,P=101325,points=pt).GM.squeeze())
    m,c,f=g(db),g(cui),g(fdb)
    print(f"{x:6.2f} {m:10.1f} {c:11.1f} {f:10.1f}  {m-f:+10.1f}   {m-c:+10.1f}")
