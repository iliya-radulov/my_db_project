import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE5 = HERE.parent
for p in (STAGE5, STAGE5.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
