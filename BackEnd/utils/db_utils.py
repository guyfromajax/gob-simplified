
from BackEnd.db import players_collection
from BackEnd.models.player import Player
from BackEnd.constants import POSITION_LIST

def build_lineup_from_mongo(team_name: str) -> dict:
    players = list(players_collection.find({"team": team_name}))
    lineup = {}

    for pos in POSITION_LIST:
        # Find first player for each position
        player_doc = next((p for p in players if p.get("position") == pos), None)
        if player_doc is None:
            raise ValueError(f"Missing {pos} for team {team_name}")

        lineup[pos] = Player(player_doc)

    return lineup
