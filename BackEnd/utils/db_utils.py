import logging
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

def is_player_eligible_for_lineup(player, game_state=None, ineligible_player_ids=None) -> bool:
    """
    Check if a player is eligible for lineup based on energy and foul restrictions.
    Fouled-out (5+ fouls) is derived from player.get_stat("F", "game"), not a persisted list.

    Args:
        player: Player object to check
        game_state: Optional game state dict with quarter, time_remaining (for energy/foul restrictions)
        ineligible_player_ids: Deprecated, ignored. Kept for backward compatibility.

    Returns:
        True if player is eligible, False otherwise
    """
    # Exclude fouled-out players (5+ fouls) from game stats
    foul_count = player.get_stat("F", "game")
    if foul_count is not None and foul_count >= 5:
        return False

    # If no game_state provided, only check for fouled-out
    if not game_state:
        return True

    quarter = game_state.get("quarter", 1)
    time_remaining = game_state.get("time_remaining", 480)  # Default to 8:00 (480 seconds)

    # Energy (NG) filtering
    ng = player.attributes.get("NG", 1.0)
    
    # Determine energy threshold based on quarter and time
    is_late_q4_or_ot = (quarter == 4 and time_remaining < 240) or quarter > 4
    energy_threshold = 0.64 if is_late_q4_or_ot else 0.8
    
    if ng < energy_threshold:
        return False
    
    # Foul filtering by quarter
    if quarter == 1:
        if foul_count > 1:
            return False
    elif quarter == 2:
        if foul_count > 2:
            return False
    elif quarter == 3:
        if foul_count > 3:
            return False
    elif quarter == 4:
        # Q4: exclude if fouls > 3 AND more than 4 minutes remaining
        if foul_count > 3 and time_remaining > 240:
            return False
    elif quarter > 4:  # Overtime
        # OT: no foul exclusion for active players (already checked for 5+ fouls above)
        pass
    
    return True

def build_lineup_from_mongo(team: Union[str, TeamManager], game_state=None) -> Dict[str, Player]:
    """Build a starting lineup using existing player objects when available.

    ``team`` may be either a team name or an actual :class:`TeamManager`
    instance.  When a ``TeamManager`` is supplied the players from its roster
    are reused so their in-memory ``stats['game']`` containers are preserved.
    Passing a string falls back to the original behaviour of constructing new
    :class:`Player` objects from the database.
    
    Args:
        team: Team name or TeamManager instance
        game_state: Optional game state dict with quarter, time_remaining
                   Used to filter players based on energy and foul restrictions (fouled-out from F >= 5)
    """

    if isinstance(team, TeamManager):
        team_name = team.name
        players = list(team.get_all_players())
    else:
        team_name = team
        players_cursor = players_collection.find({"team": team_name})
        players = [Player(p) for p in players_cursor]

    # Filter players based on energy and foul restrictions (fouled-out from F >= 5)
    eligible_players = [
        p for p in players
        if is_player_eligible_for_lineup(p, game_state)
    ]
    
    if len(eligible_players) < 5:
        raise ValueError(
            f"Team '{team_name}' has fewer than 5 eligible players. "
            f"Total players: {len(players)}, Eligible: {len(eligible_players)}"
        )

    position_order = ["PG", "SG", "SF", "PF", "C"]
    random.shuffle(position_order)

    available_players = eligible_players.copy()
    lineup: Dict[str, Player] = {}

    for idx, pos in enumerate(position_order):
        traits = POSITION_TRAITS[pos]
        rated = [(p, get_player_rating(p, traits)) for p in available_players]
        rated.sort(key=lambda tup: tup[1], reverse=True)

        # First 4 positions: choose from top 2 candidates
        # 5th position: choose from top 3 candidates
        if idx < 4:  # First 4 positions
            top_candidates = rated[:2] if len(rated) >= 2 else rated
        else:  # 5th position
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


def autoset_strategy_settings(team: TeamManager):
    """
    Automatically set strategy settings for a computer team using the same
    weighted randomization logic as initial strategy settings.
    
    This function regenerates strategy settings using _init_strategy_settings()
    to allow computer teams to adjust their strategy during timeouts, quarter
    breaks, and foul out instances.
    
    Args:
        team: TeamManager instance (must be a computer team, not user team)
    
    Returns:
        dict: New strategy settings
    """
    # ✅ DEBUG: Log if this is being called on a user team (this would be a bug!)
    if team.is_user_team:
        # logging.warning(f"⚠️ [AUTOSET STRATEGY] ERROR: autoset_strategy_settings() called on USER team: {team.name} (is_user_team={team.is_user_team}). This should NOT happen!")
        # Don't autoset strategy for user teams
        return team.strategy_settings
    
    # ✅ DEBUG: Log when autoset is called on computer teams
    old_inside = team.strategy_settings.get('inside', 'MISSING') if hasattr(team, 'strategy_settings') and team.strategy_settings else 'MISSING'
    # logging.warning(f"🔍 [AUTOSET STRATEGY] Autosetting strategy for COMPUTER team: {team.name}, old inside: {old_inside}")
    
    # Regenerate strategy settings using the same logic as initialization
    new_strategy_settings = team._init_strategy_settings()
    team.strategy_settings = new_strategy_settings
    
    new_inside = new_strategy_settings.get('inside', 'MISSING')
    # logging.warning(f"🔍 [AUTOSET STRATEGY] New inside: {new_inside}")
    
    return new_strategy_settings

