"""
Load players from teams/all_players_with_team_names.txt into gob-staging universal players collection.
Uses last column as team name; ignores player_type. Backfills team player_ids.

DESTRUCTIVE: --replace deletes ALL players in gob-staging.players and resets ALL
team player_ids to []. You must also pass --yes to confirm.
  python3 scripts/load_players_from_tsv_gob_staging.py              # append from TSV (no delete)
  python3 scripts/load_players_from_tsv_gob_staging.py --replace --yes   # wipe + reload (requires --yes)
Run from repo root.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_root = str(ROOT)
sys.path.insert(0, _root)
from BackEnd.utils.position_ratings import compute_position_ratings
from bson import ObjectId
from scripts.db_migration_cli import connect_migration_target

DB_NAME = "gob-staging"
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
GENERIC_HEADSHOT = "/static/images/players/generic_headshot.png"

# Column indices (no player_type column)
IDX = {
    "first_name": 0,
    "last_name": 1,
    "year": 2,
    "jersey": 3,
    "height": 4,
    "weight": 5,
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
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(TSV_PATH):
        print(f"❌ File not found: {TSV_PATH}")
        sys.exit(1)

    replace = args.replace
    connection = connect_migration_target(DB_NAME, write=args.apply)
    players_coll = connection.database["players"]
    teams_coll = connection.database["teams"]

    if replace:
        current = players_coll.count_documents({})
        print(f"⚠️  {'DESTRUCTIVE: deleting' if args.apply else 'DRY RUN: would delete'} all {current} player(s).")
        deleted = players_coll.delete_many({}).deleted_count if args.apply else current
        print(f"[{DB_NAME}] {'Cleared' if args.apply else 'Would clear'} {deleted} existing player(s).")
        # Reset team player_ids so backfill doesn't append to stale refs
        if args.apply:
            teams_coll.update_many({}, {"$set": {"player_ids": []}})
        print(f"[{DB_NAME}] Reset all team player_ids to [].")

    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]

    if not lines or not lines[0].strip():
        print("❌ Empty file.")
        sys.exit(1)

    # Skip header
    data_lines = []
    for line in lines[1:]:
        if not line.strip():
            continue
        data_lines.append(line.split("\t"))

    # Prefetch team name -> _id for team_id and backfill
    team_docs = list(teams_coll.find({}, {"_id": 1, "name": 1}))
    name_to_id = {d["name"]: d["_id"] for d in team_docs}
    team_player_ids = {str(t["_id"]): [] for t in team_docs}

    docs = []
    for row in data_lines:
        if len(row) <= IDX["team"]:
            continue
        team_name = row[IDX["team"]].strip()
        if not team_name:
            continue

        attrs = {k: _int(row[IDX[k]], 0) for k in ATTR_KEYS}
        attributes = dict(attrs)
        for k in ATTR_KEYS:
            attributes[f"anchor_{k}"] = attrs[k]
        attributes["EM"] = 0
        attributes["MO"] = 0
        attributes["CH"] = 0
        attributes["anchor_EM"] = 0
        attributes["anchor_MO"] = 0
        attributes["anchor_CH"] = 0
        attributes["NG"] = 1.0
        attributes["anchor_NG"] = 1.0

        height = _int(row[IDX["height"]], 75)
        player_for_ratings = {"height": height, "attributes": attributes}
        position_ratings = compute_position_ratings(player_for_ratings)

        team_oid = name_to_id.get(team_name)

        doc = {
            "first_name": row[IDX["first_name"]].strip(),
            "last_name": row[IDX["last_name"]].strip(),
            "team": team_name,
            "jersey": _int(row[IDX["jersey"]]),
            "year": row[IDX["year"]].strip(),
            "height": height,
            "weight": _int(row[IDX["weight"]], 200),
            "attributes": attributes,
            "position_ratings": position_ratings,
            "photo": GENERIC_HEADSHOT,
        }
        if team_oid:
            doc["team_id"] = team_oid
        docs.append((doc, team_oid))

    # Batch insert (ordered=False for speed)
    if not docs:
        print("No valid rows.")
        sys.exit(0)
    player_docs_only = [d[0] for d in docs]
    result = players_coll.insert_many(player_docs_only, ordered=False) if args.apply else None
    inserted_ids = result.inserted_ids if result else [d[0].get("_id") for d in docs]
    inserted = len(player_docs_only)

    for i, pid in enumerate(inserted_ids):
        _, team_oid = docs[i]
        if team_oid:
            team_key = str(team_oid)
            if team_key not in team_player_ids:
                team_player_ids[team_key] = []
            team_player_ids[team_key].append(pid)

    # Backfill team player_ids (append new IDs to existing)
    for team_oid_str, pids in team_player_ids.items():
        if not pids:
            continue
        if args.apply:
            teams_coll.update_one(
                {"_id": ObjectId(team_oid_str)},
                {"$push": {"player_ids": {"$each": pids}}},
            )

    print(f"[{DB_NAME}] Inserted {inserted} players and updated team player_ids.")
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
