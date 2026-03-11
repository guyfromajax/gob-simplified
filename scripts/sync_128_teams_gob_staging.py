"""
Sync 128 teams from teams/128_teams.txt into gob-staging universal teams collection.
- Existing teams: only add/update region, conference, prestige (do not overwrite other fields).
- New teams: insert full doc (name, mascot, team_id, colors, region, conference, prestige, player_ids: [], all team attrs 0).
Run from repo root: python3 scripts/sync_128_teams_gob_staging.py
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

TEAM_ATTR_KEYS = [
    "shot_threshold", "discipline", "fight", "rebound_modifier",
    "momentum_score", "offensive_efficiency", "team_chemistry", "defensive_efficiency",
    "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier",
]
TEAM_ATTRS_ZERO = {k: 0 for k in TEAM_ATTR_KEYS}

DB_NAME = "gob-staging"
TEAMS_FILE = os.path.join(_root, "teams", "128_teams.txt")


def parse_row(line):
    parts = line.strip().split("\t")
    if len(parts) < 9:
        return None
    try:
        return {
            "id": int(parts[0]),
            "school": parts[1].strip(),
            "mascot": parts[2].strip(),
            "team_id": parts[3].strip(),
            "primary_color": parts[4].strip(),
            "secondary_color": parts[5].strip(),
            "conference": int(parts[6]),
            "region": int(parts[7]),
            "prestige": int(parts[8]),
        }
    except (ValueError, IndexError):
        return None


def main():
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)
    if not os.path.exists(TEAMS_FILE):
        print(f"❌ File not found: {TEAMS_FILE}")
        sys.exit(1)

    teams = client[DB_NAME]["teams"]
    with open(TEAMS_FILE) as f:
        lines = f.readlines()

    # Skip header
    rows = []
    for line in lines[1:]:
        row = parse_row(line)
        if row:
            rows.append(row)

    updated = 0
    inserted = 0
    for row in rows:
        existing = teams.find_one({"$or": [{"team_id": row["team_id"]}, {"name": row["school"]}]})
        if existing:
            teams.update_one(
                {"_id": existing["_id"]},
                {"$set": {"region": row["region"], "conference": row["conference"], "prestige": row["prestige"]}},
            )
            updated += 1
        else:
            doc = {
                "name": row["school"],
                "mascot": row["mascot"],
                "team_id": row["team_id"],
                "primary_color": row["primary_color"],
                "secondary_color": row["secondary_color"],
                "region": row["region"],
                "conference": row["conference"],
                "prestige": row["prestige"],
                "player_ids": [],
                **TEAM_ATTRS_ZERO,
            }
            teams.insert_one(doc)
            inserted += 1

    print(f"[{DB_NAME}] Updated {updated} existing team(s) (region, conference, prestige only).")
    print(f"[{DB_NAME}] Inserted {inserted} new team(s).")
    print("Done.")


if __name__ == "__main__":
    main()
