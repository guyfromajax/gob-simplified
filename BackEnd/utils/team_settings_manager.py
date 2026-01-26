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
    
    try:
        # Resolve team_id to canonical format
        actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
        
        # Determine collection and document ID
        if mode == "single" and game_id:
            # Game-scoped save
            from BackEnd.db import games_collection
            collection = games_collection
            doc_id = game_id
            update_path = f"teams.{actual_team_id}.{settings_type}"
        elif mode == "franchise" and franchise_id:
            from BackEnd.db import franchises_collection
            collection = franchises_collection
            doc_id = franchise_id
            update_path = f"franchise_teams.{actual_team_id}.{settings_type}"
        elif mode == "tournament" and tournament_id:
            from BackEnd.db import tournaments_collection
            collection = tournaments_collection
            doc_id = tournament_id
            update_path = f"teams.{actual_team_id}.{settings_type}"
        else:
            logger.error(f"❌ [SAVE-TEAM-SETTINGS] Invalid mode/ID combination: mode={mode}, game_id={game_id}, franchise_id={franchise_id}, tournament_id={tournament_id}")
            return False, None, None
        
        # Validate if validation function provided
        if validate_fn:
            try:
                validate_fn(settings_data)
            except Exception as e:
                logger.error(f"❌ [SAVE-TEAM-SETTINGS] Validation failed: {e}")
                return False, None, None
        
        # Update database
        from bson import ObjectId
        try:
            doc_id_obj = ObjectId(doc_id)
        except:
            doc_id_obj = doc_id
        
        collection.update_one(
            {"_id": doc_id_obj},
            {"$set": {update_path: settings_data}}
        )
        
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
            if isinstance(request_playbook_settings, dict):
                # Check if request has valid playbook settings (has slot_assignments or other playbook keys)
                has_slot_assignments = bool(request_playbook_settings.get("slot_assignments"))
                has_playbook_keys = any(key in request_playbook_settings for key in ["motion", "set_play_inside", "set_play_attack", "set_play_outside", "zone_defense", "man_defense"])
                has_valid_request_playbook = has_slot_assignments or has_playbook_keys
                
                if has_valid_request_playbook:
                    if user_team_side == "home":
                        home_playbook = dict(request_playbook_settings)
                        slot_count = len(home_playbook.get("slot_assignments", {}))
                        logger.info(f"✅ [UNIFIED-SETTINGS] Using request playbook_settings for home team (user visited Playbooks): slot_assignments={slot_count}")
                    elif user_team_side == "away":
                        away_playbook = dict(request_playbook_settings)
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
