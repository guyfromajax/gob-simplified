#!/usr/bin/env python3
"""Load team JSON files into one explicit database target.

Dry-run is the default. Existing teams are skipped exactly as before.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.models.player import Player
from scripts.db_migration_cli import connect_migration_target


def load_teams(database, teams_dir: Path, *, apply: bool) -> tuple[int, int]:
    players_collection = database["players"]
    teams_collection = database["teams"]
    teams_added = 0
    players_added = 0

    for path in sorted(teams_dir.glob("*.json")):
        team_data = json.loads(path.read_text(encoding="utf-8"))
        team_name = team_data["name"]
        if teams_collection.find_one({"name": team_name}, {"_id": 1}):
            print(f"SKIP {team_name!r}: already exists")
            continue

        player_docs = []
        player_ids = []
        for raw_player in team_data["players"]:
            player = Player(raw_player)
            player_id = str(uuid4())
            player_ids.append(player_id)
            player_docs.append({
                "_id": player_id,
                "player_id": player_id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "team": player.team,
                "attributes": player.attributes,
                "stats": player.stats,
                "metadata": player.metadata,
            })

        if apply:
            teams_collection.insert_one({"name": team_name, "player_ids": player_ids})
            if player_docs:
                players_collection.insert_many(player_docs)
        teams_added += 1
        players_added += len(player_docs)
        print(f"{'INSERTED' if apply else 'WOULD INSERT'} {team_name}: {len(player_docs)} players")

    return teams_added, players_added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--teams-dir", type=Path, default=ROOT / "teams")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    teams, players = load_teams(connection.database, args.teams_dir, apply=args.apply)
    connection.close()
    print(f"Done: {teams} teams and {players} players {'written' if args.apply else 'planned'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
