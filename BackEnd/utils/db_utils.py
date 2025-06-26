
from BackEnd.db import players_collection
from BackEnd.models.player import Player
from BackEnd.constants import POSITION_LIST

POSITION_LIST = ["PG", "SG", "SF", "PF", "C"]

def build_lineup_from_mongo(team_name: str) -> dict:
    # Pull all players for the team
    players_cursor = players_collection.find({ "team": team_name })
    players = list(players_cursor)

    if len(players) < 5:
        raise ValueError(f"Team '{team_name}' has only {len(players)} players. At least 5 required.")

    lineup = {}

    for i, pos in enumerate(POSITION_LIST):
        player_doc = players[i]
        lineup[pos] = Player(player_doc)

    return lineup
