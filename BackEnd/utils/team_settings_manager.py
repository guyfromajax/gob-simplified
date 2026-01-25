"""
Unified team settings save/extract functions for strategy_settings and playbook_settings.

This module provides a single code path for saving and extracting team settings,
eliminating duplicate logic and ensuring consistent team_id resolution across all settings types.
"""

import logging
from typing import Optional, Dict, Any, Callable
from bson import ObjectId

logger = logging.getLogger(__name__)


def save_team_settings(
    settings_type: str,  # "strategy_settings" or "playbook_settings"
    settings_data: dict,
    team_id: str,
    mode: str,
    game_id: Optional[str] = None,
    franchise_id: Optional[str] = None,
    tournament_id: Optional[str] = None,
    validate_fn: Optional[Callable[[dict], bool]] = None,
    apply_to_gamemanager: bool = True
) -> tuple[bool, str, str]:
    """
    Unified function to save team settings (strategy_settings or playbook_settings).
    
    Args:
        settings_type: "strategy_settings" or "playbook_settings"
        settings_data: The settings dictionary to save
        team_id: Team identifier (will be normalized)
        mode: "single", "franchise", or "tournament"
        game_id: Optional game ID for game-scoped saves
        franchise_id: Optional franchise ID
        tournament_id: Optional tournament ID
        validate_fn: Optional validation function for settings_data
        apply_to_gamemanager: Whether to apply to cached GameManager if available
    
    Returns:
        tuple: (success: bool, actual_team_id: str, collection_name: str)
    """
    from BackEnd.api.gameplan_routes import (
        get_collection_and_doc_id,
        get_save_location_for_franchise_tournament,
        get_team_settings_path,
        ensure_team_objects_exist,
        normalize_team_id_to_canonical
    )
    from BackEnd.api.franchise_routes import get_user_team_from_franchise
    from BackEnd.api.tournament_routes import get_user_team_from_tournament
    from BackEnd.db import games_collection
    
    try:
        # Validate settings if validation function provided
        if validate_fn and not validate_fn(settings_data):
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Validation failed for {settings_type}")
            return False, None, None
        
        # Get collection and doc_id
        collection, doc_id = get_collection_and_doc_id(
            mode,
            franchise_id,
            tournament_id,
            game_id
        )
        
        # Load document
        if mode == "single":
            doc = collection.find_one({"_id": doc_id})
            if not doc:
                try:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
        else:
            if mode == "franchise":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            elif mode == "tournament":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
        
        if not doc:
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Document not found: {mode}={doc_id}")
            return False, None, None
        
        # Resolve team_id to canonical format
        actual_team_id = team_id
        
        if mode == "franchise":
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                logger.error(f"❌ [SAVE-TEAM-SETTINGS] User team not found in franchise document")
                return False, None, None
            actual_team_id = user_team_object_id
        elif mode == "tournament":
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                logger.error(f"❌ [SAVE-TEAM-SETTINGS] User team not found in tournament document")
                return False, None, None
            actual_team_id = user_team_object_id
        else:
            # Single mode: normalize to canonical
            actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
            
            # Verify resolved team_id exists in document
            teams = doc.get("teams", {})
            if actual_team_id not in teams:
                logger.error(f"❌ [SAVE-TEAM-SETTINGS] Resolved team_id '{actual_team_id}' not found in teams object!")
                return False, None, None
        
        # Ensure team objects exist
        ensure_team_objects_exist(
            mode, doc_id, actual_team_id,
            franchise_doc=doc if mode == "franchise" else None,
            tournament_doc=doc if mode == "tournament" else None
        )
        
        # Reload document after ensure_team_objects_exist
        if mode == "franchise":
            doc = collection.find_one(
                {"_id": ObjectId(doc_id)},
                {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
            )
        elif mode == "tournament":
            doc = collection.find_one(
                {"_id": ObjectId(doc_id)},
                {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
            )
        elif mode == "single":
            doc = collection.find_one(
                {"_id": doc_id},
                {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
            )
            if not doc:
                try:
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                    )
                except:
                    pass
        
        if not doc:
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Document not found after reload: {mode}={doc_id}")
            return False, None, None
        
        # Determine save location (game doc vs master doc) for franchise/tournament
        save_to_game_doc = False
        game_doc_team_id = actual_team_id
        if mode in ["franchise", "tournament"]:
            save_collection, save_doc_id, save_to_game_doc = get_save_location_for_franchise_tournament(
                mode,
                game_id,
                franchise_id,
                tournament_id
            )
            if save_to_game_doc:
                collection = save_collection
                doc_id = save_doc_id
                # Resolve team_id from game document
                try:
                    game_doc = games_collection.find_one(
                        {"_id": save_doc_id},
                        {"teams": 1, "home_team": 1, "away_team": 1, "_id": 1}
                    )
                    if not game_doc:
                        try:
                            game_doc = games_collection.find_one(
                                {"_id": ObjectId(save_doc_id)},
                                {"teams": 1, "home_team": 1, "away_team": 1, "_id": 1}
                            )
                        except:
                            pass
                    
                    if game_doc:
                        # Find team_id in game doc that matches user team
                        user_team_name = None
                        if mode == "franchise":
                            user_team_name, _ = get_user_team_from_franchise(doc)
                        elif mode == "tournament":
                            user_team_name, _ = get_user_team_from_tournament(doc)
                        
                        if user_team_name:
                            game_teams = game_doc.get("teams", {})
                            for tid, team_obj in game_teams.items():
                                if team_obj.get("name") == user_team_name:
                                    game_doc_team_id = tid
                                    break
                except Exception as e:
                    logger.warning(f"⚠️ [SAVE-TEAM-SETTINGS] Error resolving game doc team_id: {e}")
                    game_doc_team_id = actual_team_id
        
        # Build update path
        if save_to_game_doc:
            update_path = f"teams.{game_doc_team_id}.{settings_type}"
        else:
            update_path = f"{get_team_settings_path(mode, actual_team_id)}.{settings_type}"
        
        # Save to database
        if mode == "single":
            # Try both UUID string and ObjectId formats
            try:
                result = collection.update_one(
                    {"_id": doc_id},
                    {"$set": {update_path: settings_data}}
                )
                if result.matched_count == 0:
                    result = collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {update_path: settings_data}}
                    )
            except:
                result = collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {update_path: settings_data}}
                )
        else:
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {update_path: settings_data}}
            )
        
        if result.matched_count == 0:
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Failed to save {settings_type}: document not found")
            return False, None, None
        
        # Apply to GameManager if requested and game is in cache
        if apply_to_gamemanager and game_id and mode == "single":
            try:
                from BackEnd.api.api import ongoing_games
                gm = ongoing_games.get(game_id)
                if gm:
                    target_team = None
                    if actual_team_id == gm.home_team.team_id:
                        target_team = gm.home_team
                    elif actual_team_id == gm.away_team.team_id:
                        target_team = gm.away_team
                    
                    if target_team:
                        if settings_type == "strategy_settings":
                            default_settings = target_team._init_strategy_settings()
                            target_team.strategy_settings = {**default_settings, **settings_data}
                        else:
                            target_team.playbook_settings = settings_data
                        logger.info(f"✅ [SAVE-TEAM-SETTINGS] Applied {settings_type} to cached GameManager")
            except Exception as e:
                logger.warning(f"⚠️ [SAVE-TEAM-SETTINGS] Error applying to GameManager: {e}")
        
        return True, actual_team_id, collection.name
    
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
        
        if not teams_obj:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] No teams object found in saved document")
            return None
        
        # Resolve team_id to canonical format (same logic as save)
        actual_team_id = None
        
        if mode == "single":
            # Use normalize_team_id_to_canonical for single mode
            if game_doc:
                actual_team_id = normalize_team_id_to_canonical(team_identifier, mode, game_doc)
            else:
                # Fallback: try direct lookup, then name matching
                if team_identifier in teams_obj:
                    actual_team_id = team_identifier
                else:
                    # Try name matching
                    for tid, team_data in teams_obj.items():
                        if team_data.get("name") == team_identifier:
                            actual_team_id = tid
                            break
        else:
            # For franchise/tournament, try direct lookup first
            if team_identifier in teams_obj:
                actual_team_id = team_identifier
            else:
                # Try name matching
                for tid, team_data in teams_obj.items():
                    if team_data.get("name") == team_identifier:
                        actual_team_id = tid
                        break
        
        if not actual_team_id:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] Could not resolve team_id for '{team_identifier}'")
            return None
        
        # Extract settings
        team_data = teams_obj.get(actual_team_id, {})
        settings = team_data.get(settings_type)
        
        if settings:
            logger.info(f"✅ [EXTRACT-TEAM-SETTINGS] Found {settings_type} for team_id={actual_team_id}")
            return settings
        else:
            logger.warning(f"⚠️ [EXTRACT-TEAM-SETTINGS] No {settings_type} found for team_id={actual_team_id}")
            return None
    
    except Exception as e:
        logger.error(f"❌ [EXTRACT-TEAM-SETTINGS] Error extracting {settings_type}: {e}", exc_info=True)
        return None

