from vsm_adapter import load_vsm_as_base_object

mh = load_vsm_as_base_object("VSM_MH_50mg.dat")
fig, ax = mh.plot()