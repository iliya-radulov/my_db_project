#!/usr/bin/env python3
"""tau36_rerun.py (16 Nov 2026) - re-test of the Feng tau3-tau6 reconstruction with the CORRECTED Table-5 signs.
Base: LaFeSi_feng2023.tdb (self-contained: Table-5 liquid/bcc/fcc/Fe-Si/La-Si(Fe) compounds + tau1/tau2; no B2/D03, no tau3-6).
Added: tau3-tau6 blocks (La)x(Fe,Si)y(Fe,Si)z with the Table-5 endmembers under three readings of the missing reference:
  A  printed value only (no GHSER)
  B  printed per FORMULA + x*GLa + y*Gi + z*Gj
  E  printed per ATOM: (x+y+z)*printed + x*GLa + y*Gi + z*Gj   (Feng: energies per mole of atoms)
Signs: OLD = the earlier wrong transcription (tau4 La:Fe:Fe -10001, tau5 La:Fe:Si -48500, tau6 L +65006.5); NEW = as printed.
Benchmark: Feng Table 6 (21 alloys, 1373 K): phase sets of experiment and of Feng's own calculation."""
import warnings,sys,csv,re,itertools,numpy as np;warnings.filterwarnings("ignore")
from pycalphad import Database,equilibrium,variables as v
BASE='/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/tdb_build/LaFeSi_feng2023.tdb'
T6='/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/data_feng2023/table6_comparison.csv'
T4='/home/claude/iliya-radulov/my_db_project/stage_four/calphad_lafesi/data_feng2023/table4_epma.csv'
SITES={'TAU3':(1,2,2),'TAU4':(1,1,2),'TAU5':(1,1,1),'TAU6':(1,2,2)}      # tau6 = guess (not in Table 4)
def endm(sign):   # corrected = as printed
    s4=10001 if sign=='NEW' else -10001; s5=48500 if sign=='NEW' else -48500; l6=-65006.5 if sign=='NEW' else 65006.5
    return {
 'TAU3':({'FE:SI':'-55000-11.2*T','SI:FE':'-43004.3-10*T','FE:FE':'10001+8.0032*T','SI:SI':'45000-9*T'},'-136160.007+5*T'),
 'TAU4':({'FE:SI':'-53021.2027-16*T','SI:FE':'-32022.4058-10.01*T','FE:FE':f'{s4:+d}-5.002*T','SI:SI':'-40016.0024-8.0032*T'},'-171189.014+10*T'),
 'TAU5':({'FE:SI':f'{s5:+d}-13.6*T','SI:FE':'-20002-5.005*T','FE:FE':'15000+15*T','SI:SI':'8000.800-17.50175*T'},'-13000+5*T'),
 'TAU6':({'FE:SI':'-67855-11*T','SI:FE':'20004+10*T','FE:FE':'20008.012-15*T','SI:SI':'-49009-20*T'},f'{l6:+.1f}+10*T')}
GH={'LA':'GHSERLA#','FE':'GHSERFE#','SI':'GHSERSI#'}
def block(name,hyp,sign):
    x,y,z=SITES[name]; n=x+y+z; ends,L=endm(sign)[name]
    out=[f'PHASE {name} % 3 {x} {y} {z} !',f'CONSTITUENT {name} : LA : FE,SI : FE,SI : !']
    for key,val in ends.items():
        i,j=key.split(':'); ref=f'+{x}*{GH["LA"]}+{y}*{GH[i]}+{z}*{GH[j]}'
        expr={'A':f'+{val}','B':f'+{val}{ref}','E':f'+{n}*({val}){ref}'}[hyp]
        out.append(f' PARAMETER G({name},LA:{i}:{j};0) 298.15 {expr}; 6000 N !')
    Lx=f'+{n}*({L})' if hyp=='E' else f'+{L}'
    for ca in ('LA:FE,SI:FE','LA:FE,SI:SI','LA:FE:FE,SI','LA:SI:FE,SI','LA:FE,SI:FE,SI'):
        out.append(f' PARAMETER L({name},{ca};0) 298.15 {Lx}; 6000 N !')
    return '\n'.join(out)
MAP={'LA5SIFE3':'La5Si3','LA3SIFE2':'La3Si2','LA5SIFE4':'La5Si4','LASIFE':'LaSi','ALASIFE2':'alpha-LaSi2','BLASIFE2':'beta-LaSi2','FE2SI':'Fe2Si','FE5SI3':'Fe5Si3','FESI_B20':'FeSi','BCC_A2':'bcc','FCC_A1':'fcc','LIQUID':'liquid','FESI2_H':'FeSi2','FESI2_L':'FeSi2','DIAMOND_A4':'Si','TAU1':'tau1','TAU2':'tau2','TAU3':'tau3','TAU4':'tau4','TAU5':'tau5','TAU6':'tau6'}
def norm(s): return frozenset('bcc' if p in('alpha-Fe','B2','D03') else p for p in re.split(r'\s*\+\s*',s.strip()))
bench={r['alloy']:(norm(r['experimental']),norm(r['calculated'])) for r in csv.DictReader(open(T6))}
nom={}
for r in csv.DictReader(open(T4)):
    m=re.match(r'La(\d+)Fe(\d+)Si(\d+)',r['nominal']); nom[r['alloy']]=tuple(int(g)/100 for g in m.groups())
def run(hyp,sign,withtau=True):
    txt=open(BASE).read()
    if withtau: txt+='\n'+'\n'.join(block(n,hyp,sign) for n in SITES)
    open('/tmp/tau_test.tdb','w').write(txt); db=Database('/tmp/tau_test.tdb'); ph=list(db.phases)
    res={}
    for a,(xla,xfe,xsi) in nom.items():
        try:
            eq=equilibrium(db,['LA','FE','SI','VA'],ph,{v.X('LA'):xla,v.X('SI'):xsi,v.T:1373,v.P:101325,v.N:1},calc_opts={'pdens':500})
            res[a]=frozenset(MAP.get(str(p),str(p)) for p,n in zip(np.array(eq.Phase).ravel(),np.array(eq.NP).ravel()) if str(p) not in('','nan') and not np.isnan(n) and n>0.01)
        except Exception as e: res[a]=frozenset(['FAIL'])
    return res
def score(res):
    ex=sum(res[a]==bench[a][0] for a in res); fc=sum(res[a]==bench[a][1] for a in res)
    jx=np.mean([len(res[a]&bench[a][0])/len(res[a]|bench[a][0]) for a in res]); jf=np.mean([len(res[a]&bench[a][1])/len(res[a]|bench[a][1]) for a in res])
    tau=lambda s:{p for p in s if p in('tau3','tau4','tau5','tau6')}
    t_ex=sum(1 for a in res if tau(bench[a][0]) and tau(bench[a][0])<=res[a]); n_ex=sum(1 for a in res if tau(bench[a][0]))
    return ex,fc,jx,jf,t_ex,n_ex
if __name__=='__main__':
    out={}
    for label,hyp,sign,wt in (('no tau3-6','-','NEW',False),)+tuple((f'{h} {s}',h,s,True) for s in('OLD','NEW') for h in('A','B','E')):
        res=run(hyp,sign,wt); out[label]=res; ex,fc,jx,jf,t,n=score(res)
        print(f'{label:10s} exact vs experiment {ex:2d}/21  exact vs Feng-calc {fc:2d}/21  Jaccard exp {jx:.2f} calc {jf:.2f}  tau3-6 found where reported {t}/{n}',flush=True)
    import json; json.dump({k:{a:sorted(v_) for a,v_ in r.items()} for k,r in out.items()},open('/home/claude/tau36_rerun.json','w'))
