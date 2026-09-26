"""
Shared utility for calculating franchise standings from franchise.results

✅ SS&S: Single source of truth for franchise W/L and PF/PA calculation
Used by both /franchise/standings and /franchise/team-stats endpoints
"""

from typing import Any, Dict, Mapping


def calculate_franchise_standings(
    franchise_results: Dict[str, Any],
    team_ids_map: Dict[str, Any],
) -> Dict[str, Dict[str, int]]:
    """
    Calculate W/L and PF/PA standings from franchise.results.

    ✅ SS&S: This is the single source of truth for franchise standings calculation.
    All endpoints that need franchise W/L and PF/PA should use this function.

    Args:
        franchise_results: Dictionary from franchise.results field
            Structure: {"1": [{"away_id": "...", "home_id": "...", "away_score": X, "home_score": Y}, ...], "2": [...], ...}
        team_ids_map: Dict whose keys are team_id strings (ObjectId strings). Only .keys() is used to initialize standings.
            Callers pass e.g. {str(tid): {} for tid in team_ids} from FTD team list.

    Returns:
        Dictionary mapping team_id_str to {"W": int, "L": int, "PF": int, "PA": int}
    """
    standings_data: Dict[str, Dict[str, int]] = {}

    # Initialize all teams with zeros
    for team_id_str in team_ids_map.keys():
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
            
            # Initialize if not present (in case team not in team_ids_map)
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


def standings_display_sort_key(row: Mapping[str, Any]) -> tuple[int, int]:
    """Wins descending, then point differential descending.

    This is the order the Standings page applies
    (``(b.W - a.W) || (b.differential - a.differential)``) and the order
    ``GET /franchise/standings`` returns. Differential is PF minus PA.
    """
    wins = int(row.get("W", 0) or 0)
    if "PF" in row or "PA" in row:
        differential = int(row.get("PF", 0) or 0) - int(row.get("PA", 0) or 0)
    else:
        differential = int(row.get("differential", 0) or 0)
    return (-wins, -differential)


def current_streaks(franchise_results: Dict[str, Any] | None) -> Dict[str, str]:
    """Current W/L streak for each team, from completed results in week order.

    A tie ends the streak. The text is ``W3`` or ``L1``. Teams with no
    decided game are omitted. This does not affect standings order.
    """
    weeks: list[tuple[int, Any]] = []
    for key, games in (franchise_results or {}).items():
        try:
            week_n = int(key)
        except (TypeError, ValueError):
            continue
        weeks.append((week_n, games))
    weeks.sort(key=lambda item: item[0])
    running: Dict[str, tuple[str, int]] = {}
    for _week, games in weeks:
        if not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, dict):
                continue
            away_id = str(game.get("away_id") or "")
            home_id = str(game.get("home_id") or "")
            if not away_id or not home_id:
                continue
            try:
                away_score = int(game.get("away_score") or 0)
                home_score = int(game.get("home_score") or 0)
            except (TypeError, ValueError):
                continue
            if away_score == home_score:
                running[away_id] = ("", 0)
                running[home_id] = ("", 0)
                continue
            if away_score > home_score:
                outcomes = ((away_id, "W"), (home_id, "L"))
            else:
                outcomes = ((home_id, "W"), (away_id, "L"))
            for team_id, outcome in outcomes:
                prev = running.get(team_id)
                count = prev[1] + 1 if prev and prev[0] == outcome else 1
                running[team_id] = (outcome, count)
    return {
        team_id: outcome + str(count)
        for team_id, (outcome, count) in running.items()
        if outcome and count
    }

