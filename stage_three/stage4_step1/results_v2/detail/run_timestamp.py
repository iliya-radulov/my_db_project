import json, glob
from datetime import datetime
t = [datetime.fromisoformat(json.load(open(f))["run_timestamp"]) for f in glob.glob("*.json")]
print(max(t) - min(t))