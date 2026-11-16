import csv, sys, numpy as np
from collections import defaultdict
P=sys.argv[1]
T=["800K","1000K","1300K","1375K","1450K","1600K"]
E=["binary_FeNd","binary_FeB","binary_NdB"]
R=[r for r in csv.DictReader(open(P)) if r["survived"]=="True"]
print("survivors",len(R))
Y=np.array([[float(r[f"threshold_at_{t}"]) for t in T] for r in R])
L=[[r[e] for r in R] for e in E]
for e,l in zip(E,L):
    c=defaultdict(int)
    for x in l:c[x]+=1
    print(e,dict(c))
w=np.ones(len(R))
for it in range(500):
    for l in L:
        s=defaultdict(float)
        for x,wi in zip(l,w):s[x]+=wi
        k=len(s);tot=w.sum()
        w=np.array([wi*(tot/k)/s[x] for x,wi in zip(l,w)])
w/=w.sum()
for e,l in zip(E,L):
    s=defaultdict(float)
    for x,wi in zip(l,w):s[x]+=wi
    print("marginal",e,{k:round(v,3) for k,v in s.items()})
def wq(y,w,q):
    i=np.argsort(y);c=np.cumsum(w[i]);return y[i][np.searchsorted(c,q)]
print(f"{'T':>6} {'S0 med':>8} {'S1 med':>8} {'shift':>7} | {'S0 5-95':>16} {'S1 5-95':>16}")
u=np.ones(len(R))/len(R);mx=0
for j,t in enumerate(T):
    m0,m1=wq(Y[:,j],u,.5),wq(Y[:,j],w,.5);mx=max(mx,abs(m1-m0))
    print(f"{t:>6} {m0:8.3f} {m1:8.3f} {m1-m0:+7.3f} | {wq(Y[:,j],u,.05):7.3f}..{wq(Y[:,j],u,.95):7.3f} {wq(Y[:,j],w,.05):7.3f}..{wq(Y[:,j],w,.95):7.3f}")
print("max |median shift| =",round(mx,3),"-> ", "NOT material (<0.15)" if mx<0.15 else "MATERIAL (>=0.15)")
print("effective N (Kish): S1 =",round(1/(w**2).sum(),1),"of",len(R))
