"""
Unified payload builder for quarter simulation requests.
Standardizes the data structure sent to the backend across all game modes.
"""
from typing import Dict, Any, Optional, List
from BackEnd.utils.game_id_utils import generate_game_id, normalize_game_id


def build_quarter_simulation_payload(
    home_team: str,
    away_team: str,
    quarter: int,
    mode: str = "single",
    game_id: Optional[str] = None,
    home_lineup: Optional[Dict[str, str]] = None,
    away_lineup: Optional[Dict[str, str]] = None,
    user_team_side: Optional[str] = None,
    strategy_settings: Optional[Dict[str, int]] = None,
    franchise_id: Optional[str] = None,
    tournament_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a standardized payload for quarter simulation requests.
    
    Args:
        home_team: Name of the home team
        away_team: Name of the away team
        quarter: Quarter number (1-4)
        mode: Game mode ("single", "franchise", "tournament")
        game_id: Existing game ID (will be normalized to ObjectId format)
        home_lineup: Home team lineup (position -> player_id mapping)
        away_lineup: Away team lineup (position -> player_id mapping)
        user_team_side: Which side the user controls ("home" or "away")
        strategy_settings: User's strategy preferences (offense, defense, inside, outside, attack, etc.)
        franchise_id: Franchise ID (for franchise mode)
        tournament_id: Tournament ID (for tournament mode)
        
    Returns:
        Standardized payload dictionary for quarter simulation API
    """
    # Normalize game_id to ObjectId format
    if game_id:
        normalized_game_id = normalize_game_id(game_id)
    else:
        normalized_game_id = generate_game_id()
    
    # Base payload structure
    payload = {
        "game_id": normalized_game_id,
        "home_team": home_team,
        "away_team": away_team,
        "quarter": quarter,
        "home_lineup": home_lineup or {},
        "away_lineup": away_lineup or {}
    }
    
    # Add mode-specific fields
    if mode == "single":
        # Single game mode - user controls one team
        if user_team_side and strategy_settings:
            payload["user_team_side"] = user_team_side
            payload["strategy_settings"] = strategy_settings
    
    elif mode == "franchise":
        # Franchise mode - user controls their franchise team
        if franchise_id:
            payload["franchise_id"] = franchise_id
        if user_team_side and strategy_settings:
            payload["user_team_side"] = user_team_side
            payload["strategy_settings"] = strategy_settings
    
    elif mode == "tournament":
        # Tournament mode - user controls their team in tournament context
        if tournament_id:
            payload["tournament_id"] = tournament_id
        if user_team_side and strategy_settings:
            payload["user_team_side"] = user_team_side
            payload["strategy_settings"] = strategy_settings
    
    return payload


def extract_payload_from_url_params(url_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract quarter simulation payload from URL parameters.
    
    Args:
        url_params: Dictionary of URL parameters
        
    Returns:
        Standardized payload dictionary
    """
    # Extract basic parameters
    home_team = url_params.get('home', '')
    away_team = url_params.get('away', '')
    quarter = int(url_params.get('quarter', '1'))
    mode = url_params.get('mode', 'single')
    game_id = url_params.get('game_id')
    
    # Extract lineup parameters
    home_lineup = {}
    away_lineup = {}
    
    for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
        home_key = f'home_{pos.lower()}'
        away_key = f'away_{pos.lower()}'
        if home_key in url_params:
            home_lineup[pos] = url_params[home_key]
        if away_key in url_params:
            away_lineup[pos] = url_params[away_key]
    
    # Extract user team side
    user_team_side = url_params.get('my_team')
    
    # Extract mode-specific IDs
    franchise_id = url_params.get('franchise_id')
    tournament_id = url_params.get('tournament_id')
    
    return build_quarter_simulation_payload(
        home_team=home_team,
        away_team=away_team,
        quarter=quarter,
        mode=mode,
        game_id=game_id,
        home_lineup=home_lineup,
        away_lineup=away_lineup,
        user_team_side=user_team_side,
        franchise_id=franchise_id,
        tournament_id=tournament_id
    )


def build_auto_lineup_payload(
    home_team: str,
    away_team: str,
    quarter: int,
    mode: str = "single",
    game_id: Optional[str] = None,
    user_team_side: Optional[str] = None,
    strategy_settings: Optional[Dict[str, int]] = None,
    franchise_id: Optional[str] = None,
    tournament_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a payload for quarter simulation with auto-generated lineups.
    Used when lineups are not explicitly provided (e.g., Sim To 4th Quarter).
    
    Args:
        home_team: Name of the home team
        away_team: Name of the away team
        quarter: Quarter number (1-4)
        mode: Game mode ("single", "franchise", "tournament")
        game_id: Existing game ID
        user_team_side: Which side the user controls
        strategy_settings: User's strategy preferences (offense, defense, inside, outside, attack, etc.)
        franchise_id: Franchise ID (for franchise mode)
        tournament_id: Tournament ID (for tournament mode)
        
    Returns:
        Standardized payload dictionary with empty lineups (will be auto-generated)
    """
    return build_quarter_simulation_payload(
        home_team=home_team,
        away_team=away_team,
        quarter=quarter,
        mode=mode,
        game_id=game_id,
        home_lineup=None,  # Will be auto-generated
        away_lineup=None,  # Will be auto-generated
        user_team_side=user_team_side,
        strategy_settings=strategy_settings,
        franchise_id=franchise_id,
        tournament_id=tournament_id
    )
