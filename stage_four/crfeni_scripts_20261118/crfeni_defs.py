"""
crfeni_defs.py (18 Nov 2026) - the fixed definitions of Cr-Fe-Ni Pilot-M in one place:
classes, lineages, gate numbers and decision rules, exactly as in the pre-registration
(claude/CrFeNi_PilotM_PreReg_DRAFT_20261118.md, section 3-4). Imported by crfeni_gate.py and
crfeni_analysis.py. Changing a number here after the freeze makes the run a different, unfrozen one.
"""
# sigma sublattice-convention classes of the six Cr-Fe files (pre-registration section 3)
CLASS = {"CrFe-82Her": "A", "CrFe-87And-LB": "A",
         "CrFe-21Laf": "B",
         "CrFe-18Jac": "C", "CrFe-20Ost": "C", "CrFe-23Zha": "C"}
CLASSES = ("A", "B", "C")

# lineages (header rule; judgement from file headers, not parameter comparison)
LINEAGE = {
    "CrFe": {"CrFe-82Her": "Her82", "CrFe-87And-LB": "And87", "CrFe-21Laf": "Laf21",
             "CrFe-18Jac": "Jac18", "CrFe-20Ost": "Jac18", "CrFe-23Zha": "Zha23"},
    "CrNi": {"CrNi-06Hal": "Hal06", "CrNi-16Tan": "Tan16", "CrNi-86Din": "Din86",
             "CrNi-92Lee-LB": "Lee92"},
    "FeNi": {"FeNi-95Ans": "Ans95", "FeNi-00Ans-2SL": "Ans00", "FeNi-00Ans-4SL": "Ans00",
             "FeNi-03Dup-LB": "Dup03", "FeNi-03Dup-mod": "Dup03",
             "FeNi-85Xin": "Xin85", "FeNi-23Jac": "Xin85",
             "FeNi-10Cac": "Cac10", "FeNi-23Wit": "Cac10", "FeNi-23Zha": "Cac10",
             "FeNi-11Xio": "Xio11", "FeNi-19Ohn": "Ohn19"},
}
EDGES = ("CrFe", "CrNi", "FeNi")
N_COMBINATIONS = 6 * 4 * 12            # 288 raw combinations

# gate (applied once, before any class analysis)
G1_MIN = 60                            # survivors of edge-check rule v2, of 288
G2_MIN_SURVIVORS_PER_FILE = 5          # each class needs >= 1 Cr-Fe file with >= 5 survivors
G3_S_MIN = 0.05                        # kJ/mol-atom: S above the solver noise floor
G3_FRACTION = 0.8                      # of the survivors with a valid S
VALID_FRACTION = 0.8                   # run validity: survivors with a valid S at the primary T

# decision rule for the class effect
NOISE_FLOOR = 0.05                     # N_eff = max(N, NOISE_FLOOR), kJ/mol-atom
MATTERS_FACTOR = 2.0                   # C >= 2 * N_eff -> "convention matters"
# C <= N_eff -> "does not matter"; otherwise "inconclusive"

PRIMARY_T = 900.0
SENSITIVITY_T = (800.0, 1000.0)
