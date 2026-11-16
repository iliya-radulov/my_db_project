#!/usr/bin/env python3
"""wp4b_test.py - frozen-protocol test. Spearman rho(D, dark-phase area) over 15 conditions (mean of field A/B, k=4), permutation p (1e5, seed 20261116, one-sided rho<0),
sensitivity without (x=1.8,1200C), secondary set 141209, band sign counts if D_band.csv exists. Dark-phase data: Track_B_Anneal_Microstructure_Pilot_20261113 section 3."""
import csv,sys,numpy as np
from scipy.stats import spearmanr,rankdata
DARK={(1.2,1050):(23.6,23.4),(1.2,1150):(15.8,18.0),(1.2,1200):(14.3,15.1),(1.4,1050):(14.9,18.0),(1.4,1150):(0.15,0.16),(1.4,1200):(6.7,7.6),
 (1.6,1050):(0.5,0.2),(1.6,1150):(10.0,11.1),(1.6,1200):(1.7,2.0),(1.8,1050):(1.6,2.6),(1.8,1150):(0.2,0.05),(1.8,1200):(10.1,6.5),
 (2.0,1050):(7.8,8.9),(2.0,1150):(6.1,6.8),(2.0,1200):(12.8,14.2)}
SEC={1.2:5.2,1.4:0.22,1.6:0.00,1.8:0.04,2.0:6.6}; FLAG=(1.8,1200)
def rho_p(d,y,rng=np.random.default_rng(20261116),n=100000):
    r=spearmanr(d,y)[0]; ry=rankdata(y); rd=rankdata(d); cnt=0
    for _ in range(n): cnt+= np.corrcoef(rd,rng.permutation(ry))[0,1] <= r+1e-12
    return r,(cnt+1)/(n+1)
def load(f): 
    return {(float(r['x']),int(r['T_C'])):float(r['D_J_per_mol_atom']) for r in csv.DictReader(open(f)) if r['D_J_per_mol_atom']}
def verdict(r,p=None,band=None):
    if r<=-0.5 and (p is None or p<=0.05) and (band is None or band>=16): return 'PASS'
    if r>=-0.3: return 'FAIL'
    return 'INCONCLUSIVE'
if __name__=='__main__':
    D=load('D_self.csv'); keys=sorted(DARK); d=np.array([D[k] for k in keys]); y=np.array([np.mean(DARK[k]) for k in keys])
    print('gate: D peak-to-peak',round(np.ptp(d)/1000,3),'kJ/mol-atom (>0.05 needed)')
    r,p=rho_p(d,y); print(f'PRIMARY n=15 rho={r:.3f} p={p:.4f}')
    k2=[k for k in keys if k!=FLAG]; r2,p2=rho_p(np.array([D[k] for k in k2]),np.array([np.mean(DARK[k]) for k in k2])); print(f'SENS no (1.8,1200) n=14 rho={r2:.3f} p={p2:.4f}')
    for T in (1050,1150,1200): kk=[k for k in keys if k[1]==T]; print(f' within T={T}: rho={spearmanr([D[k] for k in kk],[np.mean(DARK[k]) for k in kk])[0]:.2f}')
    for x in (1.2,1.4,1.6,1.8,2.0): kk=[k for k in keys if k[0]==x]; print(f' within x={x}: rho={spearmanr([D[k] for k in kk],[np.mean(DARK[k]) for k in kk])[0]:.2f}')
    xs=sorted(SEC); print('SECONDARY 141209 (1150C, n=5) rho=',round(spearmanr([D[(x,1150)] for x in xs],[SEC[x] for x in xs])[0],2))
    band=None
    try:
        import collections; B=collections.defaultdict(dict)
        for r_ in csv.DictReader(open('D_band.csv')):
            if r_['D_J_per_mol_atom']: B[r_['tdb']][(float(r_['x']),int(r_['T_C']))]=float(r_['D_J_per_mol_atom'])
        rs={t:spearmanr([b[k] for k in keys],y)[0] for t,b in B.items() if all(k in b for k in keys)}
        band=sum(v_<0 for v_ in rs.values()); print(f'BAND combos complete {len(rs)}; negative sign in {band}; rho range {min(rs.values()):.2f}..{max(rs.values()):.2f}; median {np.median(list(rs.values())):.2f}')
        for t,v_ in sorted(rs.items(),key=lambda a:a[1]): print('  ',t,round(v_,2))
    except FileNotFoundError: print('band not available yet')
    print('VERDICT (primary + p + band):',verdict(r,p,band if band is not None else None),' primary-only:',verdict(r))
