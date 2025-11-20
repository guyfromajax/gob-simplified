
import random
from typing import List, Dict, Union

from BackEnd.db import players_collection
from BackEnd.models.player import Player
from BackEnd.models.team_manager import TeamManager

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

def build_lineup_from_mongo(team: Union[str, TeamManager]) -> Dict[str, Player]:
    """Build a starting lineup using existing player objects when available.

    ``team`` may be either a team name or an actual :class:`TeamManager`
    instance.  When a ``TeamManager`` is supplied the players from its roster
    are reused so their in-memory ``stats['game']`` containers are preserved.
    Passing a string falls back to the original behaviour of constructing new
    :class:`Player` objects from the database.
    """

    if isinstance(team, TeamManager):
        team_name = team.name
        players = list(team.get_all_players())
    else:
        team_name = team
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
        # print(f"Chose {chosen_player.first_name} {chosen_player.last_name} for {pos}")
        available_players.remove(chosen_player)

    return lineup


def assign_lineup_from_ids(team: TeamManager, lineup_ids: Dict[str, str]) -> Dict[str, Player]:
    """Assign lineup from player IDs, skipping None/empty values.
    
    This function will only assign positions that have valid player IDs.
    Positions with None or missing values will remain unassigned and should
    be filled by _ensure_complete_lineup().
    """
    for pos, pid in lineup_ids.items():
        # Skip None, empty string, or invalid player IDs
        if not pid:
            continue
            
        existing = team.lineup.get(pos)
        if existing and existing.player_id == pid:
            continue

        player = team.get_player_by_id(pid)
        if player and team.lineup.get(pos) is not player:
            team.lineup[pos] = player

    return team.lineup

