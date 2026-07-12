"""
XRD Integration Module
Parses .xy files and stores results in the database
"""

import os
from pathlib import Path
from parsers.parse_xy_v2 import parse_and_analyze_xy, print_xrd_report
from alloy_db import get_db

# ... rest of the file unchanged ...
