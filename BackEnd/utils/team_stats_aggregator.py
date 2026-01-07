"""
Shared utility for aggregating team stats from player stats
Used by both Tournament and Franchise modes

✅ SS&S: Single source of truth for team stats aggregation logic
"""

from typing import Dict, List, Any, Optional
from bson import ObjectId
from pymongo.collection import Collection


def aggregate_team_stats_from_players(
    players: Dict[str, Dict[str, Any]],
    team_ids: Dict[str, Any],
    teams_collection: Collection,
    collection_type: str = 'tournament',
    logger=None
) -> List[Dict[str, Any]]:
    """
    Aggregates player stats into team stats.
    
    Args:
        players: Dictionary of {player_id: {meta: {...}, season: {...}}}
        team_ids: Dictionary of team IDs (from tournament.teams or franchise.franchise_teams)
        teams_collection: MongoDB collection for teams
        collection_type: 'tournament' or 'franchise' (for logging/debugging)
        logger: Optional logger instance
    
    Returns:
        List of {team: str, stats: {...}} dictionaries
    """
    if logger is None:
        # Fallback to print if no logger provided
        log_func = print
    else:
        log_func = logger.info if hasattr(logger, 'info') else logger
    
    # Initialize team stats map
    team_stats_map: Dict[str, Dict[str, int]] = {}
    
    # Initialize team stats for all teams
    for team_id in team_ids.keys():
        team_id_str = str(team_id)
        team_stats_map[team_id_str] = {
            "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
            "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
            "DREB": 0, "OREB": 0, "TREB": 0,
            "TO": 0, "F": 0,
            "DEF_A": 0, "DEF_S": 0, "SCR_A": 0, "SCR_S": 0
        }
    
    # Aggregate stats from players object
    players_with_stats = 0
    players_without_team_id = 0
    players_without_stats = 0
    players_with_empty_stats = 0
    
    for pid, pdata in players.items():
        meta = pdata.get("meta", {})
        team_id = meta.get("team_id")
        if not team_id:
            players_without_team_id += 1
            if logger:
                logger.warning(f"⚠️ [{collection_type.upper()}_TEAM_STATS] Player {pid} missing team_id in meta: {meta}")
            continue
        
        team_id_str = str(team_id)
        season_stats = pdata.get("season", {})
        if not season_stats:
            players_without_stats += 1
            continue
        
        # Tournament mode: Include players with empty stats (zeros) - they still count for team aggregation
        # Empty stats object means player hasn't played yet, but they're still on the roster
        if collection_type == 'tournament' and len(season_stats) == 0:
            players_with_empty_stats += 1
            # Continue to next player - empty stats don't contribute to team totals
            continue
        
        if team_id_str not in team_stats_map:
            team_stats_map[team_id_str] = {
                "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
                "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
                "DREB": 0, "OREB": 0, "TREB": 0,
                "TO": 0, "F": 0,
                "DEF_A": 0, "DEF_S": 0, "SCR_A": 0, "SCR_S": 0
            }
        
        players_with_stats += 1
        # Sum all stats for this team (map 3PTM to TPM for output)
        for stat, val in season_stats.items():
            if isinstance(val, (int, float)):
                output_stat = stat
                if stat == "3PTM":
                    output_stat = "TPM"
                elif stat == "3PTA":
                    output_stat = "TPA"
                
                if output_stat in team_stats_map[team_id_str]:
                    team_stats_map[team_id_str][output_stat] += val
    
    if logger:
        log_func(f"🔍 [{collection_type.upper()}_TEAM_STATS] Processed {players_with_stats} players with stats, "
                f"{players_without_team_id} without team_id, {players_without_stats} without stats, "
                f"{players_with_empty_stats} with empty stats")
    
    # Get PF/PA and wins/losses from standings (teams collection)
    standings_data = {}
    teams_list = list(teams_collection.find({}, {"name": 1, "PF": 1, "PA": 1, "record": 1, "_id": 1}))
    for t in teams_list:
        team_id_str = str(t["_id"])
        rec = t.get("record", {"W": 0, "L": 0})
        standings_data[team_id_str] = {
            "PF": t.get("PF", 0),
            "PA": t.get("PA", 0),
            "W": rec.get("W", 0),
            "L": rec.get("L", 0)
        }
    
    # Convert to output format with team names
    output = []
    seen_team_names = set()  # For tournament deduplication
    
    for team_id_str, stats in team_stats_map.items():
        # Resolve team name (mode-specific logic)
        team_name = resolve_team_name(team_id_str, teams_collection, collection_type)
        
        # Tournament mode: Deduplicate by team name
        if collection_type == 'tournament':
            if team_name in seen_team_names:
                continue
            seen_team_names.add(team_name)
            
            # Tournament mode: Only include teams with actual stats (non-zero totals)
            has_stats = any(
                stats.get(stat, 0) > 0 
                for stat in ["PTS", "FGM", "FGA", "REB", "AST", "STL", "BLK", "TO", "F"]
            )
            if not has_stats:
                continue
        
        # Add PF/PA and wins/losses from standings
        if team_id_str in standings_data:
            stats["PF"] = standings_data[team_id_str]["PF"]
            stats["PA"] = standings_data[team_id_str]["PA"]
            stats["W"] = standings_data[team_id_str]["W"]
            stats["L"] = standings_data[team_id_str]["L"]
        else:
            # Try to find PF/PA and wins/losses by team name if team_id_str lookup failed
            try:
                team_doc_for_standings = teams_collection.find_one({"name": team_name}, {"PF": 1, "PA": 1, "record": 1, "_id": 1})
                if team_doc_for_standings:
                    stats["PF"] = team_doc_for_standings.get("PF", 0)
                    stats["PA"] = team_doc_for_standings.get("PA", 0)
                    rec = team_doc_for_standings.get("record", {"W": 0, "L": 0})
                    stats["W"] = rec.get("W", 0)
                    stats["L"] = rec.get("L", 0)
                else:
                    stats["PF"] = 0
                    stats["PA"] = 0
                    stats["W"] = 0
                    stats["L"] = 0
            except Exception:
                stats["PF"] = 0
                stats["PA"] = 0
                stats["W"] = 0
                stats["L"] = 0
        
        # Calculate TREB from DREB + OREB
        stats["TREB"] = stats.get("DREB", 0) + stats.get("OREB", 0)
        
        if logger:
            log_func(f"🔍 [{collection_type.upper()}_TEAM_STATS] Team {team_name}: "
                    f"PTS={stats.get('PTS')}, REB={stats.get('REB')}, AST={stats.get('AST')}")
        
        output.append({"team": team_name, "stats": stats})
    
    return output


def resolve_team_name(team_id_str: str, teams_collection: Collection, collection_type: str = 'tournament') -> str:
    """
    Resolves team ID to team name using mode-specific strategies.
    
    Args:
        team_id_str: Team ID as string (may be ObjectId string or team name)
        teams_collection: MongoDB collection for teams
        collection_type: 'tournament' or 'franchise' (determines resolution strategy)
    
    Returns:
        Team name string
    """
    team_name = None
    
    if collection_type == 'tournament':
        # Tournament mode: Multiple lookup strategies
        try:
            # Strategy 1: Try as ObjectId
            team_doc = teams_collection.find_one({"_id": ObjectId(team_id_str)}, {"name": 1})
            if team_doc:
                team_name = team_doc.get("name")
        except Exception:
            pass
        
        if not team_name:
            # Strategy 2: Try as team name (if team_id_str is already a team name)
            team_doc = teams_collection.find_one({"name": team_id_str}, {"name": 1})
            if team_doc:
                team_name = team_doc.get("name")
        
        if not team_name:
            # Strategy 3: Fallback to team_id_str (but normalize if it's an underscore format)
            # Convert "OCEAN_CITY" to "Ocean City" if possible
            if "_" in team_id_str:
                # Try to find team by converting underscore format to proper name
                normalized = team_id_str.replace("_", " ").title()
                team_doc = teams_collection.find_one({"name": normalized}, {"name": 1})
                if team_doc:
                    team_name = team_doc.get("name")
                else:
                    team_name = team_id_str
            else:
                team_name = team_id_str
    else:
        # Franchise mode: Simple ObjectId lookup with fallback
        try:
            team_doc = teams_collection.find_one({"_id": ObjectId(team_id_str)}, {"name": 1})
            team_name = team_doc.get("name", team_id_str) if team_doc else team_id_str
        except Exception:
            # Fallback if team_id_str is not a valid ObjectId
            team_name = team_id_str
    
    return team_name

