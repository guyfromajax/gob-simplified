
import random
from typing import List, Dict
from BackEnd.db import players_collection
from BackEnd.models.player import Player

# Trait groups per position
POSITION_TRAITS = {
    "PG": ["BH", "PS", "IQ", "OD"],
    "SG": ["SH", "PS", "OD", "AG"],
    "SF": ["AG", "ST", "ID", "OD"],
    "PF": ["ID", "ST", "RB", "IQ"],
    "C":  ["SC", "ID", "ST", "RB"]
}

def get_player_rating(player, traits: List[str]) -> float:
    total = 0
    for trait in traits:
        total += player.attributes.get(trait, 0)
    return total / len(traits)

def build_lineup_from_mongo(team_name: str) -> dict:
    players_cursor = players_collection.find({"team": team_name})
    players = [Player(p) for p in players_cursor]

    if len(players) < 5:
        raise ValueError(f"Team '{team_name}' has fewer than 5 players.")

    position_order = ["PG", "SG", "SF", "PF", "C"]
    random.shuffle(position_order)

    available_players = players.copy()
    lineup: Dict[str, Player] = {}

    for pos in position_order:
        traits = POSITION_TRAITS[pos]
        rated = [(p, get_player_rating(p, traits)) for p in available_players]
        rated.sort(key=lambda tup: tup[1], reverse=True)

        top_candidates = rated[:3] if len(rated) >= 3 else rated
        chosen_player = random.choice(top_candidates)[0]

        lineup[pos] = chosen_player
        available_players.remove(chosen_player)

    return lineup

