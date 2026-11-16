#!/usr/bin/env python3
"""wp4b_descriptor.py (16 Nov 2026) - computes D(x,T)=G(competing, tau1/tau2 suspended)-G(all) at frozen composition La1/14 Fe(13-x)/14 Si x/14,
per the FROZEN pre-registration. Usage: python wp4b_descriptor.py self   -> D_self.csv ;  python wp4b_descriptor.py band -> D_band.csv (20 merged combinations)."""
import warnings,sys,csv,os,numpy as np;warnings.filterwarnings("ignore")
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from pycalphad import Database,equilibrium,variables as v
XS=(1.2,1.4,1.6,1.8,2.0); TS={1050:1323.15,1150:1423.15,1200:1473.15}
SELF=os.environ.get('SELF_TDB','/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/tdb_build/LaFeSi_feng2023.tdb')
def gm(db,ph,cond):
    eq=equilibrium(db,['LA','FE','SI','VA'],ph,cond,calc_opts={'pdens':2000})
    P=np.array(eq.Phase).ravel();N=np.array(eq.NP).ravel()
    return float(np.array(eq.GM).ravel()[0]),'+'.join(sorted({str(p) for p,n in zip(P,N) if str(p) not in('','nan') and not np.isnan(n) and n>0.01}))
def rows(db,tag):
    allp=list(db.phases); comp=[p for p in allp if p not in('TAU1','TAU2')]; out=[]
    for x in XS:
        for Tc,Tk in TS.items():
            X={v.X('LA'):1/14,v.X('SI'):x/14,v.T:Tk,v.P:101325,v.N:1}
            try: ga,pa=gm(db,allp,X); gc,pc=gm(db,comp,X); out.append([tag,x,Tc,round(gc-ga,1),pa,pc])
            except Exception as e: out.append([tag,x,Tc,'',str(e)[:50],''])
    return out
if __name__=='__main__':
    mode=sys.argv[1]; R=[]
    if mode=='self': R=rows(Database(SELF),'self')
    else:
        import build_merged_tdb_fixed as B
        FELA=['FeLa-09Pov','FeLa-23Su'];LASI=['LaSi-10Zho','LaSi-20Xu'];FESI=['FeSi-12Ohn','FeSi-14Yua','FeSi-17Cui','FeSi-23Wit','FeSi-91Lac-LB']
        for fe in FESI:
            for fl in FELA:
                for ls in LASI:
                    try: _,db=B.build(fl,ls,fe,out=f'/tmp/w_{fl}_{ls}_{fe}.tdb'); R+=rows(db,f'{fl}+{ls}+{fe}')
                    except Exception as e: R.append([f'{fl}+{ls}+{fe}','','','',str(e)[:50],''])
                    print(R[-1],flush=True)
    w=csv.writer(open(f'D_{mode}.csv','w',newline=''));w.writerow(['tdb','x','T_C','D_J_per_mol_atom','tau1_assemblage','competing']);w.writerows(R)
    for r in R[:15] if mode=='self' else []: print(r)
