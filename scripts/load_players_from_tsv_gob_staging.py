"""
Load players from teams/all_players_with_team_names.txt into gob-staging universal players collection.
Uses last column as team name; ignores player_type. Backfills team player_ids.
Run from repo root: python3 scripts/load_players_from_tsv_gob_staging.py
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
from BackEnd.utils.position_ratings import compute_position_ratings
from bson import ObjectId

DB_NAME = "gob-staging"
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
GENERIC_HEADSHOT = "/static/images/players/generic_headshot.png"

# Column indices (skip player_type at 4 for DB)
IDX = {
    "first_name": 0,
    "last_name": 1,
    "year": 2,
    "jersey": 3,
    "height": 5,
    "weight": 6,
    "SC": 7, "SH": 8, "ID": 9, "OD": 10, "PS": 11, "BH": 12,
    "RB": 13, "ST": 14, "AG": 15, "ND": 16, "IQ": 17, "FT": 18,
    "team": 19,
}
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]


def _int(s, default=0):
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def main():
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)
    if not os.path.exists(TSV_PATH):
        print(f"❌ File not found: {TSV_PATH}")
        sys.exit(1)

    players_coll = client[DB_NAME]["players"]
    teams_coll = client[DB_NAME]["teams"]

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
    result = players_coll.insert_many(player_docs_only, ordered=False)
    inserted = len(result.inserted_ids)

    for i, pid in enumerate(result.inserted_ids):
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
        teams_coll.update_one(
            {"_id": ObjectId(team_oid_str)},
            {"$push": {"player_ids": {"$each": pids}}},
        )

    print(f"[{DB_NAME}] Inserted {inserted} players and updated team player_ids.")
    print("Done.")


if __name__ == "__main__":
    main()
