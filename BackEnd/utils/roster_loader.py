import json
from pathlib import Path
from typing import Tuple, List, Dict

from BackEnd.db import players_collection, teams_collection
from pymongo.errors import PyMongoError


def _load_from_db(team_name: str) -> Tuple[Dict | None, List[Dict]]:
    try:
        team_doc = teams_collection.find_one({"name": team_name})
        if not team_doc:
            print(f"❌ No team found: {team_name}")
            return None, []
        
        player_ids = team_doc.get("player_ids", [])
        if not player_ids:
            print(f"⚠️ No player_ids found in team doc for {team_name}")
            return team_doc, []

        valid_ids = []
        for pid in player_ids:
            try:
                valid_ids.append(ObjectId(pid))
            except Exception as e:
                print(f"⚠️ Invalid player_id: {pid} — {e}")

        players = list(players_collection.find({"_id": {"$in": valid_ids}}))
        print(f"✅ Loaded {len(players)} players for {team_name} from DB")

        return team_doc, players

    except PyMongoError as e:
        print(f"⚠️ MongoDB roster lookup failed for {team_name}: {e}")
        return None, []


def _team_file_path(team_name: str) -> Path:
    snake = team_name.lower().replace(" ", "_").replace("-", "_")
    base = Path(__file__).resolve().parents[1]
    return base / "teams" / f"{snake}.json"


def _load_from_file(team_name: str) -> Tuple[Dict | None, List[Dict]]:
    path = _team_file_path(team_name)
    if not path.exists():
        return None, []
    try:
        with open(path) as f:
            data = json.load(f)
        return data, data.get("players", [])
    except Exception as e:
        print(f"❌ Failed to load roster from file for {team_name}: {e}")
        return None, []


def load_roster(team_name: str) -> Tuple[Dict | None, List[Dict]]:
    team, players = _load_from_db(team_name)
    if players:
        return team, players
    file_team, file_players = _load_from_file(team_name)
    if file_players:
        return file_team or team, file_players
    return team, players
