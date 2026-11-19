# Cr–Fe–Ni Pilot-M — freeze record (Thu 19 Nov 2026)

Frozen before any Cr–Fe–Ni computation. Nothing was merged, edge-checked or equilibrated for Cr–Fe–Ni at any point before this record (only file-level text/header reading and audit v2 flags; the unary pre-check was run at text level).

| File | sha256 |
|---|---|
| CrFeNi_PilotM_PreReg_FROZEN_20261119.md | f05dba8e2d73b390a30914c638a24422d939c942575e83eafead05ea68c58e79 |
| crfeni_defs.py | af1a5176ea4745067c668d0465a47a60b99336a366b49d22fbb2a31e20a90c18 |
| crfeni_edge_check.py | 3f0e7f6e3d2c7eeebd18ef058fffbc436331d32eb98a43127f4cf57cc2927c37 |
| crfeni_sigma.py | 77bbbbe38f9d6fa683d069c963079e1d4bd7cb70455abd7a330cf932ef9b1f61 |
| crfeni_gate.py | e35f565bb06657db75db68e5f1977f302b3aa2e670ce83816f40f391d34a6149 |
| crfeni_analysis.py | 0cfd09bca65b9f27dcd59f81cd3eec7e1c264c860dad8b61385f2bbdc2136b28 |
| tdb_merge.py (Track A, unchanged) | 1ef3f1eeaa320be7800eb541ff72bc469ca3906944ceaa7ffe404f1f003418cb |

The five scripts are byte-identical to those delivered on 18 Nov (zip `crfeni_scripts_20261118.zip`). Only the note changed (status line, G2 confirmation, consistency-check sentence; no number, file set or script).

Run condition: the user compares the hashes on the machine that runs (`sha256sum`), then runs steps 1–4 of `README_crfeni_run.md` in order, pycalphad 0.11.2 / numpy 2.5.3, once. Any non-zero exit is a failed run (fault rule), not a result.
Outcome (to be filled after the run): —
