"""
Backfill player_ids on each document in gob-staging.teams using the current
gob-staging.players collection. Each player doc has team_id (ObjectId); we
group players by team_id and set each team's player_ids to that list.

Safe to run multiple times. Does not insert or delete any players.
Run from repo root: python3 scripts/backfill_team_player_ids_gob_staging.py
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

DB_NAME = "gob-staging"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(DB_NAME, write=args.apply)
    players_coll = connection.database["players"]
    teams_coll = connection.database["teams"]

    # Group player _ids by team_id
    team_id_to_pids = defaultdict(list)
    for p in players_coll.find({}, {"_id": 1, "team_id": 1}):
        tid = p.get("team_id")
        if tid is not None:
            team_id_to_pids[tid].append(p["_id"])

    # Set player_ids on each team
    updated = 0
    for team in teams_coll.find({}, {"_id": 1, "name": 1, "player_ids": 1}):
        tid = team["_id"]
        pids = team_id_to_pids.get(tid, [])
        current = team.get("player_ids") or []
        if args.apply:
            r = teams_coll.update_one({"_id": tid}, {"$set": {"player_ids": pids}})
        if current != pids:
            updated += 1

    total_teams = teams_coll.count_documents({})
    total_players = players_coll.count_documents({})
    print(f"[{DB_NAME}] Updated player_ids on {updated} team(s) (of {total_teams}).")
    print(f"  Players in DB: {total_players}; teams with roster: {len(team_id_to_pids)}.")
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
