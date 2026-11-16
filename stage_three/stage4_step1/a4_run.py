#!/usr/bin/env python3
"""a4_run.py (16 Nov 2026) - competing-assemblage record for the 78 Nd-Fe-B survivors.
Same kernel as ternary_threshold.py (same merged TDBs, X_TARGET, pdens=500) but the phase
fractions are read from eq.Phase/eq.NP directly (the kernel's eq.NP.sel(Phase=...) fails silently).
Writes a4_assemblage.csv: one row per (combo, T): threshold, check vs batch CSV, liquid fraction, assemblage."""
import sys, csv, json, warnings, numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0,'.')
from pycalphad import Database, equilibrium, variables as v
from ternary_threshold import ser_function, g_ser_at, ELEMENTS, X_TARGET
TEMPS=[800,1000,1300,1375,1450,1600]   # the six temperatures of the released ensemble
rows=[r for r in csv.DictReader(open(sys.argv[1])) if r["survived"]=="True"]
out=open(sys.argv[2],"w",newline=""); w=csv.writer(out)
w.writerow(["combo","T_K","threshold","batch_threshold","diff","liquid_frac","assemblage_json"])
maxdiff=0
for i,r in enumerate(rows):
    c=r["combo_id"]; db=Database(f"results_v2/merged_tdbs/FENDB_merged_v4__{c}.tdb")
    ser={e:ser_function(db,e) for e in ELEMENTS}; ph=sorted(db.phases)
    for T in TEMPS:
        eq=equilibrium(db,["FE","ND","B","VA"],ph,{v.X("ND"):X_TARGET["ND"],v.X("B"):X_TARGET["B"],v.T:T,v.P:101325,v.N:1},calc_opts={"pdens":500})
        thr=(float(eq.GM.squeeze().values)-g_ser_at(db,ser,T,X_TARGET))/1000
        fr={}
        for n,f in zip(np.array(eq.Phase.squeeze().values).ravel(),np.array(eq.NP.squeeze().values).ravel()):
            if str(n)!="" and not np.isnan(f) and f>0.005: fr[str(n)]=round(fr.get(str(n),0)+float(f),4)
        b=float(r[f"threshold_at_{T}K"]); maxdiff=max(maxdiff,abs(thr-b))
        w.writerow([c,T,round(thr,4),b,round(thr-b,4),fr.get("LIQUID",0.0),json.dumps(fr)])
    out.flush(); print(i+1,len(rows),c,"maxdiff so far",round(maxdiff,4),flush=True)
print("DONE max |diff| vs batch CSV =",maxdiff)
