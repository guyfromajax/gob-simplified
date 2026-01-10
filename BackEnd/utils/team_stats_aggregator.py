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
    logger=None,
    tournament_bracket: Dict[str, Any] | None = None,  # ✅ FIX: Optional bracket for tournament-specific W/L and PF/PA
    franchise_results: Dict[str, Any] | None = None  # ✅ FIX: Optional franchise results for franchise-specific W/L and PF/PA
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
    # ✅ SS&S: Both tournament.teams and franchise_teams use ObjectId strings as keys
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
        
        # ✅ SS&S: player meta.team_id should be ObjectId string (matches tournament.teams/franchise_teams keys)
        # If it's not in the map, try to resolve it (might be team name or different format)
        if team_id_str not in team_stats_map:
            # Try to resolve team_id_str to ObjectId string
            resolved_team_id = None
            try:
                # Try as ObjectId first
                obj_id = ObjectId(team_id_str)
                resolved_team_id = str(obj_id)
            except Exception:
                # Try as team name
                team_doc = teams_collection.find_one({"name": team_id_str}, {"_id": 1})
                if team_doc:
                    resolved_team_id = str(team_doc["_id"])
                else:
                    # Try case-insensitive
                    team_doc = teams_collection.find_one({"name": {"$regex": f"^{team_id_str}$", "$options": "i"}}, {"_id": 1})
                    if team_doc:
                        resolved_team_id = str(team_doc["_id"])
            
            if resolved_team_id and resolved_team_id in team_stats_map:
                team_id_str = resolved_team_id
            elif resolved_team_id:
                # Team not in tournament/franchise, but player has stats - initialize it
                team_stats_map[resolved_team_id] = {
                    "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
                    "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
                    "DREB": 0, "OREB": 0, "TREB": 0,
                    "TO": 0, "F": 0,
                    "DEF_A": 0, "DEF_S": 0, "SCR_A": 0, "SCR_S": 0
                }
                team_id_str = resolved_team_id
            else:
                # Can't resolve, skip this player
                if logger:
                    log_func(f"⚠️ [{collection_type.upper()}_TEAM_STATS] Cannot resolve team_id '{team_id_str}' for player {pid}, skipping")
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
    
    # ✅ FIX: Calculate W/L and PF/PA from tournament bracket (tournament-specific) instead of global teams collection
    # This prevents stats from accumulating across multiple tournaments
    standings_data = {}
    if collection_type == 'tournament' and tournament_bracket:
        # Calculate W/L and PF/PA from tournament bracket results
        # Build team name -> team_id map for lookup
        team_name_to_id = {}
        for team_id_str, team_data in team_ids.items():
            try:
                team_obj_id = ObjectId(team_id_str)
                team_doc = teams_collection.find_one({"_id": team_obj_id}, {"name": 1})
                if team_doc:
                    team_name = team_doc.get("name")
                    if team_name:
                        team_name_to_id[team_name] = team_id_str
            except Exception:
                pass
        
        # Initialize all teams with zeros
        for team_id_str in team_ids.keys():
            standings_data[team_id_str] = {"PF": 0, "PA": 0, "W": 0, "L": 0}
        
        # Process all rounds in bracket
        for round_name, matchups in tournament_bracket.items():
            if not isinstance(matchups, list):
                continue
            for matchup in matchups:
                if not isinstance(matchup, dict):
                    continue
                home_team_name = matchup.get("home_team")
                away_team_name = matchup.get("away_team")
                winner_name = matchup.get("winner")
                score = matchup.get("score", {})
                
                if not home_team_name or not away_team_name or not winner_name:
                    continue
                
                # Get team IDs from names
                home_team_id = team_name_to_id.get(home_team_name)
                away_team_id = team_name_to_id.get(away_team_name)
                
                if home_team_id and away_team_id:
                    home_score = score.get(home_team_name, 0)
                    away_score = score.get(away_team_name, 0)
                    
                    # Update winner
                    if winner_name == home_team_name:
                        standings_data[home_team_id]["W"] += 1
                        standings_data[away_team_id]["L"] += 1
                    else:
                        standings_data[away_team_id]["W"] += 1
                        standings_data[home_team_id]["L"] += 1
                    
                    # Update PF/PA
                    standings_data[home_team_id]["PF"] += home_score
                    standings_data[home_team_id]["PA"] += away_score
                    standings_data[away_team_id]["PF"] += away_score
                    standings_data[away_team_id]["PA"] += home_score
    elif collection_type == 'franchise' and franchise_results:
        # ✅ FIX: Calculate W/L and PF/PA from franchise.results (franchise-specific) instead of global teams collection
        # This prevents stats from accumulating across multiple franchises or from Single Game mode
        # Initialize all teams with zeros
        for team_id_str in team_ids.keys():
            standings_data[str(team_id_str)] = {"PF": 0, "PA": 0, "W": 0, "L": 0}
        
        # Process all weeks in results
        # franchise_results structure: {"1": [{"away_id": "...", "home_id": "...", "away_score": X, "home_score": Y}, ...], "2": [...], ...}
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
                
                # Initialize if not present (in case team not in team_ids)
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
    else:
        # Fallback: Read from teams collection (for backward compatibility or when results not provided)
        # ⚠️ WARNING: This should NOT be used for franchise mode - use franchise_results instead
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
    seen_team_ids = set()  # Track by ObjectId to prevent duplicates (SS&S: same for both modes)
    
    for team_id_str, stats in team_stats_map.items():
        # Resolve team name (mode-specific logic)
        team_name = resolve_team_name(team_id_str, teams_collection, collection_type)
        
        # ✅ SS&S: Deduplicate by ObjectId (same for both modes)
        # This prevents duplicates even if team name resolution differs
        try:
            team_obj_id = ObjectId(team_id_str)
            if team_obj_id in seen_team_ids:
                if logger:
                    log_func(f"⚠️ [{collection_type.upper()}_TEAM_STATS] Skipping duplicate team_id: {team_id_str} (name: {team_name})")
                continue
            seen_team_ids.add(team_obj_id)
        except Exception:
            # team_id_str is not an ObjectId - try to resolve it to ObjectId before adding
            # This prevents duplicates like "BENTLEY_TRUMAN" vs ObjectId
            if logger:
                log_func(f"⚠️ [{collection_type.upper()}_TEAM_STATS] team_id_str '{team_id_str}' is not a valid ObjectId, attempting resolution")
            
            # Try to resolve to ObjectId by looking up team name
            resolved_obj_id = None
            try:
                # Try as team name
                team_doc = teams_collection.find_one({"name": team_id_str}, {"_id": 1})
                if team_doc:
                    resolved_obj_id = team_doc["_id"]
                else:
                    # Try case-insensitive
                    team_doc = teams_collection.find_one({"name": {"$regex": f"^{team_id_str}$", "$options": "i"}}, {"_id": 1})
                    if team_doc:
                        resolved_obj_id = team_doc["_id"]
            except Exception:
                pass
            
            if resolved_obj_id:
                # Check if we've already seen this ObjectId
                if resolved_obj_id in seen_team_ids:
                    if logger:
                        log_func(f"⚠️ [{collection_type.upper()}_TEAM_STATS] Skipping duplicate (resolved): team_id_str '{team_id_str}' -> ObjectId '{resolved_obj_id}' (name: {team_name})")
                    continue
                seen_team_ids.add(resolved_obj_id)
                # Update team_id_str to the resolved ObjectId for consistency
                team_id_str = str(resolved_obj_id)
            else:
                # Can't resolve - skip this entry to prevent duplicates
                if logger:
                    log_func(f"⚠️ [{collection_type.upper()}_TEAM_STATS] Cannot resolve team_id_str '{team_id_str}' to ObjectId, skipping to prevent duplicates")
                continue
            
            # ✅ SS&S: Include ALL teams in tournament bracket, even if stats are zero
            # This matches Franchise mode behavior and ensures all teams appear in the table
            # Teams with zero stats will still show W/L, PF/PA from standings
        
        # Add PF/PA and wins/losses from standings
        # ✅ FIX: Use normalized team_id_str (ObjectId string) for standings lookup
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
            # Strategy 3: Try case-insensitive search and normalize formats
            # Try uppercase version (e.g., "MORRISTOWN" -> "Morristown")
            team_doc = teams_collection.find_one({"name": {"$regex": f"^{team_id_str}$", "$options": "i"}}, {"name": 1})
            if team_doc:
                team_name = team_doc.get("name")  # Use canonical name from database
            
            # Strategy 4: Try underscore format normalization (e.g., "OCEAN_CITY" -> "Ocean City")
            if not team_name and "_" in team_id_str:
                normalized = team_id_str.replace("_", " ").title()
                team_doc = teams_collection.find_one({"name": normalized}, {"name": 1})
                if team_doc:
                    team_name = team_doc.get("name")
            
            # Strategy 5: Last resort - try to find by any case variation
            if not team_name:
                # Search all teams and find case-insensitive match
                all_teams = teams_collection.find({}, {"name": 1})
                for t in all_teams:
                    if t.get("name", "").upper() == team_id_str.upper():
                        team_name = t.get("name")
                        break
            
            # Final fallback: use team_id_str as-is (should rarely happen)
            if not team_name:
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

