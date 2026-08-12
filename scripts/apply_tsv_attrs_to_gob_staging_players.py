"""
Read teams/all_players_with_team_names.txt and update gob-staging universal
players collection: set attributes (SC..FT), anchor_* for those 12, and
recomputed position_ratings. Matches players by first_name, last_name, team.
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

# Column indices (no player_type column)
IDX = {
    "first_name": 0, "last_name": 1, "year": 2, "jersey": 3,
    "height": 4, "weight": 5,
    "SC": 6, "SH": 7, "ID": 8, "OD": 9, "PS": 10, "BH": 11,
    "RB": 12, "ST": 13, "AG": 14, "ND": 15, "IQ": 16, "FT": 17,
    "team": 18,
}
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
        if len(row) <= IDX["team"]:
            continue
        first = row[IDX["first_name"]].strip()
        last = row[IDX["last_name"]].strip()
        team = row[IDX["team"]].strip()
        if not first or not last or not team:
            continue
        attrs = {k: _int(row[IDX[k]], 0) for k in ATTR_KEYS}
        height = _int(row[IDX["height"]], 75)
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

    if ops and args.apply:
        result = players_coll.bulk_write(ops, ordered=False)
        updated = result.modified_count
    else:
        updated = len(ops) if not args.apply else 0
    print(f"[{DB_NAME}] {'Updated' if args.apply else 'Would update'} {updated} players. {len(ops)} rows from TSV.")
    connection.close()


if __name__ == "__main__":
    main()
