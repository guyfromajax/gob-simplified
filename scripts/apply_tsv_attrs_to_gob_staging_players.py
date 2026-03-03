"""
Read teams/all_players_with_team_names.txt and update gob-staging universal
players collection: set attributes (SC..FT), anchor_* for those 12, and
recomputed position_ratings. Matches players by first_name, last_name, team.
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

DB_NAME = "gob-staging"
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

IDX = {
    "first_name": 0, "last_name": 1, "year": 2, "jersey": 3,
    "height": 5, "weight": 6,
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

    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]

    if not lines or len(lines) < 2:
        print("❌ No data rows.")
        sys.exit(1)

    updated = 0
    not_found = 0
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

        result = players_coll.update_one(
            {"first_name": first, "last_name": last, "team": team},
            {"$set": set_doc},
        )
        if result.matched_count:
            updated += 1
        else:
            not_found += 1

    print(f"[{DB_NAME}] Updated {updated} players. No match for {not_found} rows.")


if __name__ == "__main__":
    main()
