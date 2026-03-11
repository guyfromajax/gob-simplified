"""
Backfill player_ids on each document in gob-staging.teams using the current
gob-staging.players collection. Each player doc has team_id (ObjectId); we
group players by team_id and set each team's player_ids to that list.

Safe to run multiple times. Does not insert or delete any players.
Run from repo root: python3 scripts/backfill_team_player_ids_gob_staging.py
"""
import os
import sys
from collections import defaultdict

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

DB_NAME = "gob-staging"


def main():
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)

    players_coll = client[DB_NAME]["players"]
    teams_coll = client[DB_NAME]["teams"]

    # Group player _ids by team_id
    team_id_to_pids = defaultdict(list)
    for p in players_coll.find({}, {"_id": 1, "team_id": 1}):
        tid = p.get("team_id")
        if tid is not None:
            team_id_to_pids[tid].append(p["_id"])

    # Set player_ids on each team
    updated = 0
    for team in teams_coll.find({}, {"_id": 1, "name": 1}):
        tid = team["_id"]
        pids = team_id_to_pids.get(tid, [])
        r = teams_coll.update_one(
            {"_id": tid},
            {"$set": {"player_ids": pids}},
        )
        if r.modified_count:
            updated += 1

    total_teams = teams_coll.count_documents({})
    total_players = players_coll.count_documents({})
    print(f"[{DB_NAME}] Updated player_ids on {updated} team(s) (of {total_teams}).")
    print(f"  Players in DB: {total_players}; teams with roster: {len(team_id_to_pids)}.")
    print("Done.")


if __name__ == "__main__":
    main()
