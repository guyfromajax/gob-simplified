import json
from pathlib import Path
from typing import Tuple, List, Dict

from BackEnd.db import players_collection, teams_collection, franchises_collection
from pymongo.errors import PyMongoError
from bson import ObjectId



def _load_from_db(team_name: str, franchise_id: str | None = None) -> Tuple[Dict | None, List[Dict]]:
    from bson import ObjectId  # ✅ FIX: Import at function level so it's available throughout
    try:
        # Find the team document by name
        team_doc = teams_collection.find_one({"name": team_name})
        # print(f"🔍 Team doc: {team_doc}")
        if not team_doc:
            print(f"❌ No team found: {team_name}")
            return None, []

        # ✅ FRANCHISE MODE: If franchise_id provided, load from franchise.players (trained attributes)
        if franchise_id:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"🔍 [ROSTER LOADER DEBUG] franchise_id={franchise_id}, team_name={team_name}")
            try:
                franchise_doc = franchises_collection.find_one({"_id": ObjectId(franchise_id)}, {"players": 1})
                if franchise_doc:
                    franchise_players = franchise_doc.get("players", {})
                    logger.warning(f"🔍 [ROSTER LOADER DEBUG] Found {len(franchise_players)} players in franchise document")
                    
                    # ✅ SS&S: Use team_doc.player_ids (canonical list) instead of iterating all players and matching
                    team_player_ids = team_doc.get("player_ids", [])
                    logger.warning(f"🔍 [ROSTER LOADER DEBUG] team_player_ids count: {len(team_player_ids)}")
                    logger.warning(f"🔍 [ROSTER LOADER DEBUG] team_player_ids type: {type(team_player_ids)}, value: {team_player_ids}")
                    
                    # ✅ VALIDATION: Fail fast with clear message
                    if not team_player_ids:
                        logger.error(f"❌ [ROSTER LOADER] team_player_ids is empty! team_doc keys: {list(team_doc.keys())}")
                        # Fall through to universal collection
                    elif not isinstance(team_player_ids, (list, tuple)):
                        logger.error(f"❌ [ROSTER LOADER] team_player_ids is not a list! Type: {type(team_player_ids)}, Value: {team_player_ids}")
                        # Fall through to universal collection
                    else:
                        # Build players list from franchise.players using team's player_ids
                        players = []
                        logger.warning(f"🔍 [ROSTER LOADER DEBUG] Starting loop over {len(team_player_ids)} player IDs")
                        
                        for idx, pid in enumerate(team_player_ids):
                            try:
                                # ✅ LOG: Immediately inside loop (no conditions) to confirm it runs
                                logger.warning(f"🔍 [ROSTER LOADER DEBUG] Loop iteration {idx+1}/{len(team_player_ids)}: pid={pid}, type={type(pid)}")
                                
                                pid_str = str(pid)
                                
                                # ✅ VALIDATION: Check if player exists in franchise.players
                                franchise_player_data = franchise_players.get(pid_str, {})
                                if not franchise_player_data:
                                    logger.error(f"❌ [ROSTER LOADER] Player {pid_str} not found in franchise.players. Available keys (first 5): {list(franchise_players.keys())[:5]}")
                                    continue
                                
                                # ✅ VALIDATION: Check if attributes exist
                                franchise_attrs = franchise_player_data.get("attributes", {})
                                if not franchise_attrs:
                                    logger.error(f"❌ [ROSTER LOADER] Player {pid_str} has no attributes in franchise.players! Keys: {list(franchise_player_data.keys())}")
                                    continue
                                
                                # Get base player data from universal collection (for bio data: height, weight, jersey, year)
                                base_player = players_collection.find_one({"_id": ObjectId(pid_str)})
                                if not base_player:
                                    logger.error(f"❌ [ROSTER LOADER] Player {pid_str} not found in universal collection")
                                    continue
                                
                                # Merge franchise-specific attributes into base player
                                base_player = dict(base_player)  # Convert to dict for modification
                                
                                # ✅ VALIDATION: Ensure franchise_attrs is a dict
                                if not isinstance(franchise_attrs, dict):
                                    logger.error(f"❌ [ROSTER LOADER] franchise_attrs is not a dict! Type: {type(franchise_attrs)}, Value: {franchise_attrs}")
                                    continue
                                
                                # ✅ DEBUG: Log attribute values for ALL players (no conditions)
                                meta = franchise_player_data.get("meta", {})
                                player_name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
                                universal_sh = base_player.get("attributes", {}).get("SH", "MISSING")
                                franchise_sh = franchise_attrs.get("SH", "MISSING")
                                logger.warning(f"🔍 [ROSTER LOADER DEBUG] {player_name} ({pid_str}): universal SH={universal_sh}, franchise SH={franchise_sh}")
                                
                                # ✅ VALIDATION: Check if SH attribute exists in franchise_attrs
                                if "SH" not in franchise_attrs:
                                    logger.error(f"❌ [ROSTER LOADER] SH attribute missing in franchise_attrs for {player_name}! Available attrs: {list(franchise_attrs.keys())[:10]}")
                                
                                # Overwrite base player attributes with franchise attributes
                                base_player["attributes"] = franchise_attrs
                                
                                # ✅ DEBUG: Log after overwrite (no conditions)
                                after_sh = base_player.get("attributes", {}).get("SH", "MISSING")
                                logger.warning(f"🔍 [ROSTER LOADER DEBUG] {player_name} AFTER overwrite: SH={after_sh}")
                                
                                franchise_position_ratings = franchise_player_data.get("position_ratings", {})
                                if franchise_position_ratings:
                                    base_player["position_ratings"] = franchise_position_ratings
                                
                                players.append(base_player)
                                logger.warning(f"🔍 [ROSTER LOADER DEBUG] Successfully added {player_name} to players list (total: {len(players)})")
                                
                            except Exception as e:
                                # ✅ EXCEPTION HANDLING: Detailed error messages
                                logger.error(f"❌ [ROSTER LOADER] Exception processing player {pid} (idx {idx}): {type(e).__name__}: {str(e)}")
                                import traceback
                                logger.error(f"❌ [ROSTER LOADER] Traceback: {traceback.format_exc()}")
                                continue
                        
                        logger.warning(f"🔍 [ROSTER LOADER DEBUG] Loop completed. Returning {len(players)} players from franchise.players")
                        if players:
                            logger.warning(f"🔍 [ROSTER LOADER DEBUG] ✅ SUCCESS: Returning {len(players)} franchise players")
                            return team_doc, players
                        else:
                            logger.error(f"❌ [ROSTER LOADER] Loop completed but players list is empty! This should not happen.")
                else:
                    logger.warning(f"🔍 [ROSTER LOADER DEBUG] Franchise document not found for franchise_id={franchise_id}")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️ Error loading franchise players for {team_name}: {e}")
                import traceback
                logger.warning(f"⚠️ Traceback: {traceback.format_exc()}")

        # Fallback: Query players by team name directly in the players collection (universal)
        players = list(players_collection.find({"team": team_name}))
        # print(f"✅ Loaded {len(players)} players for {team_name} from DB")
        # print(f"🔍 Players: {players}")

        return team_doc, players

    except PyMongoError as e:
        print(f"⚠️ MongoDB roster lookup failed for {team_name}: {e}")
        return None, []



def _team_file_path(team_name: str) -> Path:
    """Return the path to the bundled roster JSON for ``team_name``.

    Test environments (and local development without Mongo) rely on the
    repository's ``teams`` directory which lives at the project root rather
    than inside ``BackEnd``.  The previous implementation assumed the latter
    which meant we never discovered the JSON files, leaving the roster empty
    and causing any access to ``team.lineup["C"]`` to explode during opening
    tip logic.  To make the loader resilient we walk the parent directories
    until we find the first ``teams`` folder that contains the requested
    roster file and fall back to the project root if necessary.
    """

    snake = team_name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{snake}.json"
    current = Path(__file__).resolve()

    for parent in current.parents:
        candidate = parent / "teams" / filename
        if candidate.exists():
            return candidate

    # Preserve the old behaviour (which effectively pointed one level up) so
    # that callers still receive a sensible path even if the file is missing.
    return current.parents[1] / "teams" / filename


def _load_from_file(team_name: str) -> Tuple[Dict | None, List[Dict]]:
    path = _team_file_path(team_name)
    if not path.exists():
        return None, []
    try:
        with open(path) as f:
            data = json.load(f)
        return data, data.get("players", [])
    except Exception as e:
        print(f"❌ Failed to load roster from file for {team_name}: {e}")
        return None, []


def load_roster(team_name: str, franchise_id: str | None = None) -> Tuple[Dict | None, List[Dict]]:
    team, players = _load_from_db(team_name, franchise_id)
    if players:
        return team, players
    file_team, file_players = _load_from_file(team_name)
    if file_players:
        return file_team or team, file_players
    return team, players
