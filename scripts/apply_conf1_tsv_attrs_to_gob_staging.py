"""
Update only Conference 1 (8 teams, 96 players) in gob-staging.players with the 12
attribute values from teams/all_players_with_team_names.txt.
Sets attributes.SC .. FT, attributes.anchor_SC .. anchor_FT, and position_ratings.
Matches by first_name, last_name, team. Requires --yes.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_root = str(ROOT)
sys.path.insert(0, _root)
from BackEnd.utils.position_ratings import compute_position_ratings
from pymongo import UpdateOne
from scripts.db_migration_cli import connect_migration_target

DB_NAME = "gob-staging"
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

CONFERENCE_1 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}

# TSV: 0=first_name, 1=last_name, 2=year, 3=jersey, 4=height, 5=weight, 6-17=attrs, 18=team
IDX_FIRST, IDX_LAST = 0, 1
IDX_HEIGHT, IDX_WEIGHT = 4, 5
ATTR_START, ATTR_END = 6, 18
IDX_TEAM = 18
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]


def _int(s, default=0):
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(TSV_PATH):
        print(f"❌ File not found: {TSV_PATH}")
        sys.exit(1)

    connection = connect_migration_target(DB_NAME, write=args.apply)
    players_coll = connection.database["players"]

    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]

    if not lines or len(lines) < 2:
        print("❌ No data rows.")
        sys.exit(1)

    ops = []
    for line in lines[1:]:
        if not line.strip():
            continue
        row = line.split("\t")
        if len(row) <= IDX_TEAM:
            continue
        team = row[IDX_TEAM].strip()
        if team not in CONFERENCE_1:
            continue
        first = row[IDX_FIRST].strip()
        last = row[IDX_LAST].strip()
        if not first or not last or not team:
            continue
        attrs = {}
        for i, k in enumerate(ATTR_KEYS):
            attrs[k] = _int(row[ATTR_START + i], 0)
        height = _int(row[IDX_HEIGHT], 75)
        player_for_ratings = {"height": height, "attributes": dict(attrs)}
        position_ratings = compute_position_ratings(player_for_ratings)

        set_doc = {"position_ratings": position_ratings}
        for k in ATTR_KEYS:
            set_doc[f"attributes.{k}"] = attrs[k]
            set_doc[f"attributes.anchor_{k}"] = attrs[k]

        ops.append(UpdateOne(
            {"first_name": first, "last_name": last, "team": team},
            {"$set": set_doc},
        ))

    if not ops:
        print("No Conference 1 rows to update.")
        return
    result = players_coll.bulk_write(ops, ordered=False) if args.apply else None
    count = result.modified_count if result else len(ops)
    print(f"[{DB_NAME}] {'Updated' if args.apply else 'Would update'} {count} Conference 1 players.")
    connection.close()


if __name__ == "__main__":
    main()
