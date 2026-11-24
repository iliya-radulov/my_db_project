import warnings; warnings.filterwarnings('ignore')
from pycalphad import Database
def with_ordering(merged_path, ohn_path='FeSi-12Ohn_pycalphad_VA3.tdb', out=None):
    m=Database(merged_path); o=Database(ohn_path)
    names=['A2_BCC','B2_BCC','BCC_4SL']
    for p in names: m.phases[p]=o.phases[p]
    from tinydb import where
    for par in o._parameters.search(where('phase_name').one_of(names)): m._parameters.insert(dict(par))
    for k,val in o.symbols.items():
        if k not in m.symbols: m.symbols[k]=val
    if out: m.to_file(out,fmt='tdb',if_incompatible='fix') if False else open(out,'w').write(m.to_string(fmt='tdb'))
    return m
if __name__=='__main__':
    m=with_ordering('merged_12Ohn.tdb',out='merged_12Ohn_ordered.tdb'); print(sorted(m.phases))
