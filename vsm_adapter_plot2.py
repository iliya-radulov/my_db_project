from vsm_adapter2 import MHmajorFromParsed
from parse_vsm_final2 import parse_vsm_file

parsed = parse_vsm_file("VSM_MH_50mg.dat")
obj = MHmajorFromParsed(parsed)
fig, ax = obj.plot()