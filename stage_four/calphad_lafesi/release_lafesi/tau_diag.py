import warnings;warnings.filterwarnings("ignore")
import numpy as np
from pycalphad import Database,calculate,equilibrium,variables as v
import tau36_rerun as t
for hyp,sign in (('B','OLD'),('B','NEW'),('E','NEW')):
    txt=open(t.BASE).read()+'\n'+'\n'.join(t.block(n,hyp,sign) for n in t.SITES)
    open('/tmp/d.tdb','w').write(txt); db=Database('/tmp/d.tdb')
    print(hyp,sign,'tau phases loaded:',[p for p in db.phases if p.startswith('TAU')])
    # alloy 5 (tau5 expected single phase) and alloy 3 (tau4)
    for a in ('5','3','6'):
        xla,xfe,xsi=t.nom[a]
        eq=equilibrium(db,['LA','FE','SI','VA'],list(db.phases),{v.X('LA'):xla,v.X('SI'):xsi,v.T:1373,v.P:101325,v.N:1},calc_opts={'pdens':500})
        g=float(eq.GM.values.ravel()[0])
        out=[]
        for p in ('TAU3','TAU4','TAU5','TAU6'):
            c=calculate(db,['LA','FE','SI','VA'],p,T=1373,P=101325,N=1,pdens=2000)
            gm=c.GM.values.ravel(); X=c.X.sel(component='LA').values.ravel()
            out.append(f'{p}:Gmin={gm.min()/1000:.1f}kJ@xLa={X[gm.argmin()]:.2f}')
        print(f'  alloy {a} x={t.nom[a]} Geq={g/1000:.1f}  ',' '.join(out))
