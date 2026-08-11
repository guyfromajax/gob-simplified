"""
Re-populate gob-staging universal teams collection from teams/128_teams.txt.
Deletes all existing team docs and inserts 128 with: name, mascot, team_id,
primary_color, secondary_color, region, conference, prestige, player_ids, and
zeroed team attributes (for Single/Tournament/Franchise init).

TSV columns: id, team, mascot, team_id, primary_color, secondary_color, conference, region, prestige
Region is letter (A–H). Run from repo root: python3 scripts/repopulate_teams_gob_staging.py
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(TEAMS_FILE):
        print(f"❌ File not found: {TEAMS_FILE}")
        sys.exit(1)

    connection = connect_migration_target(DB_NAME, write=args.apply)
    teams_coll = connection.database["teams"]
    with open(TEAMS_FILE) as f:
        lines = f.readlines()

    rows = []
    for line in lines[1:]:
        row = parse_row(line)
        if row:
            rows.append(row)

    if len(rows) != 128:
        print(f"⚠️ Expected 128 rows, got {len(rows)}. Proceeding anyway.")

    existing_count = teams_coll.count_documents({})
    deleted = teams_coll.delete_many({}).deleted_count if args.apply else existing_count
    print(f"[{DB_NAME}] {'Deleted' if args.apply else 'Would delete'} {deleted} existing team(s).")

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

    if docs and args.apply:
        teams_coll.insert_many(docs)
    print(f"[{DB_NAME}] {'Inserted' if args.apply else 'Would insert'} {len(docs)} team(s).")
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
