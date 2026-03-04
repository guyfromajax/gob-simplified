"""
Update only Conference 1 (8 teams, 96 players) in gob-staging.players with the 12
attribute values from teams/all_players_with_team_names.txt.
Sets attributes.SC .. FT, attributes.anchor_SC .. anchor_FT, and position_ratings.
Matches by first_name, last_name, team. Requires --yes.
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
from pymongo import UpdateOne

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
    if "--yes" not in sys.argv:
        print("Updates gob-staging.players (Conference 1 only) from TSV. Requires --yes.")
        sys.exit(1)
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
    result = players_coll.bulk_write(ops, ordered=False)
    print(f"[{DB_NAME}] Updated {result.modified_count} Conference 1 players (12 attrs + anchor_* + position_ratings).")
    print(f"  Matched {result.matched_count} of {len(ops)} TSV rows.")


if __name__ == "__main__":
    main()
