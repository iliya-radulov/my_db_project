#!/usr/bin/env python3
"""wp4_band_fixed.py (16 Nov 2026) - WP4 band on the FIXED merge (build_merged_tdb_fixed.py).
For each of the 20 binary combinations: build, edge-check each binary (disordered subset as reference,
|dG|<=1 J/mol, T=800/1200/1600 K, x=0.05..0.95), then dG_f(tau1) and the driving force
G(competing, tau1/tau2 suspended) - G(tau1) at La(Fe11.5Si1.5), 1373 K. Writes wp4_band_fixed.csv."""
import warnings,sys,csv,os,numpy as np;warnings.filterwarnings("ignore")
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import build_merged_tdb_fixed as B
from pycalphad import Database,equilibrium,variables as v
FELA=['FeLa-09Pov','FeLa-23Su'];LASI=['LaSi-10Zho','LaSi-20Xu'];FESI=['FeSi-12Ohn','FeSi-14Yua','FeSi-17Cui','FeSi-23Wit','FeSi-91Lac-LB']
XS={'LA':1/14,'FE':11.5/14,'SI':1.5/14}; GSER={'LA':-106858,'FE':-69977,'SI':-49705}  # GHSER at 1373 K (verified in the probe)
Gser=sum(XS[e]*GSER[e] for e in XS)
def gm(db,comps,ph,cond):
    eq=equilibrium(db,comps,ph,cond,calc_opts={'pdens':2000})
    P=np.array(eq.Phase).ravel();N=np.array(eq.NP).ravel()
    return float(np.array(eq.GM).ravel()[0]),sorted({str(p) for p,n in zip(P,N) if str(p) not in('','nan') and not np.isnan(n) and n>0.01})
def edge(db,allp,f,A,Bel):
    bdb=Database(B.COLL+'/'+f+'.tdb');ph=[p for p in bdb.phases if p not in B.SKIP_PHASES];bad=skip=0;worst=0
    for T in (800,1200,1600):
        for x in np.arange(0.05,0.951,0.1):
            c={v.X(Bel):float(x),v.T:T,v.P:101325,v.N:1}
            try: d=gm(db,[A,Bel,'VA'],allp,c)[0]-gm(bdb,[A,Bel,'VA'],ph,c)[0]
            except Exception: skip+=1;continue
            if not np.isfinite(d): skip+=1;continue
            worst=max(worst,abs(d)); bad+=abs(d)>1
    return bad,skip,worst
rows=[]
for fe in FESI:
  for fl in FELA:
    for ls in LASI:
      tag=f'{fl}+{ls}+{fe}'
      try:
        _,db=B.build(fl,ls,fe,out=f'/tmp/b_{fl}_{ls}_{fe}.tdb');allp=list(db.phases)
        e=[edge(db,allp,fl,'FE','LA'),edge(db,allp,ls,'LA','SI'),edge(db,allp,fe,'FE','SI')]
        X={v.X('LA'):XS['LA'],v.X('SI'):XS['SI'],v.T:1373,v.P:101325,v.N:1}
        ga,pa=gm(db,['LA','FE','SI','VA'],allp,X);gc,pc=gm(db,['LA','FE','SI','VA'],[p for p in allp if p not in('TAU1','TAU2')],X)
        rows.append([tag,sum(x[0] for x in e),sum(x[1] for x in e),round(max(x[2] for x in e),2),round(ga-Gser),'+'.join(pa),round(gc-ga),'+'.join(pc)])
      except Exception as ex: rows.append([tag,'','','','','','',str(ex)[:60]])
      print(rows[-1],flush=True)
w=csv.writer(open('wp4_band_fixed.csv','w',newline=''));w.writerow(['combo','edge_mismatches','edge_skipped','max_dG_edge','dGf_tau1','tau1_assemblage','driving_force','competing']);w.writerows(rows)
