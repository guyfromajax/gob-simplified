"""
Re-populate gob-staging universal teams collection from teams/128_teams.txt.
Deletes all existing team docs and inserts 128 with: name, mascot, team_id,
primary_color, secondary_color, region, conference, prestige, player_ids, and
zeroed team attributes (for Single/Tournament/Franchise init).

TSV columns: id, team, mascot, team_id, primary_color, secondary_color, conference, region, prestige
Region is letter (A–H). Run from repo root: python3 scripts/repopulate_teams_gob_staging.py
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
            "name": parts[1].strip(),
            "mascot": parts[2].strip(),
            "team_id": parts[3].strip(),
            "primary_color": parts[4].strip(),
            "secondary_color": parts[5].strip(),
            "conference": int(parts[6]),
            "region": parts[7].strip(),
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

    teams_coll = client[DB_NAME]["teams"]
    with open(TEAMS_FILE) as f:
        lines = f.readlines()

    rows = []
    for line in lines[1:]:
        row = parse_row(line)
        if row:
            rows.append(row)

    if len(rows) != 128:
        print(f"⚠️ Expected 128 rows, got {len(rows)}. Proceeding anyway.")

    deleted = teams_coll.delete_many({}).deleted_count
    print(f"[{DB_NAME}] Deleted {deleted} existing team(s).")

    docs = []
    for row in rows:
        doc = {
            "name": row["name"],
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
        docs.append(doc)

    if docs:
        teams_coll.insert_many(docs)
    print(f"[{DB_NAME}] Inserted {len(docs)} team(s).")
    print("Done.")


if __name__ == "__main__":
    main()
