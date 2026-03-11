"""
Add prestige field (integer, 0) to all documents in the universal teams collection in gob-staging.
Run from repo root: python3 scripts/add_prestige_gob_staging.py
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

DB_NAME = "gob-staging"


def main():
    if not client:
        print("❌ MongoDB client not available (MONGO_URI not set or connection failed).")
        return
    teams = client[DB_NAME]["teams"]
    result = teams.update_many({}, {"$set": {"prestige": 0}})
    print(f"[{DB_NAME}] ✅ Set prestige=0 on {result.modified_count} team(s) (matched {result.matched_count})")
    print("Done.")


if __name__ == "__main__":
    main()
