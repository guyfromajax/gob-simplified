import json
from pathlib import Path
from typing import Tuple, List, Dict

from BackEnd.db import players_collection, teams_collection, franchises_collection
from pymongo.errors import PyMongoError
from bson import ObjectId



def _load_from_db(team_name: str, franchise_id: str | None = None) -> Tuple[Dict | None, List[Dict]]:
    try:
        # Find the team document by name
        team_doc = teams_collection.find_one({"name": team_name})
        # print(f"🔍 Team doc: {team_doc}")
        if not team_doc:
            print(f"❌ No team found: {team_name}")
            return None, []

        # ✅ FRANCHISE MODE: If franchise_id provided, load from franchise.players (trained attributes)
        if franchise_id:
            try:
                franchise_doc = franchises_collection.find_one({"_id": ObjectId(franchise_id)}, {"players": 1})
                if franchise_doc:
                    franchise_players = franchise_doc.get("players", {})
                    # Get team_id from team_doc to filter players
                    team_id = team_doc.get("team_id")
                    if team_id:
                        # Build players list from franchise.players, matching team_id
                        players = []
                        for player_id_str, franchise_player_data in franchise_players.items():
                            meta = franchise_player_data.get("meta", {})
                            player_team_id = meta.get("team_id")
                            # Match by team_id (ObjectId string)
                            if str(player_team_id) == str(team_id) or meta.get("team") == team_name:
                                # Get base player data from universal collection
                                from bson import ObjectId
                                base_player = players_collection.find_one({"_id": ObjectId(player_id_str)})
                                if base_player:
                                    # Merge franchise-specific attributes into base player
                                    base_player = dict(base_player)  # Convert to dict for modification
                                    franchise_attrs = franchise_player_data.get("attributes", {})
                                    if franchise_attrs:
                                        base_player["attributes"] = franchise_attrs
                                    franchise_position_ratings = franchise_player_data.get("position_ratings", {})
                                    if franchise_position_ratings:
                                        base_player["position_ratings"] = franchise_position_ratings
                                    players.append(base_player)
                        if players:
                            return team_doc, players
            except Exception as e:
                print(f"⚠️ Error loading franchise players for {team_name}: {e}")

        # Fallback: Query players by team name directly in the players collection (universal)
        players = list(players_collection.find({"team": team_name}))
        # print(f"✅ Loaded {len(players)} players for {team_name} from DB")
        # print(f"🔍 Players: {players}")

        return team_doc, players

    except PyMongoError as e:
        print(f"⚠️ MongoDB roster lookup failed for {team_name}: {e}")
        return None, []



def _team_file_path(team_name: str) -> Path:
    """Return the path to the bundled roster JSON for ``team_name``.

    Test environments (and local development without Mongo) rely on the
    repository's ``teams`` directory which lives at the project root rather
    than inside ``BackEnd``.  The previous implementation assumed the latter
    which meant we never discovered the JSON files, leaving the roster empty
    and causing any access to ``team.lineup["C"]`` to explode during opening
    tip logic.  To make the loader resilient we walk the parent directories
    until we find the first ``teams`` folder that contains the requested
    roster file and fall back to the project root if necessary.
    """

    snake = team_name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{snake}.json"
    current = Path(__file__).resolve()

    for parent in current.parents:
        candidate = parent / "teams" / filename
        if candidate.exists():
            return candidate

    # Preserve the old behaviour (which effectively pointed one level up) so
    # that callers still receive a sensible path even if the file is missing.
    return current.parents[1] / "teams" / filename


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


def load_roster(team_name: str, franchise_id: str | None = None) -> Tuple[Dict | None, List[Dict]]:
    team, players = _load_from_db(team_name, franchise_id)
    if players:
        return team, players
    file_team, file_players = _load_from_file(team_name)
    if file_players:
        return file_team or team, file_players
    return team, players
