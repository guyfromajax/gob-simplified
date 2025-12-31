from typing import Any, Dict
import logging

from bson import ObjectId
from pymongo import ReturnDocument

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import db, players_collection, tournaments_collection, games_collection, teams_collection
from BackEnd.utils.roster_loader import load_roster

logger = logging.getLogger(__name__)


def _clean_stat_block(stats: Dict[str, Any]) -> Dict[str, float]:
    """Return only numeric, non-negative stat entries.

    Any field that is not a number or is negative is discarded. The ``name``
    field, sometimes present in box score rows, is also ignored.
    """

    clean: Dict[str, float] = {}
    for stat, val in stats.items():
        if stat == "name":
            continue
        if isinstance(val, (int, float)) and val >= 0:
            clean[stat] = val
    return clean


def _per_game_block(totals: Dict[str, Any]) -> Dict[str, float]:
    """Return per-game averages for a totals block."""

    gp = totals.get("GP", 0)
    if not gp:
        return {stat: 0 for stat in BOX_SCORE_KEYS}
    
    # ✅ FIX: Filter out non-numeric stats (like Outlet_Score_List which is a list)
    result = {}
    for stat in BOX_SCORE_KEYS:
        val = totals.get(stat, 0)
        # Only calculate per-game for numeric values (int or float)
        if isinstance(val, (int, float)):
            result[stat] = val / gp
        else:
            # For non-numeric stats (lists, etc.), just return 0 or skip
            result[stat] = 0
    
    return result


def _pct_block(totals: Dict[str, Any]) -> Dict[str, float]:
    """Return shooting percentage metrics for a totals block."""

    fga = totals.get("FGA", 0)
    fgm = totals.get("FGM", 0)
    tpa = totals.get("3PTA", 0)
    tpm = totals.get("3PTM", 0)
    fta = totals.get("FTA", 0)
    ftm = totals.get("FTM", 0)
    pts = totals.get("PTS", 0)
    fg_pct = (fgm / fga * 100) if fga else 0.0
    fg3_pct = (tpm / tpa * 100) if tpa else 0.0
    ft_pct = (ftm / fta * 100) if fta else 0.0
    ts_den = 2 * (fga + 0.44 * fta)
    ts_pct = (pts / ts_den * 100) if ts_den else 0.0
    efg_pct = ((fgm + 0.5 * tpm) / fga * 100) if fga else 0.0
    return {"FG%": fg_pct, "3PT%": fg3_pct, "FT%": ft_pct, "TS%": ts_pct, "eFG%": efg_pct}


def init_franchise_player_stats(franchise_id: str | ObjectId, roster: list[dict]) -> None:
    """Seed a franchise document with zeroed player stat containers.

    Args:
        franchise_id: The ``_id`` of the franchise document to update. Can be
            a ``str`` or :class:`~bson.objectid.ObjectId`.
        roster: Iterable of player documents. Each entry should contain at
            least ``_id``, ``first_name``, ``last_name`` and ``team`` fields.

    The function populates ``players.<player_id>`` with ``meta``, ``season`` and
    ``career`` blocks. All stat fields start at zero. Player documents in the
    ``players`` collection are left untouched.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
    update: Dict[str, Any] = {}

    for player in roster:
        pid = str(player.get("_id"))
        if not pid:
            continue
        meta = {
            "first_name": player.get("first_name", ""),
            "last_name": player.get("last_name", ""),
            "team": player.get("team", ""),
        }
        tid = player.get("team_id")
        if tid is not None:
            meta["team_id"] = str(tid)
        update[f"players.{pid}"] = {
            "meta": meta,
            "season": zero_stats.copy(),
            "career": zero_stats.copy(),
        }

    if update:
        db.franchises.update_one({"_id": fid}, {"$set": update})


def apply_stats_from_summary(summary: Dict[str, Any], game_id: str, tournament_id: str | None = None) -> None:
    """Accumulate each player's game stats into season and career totals.

    This function is idempotent per (tournament_id, game_id) pair.  If the
    combination has already been applied for a player, no changes will occur.
    After applying, the player's game stats are reset to zero.
    """
    token = f"{tournament_id}:{game_id}" if tournament_id else str(game_id)

    # Get box_score from top level or build from team objects
    box_score = summary.get("box_score", {})
    if not box_score:
        # Build box_score from team objects (new structure)
        home_team_obj = summary.get("home_team", {})
        away_team_obj = summary.get("away_team", {})
        if home_team_obj and isinstance(home_team_obj, dict):
            home_team_name = home_team_obj.get("name")
            if home_team_name and "box_score" in home_team_obj:
                box_score[home_team_name] = home_team_obj.get("box_score", {})
        if away_team_obj and isinstance(away_team_obj, dict):
            away_team_name = away_team_obj.get("name")
            if away_team_name and "box_score" in away_team_obj:
                box_score[away_team_name] = away_team_obj.get("box_score", {})
    
    # ✅ FIX: Process ALL players from box_score (not just lineup players from players array)
    # box_score structure: {team_name: {pos: {playerId, name, jersey, stats...}, ...}, ...}
    # This includes all players who participated (lineup + bench), not just final lineup
    # Matches franchise mode pattern (lines 1230-1285)
    team_map = {
        "home": summary.get("home_team"),
        "away": summary.get("away_team"),
    }
    
    # Extract team names from team_map
    home_team_obj = team_map.get("home")
    away_team_obj = team_map.get("away")
    home_team_name = None
    away_team_name = None
    
    if isinstance(home_team_obj, dict):
        home_team_name = home_team_obj.get("name")
    elif isinstance(home_team_obj, str):
        home_team_name = home_team_obj
    
    if isinstance(away_team_obj, dict):
        away_team_name = away_team_obj.get("name")
    elif isinstance(away_team_obj, str):
        away_team_name = away_team_obj
    
    processed_player_ids = set()  # Track processed players to avoid double-counting
    
    # Process all players from box_score (all players who played, not just final lineup)
    for team_name in [home_team_name, away_team_name]:
        if not team_name:
            continue
        team_box = box_score.get(team_name, {})
        if not team_box:
            logger.warning(f"⚠️ [APPLY-STATS] No box_score data for team: {team_name}")
            continue
        
        # Process all players in this team's box_score
        for pos_key, player_data in team_box.items():
            if not isinstance(player_data, dict):
                continue
            raw_pid = player_data.get("playerId")
            if not raw_pid:
                continue
            query_pid = ObjectId(raw_pid) if ObjectId.is_valid(raw_pid) else raw_pid
            pid_str = str(query_pid)
            
            # Skip if already processed (avoid double-counting if same player appears multiple times)
            if pid_str in processed_player_ids:
                continue
            processed_player_ids.add(pid_str)
            
            # Get stats from player_data (box_score includes all stats)
            stat_block = player_data
            if not stat_block:
                logger.warning(f"⚠️ [APPLY-STATS] No stats found for player {pid_str} (team={team_name}, pos={pos_key})")
                continue
            
            # Clean stat block and filter out non-stat fields
            cleaned_stats = _clean_stat_block(stat_block)
            inc_fields: Dict[str, Any] = {}
            set_fields: Dict[str, Any] = {}
            for stat, val in cleaned_stats.items():
                # Skip non-stat fields (playerId, name, jersey, etc.)
                if stat in ["playerId", "name", "jersey", "x", "y", "coords", "team", "pos"]:
                    continue
                # ✅ MIN special handling: Convert seconds to minutes (integer division)
                # Game MIN is tracked in seconds, but season/career MIN should be in minutes
                if stat == "MIN":
                    val = val // 60  # Convert seconds to minutes (integer division)
                inc_fields[f"stats.season.{stat}"] = val
                inc_fields[f"stats.career.{stat}"] = val
                set_fields[f"stats.game.{stat}"] = 0
            if not inc_fields and not set_fields:
                continue
            
            update_doc: Dict[str, Any] = {"$addToSet": {"stats.applied_games": token}}
            if inc_fields:
                update_doc["$inc"] = inc_fields
            if set_fields:
                update_doc["$set"] = set_fields
            players_collection.update_one(
                {"_id": query_pid, "stats.applied_games": {"$ne": token}},
                update_doc,
            )

            # Persist the latest season stats to the tournament document if applicable.
            if tournament_id:
                try:
                    tid = ObjectId(tournament_id)
                except Exception:
                    tid = None
                if tid:
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Processing player {query_pid} for tournament {tournament_id}")
                # ✅ FIX: Get existing player entry from tournament document to preserve meta.team_id
                tournament_doc = tournaments_collection.find_one(
                    {"_id": tid},
                    {f"players.{str(query_pid)}": 1}
                )
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Found tournament doc: {bool(tournament_doc)}, has players key: {bool(tournament_doc.get('players') if tournament_doc else False)}")
                existing_player = tournament_doc.get("players", {}).get(str(query_pid), {}) if tournament_doc else {}
                existing_meta = existing_player.get("meta", {})
                existing_season = existing_player.get("season", {})
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: existing_meta.team: {existing_meta.get('team')}, existing_meta.team_id: {existing_meta.get('team_id')}, existing_season.GP: {existing_season.get('GP', 0)}")
                
                # ✅ FIX: For tournament mode, accumulate stats from game summary (not from players_collection)
                # This ensures tournament stats only include tournament games, not all games
                # Get stats from the game summary's box_score (already processed above)
                # Filter out non-stat fields (playerId, name, jersey, etc.)
                game_stats = {}
                for stat, val in cleaned_stats.items():
                    if stat not in ["playerId", "name", "jersey", "x", "y", "coords", "team", "pos"]:
                        game_stats[stat] = val
                
                # Initialize increment document for tournament document
                tournament_inc_doc: Dict[str, Any] = {}
                for stat, val in game_stats.items():
                    # ✅ MIN special handling: Convert seconds to minutes (integer division)
                    if stat == "MIN":
                        val = val // 60  # Convert seconds to minutes (integer division)
                    tournament_inc_doc[f"players.{str(query_pid)}.season.{stat}"] = val
                
                # Increment GP (games played)
                tournament_inc_doc[f"players.{str(query_pid)}.season.GP"] = 1
                
                # Get player metadata from players_collection (for name, team, etc.)
                player_doc = players_collection.find_one(
                    {"_id": query_pid},
                    {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1},
                )
                if not player_doc:
                    continue
                
                # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
                # Wrap metadata in meta object (matches Franchise pattern)
                # ✅ FIX: Preserve existing meta.team_id from tournament document if it exists
                # ✅ FIX: Ensure team name matches bracket team names (for leaders filtering)
                # Use player_doc team name as source of truth (it matches teams collection)
                # This ensures meta.team matches bracket team names exactly
                team_name = player_doc.get("team", existing_meta.get("team", ""))
                meta = {
                    "first_name": player_doc.get("first_name", existing_meta.get("first_name", "")),
                    "last_name": player_doc.get("last_name", existing_meta.get("last_name", "")),
                    "team": team_name,  # ✅ FIX: Use player_doc team name to match bracket
                }
                # ✅ FIX: Preserve team_id from tournament document first, then fallback to player_doc
                # This ensures team_id is always set (required for team stats aggregation)
                team_id = existing_meta.get("team_id") or player_doc.get("team_id")
                if team_id:
                    meta["team_id"] = str(team_id)
                elif player_doc.get("team"):
                    # ✅ FIX: If team_id not found, resolve from team name to ensure it's set
                    # teams_collection is already imported at module level
                    team_doc = teams_collection.find_one({"name": player_doc.get("team")})
                    if team_doc and team_doc.get("_id"):
                        meta["team_id"] = str(team_doc["_id"])
                        team_id = meta["team_id"]
                
                # Update tournament document with stat increments and metadata
                tournament_update: Dict[str, Any] = {
                    "$inc": tournament_inc_doc,
                    "$set": {
                        f"players.{str(query_pid)}.meta": meta,
                    }
                }
                
                # ✅ FIX: Preserve existing attributes and position_ratings if they exist
                if "attributes" in existing_player:
                    tournament_update["$set"][f"players.{str(query_pid)}.attributes"] = existing_player["attributes"]
                if "position_ratings" in existing_player:
                    tournament_update["$set"][f"players.{str(query_pid)}.position_ratings"] = existing_player["position_ratings"]
                
                # ✅ FIX: Check if game already applied (idempotency check)
                # Check if applied_games array exists and contains this token
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Checking idempotency, token: {token}")
                check_doc = tournaments_collection.find_one(
                    {"_id": tid},
                    {f"players.{str(query_pid)}.season.applied_games": 1}
                )
                if check_doc:
                    player_data = check_doc.get("players", {}).get(str(query_pid), {})
                    season_data = player_data.get("season", {})
                    applied_games = season_data.get("applied_games", [])
                    logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Existing applied_games: {applied_games}")
                    if isinstance(applied_games, list) and token in applied_games:
                        logger.warning(f"⚠️ [APPLY-STATS] Tournament mode - Player {query_pid}: Game {token} already in applied_games, skipping (idempotent)")
                        continue  # Already applied, skip
                
                # Apply the update with idempotency check
                # Use $nin (not in) to check if token is not in the applied_games array
                # Also handle case where applied_games doesn't exist yet
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Executing update_one with idempotency check (token not in applied_games)")
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: tournament_inc_doc has {len(tournament_inc_doc)} fields to increment")
                result = tournaments_collection.update_one(
                    {
                        "_id": tid,
                        "$or": [
                            {f"players.{str(query_pid)}.season.applied_games": {"$exists": False}},
                            {f"players.{str(query_pid)}.season.applied_games": {"$nin": [token]}}
                        ]
                    },
                    tournament_update,
                )
                logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Update result - matched_count: {result.matched_count}, modified_count: {result.modified_count}")
                
                # ✅ FIX: After incrementing, calculate per_game and percentages from updated stats
                # Only do this if the update was successful
                if result.modified_count > 0:
                    logger.info(f"✅ [APPLY-STATS] Tournament mode - Player {query_pid}: Stats updated successfully, reloading to calculate per_game and percentages")
                    # Reload the tournament document to get updated season stats
                    updated_tournament_doc = tournaments_collection.find_one(
                        {"_id": tid},
                        {f"players.{str(query_pid)}": 1}
                    )
                    if updated_tournament_doc:
                        updated_player = updated_tournament_doc.get("players", {}).get(str(query_pid), {})
                        updated_season = updated_player.get("season", {})
                        logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Updated season stats - GP: {updated_season.get('GP', 0)}, PTS: {updated_season.get('PTS', 0)}")
                        
                        # Calculate per_game and percentages
                        season_per_game = _per_game_block(updated_season)
                        season_percentages = _pct_block(updated_season)
                        logger.info(f"🔍 [APPLY-STATS] Tournament mode - Player {query_pid}: Calculated per_game and percentages, updating tournament document")
                        
                        # Update with calculated fields and mark as applied
                        tournaments_collection.update_one(
                            {"_id": tid},
                            {
                                "$set": {
                                    f"players.{str(query_pid)}.season.per_game": season_per_game,
                                    f"players.{str(query_pid)}.season.percentages": season_percentages,
                                },
                                "$addToSet": {
                                    f"players.{str(query_pid)}.season.applied_games": token,
                                }
                            }
                        )
                        logger.info(f"✅ [APPLY-STATS] Tournament mode - Player {query_pid}: per_game and percentages updated successfully")
                    else:
                        logger.error(f"❌ [APPLY-STATS] Tournament mode - Player {query_pid}: Failed to reload updated tournament document")
                else:
                    logger.warning(f"⚠️ [APPLY-STATS] Tournament mode - Player {query_pid}: Update did not modify document (matched_count: {result.matched_count}, modified_count: {result.modified_count})")
    
    # ✅ FIX: After processing all players from game summary, ensure ALL roster players from both teams are initialized
    # This ensures bench players (who didn't play) also have stats entries (with zeros)
    if tournament_id:
        try:
            tid = ObjectId(tournament_id)
        except Exception:
            tid = None
        if tid:
            # ✅ TASK 2: Log before calling to verify execution flow
            logger.info(f"🔍 [APPLY-STATS] About to call _ensure_all_roster_players_initialized for tournament_id: {tid}")
            print(f"🔍 [APPLY-STATS] About to call _ensure_all_roster_players_initialized for tournament_id: {tid}")
            _ensure_all_roster_players_initialized(summary, tid)
            logger.info(f"✅ [APPLY-STATS] _ensure_all_roster_players_initialized completed")
            print(f"✅ [APPLY-STATS] _ensure_all_roster_players_initialized completed")


def _ensure_all_roster_players_initialized(summary: Dict[str, Any], tournament_id: ObjectId) -> None:
    """
    Ensure all players from both teams' rosters are initialized in the tournament document.
    This ensures bench players (who didn't play) also have stats entries with zeros.
    
    Args:
        summary: Game summary with home_team and away_team
        tournament_id: Tournament ObjectId
    """
    # ✅ TASK 2: Add logging to verify function is called
    logger.info(f"🔍 [ENSURE-ROSTER] Function called for tournament_id: {tournament_id}")
    print(f"🔍 [ENSURE-ROSTER] Function called for tournament_id: {tournament_id}")
    
    home_team_obj = summary.get("home_team")
    away_team_obj = summary.get("away_team")
    
    # Extract team names
    home_team_name = None
    away_team_name = None
    
    if isinstance(home_team_obj, dict):
        home_team_name = home_team_obj.get("name")
    elif isinstance(home_team_obj, str):
        home_team_name = home_team_obj
    
    if isinstance(away_team_obj, dict):
        away_team_name = away_team_obj.get("name")
    elif isinstance(away_team_obj, str):
        away_team_name = away_team_obj
    
    if not home_team_name or not away_team_name:
        logger.warning(f"⚠️ [ENSURE-ROSTER] Cannot get team names from summary: home={home_team_name}, away={away_team_name}")
        print(f"⚠️ [ENSURE-ROSTER] Cannot get team names from summary: home={home_team_name}, away={away_team_name}")
        return
    
    logger.info(f"🔍 [ENSURE-ROSTER] Processing teams: {home_team_name} vs {away_team_name}")
    print(f"🔍 [ENSURE-ROSTER] Processing teams: {home_team_name} vs {away_team_name}")
    
    # Get tournament document to check existing players
    tournament_doc = tournaments_collection.find_one({"_id": tournament_id}, {"players": 1})
    existing_players = tournament_doc.get("players", {}) if tournament_doc else {}
    existing_count = len(existing_players)
    logger.info(f"🔍 [ENSURE-ROSTER] Tournament document has {existing_count} existing players")
    print(f"🔍 [ENSURE-ROSTER] Tournament document has {existing_count} existing players")
    
    # Load rosters for both teams
    _, home_roster = load_roster(home_team_name)
    _, away_roster = load_roster(away_team_name)
    home_roster_size = len(home_roster) if home_roster else 0
    away_roster_size = len(away_roster) if away_roster else 0
    logger.info(f"🔍 [ENSURE-ROSTER] Roster sizes: {home_team_name}={home_roster_size}, {away_team_name}={away_roster_size}")
    print(f"🔍 [ENSURE-ROSTER] Roster sizes: {home_team_name}={home_roster_size}, {away_team_name}={away_roster_size}")
    
    # Get team documents to resolve team_id
    home_team_doc = teams_collection.find_one({"name": home_team_name})
    away_team_doc = teams_collection.find_one({"name": away_team_name})
    
    home_team_id = str(home_team_doc["_id"]) if home_team_doc and home_team_doc.get("_id") else None
    away_team_id = str(away_team_doc["_id"]) if away_team_doc and away_team_doc.get("_id") else None
    
    players_initialized = 0
    players_already_exist = 0
    players_team_id_updated = 0
    
    # Initialize all home team players
    for player in home_roster:
        pid = str(player.get("_id"))
        # ✅ FIX: Always ensure meta.team_id is set, even if player already exists
        # This ensures team stats aggregation works correctly
        if pid in existing_players:
            existing_player = existing_players[pid]
            existing_meta = existing_player.get("meta", {})
            # Update team_id if missing (preserve existing season stats)
            if not existing_meta.get("team_id") and home_team_id:
                tournaments_collection.update_one(
                    {"_id": tournament_id},
                    {"$set": {f"players.{pid}.meta.team_id": home_team_id}}
                )
                players_team_id_updated += 1
            players_already_exist += 1
            continue
        
        # ✅ FIX: Only initialize if player doesn't exist (players should already be initialized in create_tournament)
        # But if somehow missing, initialize with empty season stats (preserve structure from create_tournament)
        meta = {
            "first_name": player.get("first_name", ""),
            "last_name": player.get("last_name", ""),
            "team": home_team_name,  # ✅ FIX: Store team name (not ObjectId) for bracket matching
        }
        if home_team_id:
            meta["team_id"] = home_team_id
        
        # ✅ FIX: Initialize season as empty dict (not zero_stats) to match create_tournament pattern
        # But preserve any existing season stats if player was partially initialized
        tournaments_collection.update_one(
            {"_id": tournament_id},
            {
                "$setOnInsert": {  # ✅ FIX: Only set if player doesn't exist (preserve existing data)
                    f"players.{pid}.meta": meta,
                    f"players.{pid}.season": {},
                    f"players.{pid}.attributes": player.get("attributes", {}),
                    f"players.{pid}.position_ratings": player.get("position_ratings", {}),
                }
            },
            upsert=True
        )
        players_initialized += 1
    
    # Initialize all away team players
    for player in away_roster:
        pid = str(player.get("_id"))
        # ✅ FIX: Always ensure meta.team_id is set, even if player already exists
        # This ensures team stats aggregation works correctly
        if pid in existing_players:
            existing_player = existing_players[pid]
            existing_meta = existing_player.get("meta", {})
            # Update team_id if missing (preserve existing season stats)
            if not existing_meta.get("team_id") and away_team_id:
                tournaments_collection.update_one(
                    {"_id": tournament_id},
                    {"$set": {f"players.{pid}.meta.team_id": away_team_id}}
                )
                players_team_id_updated += 1
            players_already_exist += 1
            continue
        
        # ✅ FIX: Only initialize if player doesn't exist (players should already be initialized in create_tournament)
        # But if somehow missing, initialize with empty season stats (preserve structure from create_tournament)
        meta = {
            "first_name": player.get("first_name", ""),
            "last_name": player.get("last_name", ""),
            "team": away_team_name,  # ✅ FIX: Store team name (not ObjectId) for bracket matching
        }
        if away_team_id:
            meta["team_id"] = away_team_id
        
        # ✅ FIX: Initialize season as empty dict (not zero_stats) to match create_tournament pattern
        # But preserve any existing season stats if player was partially initialized
        tournaments_collection.update_one(
            {"_id": tournament_id},
            {
                "$setOnInsert": {  # ✅ FIX: Only set if player doesn't exist (preserve existing data)
                    f"players.{pid}.meta": meta,
                    f"players.{pid}.season": {},
                    f"players.{pid}.attributes": player.get("attributes", {}),
                    f"players.{pid}.position_ratings": player.get("position_ratings", {}),
                }
            },
            upsert=True
        )
        players_initialized += 1
    
    # ✅ TASK 2: Always log results, even if no new players initialized
    total_players_checked = home_roster_size + away_roster_size
    logger.info(f"✅ [ENSURE-ROSTER] Complete - Initialized: {players_initialized}, Already existed: {players_already_exist}, Team ID updated: {players_team_id_updated}, Total checked: {total_players_checked}")
    print(f"✅ [ENSURE-ROSTER] Complete - Initialized: {players_initialized}, Already existed: {players_already_exist}, Team ID updated: {players_team_id_updated}, Total checked: {total_players_checked}")


def recompute_tournament_leaders(tournament_id: str, limit: int = 10) -> Dict[str, Any]:
    """Rebuild cached leaderboards for a tournament.

    Returns the computed leaderboards dict.  If the tournament is not found,
    an empty dict is returned.  Results are written back to the tournament
    document under the ``leaderboards`` field.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        return {}

    tourney = tournaments_collection.find_one({"_id": tid})
    if not tourney:
        return {}

    teams: set[str] = set()
    for round_matches in tourney.get("bracket", {}).values():
        for match in round_matches:
            teams.add(match.get("home_team"))
            teams.add(match.get("away_team"))
    teams.discard(None)

    players: list[Dict[str, Any]] = []
    # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
    tournament_players = tourney.get("players", {}) or tourney.get("player_stats", {})  # Backward compatibility
    for pid, pdata in tournament_players.items():
        # ✅ MIGRATION: Support both old (direct fields) and new (meta wrapper) structures
        meta = pdata.get("meta", {})
        team_name = meta.get("team") or pdata.get("team", "")
        if team_name not in teams:
            continue
        
        first_name = meta.get("first_name") or pdata.get("first_name", "")
        last_name = meta.get("last_name") or pdata.get("last_name", "")
        season_stats = pdata.get("season", {})
        
        players.append(
            {
                "player_id": str(pid),
                "first_name": first_name,
                "last_name": last_name,
                "team_name": team_name,
                "stats": season_stats,
            }
        )

    categories = [
        ("PTS", "MIN"),
        ("REB", "MIN"),
        ("AST", "MIN"),
        ("STL", "MIN"),
        ("BLK", "MIN"),
        ("TPM", "TPA"),
        ("FG%", "FGA"),
        ("FT%", "FTA"),
    ]

    def stat_val(stats: Dict[str, Any], key: str) -> float:
        if key == "FG%":
            makes = stats.get("FGM", 0)
            attempts = stats.get("FGA", 0)
            return (makes / attempts * 100) if attempts else 0.0
        if key == "FT%":
            makes = stats.get("FTM", 0)
            attempts = stats.get("FTA", 0)
            return (makes / attempts * 100) if attempts else 0.0
        if key == "TPM":
            return stats.get("3PTM", 0)
        if key == "TPA":
            return stats.get("3PTA", 0)
        return stats.get(key, 0)

    leaderboards: Dict[str, list] = {}
    for stat, tie_key in categories:
        entries = []
        for p in players:
            season = p.get("stats", {})
            value = stat_val(season, stat)
            tie_val = stat_val(season, tie_key) if tie_key else 0
            if stat == "FG%" and season.get("FGA", 0) == 0:
                continue
            if stat == "FT%" and season.get("FTA", 0) == 0:
                continue
            if stat == "TPM":
                attempts = season.get("3PTA", season.get("TPA", 0))
                if attempts == 0:
                    continue
            entries.append(
                {
                    "player_id": p["player_id"],
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "team_name": p.get("team_name", ""),
                    "value": value,
                    "_tie": tie_val,
                }
            )
        entries.sort(
            key=lambda x: (
                -x["value"],
                -x["_tie"],
                f"{x['first_name']} {x['last_name']}",
            )
        )
        top = []
        for idx, e in enumerate(entries[:limit], start=1):
            top.append(
                {
                    "rank": idx,
                    "player_id": e["player_id"],
                    "first_name": e["first_name"],
                    "last_name": e["last_name"],
                    "team_name": e["team_name"],
                    "value": e["value"],
                }
            )
        leaderboards[stat] = top

    tournaments_collection.update_one(
        {"_id": tid}, {"$set": {"leaderboards": leaderboards}}
    )
    return leaderboards


def rollup_game_to_franchise(franchise_id: str | ObjectId, game_id: str | ObjectId) -> None:
    """Aggregate a game's stats into a franchise document.

    The update is idempotent per ``game_id`` thanks to the ``processed_games``
    guard.  Per-player season and career totals are incremented, per-game
    averages and shooting percentages are recomputed within the ``season`` and
    ``career`` blocks, and ``game_id`` is appended to ``processed_games``.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    game = games_collection.find_one({"_id": game_id})
    if not game and isinstance(game_id, str):
        try:
            game = games_collection.find_one({"_id": ObjectId(game_id)})
        except Exception:
            game = None
    if not game:
        return

    players = game.get("players", [])
    box_score = game.get("box_score", {})
    team_map = {"home": game.get("home_team"), "away": game.get("away_team")}

    inc_doc: Dict[str, Any] = {}
    set_doc: Dict[str, Any] = {}

    for p in players:
        pid = str(p.get("playerId"))
        team_side = p.get("team")
        pos = p.get("pos")
        team_name = team_map.get(team_side)
        if not pid or not team_name:
            continue
        stat_block = box_score.get(team_name, {}).get(pos, p.get("stats", {}))
        for stat, val in _clean_stat_block(stat_block).items():
            # ✅ MIN special handling: Convert seconds to minutes (integer division)
            # Game MIN is tracked in seconds, but season/career MIN should be in minutes
            if stat == "MIN":
                val = val // 60  # Convert seconds to minutes (integer division)
            # ✅ SS&S: Write to players object (single source of truth), not player_stats
            inc_doc[f"players.{pid}.season.{stat}"] = inc_doc.get(
                f"players.{pid}.season.{stat}", 0
            ) + val
            inc_doc[f"players.{pid}.career.{stat}"] = inc_doc.get(
                f"players.{pid}.career.{stat}", 0
            ) + val
        inc_doc[f"players.{pid}.season.GP"] = inc_doc.get(
            f"players.{pid}.season.GP", 0
        ) + 1
        inc_doc[f"players.{pid}.career.GP"] = inc_doc.get(
            f"players.{pid}.career.GP", 0
        ) + 1

        # ✅ SS&S: Set meta in players object if not already present
        meta = players_collection.find_one(
            {"_id": pid}, {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1}
        )
        if meta:
            # Only set meta if it doesn't already exist (preserve existing meta)
            set_doc[f"players.{pid}.meta.first_name"] = meta.get("first_name", "")
            set_doc[f"players.{pid}.meta.last_name"] = meta.get("last_name", "")
            set_doc[f"players.{pid}.meta.team"] = meta.get("team", "")
            if meta.get("team_id"):
                set_doc[f"players.{pid}.meta.team_id"] = str(meta.get("team_id"))

    if not inc_doc:
        return

    # ✅ SS&S: Use applied_games (not processed_games) for consistency with finalize_game()
    update_doc: Dict[str, Any] = {
        "$inc": inc_doc,
        "$addToSet": {"applied_games": game_id},
    }
    if set_doc:
        update_doc["$set"] = set_doc

    # ✅ SS&S: Use applied_games (not processed_games) for consistency with finalize_game()
    result = db.franchises.find_one_and_update(
        {"_id": fid, "applied_games": {"$ne": game_id}},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        return

    # ✅ SS&S: Calculate per_game and percentages from players object (not player_stats)
    stats_doc: Dict[str, Any] = {}
    for p in players:
        pid = str(p.get("playerId"))
        pdata = result.get("players", {}).get(pid, {})
        season_totals = pdata.get("season", {})
        career_totals = pdata.get("career", {})
        # Store per_game and percentages in players object for easy access
        stats_doc[f"players.{pid}.season.per_game"] = _per_game_block(season_totals)
        stats_doc[f"players.{pid}.career.per_game"] = _per_game_block(career_totals)
        stats_doc[f"players.{pid}.season.percentages"] = _pct_block(season_totals)
        stats_doc[f"players.{pid}.career.percentages"] = _pct_block(career_totals)

    if stats_doc:
        db.franchises.update_one({"_id": fid}, {"$set": stats_doc})


def _update_offensive_play_season_stats(game: Dict[str, Any], mode: str, doc_id: str | ObjectId) -> None:
    """Update offensive play season_stats from game_stats for both teams.
    
    Extracts plays data from the game document and rolls up game_stats
    to season_stats for each offensive play. This is called at the end
    of games in tournament and franchise modes.
    
    Args:
        game: Game document from games collection
        mode: "tournament" or "franchise"
        doc_id: Tournament or franchise document ID
    """
    import logging
    logger = logging.getLogger(__name__)
    
    teams_obj = game.get("teams", {})
    if not teams_obj:
        logger.warning(f"⚠️ [UPDATE_PLAY_STATS] No teams object in game document")
        return
    
    logger.info(f"🔍 [UPDATE_PLAY_STATS] Processing {len(teams_obj)} teams, mode={mode}, doc_id={doc_id}")
    logger.info(f"🔍 [UPDATE_PLAY_STATS] Teams keys: {list(teams_obj.keys())}")
    
    from BackEnd.db import tournaments_collection, franchises_collection, teams_collection
    
    # ✅ FIX: For franchise mode, build team_name -> ObjectId team_id map (same as finalize_game)
    # Game document uses team_id strings (like "LITTLE_YORK") as keys, but franchise document
    # uses ObjectId strings (like "68c98b09674d3f9b04546b35") as keys in franchise_teams
    team_name_to_franchise_id: Dict[str, str] = {}
    game_key_to_franchise_id: Dict[str, str] = {}  # Map game document keys to franchise ObjectIds
    if mode == "franchise":
        try:
            doc_obj_id = ObjectId(doc_id) if isinstance(doc_id, str) else doc_id
            franchise_doc = franchises_collection.find_one({"_id": doc_obj_id}, {"franchise_teams": 1})
            if franchise_doc:
                franchise_teams = franchise_doc.get("franchise_teams", {})
                for team_id_str, team_data in franchise_teams.items():
                    # Look up team name from teams collection
                    try:
                        team_obj_id = ObjectId(team_id_str)
                        team_doc = teams_collection.find_one({"_id": team_obj_id}, {"name": 1, "team_id": 1})
                        if team_doc:
                            team_name = team_doc.get("name")
                            team_id_field = team_doc.get("team_id")  # e.g., "LITTLE_YORK"
                            if team_name:
                                team_name_to_franchise_id[team_name] = team_id_str
                            if team_id_field:
                                game_key_to_franchise_id[team_id_field] = team_id_str
                    except Exception:
                        continue
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Built team_name_to_franchise_id map: {team_name_to_franchise_id}")
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Built game_key_to_franchise_id map: {game_key_to_franchise_id}")
        except Exception as e:
            logger.error(f"❌ [UPDATE_PLAY_STATS] Error building team_name map: {e}")
    
    # Get team names from game document for matching
    home_team_data = game.get("home_team", {})
    away_team_data = game.get("away_team", {})
    home_team_name = home_team_data.get("name") if isinstance(home_team_data, dict) else None
    away_team_name = away_team_data.get("name") if isinstance(away_team_data, dict) else None
    home_team_id_key = game.get("home_team_id")  # e.g., "LITTLE_YORK"
    away_team_id_key = game.get("away_team_id")  # e.g., "FOUR_CORNERS"
    
    # Build update operations for all teams
    all_inc_doc: Dict[str, Any] = {}
    all_set_doc: Dict[str, Any] = {}
    
    for game_team_key, team_data in teams_obj.items():
        plays = team_data.get("plays", {})
        if not plays:
            logger.warning(f"⚠️ [UPDATE_PLAY_STATS] No plays found for team_key={game_team_key}")
            continue
        
        logger.info(f"🔍 [UPDATE_PLAY_STATS] Team {game_team_key} has {len(plays)} plays")
        
        # ✅ FIX: Resolve actual franchise team_id (ObjectId string) from game team key
        # Game document keys are team_id strings (like "LITTLE_YORK") or team names
        # We need to map to the ObjectId string used in franchise_teams
        actual_team_id = game_team_key  # Default to game key (works for tournament mode)
        if mode == "franchise":
            # Try multiple matching strategies
            if game_team_key in game_key_to_franchise_id:
                # Direct match: game_team_key is a team_id string (e.g., "LITTLE_YORK")
                actual_team_id = game_key_to_franchise_id[game_team_key]
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Mapped team_id '{game_team_key}' → franchise_id={actual_team_id}")
            elif game_team_key == home_team_id_key and home_team_name and home_team_name in team_name_to_franchise_id:
                # Match via home team name
                actual_team_id = team_name_to_franchise_id[home_team_name]
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Mapped home team '{home_team_name}' (key={game_team_key}) → franchise_id={actual_team_id}")
            elif game_team_key == away_team_id_key and away_team_name and away_team_name in team_name_to_franchise_id:
                # Match via away team name
                actual_team_id = team_name_to_franchise_id[away_team_name]
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Mapped away team '{away_team_name}' (key={game_team_key}) → franchise_id={actual_team_id}")
            elif game_team_key in team_name_to_franchise_id:
                # Direct match: game_team_key is a team name
                actual_team_id = team_name_to_franchise_id[game_team_key]
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Mapped team name '{game_team_key}' → franchise_id={actual_team_id}")
            else:
                logger.warning(f"⚠️ [UPDATE_PLAY_STATS] Could not map team '{game_team_key}' to franchise_id, using game_key as-is (update will likely fail)")
                actual_team_id = game_team_key
        
        plays_with_stats = 0
        
        for play_name, play_data in plays.items():
            game_stats = play_data.get("game_stats", {})
            if not game_stats:
                continue
            
            times_run = game_stats.get("times_run", 0)
            successes = game_stats.get("successes", 0)
            player_points = game_stats.get("player_points", {})
            
            if times_run > 0 or successes > 0 or player_points:
                plays_with_stats += 1
                logger.info(f"🔍 [UPDATE_PLAY_STATS] Play '{play_name}' (team={actual_team_id}): times_run={times_run}, successes={successes}, player_points={len(player_points)} players")
            
            # Base path for this play in the document (use actual_team_id, not game_team_key)
            if mode == "franchise":
                base_path = f"franchise_teams.{actual_team_id}.plays.{play_name}.season_stats"
            else:  # tournament
                base_path = f"teams.{actual_team_id}.plays.{play_name}.season_stats"
            
            # Increment times_run and successes
            if "times_run" in game_stats and game_stats["times_run"] > 0:
                all_inc_doc[f"{base_path}.times_run"] = game_stats["times_run"]
            if "successes" in game_stats and game_stats["successes"] > 0:
                all_inc_doc[f"{base_path}.successes"] = game_stats["successes"]
            
            # Merge player_points dict (increment each player's points)
            if player_points:
                for player_id, points in player_points.items():
                    if points > 0:
                        all_inc_doc[f"{base_path}.player_points.{player_id}"] = points
        
        logger.info(f"🔍 [UPDATE_PLAY_STATS] Team {actual_team_id}: {plays_with_stats} plays with stats")
    
    logger.info(f"🔍 [UPDATE_PLAY_STATS] Total: {len(all_inc_doc)} update operations across all teams")
    
    # Update the document if we have any stats to increment
    if all_inc_doc or all_set_doc:
        try:
            doc_obj_id = ObjectId(doc_id) if isinstance(doc_id, str) else doc_id
        except Exception as e:
            logger.error(f"❌ [UPDATE_PLAY_STATS] Invalid doc_id format: {doc_id}, error: {e}")
            return
        
        collection = franchises_collection if mode == "franchise" else tournaments_collection
        
        update_doc: Dict[str, Any] = {}
        if all_inc_doc:
            update_doc["$inc"] = all_inc_doc
        if all_set_doc:
            update_doc["$set"] = all_set_doc
        
        if update_doc:
            logger.info(f"🔍 [UPDATE_PLAY_STATS] Updating {mode} document {doc_obj_id} with {len(all_inc_doc)} increments")
            result = collection.update_one(
                {"_id": doc_obj_id},
                update_doc
            )
            logger.info(f"✅ [UPDATE_PLAY_STATS] Update result: matched={result.matched_count}, modified={result.modified_count}")
        else:
            logger.warning(f"⚠️ [UPDATE_PLAY_STATS] No update operations to perform (inc_doc and set_doc both empty)")
    else:
        logger.warning(f"⚠️ [UPDATE_PLAY_STATS] No stats to increment (all_inc_doc and all_set_doc both empty)")


def _update_defensive_playcall_season_stats(game: Dict[str, Any]) -> None:
    """Update defensive playcall season_stats from game_stats for both teams.
    
    Extracts scouting data from the game document and copies all game_stats
    values to season_stats for each defensive playcall (Man, 2-3 Zone, etc.).
    This is called at the end of games in tournament and franchise modes.
    """
    teams_obj = game.get("teams", {})
    if not teams_obj:
        return
    
    for team_id, team_data in teams_obj.items():
        scouting = team_data.get("scouting", {})
        defense_data = scouting.get("defense", {})
        
        if not defense_data:
            continue
        
        # Build $inc operations for all defensive playcall season_stats
        inc_doc: Dict[str, Any] = {}
        
        for playcall_name, playcall_data in defense_data.items():
            game_stats = playcall_data.get("game_stats", {})
            if not game_stats:
                continue
            
            # Base stats: used, success
            if "used" in game_stats:
                inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.used"] = game_stats["used"]
            if "success" in game_stats:
                inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.success"] = game_stats["success"]
            
            # Granular stats: vs_motion, vs_set, vs_inside, vs_attack, vs_outside
            for vs_key in ["vs_motion", "vs_set", "vs_inside", "vs_attack", "vs_outside"]:
                vs_data = game_stats.get(vs_key, {})
                if isinstance(vs_data, dict):
                    if "attempts" in vs_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{vs_key}.attempts"] = vs_data["attempts"]
                    if "success" in vs_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{vs_key}.success"] = vs_data["success"]
            
            # Combination stats: vs_motion_inside, vs_motion_attack, etc.
            for combo_key in ["vs_motion_inside", "vs_motion_attack", "vs_motion_outside",
                             "vs_set_inside", "vs_set_attack", "vs_set_outside"]:
                combo_data = game_stats.get(combo_key, {})
                if isinstance(combo_data, dict):
                    if "attempts" in combo_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{combo_key}.attempts"] = combo_data["attempts"]
                    if "success" in combo_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{combo_key}.success"] = combo_data["success"]
        
        # Update the team document if we have any stats to increment
        if inc_doc:
            # Find team by team_id (which is stored in the teams object key)
            # team_id is typically a string matching the team_id field in teams collection
            result = teams_collection.update_one(
                {"team_id": team_id},
                {"$inc": inc_doc}
            )
            
            # If team_id lookup failed, try finding by name as fallback
            if result.matched_count == 0:
                # Get team name from game document
                home_team_id = game.get("home_team_id")
                away_team_id = game.get("away_team_id")
                home_team_data = game.get("home_team", {})
                away_team_data = game.get("away_team", {})
                home_team_name = home_team_data.get("name") if isinstance(home_team_data, dict) else game.get("home_team", "")
                away_team_name = away_team_data.get("name") if isinstance(away_team_data, dict) else game.get("away_team", "")
                
                team_name = None
                if team_id == home_team_id:
                    team_name = home_team_name
                elif team_id == away_team_id:
                    team_name = away_team_name
                
                if team_name:
                    teams_collection.update_one(
                        {"name": team_name},
                        {"$inc": inc_doc}
                    )


def backfill_franchise_player_stats(franchise_id: str | ObjectId) -> None:
    """Migrate a franchise document from legacy ``players`` schema.

    Existing ``players`` entries are converted to the ``player_stats`` structure
    used by :func:`rollup_game_to_franchise`.  ``applied_games`` is renamed to
    ``processed_games`` and per-game/percentage helpers are generated for both
    season and career totals.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    doc = db.franchises.find_one({"_id": fid})
    if not doc:
        return

    player_stats: Dict[str, Any] = {}
    for pid, pdata in (doc.get("players") or {}).items():
        meta = pdata.get("meta", {})
        season_totals = _clean_stat_block(pdata.get("season", {}))
        career_totals = _clean_stat_block(pdata.get("career", {}))
        player_stats[pid] = {
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "team": meta.get("team", ""),
            "season": {
                **season_totals,
                "per_game": _per_game_block(season_totals),
                "percentages": _pct_block(season_totals),
            },
            "career": {
                **career_totals,
                "per_game": _per_game_block(career_totals),
                "percentages": _pct_block(career_totals),
            },
        }

    processed_games = [str(g) for g in doc.get("applied_games", []) if g]

    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                "player_stats": player_stats,
                "processed_games": processed_games,
            },
            "$unset": {"players": "", "applied_games": ""},
        },
    )


def finalize_game(
    game_id: str,
    *,
    mode: str | None = None,
    tournament_id: str | None = None,
    franchise_id: str | None = None,
) -> None:
    """Persist finished game stats into aggregate documents for supported modes.

    Scrimmage games (or calls with ``mode`` omitted) should not write any
    aggregate data.  They rely solely on :func:`update_game_stats` for per-turn
    box score updates.  Passing ``mode="scrimmage"`` therefore causes an early
    return so future modes don't unintentionally create aggregates.
    """
    if mode in (None, "scrimmage"):
        # Explicitly skip aggregation for scrimmages and unspecified modes.
        return
    if mode == "tournament" and tournament_id:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🔍 [FINALIZE_GAME] Tournament mode: game_id={game_id}, tournament_id={tournament_id}")
        print(f"🔍 [FINALIZE_GAME] Tournament mode: game_id={game_id}, tournament_id={tournament_id}")
        
        try:
            tid = ObjectId(tournament_id)
        except Exception as e:
            logger.error(f"❌ [FINALIZE_GAME] Invalid tournament_id format: {tournament_id}, error: {e}")
            print(f"❌ [FINALIZE_GAME] Invalid tournament_id format: {tournament_id}, error: {e}")
            return

        # Check if game is already in applied_games
        tournament_doc = tournaments_collection.find_one({"_id": tid}, {"applied_games": 1})
        if tournament_doc:
            applied_games = tournament_doc.get("applied_games", [])
            logger.info(f"🔍 [FINALIZE_GAME] Tournament {tournament_id} has {len(applied_games)} games in applied_games")
            print(f"🔍 [FINALIZE_GAME] Tournament {tournament_id} has {len(applied_games)} games in applied_games: {applied_games}")
            if game_id in applied_games or str(game_id) in [str(g) for g in applied_games]:
                logger.warning(f"⚠️ [FINALIZE_GAME] Game {game_id} already in applied_games, skipping (idempotent)")
                print(f"⚠️ [FINALIZE_GAME] Game {game_id} already in applied_games, skipping (idempotent)")
                return
        else:
            logger.error(f"❌ [FINALIZE_GAME] Tournament {tournament_id} not found")
            return

        logger.info(f"🔍 [FINALIZE_GAME] Attempting to add game_id to applied_games (format: {type(game_id).__name__})")
        result = tournaments_collection.update_one(
            {"_id": tid, "applied_games": {"$ne": game_id}},
            {"$addToSet": {"applied_games": game_id}},
        )

        logger.info(f"🔍 [FINALIZE_GAME] Update result: matched={result.matched_count}, modified={result.modified_count}")
        
        if result.modified_count == 0:
            # Check why it failed
            check_doc = tournaments_collection.find_one({"_id": tid}, {"applied_games": 1})
            if check_doc:
                applied = check_doc.get("applied_games", [])
                logger.warning(f"⚠️ [FINALIZE_GAME] Update had no effect. Tournament applied_games: {applied}, game_id={game_id} (type: {type(game_id).__name__})")
                # Try string comparison
                game_id_str = str(game_id)
                if game_id_str in [str(g) for g in applied]:
                    logger.warning(f"⚠️ [FINALIZE_GAME] Game_id found in applied_games as string match, skipping")
                else:
                    logger.error(f"❌ [FINALIZE_GAME] Game_id NOT in applied_games but update failed - possible format mismatch")
            return

        try:
            gid = ObjectId(game_id)
        except Exception:
            gid = game_id

        logger.info(f"🔍 [FINALIZE_GAME] Loading game document: game_id={game_id}, gid={gid}")
        game = games_collection.find_one({"_id": gid}) or {}
        
        if not game:
            logger.error(f"❌ [FINALIZE_GAME] Game document not found: game_id={game_id}, gid={gid}")
            return
        
        logger.info(f"✅ [FINALIZE_GAME] Game document found, calling apply_stats_from_summary")
        logger.info(f"🔍 [FINALIZE_GAME] Game has {len(game.get('players', []))} players in summary")
        logger.info(f"🔍 [FINALIZE_GAME] Tournament ID: {tournament_id}, will call _ensure_all_roster_players_initialized")
        
        apply_stats_from_summary(game, game_id, tournament_id)
        logger.info(f"✅ [FINALIZE_GAME] apply_stats_from_summary completed")
        
        recompute_tournament_leaders(tournament_id)
        logger.info(f"✅ [FINALIZE_GAME] recompute_tournament_leaders completed")
        
        # Update defensive playcall season_stats from game_stats
        _update_defensive_playcall_season_stats(game)
        
        # Update offensive play season_stats from game_stats
        _update_offensive_play_season_stats(game, "tournament", tid)
        
        logger.info(f"✅ [FINALIZE_GAME] Tournament stats finalization complete for game_id={game_id}")

        return

    if mode == "franchise" and franchise_id:
        import logging
        logger = logging.getLogger(__name__)
        print(f"🔍 [FINALIZE_GAME] Starting franchise stats rollup: game_id={game_id}, franchise_id={franchise_id}")
        logger.info(f"🔍 [FINALIZE_GAME] Starting franchise stats rollup: game_id={game_id}, franchise_id={franchise_id}")
        
        try:
            fid = ObjectId(franchise_id)
        except Exception as e:
            logger.error(f"❌ [FINALIZE_GAME] Invalid franchise_id format: {franchise_id}, error: {e}")
            return

        # Try to find game by game_id (could be ObjectId or string)
        game = games_collection.find_one({"_id": game_id})
        if not game and isinstance(game_id, str):
            try:
                game = games_collection.find_one({"_id": ObjectId(game_id)})
                logger.info(f"🔍 [FINALIZE_GAME] Found game using ObjectId conversion: {game_id}")
            except Exception as e:
                logger.warning(f"⚠️ [FINALIZE_GAME] Could not convert game_id to ObjectId: {game_id}, error: {e}")
                game = None
        
        if not game:
            logger.error(f"❌ [FINALIZE_GAME] Game not found in games collection: game_id={game_id}")
            # Try alternative lookup by week and teams
            logger.info(f"🔍 [FINALIZE_GAME] Attempting alternative lookup...")
            return

        home_name = game.get('home_team', {}).get('name') if isinstance(game.get('home_team'), dict) else game.get('home_team')
        away_name = game.get('away_team', {}).get('name') if isinstance(game.get('away_team'), dict) else game.get('away_team')
        print(f"✅ [FINALIZE_GAME] Found game: game_id={game.get('_id')}, week={game.get('week')}, home={home_name}, away={away_name}")
        logger.info(f"✅ [FINALIZE_GAME] Found game: game_id={game.get('_id')}, week={game.get('week')}, home={home_name}, away={away_name}")

        players = game.get("players", [])
        team_map = {"home": game.get("home_team"), "away": game.get("away_team")}
        
        # Extract team names from team_map (handle both dict and string)
        home_team_name = team_map.get("home")
        if isinstance(home_team_name, dict):
            home_team_name = home_team_name.get("name")
        away_team_name = team_map.get("away")
        if isinstance(away_team_name, dict):
            away_team_name = away_team_name.get("name")
        
        # ✅ SS&S: Build box_score from top level OR nested structure (like apply_stats_from_summary does)
        # summarize_game_state() stores box_score nested under home_team/away_team, not at top level
        box_score = game.get("box_score", {})
        if not box_score:
            # Build box_score from nested team objects (new structure from summarize_game_state)
            home_team_obj = game.get("home_team", {})
            away_team_obj = game.get("away_team", {})
            if home_team_obj and isinstance(home_team_obj, dict):
                home_team_name_from_obj = home_team_obj.get("name")
                if home_team_name_from_obj and "box_score" in home_team_obj:
                    box_score[home_team_name_from_obj] = home_team_obj.get("box_score", {})
            if away_team_obj and isinstance(away_team_obj, dict):
                away_team_name_from_obj = away_team_obj.get("name")
                if away_team_name_from_obj and "box_score" in away_team_obj:
                    box_score[away_team_name_from_obj] = away_team_obj.get("box_score", {})
        
        logger.info(f"🔍 [FINALIZE_GAME] Processing {len(players)} players, box_score keys: {list(box_score.keys())}, home_team: {home_team_name}, away_team: {away_team_name}")

        # ✅ SS&S: Build team_name -> team_id map from franchise_teams
        franchise_doc = db.franchises.find_one({"_id": fid}, {"franchise_teams": 1})
        franchise_teams = franchise_doc.get("franchise_teams", {}) if franchise_doc else {}
        team_name_to_id: Dict[str, str] = {}
        for team_id_str, team_data in franchise_teams.items():
            # Look up team name from teams collection
            try:
                team_obj_id = ObjectId(team_id_str)
                team_doc = teams_collection.find_one({"_id": team_obj_id}, {"name": 1})
                if team_doc:
                    team_name = team_doc.get("name")
                    if team_name:
                        team_name_to_id[team_name] = team_id_str
            except Exception:
                continue
        
        logger.info(f"🔍 [FINALIZE_GAME] Built team_name_to_id map: {team_name_to_id}")

        inc_doc: Dict[str, Any] = {}
        set_doc: Dict[str, Any] = {}
        players_processed = 0
        
        # ✅ SS&S: Process ALL players from box_score (not just lineup players from players array)
        # box_score structure: {team_name: {pos: {playerId, name, jersey, stats...}, ...}, ...}
        # This includes all players who participated (lineup + bench), not just final lineup
        processed_player_ids = set()  # Track processed players to avoid double-counting
        
        for team_name in [home_team_name, away_team_name]:
            if not team_name:
                continue
            team_box = box_score.get(team_name, {})
            if not team_box:
                logger.warning(f"⚠️ [FINALIZE_GAME] No box_score data for team: {team_name}")
                continue
            
            # Process all players in this team's box_score
            for pos_key, player_data in team_box.items():
                if not isinstance(player_data, dict):
                    continue
                pid = player_data.get("playerId")
                if not pid:
                    continue
                pid_str = str(pid)
                
                # Skip if already processed (avoid double-counting if same player appears multiple times)
                if pid_str in processed_player_ids:
                    continue
                processed_player_ids.add(pid_str)
                
                # Get stats from player_data (box_score includes all stats)
                stat_block = player_data
                if not stat_block:
                    logger.warning(f"⚠️ [FINALIZE_GAME] No stats found for player {pid_str} (team={team_name}, pos={pos_key})")
                    continue
                
                players_processed += 1
                for stat, val in _clean_stat_block(stat_block).items():
                    # Skip non-stat fields (playerId, name, jersey, etc.)
                    if stat in ["playerId", "name", "jersey", "x", "y", "coords", "team", "pos"]:
                        continue
                    # ✅ MIN special handling: Convert seconds to minutes (integer division)
                    # Game MIN is tracked in seconds, but season/career MIN should be in minutes
                    if stat == "MIN":
                        val = val // 60  # Convert seconds to minutes (integer division)
                    inc_doc[f"players.{pid_str}.season.{stat}"] = inc_doc.get(
                        f"players.{pid_str}.season.{stat}", 0
                    ) + val
                    inc_doc[f"players.{pid_str}.career.{stat}"] = inc_doc.get(
                        f"players.{pid_str}.career.{stat}", 0
                    ) + val
                
                # ✅ SS&S: Increment GP (games played) for all players who participated
                inc_doc[f"players.{pid_str}.season.GP"] = inc_doc.get(
                    f"players.{pid_str}.season.GP", 0
                ) + 1
                inc_doc[f"players.{pid_str}.career.GP"] = inc_doc.get(
                    f"players.{pid_str}.career.GP", 0
                ) + 1
                
                # ✅ SS&S: Set meta.team_id if team_name is in our map
                if team_name in team_name_to_id:
                    set_doc[f"players.{pid_str}.meta.team_id"] = team_name_to_id[team_name]
                    logger.debug(f"🔍 [FINALIZE_GAME] Setting meta.team_id for player {pid_str}: {team_name_to_id[team_name]}")
        
        logger.info(f"🔍 [FINALIZE_GAME] Processed {players_processed} players, {len(inc_doc)} stat increments, {len(set_doc)} meta fields to set")

        update: Dict[str, Any] = {"$addToSet": {"applied_games": game_id}}
        if inc_doc:
            update["$inc"] = inc_doc
            logger.info(f"🔍 [FINALIZE_GAME] Update doc has {len(inc_doc)} stat increments")
        else:
            logger.warning(f"⚠️ [FINALIZE_GAME] No stats to increment (inc_doc is empty)")
        
        # ✅ SS&S: Set meta fields (including team_id) if any
        if set_doc:
            update["$set"] = set_doc
            logger.info(f"🔍 [FINALIZE_GAME] Update doc has {len(set_doc)} meta fields to set")

        result = db.franchises.update_one(
            {"_id": fid, "applied_games": {"$ne": game_id}},
            update,
        )
        if result.modified_count == 0:
            logger.warning(f"⚠️ [FINALIZE_GAME] Update had no effect (modified_count=0). Game may already be in applied_games or franchise not found.")
            # Check if game is already applied
            franchise_check = db.franchises.find_one({"_id": fid}, {"applied_games": 1})
            if franchise_check:
                applied = franchise_check.get("applied_games", [])
                if game_id in applied:
                    logger.info(f"ℹ️ [FINALIZE_GAME] Game {game_id} already in applied_games, skipping (idempotent)")
                else:
                    logger.error(f"❌ [FINALIZE_GAME] Franchise found but update failed. applied_games={applied}, game_id={game_id}")
            return
        
        print(f"✅ [FINALIZE_GAME] Successfully updated franchise document: modified_count={result.modified_count}")
        logger.info(f"✅ [FINALIZE_GAME] Successfully updated franchise document: modified_count={result.modified_count}")

        apply_stats_from_summary(game, game_id)
        
        # Update defensive playcall season_stats from game_stats
        _update_defensive_playcall_season_stats(game)
        
        # Update offensive play season_stats from game_stats
        _update_offensive_play_season_stats(game, "franchise", fid)

        return

    return

def update_game_stats(game_id: str | None, deltas: Dict[str, Any], score: Dict[str, Any]) -> None:
    """Apply per-turn stat deltas to the ongoing game's document."""
    if not game_id or not deltas:
        return
    for pid, pdata in deltas.items():
        stats = pdata.get("stats", {})
        if not stats:
            continue
        inc_doc = {f"players.$.stats.{stat}": amt for stat, amt in stats.items()}
        set_doc: Dict[str, Any] = {}
        team_name = pdata.get("team")
        if team_name and team_name in score:
            set_doc[f"score.{team_name}"] = score[team_name]
        update_doc: Dict[str, Any] = {"$inc": inc_doc}
        if set_doc:
            update_doc["$set"] = set_doc
        games_collection.update_one(
            {"_id": game_id, "players.playerId": pid},
            update_doc,
        )
