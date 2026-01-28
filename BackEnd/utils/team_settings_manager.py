"""
Unified Team Settings Manager

This module provides unified functions for saving and extracting team settings
(strategy_settings and playbook_settings) to ensure consistent team_id resolution
and reduce code duplication.

Key Functions:
- save_team_settings(): Unified save function for both settings types
- extract_team_settings(): Unified extract function for both settings types
- load_and_apply_team_settings_to_gamemanager(): Unified function to load both settings
  from DB/request and apply them to GameManager consistently
"""

import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


def save_team_settings(
    settings_type: str,  # "strategy_settings" or "playbook_settings"
    settings_data: dict,
    team_id: str,
    mode: str,
    game_id: Optional[str] = None,
    franchise_id: Optional[str] = None,
    tournament_id: Optional[str] = None,
    validate_fn: Optional[callable] = None,  # Optional validation function
    apply_to_gamemanager: bool = False
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Unified function to save team settings to the appropriate document.
    
    Args:
        settings_type: "strategy_settings" or "playbook_settings"
        settings_data: The settings dictionary to save
        team_id: Team identifier (name, ObjectId, or canonical team_id)
        mode: "single", "franchise", or "tournament"
        game_id: Optional game ID for game-scoped saves
        franchise_id: Optional franchise ID for franchise mode
        tournament_id: Optional tournament ID for tournament mode
        validate_fn: Optional validation function (for strategy_settings)
        apply_to_gamemanager: Whether to apply settings to cached GameManager
    
    Returns:
        Tuple of (success, actual_team_id, collection_name)
    """
    from BackEnd.api.gameplan_routes import normalize_team_id_to_canonical
    from bson import ObjectId
    
    try:
        # Determine collection and document ID first
        if mode == "single" and game_id:
            # Game-scoped save - resolve to canonical format
            actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
            from BackEnd.db import games_collection
            collection = games_collection
            doc_id = game_id
            update_path = f"teams.{actual_team_id}.{settings_type}"
            
            # Validate if validation function provided
            if validate_fn:
                try:
                    validate_fn(settings_data)
                except Exception as e:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Validation failed: {e}")
                    return False, None, None
            
            # Update database
            try:
                doc_id_obj = ObjectId(doc_id)
            except:
                doc_id_obj = doc_id
            
            collection.update_one(
                {"_id": doc_id_obj},
                {"$set": {update_path: settings_data}}
            )
            
        elif mode == "franchise":
            # ✅ PHASE 5.7: Use get_save_location_for_franchise_tournament to determine save location
            # This checks if game is active and saves to game doc, otherwise saves to FTD
            from BackEnd.api.gameplan_routes import get_save_location_for_franchise_tournament
            collection, doc_id, is_game_doc = get_save_location_for_franchise_tournament(
                mode=mode,
                game_id=game_id,
                franchise_id=franchise_id,
                tournament_id=tournament_id
            )
            logger.warning(f"🔍 [SAVE-TEAM-SETTINGS] franchise mode: game_id={game_id!r}, franchise_id={franchise_id!r}, team_id={team_id!r}, "
                f"settings_type={settings_type}, is_game_doc={is_game_doc}")
            
            # Validate if validation function provided
            if validate_fn:
                try:
                    validate_fn(settings_data)
                except Exception as e:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Validation failed: {e}")
                    return False, None, None
            
            if is_game_doc:
                # Saving to game doc - resolve to canonical format (game docs use canonical keys)
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
                update_path = f"teams.{actual_team_id}.{settings_type}"
                
                try:
                    doc_id_obj = ObjectId(doc_id)
                except:
                    doc_id_obj = doc_id
                
                collection.update_one(
                    {"_id": doc_id_obj},
                    {"$set": {update_path: settings_data}}
                )
            else:
                # ✅ FTD: Saving to FTD collection (FCC / pre-game). Always use authoritative user_team_object_id
                # from franchise doc so save and load use the same FTD doc (request team_id can differ).
                from BackEnd.db import franchise_team_data_collection, franchises_collection
                from BackEnd.api.franchise_routes import get_user_team_from_franchise
                try:
                    franchise_id_obj = ObjectId(franchise_id)
                except Exception as e:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Invalid franchise_id: {franchise_id}: {e}")
                    return False, None, None
                franchise_doc = franchises_collection.find_one(
                    {"_id": franchise_id_obj},
                    {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
                if not franchise_doc:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Franchise not found: {franchise_id}")
                    return False, None, None
                _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
                if not user_team_object_id:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] user_team_object_id missing in franchise {franchise_id}")
                    return False, None, None
                try:
                    team_id_obj = ObjectId(user_team_object_id)
                except Exception as e:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Invalid user_team_object_id: {user_team_object_id}: {e}")
                    return False, None, None
                actual_team_id = user_team_object_id
                logger.warning(
                    f"🔍 [SAVE-TEAM-SETTINGS] FCC/master save: using authoritative user_team_object_id={actual_team_id!r} "
                    f"(request team_id={team_id!r} ignored)"
                )
                pre = franchise_team_data_collection.count_documents(
                    {"franchise_id": franchise_id_obj, "team_id": team_id_obj}
                )
                result = franchise_team_data_collection.update_one(
                    {"franchise_id": franchise_id_obj, "team_id": team_id_obj},
                    {"$set": {settings_type: settings_data}},
                    upsert=True
                )
                logger.warning(
                    f"🔍 [SAVE-TEAM-SETTINGS] FTD update_one: franchise_id={franchise_id!r}, team_id={actual_team_id!r}, "
                    f"settings_type={settings_type}, matched={result.matched_count}, modified={result.modified_count}, "
                    f"upserted_id={result.upserted_id}, FTD_existed_before={pre}"
                )
                if settings_type == "strategy_settings":
                    logger.warning(f"🔍 [SAVE-TEAM-SETTINGS] strategy_settings keys: {list(settings_data.keys())}")
                else:
                    logger.warning(f"🔍 [SAVE-TEAM-SETTINGS] playbook_settings keys: {list(settings_data.keys())}, "
                        f"slot_assignments count={len(settings_data.get('slot_assignments') or {})}")
                logger.info(f"✅ [SAVE-TEAM-SETTINGS] Saved {settings_type} to FTD for team {actual_team_id}")
                return True, actual_team_id, "franchise_team_data"
                
        elif mode == "tournament":
            # ✅ PHASE 5.7: Use get_save_location_for_franchise_tournament to determine save location
            from BackEnd.api.gameplan_routes import get_save_location_for_franchise_tournament
            collection, doc_id, is_game_doc = get_save_location_for_franchise_tournament(
                mode=mode,
                game_id=game_id,
                franchise_id=franchise_id,
                tournament_id=tournament_id
            )
            
            # Validate if validation function provided
            if validate_fn:
                try:
                    validate_fn(settings_data)
                except Exception as e:
                    logger.error(f"❌ [SAVE-TEAM-SETTINGS] Validation failed: {e}")
                    return False, None, None
            
            if is_game_doc:
                # Saving to game doc - resolve to canonical format (game docs use canonical keys)
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
                update_path = f"teams.{actual_team_id}.{settings_type}"
            else:
                # Saving to tournament master doc - use ObjectId string directly
                actual_team_id = team_id
                update_path = f"teams.{actual_team_id}.{settings_type}"
            
            try:
                doc_id_obj = ObjectId(doc_id)
            except:
                doc_id_obj = doc_id
            
            collection.update_one(
                {"_id": doc_id_obj},
                {"$set": {update_path: settings_data}}
            )
        else:
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Invalid mode/ID combination: mode={mode}, game_id={game_id}, franchise_id={franchise_id}, tournament_id={tournament_id}")
            return False, None, None
        
        # Optionally apply to GameManager
        if apply_to_gamemanager and game_id:
            from BackEnd.api.api import ongoing_games
            gm = ongoing_games.get(game_id)
            if gm:
                if settings_type == "strategy_settings":
                    if gm.home_team.team_id == actual_team_id or gm.home_team.name == team_id:
                        gm.home_team.strategy_settings = dict(settings_data)
                    elif gm.away_team.team_id == actual_team_id or gm.away_team.name == team_id:
                        gm.away_team.strategy_settings = dict(settings_data)
                elif settings_type == "playbook_settings":
                    if gm.home_team.team_id == actual_team_id or gm.home_team.name == team_id:
                        gm.home_team.playbook_settings = dict(settings_data)
                    elif gm.away_team.team_id == actual_team_id or gm.away_team.name == team_id:
                        gm.away_team.playbook_settings = dict(settings_data)
        
        return True, actual_team_id, collection.name if hasattr(collection, 'name') else "unknown"
    
    except Exception as e:
        logger.error(f"❌ [SAVE-TEAM-SETTINGS] Error saving {settings_type}: {e}", exc_info=True)
        return False, None, None


def extract_team_settings(
    saved_doc: dict,
    team_identifier: str,  # Can be team name, ObjectId, or canonical team_id
    settings_type: str,  # "strategy_settings" or "playbook_settings"
    mode: str,
    game_doc: Optional[dict] = None  # For single mode team_id resolution
) -> Optional[dict]:
    """
    Unified function to extract team settings from a saved document.
    
    Uses the same team_id resolution logic as save_team_settings to ensure
    consistent key matching.
    
    Args:
        saved_doc: The saved document (game, tournament, or franchise)
        team_identifier: Team identifier (name, ObjectId, or canonical team_id)
        settings_type: "strategy_settings" or "playbook_settings"
        mode: "single", "franchise", or "tournament"
        game_doc: Optional game document for single mode resolution
    
    Returns:
        dict: The settings dictionary, or None if not found
    """
    from BackEnd.api.gameplan_routes import normalize_team_id_to_canonical
    
    try:
        # Get teams object based on mode
        if mode == "franchise":
            teams_obj = saved_doc.get("franchise_teams", {})
        elif mode == "tournament":
            teams_obj = saved_doc.get("teams", {})
        else:
            teams_obj = saved_doc.get("teams", {})
        
        # 🔍 DEBUG: Log available keys in teams object
        available_keys = list(teams_obj.keys()) if teams_obj else []
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Available team keys in saved_doc: {available_keys}")
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Looking for team_identifier='{team_identifier}', settings_type='{settings_type}', mode='{mode}'")
        
        if not teams_obj:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] No teams object found in saved document")
            return None
        
        # Resolve team_id to canonical format (same logic as save)
        actual_team_id = None
        
        if mode == "single":
            # Use normalize_team_id_to_canonical for single mode
            if game_doc:
                actual_team_id = normalize_team_id_to_canonical(team_identifier, mode, game_doc)
                logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Resolved via normalize_team_id_to_canonical: '{team_identifier}' → '{actual_team_id}'")
            else:
                # Fallback: try direct lookup, then name matching
                if team_identifier in teams_obj:
                    actual_team_id = team_identifier
                    logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Direct lookup found: '{team_identifier}'")
                else:
                    # Try name matching
                    for tid, team_data in teams_obj.items():
                        if team_data.get("name") == team_identifier:
                            actual_team_id = tid
                            logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Name match found: '{team_identifier}' → '{tid}'")
                            break
        else:
            # For franchise/tournament, try direct lookup first
            if team_identifier in teams_obj:
                actual_team_id = team_identifier
                logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Direct lookup found: '{team_identifier}'")
            else:
                # Try name matching
                for tid, team_data in teams_obj.items():
                    if team_data.get("name") == team_identifier:
                        actual_team_id = tid
                        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Name match found: '{team_identifier}' → '{tid}'")
                        break
        
        if not actual_team_id:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] Could not resolve team_id for '{team_identifier}'")
            logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Available keys: {available_keys}")
            logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Team names in teams_obj: {[team_data.get('name') for team_data in teams_obj.values()]}")
            return None
        
        # Extract settings
        team_data = teams_obj.get(actual_team_id, {})
        settings = team_data.get(settings_type)
        
        # 🔍 DEBUG: Log extraction result
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] Lookup result:")
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS]   actual_team_id = '{actual_team_id}'")
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS]   team_data exists: {bool(team_data)}")
        logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS]   {settings_type} exists: {bool(settings)}")
        if settings:
            if settings_type == "playbook_settings":
                slot_count = len(settings.get("slot_assignments", {}))
                logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS]   playbook_settings slot_assignments count: {slot_count}")
        
        if settings:
            logger.info(f"✅ [EXTRACT-TEAM-SETTINGS] Found {settings_type} for team_id={actual_team_id}")
            return settings
        else:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] No {settings_type} found for team_id={actual_team_id}")
            logger.warning(f"🔍 [EXTRACT-TEAM-SETTINGS] team_data keys: {list(team_data.keys()) if team_data else 'NO_TEAM_DATA'}")
            return None
    
    except Exception as e:
        logger.error(f"❌ [EXTRACT-TEAM-SETTINGS] Error extracting {settings_type}: {e}", exc_info=True)
        return None


def _transform_playbook_api_response_to_db_structure(playbook_settings: dict) -> dict:
    """
    Transform playbook settings from API response structure to database structure.
    
    API response structure (from /api/playbooks GET):
    {
        "slot_assignments": {...},
        "motion_dropdowns": {...},
        "position_filters": {...},
        "even_distribution_all": bool,
        "motion": [...],  # Play lists (not percentages)
        "set_play_inside": [...],
        "playbook_percentages": {
            "motion": {...},  # Actual percentages
            "set_play_inside": {...},
            ...
        }
    }
    
    Database structure (what GameManager expects):
    {
        "slot_assignments": {...},
        "motion_dropdowns": {...},
        "position_filters": {...},
        "even_distribution_all": bool,
        "motion": {...},  # Percentages dict (not play lists)
        "set_play_inside": {...},
        ...
    }
    """
    # ✅ FIX: Safety check - handle non-dict types (list, None, etc.)
    if not isinstance(playbook_settings, dict):
        logger.error(f"❌ [TRANSFORM-PLAYBOOK] playbook_settings is not a dict (type: {type(playbook_settings)}), returning empty dict")
        return {}
    
    # Check if this is the API response structure (has playbook_percentages nested)
    if "playbook_percentages" in playbook_settings:
        # Transform: extract percentages from nested structure
        percentages = playbook_settings.get("playbook_percentages", {})
        
        # Build database structure
        db_structure = {
            "slot_assignments": playbook_settings.get("slot_assignments", {}),
            "motion_dropdowns": playbook_settings.get("motion_dropdowns", {}),
            "position_filters": playbook_settings.get("position_filters", {}),
            "even_distribution_all": playbook_settings.get("even_distribution_all", False),
            # Flatten percentages to top level
            "motion": percentages.get("motion", {}),
            "set_play_inside": percentages.get("set_play_inside", {}),
            "set_play_attack": percentages.get("set_play_attack", {}),
            "set_play_outside": percentages.get("set_play_outside", {}),
            "zone_defense": percentages.get("zone_defense", {}),
            "man_defense": percentages.get("man_defense", {})
        }
        
        logger.info(f"✅ [UNIFIED-SETTINGS] Transformed API response structure to DB structure for playbook_settings")
        return db_structure
    
    # Already in database structure (or missing playbook_percentages key)
    # Check if it has motion at top level (database structure) or if it's missing percentages entirely
    if "motion" in playbook_settings and isinstance(playbook_settings.get("motion"), dict):
        # Already in database structure
        return playbook_settings
    
    # If we get here, it might be missing percentages - return as-is (will be handled by validation)
    return playbook_settings


def load_and_apply_team_settings_to_gamemanager(
    saved_doc: dict,
    home_team_name: str,
    away_team_name: str,
    mode: str,
    request_strategy_settings: Optional[dict] = None,
    request_playbook_settings: Optional[dict] = None,
    user_team_side: Optional[str] = None,
    gm=None  # Optional GameManager instance (if already created)
) -> Tuple[Dict, Dict, Dict, Dict]:
    """
    Unified function to load both strategy_settings and playbook_settings from DB/request
    and apply them to GameManager consistently.
    
    This ensures both settings types follow the same logic:
    1. Extract from DB
    2. Override with request if valid (user visited respective page)
    3. Apply to GameManager
    
    Args:
        saved_doc: The saved game document
        home_team_name: Home team name
        away_team_name: Away team name
        mode: "single", "franchise", or "tournament"
        request_strategy_settings: Optional strategy_settings from request (if user visited Game Plan)
        request_playbook_settings: Optional playbook_settings from request (if user visited Playbooks)
        user_team_side: "home" or "away" (for determining which team gets request settings)
        gm: Optional GameManager instance (if already created, settings will be applied directly)
    
    Returns:
        Tuple of (home_strategy, away_strategy, home_playbook, away_playbook)
    """
    from BackEnd.utils.team_settings_manager import extract_team_settings
    
    # Extract both settings from DB
    home_strategy_db = extract_team_settings(
        saved_doc=saved_doc,
        team_identifier=home_team_name,
        settings_type="strategy_settings",
        mode=mode,
        game_doc=saved_doc if mode == "single" else None
    ) or {}
    
    away_strategy_db = extract_team_settings(
        saved_doc=saved_doc,
        team_identifier=away_team_name,
        settings_type="strategy_settings",
        mode=mode,
        game_doc=saved_doc if mode == "single" else None
    ) or {}
    
    home_playbook_db = extract_team_settings(
        saved_doc=saved_doc,
        team_identifier=home_team_name,
        settings_type="playbook_settings",
        mode=mode,
        game_doc=saved_doc if mode == "single" else None
    ) or {}
    
    away_playbook_db = extract_team_settings(
        saved_doc=saved_doc,
        team_identifier=away_team_name,
        settings_type="playbook_settings",
        mode=mode,
        game_doc=saved_doc if mode == "single" else None
    ) or {}
    
    # Determine final settings (request overrides DB if valid)
    home_strategy = home_strategy_db
    away_strategy = away_strategy_db
    home_playbook = home_playbook_db
    away_playbook = away_playbook_db
    
    # Strategy_settings: Override with request if valid
    if request_strategy_settings and user_team_side:
        try:
            if isinstance(request_strategy_settings, dict):
                required_keys = ['offense', 'inside', 'attack', 'outside', 'tempo', 'defense', 'aggression', 'hc_trap', 'fc_press', 'rebounding']
                has_valid_request_settings = all(key in request_strategy_settings for key in required_keys)
                
                if has_valid_request_settings:
                    if user_team_side == "home":
                        home_strategy = dict(request_strategy_settings)
                        logger.info(f"✅ [UNIFIED-SETTINGS] Using request strategy_settings for home team (user visited Game Plan)")
                    elif user_team_side == "away":
                        away_strategy = dict(request_strategy_settings)
                        logger.info(f"✅ [UNIFIED-SETTINGS] Using request strategy_settings for away team (user visited Game Plan)")
        except Exception as e:
            logger.error(f"❌ [UNIFIED-SETTINGS] Error processing request strategy_settings: {e}, using DB settings", exc_info=True)
    
    # Playbook_settings: Override with request if valid (has slot_assignments or other keys)
    if request_playbook_settings and user_team_side:
        try:
            # ✅ FIX: Safety check - ensure it's a dict, not a list or other type
            if not isinstance(request_playbook_settings, dict):
                logger.error(f"❌ [UNIFIED-SETTINGS] request_playbook_settings is not a dict (type: {type(request_playbook_settings)}), skipping")
            else:
                # ✅ FIX: Transform API response structure to database structure
                transformed_playbook = _transform_playbook_api_response_to_db_structure(request_playbook_settings)
                
                # Check if request has valid playbook settings (has slot_assignments or other playbook keys)
                has_slot_assignments = bool(transformed_playbook.get("slot_assignments"))
                has_playbook_keys = any(key in transformed_playbook for key in ["motion", "set_play_inside", "set_play_attack", "set_play_outside", "zone_defense", "man_defense"])
                has_valid_request_playbook = has_slot_assignments or has_playbook_keys
                
                if has_valid_request_playbook:
                    if user_team_side == "home":
                        home_playbook = dict(transformed_playbook)
                        slot_count = len(home_playbook.get("slot_assignments", {}))
                        logger.info(f"✅ [UNIFIED-SETTINGS] Using request playbook_settings for home team (user visited Playbooks): slot_assignments={slot_count}")
                    elif user_team_side == "away":
                        away_playbook = dict(transformed_playbook)
                        slot_count = len(away_playbook.get("slot_assignments", {}))
                        logger.info(f"✅ [UNIFIED-SETTINGS] Using request playbook_settings for away team (user visited Playbooks): slot_assignments={slot_count}")
        except Exception as e:
            logger.error(f"❌ [UNIFIED-SETTINGS] Error processing request playbook_settings: {e}, using DB settings", exc_info=True)
    
    # Apply to GameManager if provided
    if gm:
        # Apply strategy_settings
        if home_strategy:
            gm.home_team.strategy_settings = dict(home_strategy)
        if away_strategy:
            gm.away_team.strategy_settings = dict(away_strategy)
        
        # Apply playbook_settings
        if home_playbook:
            gm.home_team.playbook_settings = dict(home_playbook)
        if away_playbook:
            gm.away_team.playbook_settings = dict(away_playbook)
        
        logger.info(f"✅ [UNIFIED-SETTINGS] Applied settings to GameManager: home_strategy={bool(home_strategy)}, away_strategy={bool(away_strategy)}, home_playbook={bool(home_playbook)}, away_playbook={bool(away_playbook)}")
    
    return home_strategy, away_strategy, home_playbook, away_playbook
