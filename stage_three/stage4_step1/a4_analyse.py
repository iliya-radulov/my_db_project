import csv, json, sys, numpy as np
from collections import defaultdict
R=list(csv.DictReader(open(sys.argv[1])))
T=[800,1000,1300,1375,1450,1600]
D=defaultdict(dict)
for r in R: D[r["combo"]][int(r["T_K"])]=(float(r["threshold"]),float(r["liquid_frac"]),json.loads(r["assemblage_json"]))
N=len(D); print("combos",N)
# P1
mx=defaultdict(int); mono=0
for c,d in D.items():
    th=[d[t][0] for t in T]; k=T[int(np.argmax(th))]; mx[k]+=1
    if k in (800,1600): mono+=1
print("P1 argmax T counts:",dict(mx)," | combos with max at an end (monotone-ish):",mono)
# P2
l1300=[D[c][1300][1] for c in D]; l1450=[D[c][1450][1] for c in D]
print("P2 liquid at 1300: min %.3f, n(liq>0.005)=%d/%d"%(min(l1300),sum(x>0.005 for x in l1300),N))
print("   liquid majority (>0.5) at 1450: %d/%d = %.0f%%"%(sum(x>0.5 for x in l1450),N,100*np.mean(np.array(l1450)>0.5)))
# liquid fraction by T
for t in T: print("   liquid frac @%4d K: median %.3f  range %.3f-%.3f"%(t,np.median([D[c][t][1] for c in D]),min(D[c][t][1] for c in D),max(D[c][t][1] for c in D)))
# P3 rank: files with least negative thr at 1300-1450 vs liquid at 1375
def fm(c): return c.split("___")
for t in (1300,1375,1450):
    th=np.array([D[c][t][0] for c in D]); lq=np.array([D[c][t][1] for c in D])
    from scipy.stats import spearmanr
    print("P3/P4 @%d: Spearman(threshold, liquid) = %.2f"%(t,spearmanr(th,lq).correlation))
# which FeB file has lowest/highest liquid at 1375
g=defaultdict(list)
for c in D: g[fm(c)[1]].append(D[c][1375][1])
print("1375 K liquid by FeB file:",{k:round(float(np.mean(v)),3) for k,v in sorted(g.items(),key=lambda a:np.mean(a[1]))})
g=defaultdict(list)
for c in D: g[fm(c)[1]].append(D[c][1375][0])
print("1375 K threshold by FeB file:",{k:round(float(np.mean(v)),2) for k,v in sorted(g.items(),key=lambda a:-np.mean(a[1]))})
# assemblage classes at 1300 and 1450
for t in (1000,1300,1450):
    cl=defaultdict(int)
    for c in D: cl["+".join(sorted(D[c][t][2]))]+=1
    print("assemblages @%d:"%t); [print("  %2d  %s"%(n,k)) for k,n in sorted(cl.items(),key=lambda a:-a[1])[:6]]
