"""
Shared utility for calculating franchise standings from franchise.results

✅ SS&S: Single source of truth for franchise W/L and PF/PA calculation
Used by both /franchise/standings and /franchise/team-stats endpoints
"""

from typing import Dict, Any


def calculate_franchise_standings(
    franchise_results: Dict[str, Any],
    franchise_teams: Dict[str, Any]
) -> Dict[str, Dict[str, int]]:
    """
    Calculate W/L and PF/PA standings from franchise.results.
    
    ✅ SS&S: This is the single source of truth for franchise standings calculation.
    All endpoints that need franchise W/L and PF/PA should use this function.
    
    Args:
        franchise_results: Dictionary from franchise.results field
            Structure: {"1": [{"away_id": "...", "home_id": "...", "away_score": X, "home_score": Y}, ...], "2": [...], ...}
        franchise_teams: Dictionary from franchise.franchise_teams field
            Keys are team_id strings (ObjectId strings)
    
    Returns:
        Dictionary mapping team_id_str to {"W": int, "L": int, "PF": int, "PA": int}
    """
    standings_data: Dict[str, Dict[str, int]] = {}
    
    # Initialize all teams with zeros
    for team_id_str in franchise_teams.keys():
        standings_data[str(team_id_str)] = {"PF": 0, "PA": 0, "W": 0, "L": 0}
    
    # Process all weeks in results
    for week_str, week_results in franchise_results.items():
        if not isinstance(week_results, list):
            continue
        for game_result in week_results:
            if not isinstance(game_result, dict):
                continue
            
            away_id = game_result.get("away_id")
            home_id = game_result.get("home_id")
            away_score = game_result.get("away_score", 0)
            home_score = game_result.get("home_score", 0)
            
            if not away_id or not home_id:
                continue
            
            # Normalize team IDs to strings
            away_id_str = str(away_id)
            home_id_str = str(home_id)
            
            # Initialize if not present (in case team not in franchise_teams)
            if away_id_str not in standings_data:
                standings_data[away_id_str] = {"PF": 0, "PA": 0, "W": 0, "L": 0}
            if home_id_str not in standings_data:
                standings_data[home_id_str] = {"PF": 0, "PA": 0, "W": 0, "L": 0}
            
            # Determine winner
            if away_score > home_score:
                standings_data[away_id_str]["W"] += 1
                standings_data[home_id_str]["L"] += 1
            elif home_score > away_score:
                standings_data[home_id_str]["W"] += 1
                standings_data[away_id_str]["L"] += 1
            # Tie: no win/loss (or handle ties if needed)
            
            # Update PF/PA
            standings_data[away_id_str]["PF"] += away_score
            standings_data[away_id_str]["PA"] += home_score
            standings_data[home_id_str]["PF"] += home_score
            standings_data[home_id_str]["PA"] += away_score
    
    return standings_data

