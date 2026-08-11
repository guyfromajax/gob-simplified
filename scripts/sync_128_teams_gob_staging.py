"""
Sync 128 teams from teams/128_teams.txt into gob-staging universal teams collection.
- Existing teams: only add/update region, conference, prestige (do not overwrite other fields).
- New teams: insert full doc (name, mascot, team_id, colors, region, conference, prestige, player_ids: [], all team attrs 0).
Run from repo root: python3 scripts/sync_128_teams_gob_staging.py
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_root = str(ROOT)
sys.path.insert(0, _root)
from scripts.db_migration_cli import connect_migration_target

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(TEAMS_FILE):
        print(f"❌ File not found: {TEAMS_FILE}")
        sys.exit(1)

    connection = connect_migration_target(DB_NAME, write=args.apply)
    teams = connection.database["teams"]
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
            if args.apply:
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
            if args.apply:
                teams.insert_one(doc)
            inserted += 1

    print(f"[{DB_NAME}] Updated {updated} existing team(s) (region, conference, prestige only).")
    print(f"[{DB_NAME}] Inserted {inserted} new team(s).")
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
