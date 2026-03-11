"""
One-off: update team_id for four teams in gob-staging to match 128_teams.txt.
Run from repo root: python3 scripts/update_team_ids_gob_staging.py
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

# name (exact match in DB) -> new team_id
UPDATES = [
    ("Queen's Guard", "queens_guard"),
    ("Couer d'Alene", "couer_d_alene"),
    ("Pike's Prep", "pikes_prep"),
    ("River's Edge", "rivers_edge"),
]


def main():
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)
    teams = client[DB_NAME]["teams"]
    for name, new_team_id in UPDATES:
        result = teams.update_one({"name": name}, {"$set": {"team_id": new_team_id}})
        if result.modified_count:
            print(f"  Updated {name!r} -> team_id={new_team_id!r}")
        elif result.matched_count:
            print(f"  No change for {name!r} (already {new_team_id!r})")
        else:
            print(f"  ⚠ No team found with name={name!r}")
    print("Done.")


if __name__ == "__main__":
    main()
