"""
One-off: Update IDA Academy -> IDA (name and team_id) in gob-staging teams collection.
Run from repo root: python3 scripts/fix_ida_team_gob_staging.py
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

from BackEnd.db import client

if __name__ == "__main__":
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)
    teams = client["gob-staging"]["teams"]
    r = teams.update_one(
        {"name": "IDA Academy"},
        {"$set": {"name": "IDA", "team_id": "IDA"}},
    )
    if r.matched_count:
        print("✅ [gob-staging] Updated team: IDA Academy → IDA (name and team_id)")
    else:
        print("ℹ️  [gob-staging] No document with name 'IDA Academy' found (may already be IDA)")
