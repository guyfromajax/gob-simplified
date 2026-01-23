from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db, games_collection
from BackEnd.api.franchise_routes import get_user_team_from_franchise
from BackEnd.api.tournament_routes import get_user_team_from_tournament

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

# ✅ CORS FIX: Removed explicit OPTIONS handlers - CORS middleware handles preflight automatically
# The middleware configured in api.py properly handles CORS for all routes including these
# Explicit handlers were causing conflicts by using "*" with credentials (not allowed by CORS spec)

@router.get("/game-plan.html")
def serve_game_plan_html():
    """Return the game plan page so query params work in production."""
    return FileResponse(STATIC_DIR / "game-plan.html")

@router.get("/playbooks.html")
def serve_playbooks_html():
    """Return the playbooks page so query params work in production."""
    return FileResponse(STATIC_DIR / "playbooks.html")

class GamePlanSettings(BaseModel):
    strategy_settings: dict[str, int]

class GamePlanRequest(BaseModel):
    mode: str  # "franchise", "tournament", "single"
    team_id: str
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None

class GamePlanUpdateRequest(BaseModel):
    mode: str
    team_id: str
    strategy_settings: dict[str, int]
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None


def validate_settings(strategy_settings: dict):
    """Validate that settings are integers 0-4 and offense not all zero."""
    # Validate strategy_settings (defense/general)
    for key, value in strategy_settings.items():
        if not isinstance(value, int) or value < 0 or value > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy setting '{key}' must be an integer between 0 and 4"
            )
    
    # Ensure at least one offense setting is above 0 (offense, inside, outside, attack)
    offense_keys = ["offense", "inside", "outside", "attack"]
    offense_values = [strategy_settings.get(key, 0) for key in offense_keys]
    if all(v == 0 for v in offense_values):
        raise HTTPException(
            status_code=400,
            detail="At least one Offense setting must be above 'Never'. Please increase any Offense slider."
        )


def get_default_settings():
    """Return default settings (all set to 2 = Normal)."""
    return {
        "strategy_settings": {
            "offense": 2,  # Motion vs Set Play split (0=motion only, 4=set plays only)
            "inside": 2,   # Inside focus preference
            "attack": 2,  # Attack focus preference
            "outside": 2, # Outside focus preference
            "fast_breaks": 2,
            "defense": 2,
            "aggression": 2,
            "hc_trap": 2,  # Half court trap (matches frontend key)
            "fc_press": 2, # Full court press (matches frontend key)
            "rebounding": 2
            # Note: tempo is initialized randomly per game, not stored in game plan settings
        }
    }


def get_collection_and_doc_id(mode: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None):
    """
    ✅ PHASE 5.5: Helper to get collection and doc_id based on mode.
    
    Returns:
        tuple: (collection, doc_id) where doc_id is normalized
    """
    # ✅ PHASE 5.5: Normalize mode (strip whitespace, lowercase) to handle edge cases
    mode = mode.strip().lower() if mode else ""
    
    if mode == "franchise":
        if not franchise_id:
            raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
        return db.franchises, franchise_id
    elif mode == "tournament":
        if not tournament_id:
            raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
        return db.tournaments, tournament_id
    elif mode == "single":
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id required for single game mode")
        from BackEnd.utils.game_id_utils import normalize_game_id
        normalized_game_id = normalize_game_id(game_id)
        return db.games, normalized_game_id
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")


def get_team_settings_path(mode: str, team_id: str) -> str:
    """
    ✅ PHASE 5.5: Helper to get the MongoDB update path for team settings.
    
    Returns:
        str: Update path like "franchise_teams.{team_id}.playbook_settings" or "teams.{team_id}.playbook_settings"
    """
    if mode == "franchise":
        return f"franchise_teams.{team_id}"
    else:
        # Tournament and single both use "teams"
        return f"teams.{team_id}"


def get_save_location_for_franchise_tournament(mode: str, game_id: str = None, franchise_id: str = None, tournament_id: str = None):
    """
    ✅ PHASE 5.7: Determine save location for franchise/tournament mode.
    
    If game_id is provided AND game exists AND game is active (quarter > 0):
        Save to game doc (game-specific settings)
    Else:
        Save to franchise/tournament doc (master settings)
    
    Args:
        mode: Game mode ("franchise" or "tournament")
        game_id: Optional game ID
        franchise_id: Franchise ID (for franchise mode)
        tournament_id: Tournament ID (for tournament mode)
    
    Returns:
        tuple: (collection, doc_id, is_game_doc) where:
            - collection: MongoDB collection to save to
            - doc_id: Document ID to save to
            - is_game_doc: True if saving to game doc, False if saving to master doc
    """
    from BackEnd.db import games_collection, franchises_collection, tournaments_collection
    
    # If no game_id provided, always save to master
    if not game_id:
        if mode == "franchise":
            return franchises_collection, franchise_id, False
        elif mode == "tournament":
            return tournaments_collection, tournament_id, False
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode for get_save_location: {mode}")
    
    # Check if game exists and is active
    try:
        game_doc = games_collection.find_one(
            {"_id": game_id},
            {"quarter": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "_id": 1}
        )
        if not game_doc:
            # Try as ObjectId
            try:
                game_doc = games_collection.find_one(
                    {"_id": ObjectId(game_id)},
                    {"quarter": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "_id": 1}
                )
            except:
                pass
        
        if game_doc:
            # Verify game belongs to this franchise/tournament
            game_mode = game_doc.get("mode")
            game_franchise_id = game_doc.get("franchise_id")
            game_tournament_id = game_doc.get("tournament_id")
            
            if mode == "franchise":
                if game_mode == "franchise" and str(game_franchise_id) == str(franchise_id):
                    quarter = game_doc.get("quarter", 0)
                    if quarter > 0:
                        # Game is active - save to game doc
                        return games_collection, game_id, True
            elif mode == "tournament":
                if game_mode == "tournament" and str(game_tournament_id) == str(tournament_id):
                    quarter = game_doc.get("quarter", 0)
                    if quarter > 0:
                        # Game is active - save to game doc
                        return games_collection, game_id, True
        
        # Game doesn't exist or isn't active - save to master
        if mode == "franchise":
            return franchises_collection, franchise_id, False
        elif mode == "tournament":
            return tournaments_collection, tournament_id, False
    except Exception as e:
        logger.warning(f"⚠️ [PHASE 5.7] Error checking game status, defaulting to master save: {e}")
        # On error, default to master save
        if mode == "franchise":
            return franchises_collection, franchise_id, False
        elif mode == "tournament":
            return tournaments_collection, tournament_id, False
    
    # Fallback to master
    if mode == "franchise":
        return franchises_collection, franchise_id, False
    elif mode == "tournament":
        return tournaments_collection, tournament_id, False
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode for get_save_location: {mode}")


def normalize_team_id_to_canonical(team_id: str, mode: str, doc: dict = None) -> str:
    """
    ✅ PHASE 5.1: Normalize team_id to canonical format (e.g., "MORRISTOWN", "OCEAN_CITY").
    
    This function normalizes team_id at API entry points to ensure consistent format.
    For single mode, it resolves team names to canonical team_id keys in the game document.
    For franchise/tournament mode, it uses the document's authoritative team_id.
    
    Args:
        team_id: Team identifier (could be team name, ObjectId, or canonical team_id)
        mode: Game mode ("single", "franchise", "tournament")
        doc: Game/franchise/tournament document (required for single mode)
    
    Returns:
        Canonical team_id string (e.g., "SOUTH_LANCASTER")
    
    Raises:
        HTTPException: If team_id cannot be resolved to canonical format
    """
    if not team_id:
        raise HTTPException(status_code=400, detail="team_id is required")
    
    # For franchise/tournament mode, use document's authoritative team_id
    if mode == "franchise":
        if not doc:
            raise HTTPException(status_code=400, detail="Document required for franchise mode")
        user_team_id, user_team_object_id = get_user_team_from_franchise(doc)
        # For now, return the ObjectId string (will be standardized later)
        return str(user_team_object_id) if user_team_object_id else user_team_id
    elif mode == "tournament":
        if not doc:
            raise HTTPException(status_code=400, detail="Document required for tournament mode")
        user_team_id, user_team_object_id = get_user_team_from_tournament(doc)
        # For now, return the ObjectId string (will be standardized later)
        return str(user_team_object_id) if user_team_object_id else user_team_id
    else:
        # Single mode: Resolve to canonical team_id key in game document
        if not doc:
            raise HTTPException(status_code=400, detail="Game document required for single mode")
        
        teams = doc.get("teams", {})
        
        # Step 1: Try direct key match (if team_id is already a canonical team_id)
        if team_id in teams and (team_id.isupper() and "_" in team_id):
            return team_id
        
        # Step 2: Try name match (iterate through teams to find by team name)
        # ✅ PHASE 5.2: Simplified - removed home/away fallback (not needed for new games)
        # Frontend may still send team names, so we keep name resolution for compatibility
        for tid in teams.keys():
            team_obj = teams.get(tid, {})
            # Match if key equals team_id OR team_obj.name equals team_id (case-insensitive)
            if tid == team_id or (team_obj.get("name") or "").lower() == (team_id or "").lower():
                return tid
        
        # Step 3: Fail loudly if not found
        available_teams = {tid: teams.get(tid, {}).get("name", "unknown") for tid in teams.keys()}
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve team '{team_id}' to canonical team_id. Available teams: {list(available_teams.keys())}"
        )


def populate_team_plays(mode="single"):
    """
    Populate team plays with REFERENCES to universal plays collection (not full skeletons).
    This reference-based approach dramatically reduces document size.
    
    Args:
        mode: "single", "tournament", or "franchise"
        - For tournament mode: randomizes effectiveness (0-80), momentum (0-10), cloaking (0-10) for each play
        - For other modes: uses initial values from universal play or defaults to 0
        
    Returns:
        dict: {play_name: play_data} with play_id reference and stats (NO skeletons)
    """
    import random
    
    try:
        from BackEnd.db import plays_collection
        
        # Get all plays from universal collection
        all_plays = list(plays_collection.find({}))
        
        # Convert to dictionary format for team storage
        plays_dict = {}
        for play in all_plays:
            play_name = play["name"]
            
            # For tournament mode, randomize values for each play
            if mode == "tournament":
                # Each play and each value gets its own random roll
                initial_effectiveness = random.randint(0, 80)
                initial_momentum = random.randint(0, 10)
                initial_cloaking = random.randint(0, 10)
            else:
                # Get initial values from universal play (if they exist), otherwise default to 0
                initial_effectiveness = play.get("effectiveness", 0)
                initial_momentum = play.get("momentum", 0)
                initial_cloaking = play.get("cloaking", 0)
            
            play_data = {
                "play_id": str(play["_id"]),  # Reference to universal play (the "library card")
                "name": play["name"],
                "play_type": play["play_type"], 
                "play_focus": play["play_focus"],
                # Per-team effectiveness, momentum, and cloaking (separate from calculated effectiveness in stats)
                "effectiveness": initial_effectiveness,
                "momentum": initial_momentum,
                "cloaking": initial_cloaking,
                # NO SKELETONS - fetched from universal collection when needed
                "game_stats": {
                    "times_run": 0,
                    "successes": 0,
                    "player_points": {},  # {player_id: total_points} - tracks points scored per player on this play
                    "effectiveness": 0.0  # Calculated effectiveness from stats
                }
            }
            
            # Add season_stats for tournament and franchise modes
            if mode in ["tournament", "franchise"]:
                play_data["season_stats"] = {
                    "times_run": 0,
                    "successes": 0,
                    "player_points": {},  # {player_id: total_points} - tracks points scored per player on this play
                    "effectiveness": 0.0  # Calculated effectiveness from stats
                }
            
            plays_dict[play_name] = play_data
        
        return plays_dict
    except Exception as e:
        print(f"🚨 Error in populate_team_plays: {e}")
        return {}


def get_play_ids_by_names(play_names):
    """
    Get play_id (ObjectId strings) for a list of play names.
    
    Args:
        play_names: List of play name strings
        
    Returns:
        List of play_id strings (ObjectId as string), or empty list if play not found
    """
    try:
        from BackEnd.db import plays_collection
        
        logger.info(f"🔍 [POSITION FILTERS] Looking up {len(play_names)} play names: {play_names}")
        play_ids = []
        for play_name in play_names:
            play = plays_collection.find_one({"name": play_name})
            if play and play.get("_id"):
                play_id_str = str(play["_id"])
                play_ids.append(play_id_str)
                logger.info(f"✅ [POSITION FILTERS] Found play '{play_name}' → play_id: {play_id_str}")
            else:
                logger.warning(f"⚠️ [POSITION FILTERS] Play '{play_name}' not found in database")
        
        logger.info(f"🔍 [POSITION FILTERS] Resolved {len(play_ids)}/{len(play_names)} plays to play_ids: {play_ids}")
        return play_ids
    except Exception as e:
        logger.error(f"🚨 Error in get_play_ids_by_names: {e}", exc_info=True)
        return []


def initialize_playbook_settings():
    """
    Initialize playbook_settings with defaults: Even distribution across all plays in each container.
    
    ✅ UPDATED (February 2025): Changed from first play = 100% to even distribution.
    Standard and PF position filters are enabled by default.
    
    Returns:
        dict: playbook_settings structure with defaults:
        - motion: {play_name: percentage} - Evenly distributed across all motion plays
        - set_play_inside: {play_name: percentage} - Evenly distributed across all inside set plays
        - set_play_attack: {play_name: percentage} - Evenly distributed across all attack set plays
        - set_play_outside: {play_name: percentage} - Evenly distributed across all outside set plays
        - zone_defense: {defense_name: percentage} - Evenly distributed across all zone defenses
        - man_defense: {"Man": 100} - Only one man defense exists
        - slot_assignments: {}
        - motion_dropdowns: {}
        - position_filters: {standard: [...], PG: [], SG: [], SF: [], PF: [...], C: []}
    """
    try:
        from BackEnd.db import plays_collection
        
        # Get all plays from universal collection
        all_plays = list(plays_collection.find({}))
        
        # Initialize structure
        playbook_settings = {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {},
            "man_defense": {},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {
                "standard": [],  # Empty = show all plays when selected
                "PG": [],        # Point Guard plays (play_id ObjectId strings)
                "SG": [],        # Shooting Guard plays (play_id ObjectId strings)
                "SF": [],        # Small Forward plays (play_id ObjectId strings)
                "PF": [],        # Power Forward plays (play_id ObjectId strings)
                "C": []          # Center plays (play_id ObjectId strings)
            },
            "even_distribution_all": False  # Macro toggle for Even Distribution - All
        }
        
        # Group plays by type and focus
        motion_plays = []
        set_plays_inside = []
        set_plays_attack = []
        set_plays_outside = []
        
        for play in all_plays:
            play_name = play.get("name", "")
            play_type = play.get("play_type", "")
            play_focus = play.get("play_focus", "")
            
            # Skip "To Be Added" placeholder plays
            if play_name == "To Be Added":
                continue
            
            if play_type == "motion":
                motion_plays.append(play_name)
            elif play_type == "set_play":
                if play_focus == "inside":
                    set_plays_inside.append(play_name)
                elif play_focus == "attack":
                    set_plays_attack.append(play_name)
                elif play_focus == "outside":
                    set_plays_outside.append(play_name)
        
        # ✅ UPDATED (February 2025): Even distribution across all plays in each container
        # Sort plays by name for consistency, then distribute evenly
        if motion_plays:
            motion_plays.sort()
            percentage_per_play = 100.0 / len(motion_plays)
            # Distribute with rounding to ensure total = 100%
            remainder = 100.0
            for i, play_name in enumerate(motion_plays):
                if i == len(motion_plays) - 1:
                    # Last play gets remainder to ensure total = 100%
                    playbook_settings["motion"][play_name] = round(remainder)
                else:
                    playbook_settings["motion"][play_name] = round(percentage_per_play)
                    remainder -= round(percentage_per_play)
        
        if set_plays_inside:
            set_plays_inside.sort()
            percentage_per_play = 100.0 / len(set_plays_inside)
            remainder = 100.0
            for i, play_name in enumerate(set_plays_inside):
                if i == len(set_plays_inside) - 1:
                    playbook_settings["set_play_inside"][play_name] = round(remainder)
                else:
                    playbook_settings["set_play_inside"][play_name] = round(percentage_per_play)
                    remainder -= round(percentage_per_play)
        
        if set_plays_attack:
            set_plays_attack.sort()
            percentage_per_play = 100.0 / len(set_plays_attack)
            remainder = 100.0
            for i, play_name in enumerate(set_plays_attack):
                if i == len(set_plays_attack) - 1:
                    playbook_settings["set_play_attack"][play_name] = round(remainder)
                else:
                    playbook_settings["set_play_attack"][play_name] = round(percentage_per_play)
                    remainder -= round(percentage_per_play)
        
        if set_plays_outside:
            set_plays_outside.sort()
            percentage_per_play = 100.0 / len(set_plays_outside)
            remainder = 100.0
            for i, play_name in enumerate(set_plays_outside):
                if i == len(set_plays_outside) - 1:
                    playbook_settings["set_play_outside"][play_name] = round(remainder)
                else:
                    playbook_settings["set_play_outside"][play_name] = round(percentage_per_play)
                    remainder -= round(percentage_per_play)
        
        # Zone defense: Even distribution across all zone defenses
        # Zone defenses are hardcoded: "2-3 Zone", "3-2 Zone", "1-3-1 Zone"
        zone_defenses = ["2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        if zone_defenses:
            percentage_per_defense = 100.0 / len(zone_defenses)
            remainder = 100.0
            for i, defense_name in enumerate(zone_defenses):
                if i == len(zone_defenses) - 1:
                    playbook_settings["zone_defense"][defense_name] = round(remainder)
                else:
                    playbook_settings["zone_defense"][defense_name] = round(percentage_per_defense)
                    remainder -= round(percentage_per_defense)
        
        # Man defense: "Man" gets 100% (only one man defense exists)
        playbook_settings["man_defense"]["Man"] = 100
        
        # Initialize position filters with play assignments
        logger.info("🔍 [INITIALIZE PLAYBOOK] Starting position filter population...")
        
        # Standard: All basic plays
        standard_plays = [
            # Motion
            "3-2 Motion",
            "4-1 Motion",
            "5-0 Motion",
            # Set Play Inside
            "Base Post Play",
            # Set Play Attack
            "Pick & Roll (Lower Wing)",
            # Set Play Outside
            "Double Screen For SG"
        ]
        standard_play_ids = get_play_ids_by_names(standard_plays)
        playbook_settings["position_filters"]["standard"] = standard_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] Standard position filter populated with {len(standard_play_ids)} play_ids")
        
        # PF: Power Forward specific plays
        pf_plays = [
            # Motion
            "PF Post Motion",
            # Set Play Inside
            "PF Post Up",
            # Set Play Attack
            "PF High Post Drive",
            # Set Play Outside
            "PF Corner Shot",
            "PF Quick Jumper"
        ]
        pf_play_ids = get_play_ids_by_names(pf_plays)
        playbook_settings["position_filters"]["PF"] = pf_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] PF position filter populated with {len(pf_play_ids)} play_ids")
        
        # PG: Point Guard specific plays
        pg_plays = [
            # Set Play Inside
            "PG Post Up",
            # Set Play Attack
            "PG Wrap-Around",
            # Set Play Outside
            "PG Wing Three"
        ]
        pg_play_ids = get_play_ids_by_names(pg_plays)
        playbook_settings["position_filters"]["PG"] = pg_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] PG position filter populated with {len(pg_play_ids)} play_ids")
        
        # SG: Shooting Guard specific plays
        sg_plays = [
            # Set Play Inside
            "SG Pass & Cut",
            # Set Play Attack
            "SG Pick & Roll",
            # Set Play Outside
            "SG Wheel Three"
        ]
        sg_play_ids = get_play_ids_by_names(sg_plays)
        playbook_settings["position_filters"]["SG"] = sg_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] SG position filter populated with {len(sg_play_ids)} play_ids")
        
        # SF: Small Forward specific plays
        sf_plays = [
            # Set Play Inside
            "SF Back Door",
            # Set Play Attack
            "SF Isolation",
            # Set Play Outside
            "SF Misdirection Three"
        ]
        sf_play_ids = get_play_ids_by_names(sf_plays)
        playbook_settings["position_filters"]["SF"] = sf_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] SF position filter populated with {len(sf_play_ids)} play_ids")
        
        # C: Center specific plays
        c_plays = [
            # Set Play Inside
            "C Post Iso",
            # Set Play Attack
            "C High Post Clear Out",
            # Set Play Outside
            "C Screen & Three"
        ]
        c_play_ids = get_play_ids_by_names(c_plays)
        playbook_settings["position_filters"]["C"] = c_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] C position filter populated with {len(c_play_ids)} play_ids")
        
        return playbook_settings
        
    except Exception as e:
        logger.error(f"🚨 Error in initialize_playbook_settings: {e}", exc_info=True)
        # Return minimal defaults on error
        return {
            "motion": {},
            "set_play_inside": {},
            "set_play_attack": {},
            "set_play_outside": {},
            "zone_defense": {"2-3 Zone": 100},
            "man_defense": {"Man": 100},
            "slot_assignments": {},
            "motion_dropdowns": {},
            "position_filters": {
                "standard": [],
                "PG": [],
                "SG": [],
                "SF": [],
                "PF": [],
                "C": []
            },
            "even_distribution_all": False
        }


def populate_scouting_data(mode="single"):
    """
    Populate scouting_data with defense structures.
    This mirrors the structure created by TeamManager._init_scouting_data() but as a standalone function.
    
    Args:
        mode: "single", "tournament", or "franchise"
        - For tournament mode: randomizes effectiveness (0-80), momentum (0-10), cloaking (0-10) for each defense
        - For other modes: uses default values (0)
        
    Returns:
        dict: scouting_data structure with defense initialized
    """
    import random
    from copy import deepcopy
    
    # Create defense structure template
    defense_template = {
        "used": 0,
        "success": 0,
        "effectiveness": 0.0,
        "momentum": 0,
        "cloaking": 0,
        "game_stats": {
            "used": 0,
            "success": 0,
            "ev_scores": [],
            "lean_scores": [],
            "vs_motion": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_set": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_motion_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_motion_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_motion_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_set_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_set_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
            "vs_set_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
        },
        "season_stats": {
            "used": 0,
            "success": 0,
            "vs_motion": {"attempts": 0, "success": 0},
            "vs_set": {"attempts": 0, "success": 0},
            "vs_inside": {"attempts": 0, "success": 0},
            "vs_attack": {"attempts": 0, "success": 0},
            "vs_outside": {"attempts": 0, "success": 0},
            "vs_motion_inside": {"attempts": 0, "success": 0},
            "vs_motion_attack": {"attempts": 0, "success": 0},
            "vs_motion_outside": {"attempts": 0, "success": 0},
            "vs_set_inside": {"attempts": 0, "success": 0},
            "vs_set_attack": {"attempts": 0, "success": 0},
            "vs_set_outside": {"attempts": 0, "success": 0}
        }
    }
    
    # Initialize defense structure
    if mode == "tournament":
        # For tournament mode, each defense gets its own random values
        defense_structure = {
            "Man": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "2-3 Zone": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "3-2 Zone": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "1-3-1 Zone": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "vs_Fast_Break": {"used": 0, "success": 0},
            "FCP": {"used": 0, "success": 0},
            "HCT": {"used": 0, "success": 0}
        }
    else:
        # For other modes, use template with default values
        defense_structure = {
            "Man": deepcopy(defense_template),
            "2-3 Zone": deepcopy(defense_template),
            "3-2 Zone": deepcopy(defense_template),
            "1-3-1 Zone": deepcopy(defense_template),
            "vs_Fast_Break": {"used": 0, "success": 0},
            "FCP": {"used": 0, "success": 0},
            "HCT": {"used": 0, "success": 0}
        }
    
    # Return minimal scouting_data structure (just defense for now)
    # The full structure with offense tracking is created by TeamManager._init_scouting_data()
    # but for initialization purposes, we only need defense
    return {
        "defense": defense_structure,
        "offense": {}  # Will be populated by TeamManager if needed
    }


# ✅ PERFORMANCE: Cache expensive function results at module level (mode-aware caching)
_cached_populated_plays = {}  # {mode: plays_dict} - cache per mode
_cached_playbook_settings = None
_cached_default_settings = None

def _get_cached_populated_plays(mode="franchise"):
    """Get cached populated plays, or populate if not cached (mode-aware)."""
    global _cached_populated_plays
    if mode not in _cached_populated_plays:
        _cached_populated_plays[mode] = populate_team_plays(mode=mode)
    return _cached_populated_plays[mode]

def _get_cached_playbook_settings():
    """Get cached playbook settings, or initialize if not cached."""
    global _cached_playbook_settings
    if _cached_playbook_settings is None:
        _cached_playbook_settings = initialize_playbook_settings()
    return _cached_playbook_settings

def _get_cached_default_settings():
    """Get cached default settings, or get if not cached."""
    global _cached_default_settings
    if _cached_default_settings is None:
        _cached_default_settings = get_default_settings()
    return _cached_default_settings

def ensure_team_objects_exist(mode: str, doc_id: str, team_id: str, franchise_doc=None, tournament_doc=None):
    """
    Ensure team objects exist in the mode document. Create with defaults if missing.
    
    ✅ PERFORMANCE: Optimized to only check/update the requested team, not all teams.
    - Accepts optional pre-loaded documents to avoid double-loading
    - Only processes the requested team_id (not all 8 teams for franchise mode)
    - Uses cached results for expensive operations
    """
    collection = None
    
    if mode == "franchise":
        collection = db.franchises
    elif mode == "tournament":
        collection = db.tournaments
    elif mode == "single":
        collection = db.games
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    
    # ✅ PERFORMANCE: Reuse pre-loaded document if provided, otherwise load with projection
    doc = None
    if mode == "franchise" and franchise_doc:
        doc = franchise_doc
    elif mode == "tournament" and tournament_doc:
        doc = tournament_doc
    
    if not doc:
        # Handle different ID formats for different modes
        if mode == "single":
            # ✅ PERFORMANCE: Add projection for Single Game mode - only fetch teams field
            # This reduces data transfer by 70-90% for game documents
            # For single game mode, try both UUID string and ObjectId formats
            doc = collection.find_one(
                {"_id": doc_id},
                {"teams": 1, "_id": 1}
            )
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"teams": 1, "_id": 1}
                    )
                except:
                    pass
        else:
            # ✅ PERFORMANCE: Load with projection (only franchise_teams/teams field) for franchise/tournament modes
            # This reduces from 402KB to ~50KB (87% reduction) for franchise mode
            if mode == "franchise":
                doc = collection.find_one({"_id": ObjectId(doc_id)}, {"franchise_teams": 1, "_id": 1})
            elif mode == "tournament":
                doc = collection.find_one({"_id": ObjectId(doc_id)}, {"teams": 1, "_id": 1})
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"{mode.capitalize()} not found")
    
    # ✅ PERFORMANCE: For franchise mode, only check/update the requested team (not all 8 teams)
    if mode == "franchise":
        franchise_teams = doc.get("franchise_teams", {})
        # ✅ PERFORMANCE: Only check the requested team_id, not all teams
        if team_id not in franchise_teams:
            # Team object doesn't exist, create it
            defaults = _get_cached_default_settings()
            populated_plays = _get_cached_populated_plays(mode="franchise")
            playbook_settings = _get_cached_playbook_settings()
            
            from BackEnd.models.team_manager import TeamManager
            team_attrs = TeamManager.init_team_attributes(mode="franchise")
            franchise_teams[team_id] = {
                "team_chemistry": team_attrs["team_chemistry"],
                "offensive_efficiency": team_attrs["offensive_efficiency"],
                "shot_threshold": team_attrs["shot_threshold"],
                "discipline": team_attrs["discipline"],
                "fight": team_attrs["fight"],
                "rebound_modifier": team_attrs["rebound_modifier"],
                "defensive_efficiency": team_attrs["defensive_efficiency"],
                "fb_efficiency": team_attrs["fb_efficiency"],
                "pt_efficiency": team_attrs["pt_efficiency"],
                "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                "strategy_settings": defaults["strategy_settings"].copy(),
                "plays": populated_plays.copy(),
                "playbook_settings": playbook_settings.copy()
            }
            # Update only this team in the database
            collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {f"franchise_teams.{team_id}": franchise_teams[team_id]}}
            )
        else:
            # Team object exists, check if it has all required fields
            team_obj = franchise_teams[team_id]
            updates = {}
            defaults = _get_cached_default_settings()
            
            if "strategy_settings" not in team_obj:
                updates[f"franchise_teams.{team_id}.strategy_settings"] = defaults["strategy_settings"].copy()
            if not team_obj.get("plays"):
                updates[f"franchise_teams.{team_id}.plays"] = _get_cached_populated_plays(mode="franchise").copy()
            if "playbook_settings" not in team_obj:
                updates[f"franchise_teams.{team_id}.playbook_settings"] = _get_cached_playbook_settings().copy()
            
            if updates:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": updates}
                )
                # Update local copy for return value
                for key, value in updates.items():
                    # Extract field name from key (e.g., "franchise_teams.{team_id}.strategy_settings" -> "strategy_settings")
                    field_name = key.split(".")[-1]
                    franchise_teams[team_id][field_name] = value
        
        return franchise_teams
    
    # ✅ PERFORMANCE: For tournament and single game modes, only check/update the requested team
    else:
        # ✅ FIX: For Single Game mode, use team_id directly from game document (no teams collection lookup)
        # For Tournament mode, still need to resolve team_id from teams collection
        if mode == "single":
            # Single Game mode: team_id is already resolved from game document (e.g., "FOUR_CORNERS")
            # Use it directly - no need to look up in universal teams collection
            # The team_id has already been resolved from the game document's teams object
            actual_team_id = team_id
            
            # Check if team object exists in game document
            teams = doc.get("teams", {})
            team_obj = teams.get(actual_team_id)
            
            # ✅ PERFORMANCE: Removed debug logging
        else:
            # Tournament mode: Normalize team_id to ObjectId - try name first, then ObjectId
            team = db.teams.find_one({"name": team_id})
            if not team:
                try:
                    team = db.teams.find_one({"_id": ObjectId(team_id)})
                except:
                    pass
            if not team:
                raise HTTPException(status_code=404, detail="Team not found")
            
            actual_team_id = str(team["_id"])
            
            # Check if team object exists in tournament document
            teams = doc.get("teams", {})
            team_obj = teams.get(actual_team_id)
        
        # Check if team object exists (for both single and tournament modes)
        team_key = f"teams.{actual_team_id}"
        
        if not team_obj:
            # Create team object with defaults
            defaults = _get_cached_default_settings()
            # ✅ PERFORMANCE: Use cached populated plays
            populated_plays = _get_cached_populated_plays(mode=mode)
            # Initialize scouting_data with randomized values for tournament mode
            scouting_data = populate_scouting_data(mode=mode)
            # ✅ PERFORMANCE: Use cached playbook settings
            playbook_settings = _get_cached_playbook_settings()
            
            # ✅ SS&S: Use mode initialization system for tournament teams (matches Franchise pattern)
            # This randomizes team attributes per Mode Initialization System documentation
            from BackEnd.models.team_manager import TeamManager
            team_attrs = TeamManager.init_team_attributes(mode=mode)
            
            team_obj = {
                "team_chemistry": team_attrs["team_chemistry"],
                "offensive_efficiency": team_attrs["offensive_efficiency"],
                "shot_threshold": team_attrs["shot_threshold"],
                "discipline": team_attrs["discipline"],
                "fight": team_attrs["fight"],
                "rebound_modifier": team_attrs["rebound_modifier"],
                "defensive_efficiency": team_attrs["defensive_efficiency"],
                "fb_efficiency": team_attrs["fb_efficiency"],
                "pt_efficiency": team_attrs["pt_efficiency"],
                "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                "strategy_settings": defaults["strategy_settings"].copy(),
                "plays": populated_plays.copy(),
                "scouting_data": scouting_data,
                "playbook_settings": playbook_settings
            }
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {f"{team_key}": team_obj}}
                )
                # ✅ FIX: Reload document to get the newly created team object
                doc = collection.find_one({"_id": doc_id})
                teams = doc.get("teams", {}) if doc else {}
                team_obj = teams.get(actual_team_id)
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}": team_obj}}
                )
                # ✅ FIX: Reload document to get the newly created team object
                doc = collection.find_one({"_id": ObjectId(doc_id)})
                teams = doc.get("teams", {}) if doc else {}
                team_obj = teams.get(actual_team_id)
        elif "strategy_settings" not in team_obj or not team_obj.get("plays") or "shot_threshold" not in team_obj or "playbook_settings" not in team_obj:
            # Add missing settings
            defaults = get_default_settings()
            # Pass mode to populate_team_plays for tournament randomization
            populated_plays = populate_team_plays(mode=mode)
            # Initialize playbook_settings if missing
            if "playbook_settings" not in team_obj:
                playbook_settings = initialize_playbook_settings()
                # ✅ PERFORMANCE: Removed debug logging
            else:
                # Check if position_filters is missing or empty, and populate if needed
                existing_playbook_settings = team_obj.get("playbook_settings", {})
                position_filters = existing_playbook_settings.get("position_filters", {})
                # Check if all position filter arrays are empty
                all_empty = True
                if position_filters:
                    for key in ["standard", "PG", "SG", "SF", "PF", "C"]:
                        if position_filters.get(key) and len(position_filters[key]) > 0:
                            all_empty = False
                            break
                
                if not position_filters or all_empty:
                    # Position filters are missing or empty, populate them
                    logger.info(f"🔍 [TEAM OBJECTS] Position filters missing/empty for team {actual_team_id}, populating...")
                    playbook_settings = initialize_playbook_settings()
                    # Merge with existing playbook_settings to preserve other settings
                    existing_playbook_settings["position_filters"] = playbook_settings["position_filters"]
                    playbook_settings = existing_playbook_settings
                else:
                    playbook_settings = existing_playbook_settings
            updates = {}
            if "strategy_settings" not in team_obj:
                updates[f"{team_key}.strategy_settings"] = defaults["strategy_settings"].copy()
            if not team_obj.get("plays"):
                updates[f"{team_key}.plays"] = populated_plays.copy()
            if "playbook_settings" not in team_obj:
                updates[f"{team_key}.playbook_settings"] = playbook_settings
            elif playbook_settings != existing_playbook_settings:
                # Position filters were populated, update them
                updates[f"{team_key}.playbook_settings"] = playbook_settings
            
            # Add missing team attributes if they don't exist (for backwards compatibility)
            # ✅ SS&S: Use mode initialization system instead of copying from core teams collection
            if "shot_threshold" not in team_obj:
                from BackEnd.models.team_manager import TeamManager
                team_attrs = TeamManager.init_team_attributes(mode=mode)
                updates[f"{team_key}.shot_threshold"] = team_attrs["shot_threshold"]
                updates[f"{team_key}.discipline"] = team_attrs["discipline"]
                updates[f"{team_key}.fight"] = team_attrs["fight"]
                updates[f"{team_key}.rebound_modifier"] = team_attrs["rebound_modifier"]
                updates[f"{team_key}.offensive_efficiency"] = team_attrs["offensive_efficiency"]
                updates[f"{team_key}.team_chemistry"] = team_attrs["team_chemistry"]
                updates[f"{team_key}.defensive_efficiency"] = team_attrs["defensive_efficiency"]
                updates[f"{team_key}.fb_efficiency"] = team_attrs["fb_efficiency"]
                updates[f"{team_key}.pt_efficiency"] = team_attrs["pt_efficiency"]
                updates[f"{team_key}.fb_opp_modifier"] = team_attrs["fb_opp_modifier"]
                updates[f"{team_key}.pt_opp_modifier"] = team_attrs["pt_opp_modifier"]
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": updates}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": updates}
                )
        
        # Always check if position_filters need to be populated (even if all other fields exist)
        logger.info(f"🔍 [ENSURE TEAM OBJECTS] Checking position filters for team {actual_team_id}...")
        team_obj = doc.get("teams", {}).get(actual_team_id)
        if team_obj and team_obj.get("playbook_settings"):
            existing_playbook_settings = team_obj.get("playbook_settings", {})
            position_filters = existing_playbook_settings.get("position_filters", {})
            logger.info(f"🔍 [ENSURE TEAM OBJECTS] Found playbook_settings, position_filters: {position_filters}")
            
            # Check if all position filter arrays are empty
            all_empty = True
            if position_filters:
                for key in ["standard", "PG", "SG", "SF", "PF", "C"]:
                    arr = position_filters.get(key, [])
                    if arr and len(arr) > 0:
                        all_empty = False
                        logger.info(f"🔍 [ENSURE TEAM OBJECTS] Position '{key}' has {len(arr)} play_ids")
                        break
                    else:
                        logger.info(f"🔍 [ENSURE TEAM OBJECTS] Position '{key}' is empty")
            
            if not position_filters or all_empty:
                # Position filters are missing or empty, populate them
                logger.info(f"🔍 [TEAM OBJECTS] Position filters missing/empty for team {actual_team_id}, populating...")
                new_playbook_settings = initialize_playbook_settings()
                logger.info(f"🔍 [TEAM OBJECTS] Initialized playbook_settings with position_filters: {new_playbook_settings.get('position_filters', {})}")
                
                # Merge with existing playbook_settings to preserve other settings
                existing_playbook_settings["position_filters"] = new_playbook_settings["position_filters"]
                
                # Update the database
                logger.info(f"🔍 [TEAM OBJECTS] Updating database for team {actual_team_id} with path: {team_key}.playbook_settings")
                if mode == "single":
                    result = collection.update_one(
                        {"_id": doc_id},
                        {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                    )
                    logger.info(f"🔍 [TEAM OBJECTS] Database update result (single): matched={result.matched_count}, modified={result.modified_count}")
                else:
                    result = collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                    )
                    logger.info(f"🔍 [TEAM OBJECTS] Database update result (tournament/franchise): matched={result.matched_count}, modified={result.modified_count}")
                logger.info(f"✅ [TEAM OBJECTS] Position filters populated for team {actual_team_id}")
            else:
                logger.info(f"✅ [ENSURE TEAM OBJECTS] Position filters already populated for team {actual_team_id}")
        else:
            logger.info(f"🔍 [ENSURE TEAM OBJECTS] No playbook_settings found for team {actual_team_id}, will be created if needed")
        
        return doc.get("teams", {})


@router.get("/api/gameplan")
def get_gameplan(mode: str, team_id: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None, source: str = None):
    """
    Get game plan settings for a team in the specified mode.
    
    Args:
        source: Optional source parameter. If "db", always reads from database (for lineup screen consistency).
                If None or "cache", checks cache first for performance during active gameplay, but DB is always available as fallback.
    """
    try:
        # ✅ PHASE 5.5: Use helper to get collection and doc_id (simplifies mode handling)
        collection, doc_id = get_collection_and_doc_id(mode, franchise_id, tournament_id, game_id)
        
        # ✅ PHASE 1.1: Log normalization if game_id was changed
        if mode == "single" and game_id and game_id != doc_id:
            logger.warning(f"🔍 [NORMALIZE] GET /api/gameplan - Normalized game_id from '{game_id}' to '{doc_id}'")
        
        # ✅ PHASE 3.2: Cache is performance mirror, DB is always available as fallback
        # If source=db, skip cache and always read from database (for lineup screen consistency)
        # Otherwise, check cache first for performance during active gameplay, but DB is always available as fallback
        force_db_read = source == "db"
        gm = None
        use_gamemanager_settings = False
        
        # Only check cache if not forcing DB read (single mode only)
        # For tournament/franchise modes, skip GameManager and load directly from DB
        if mode == "single" and not force_db_read:
            try:
                from BackEnd.api.api import ongoing_games
                gm = ongoing_games.get(game_id)
                if gm:
                    # Determine which team
                    target_team = None
                    if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                        target_team = gm.home_team
                    elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                        target_team = gm.away_team
                    
                    if target_team and hasattr(target_team, 'strategy_settings') and target_team.strategy_settings:
                        inside_value = target_team.strategy_settings.get("inside")
                        logger.warning(f"✅ [GET-GAMEPLAN] Found GameManager settings for single mode: team={target_team.name}, inside={inside_value}")
                        logger.warning(f"✅ [CACHE-TELEMETRY] Cache HIT: get_gameplan({game_id}) - using GameManager cache")
                        use_gamemanager_settings = True
                    else:
                        logger.warning(f"❌ [CACHE-TELEMETRY] Cache MISS: get_gameplan({game_id}) - GameManager found but no strategy_settings, reading from DB")
                else:
                    logger.warning(f"❌ [CACHE-TELEMETRY] Cache MISS: get_gameplan({game_id}) - GameManager not available, reading from DB")
            except Exception as e:
                logger.warning(f"⚠️ [GET-GAMEPLAN] Error checking GameManager: {e}")
                gm = None
                use_gamemanager_settings = False
        # For tournament/franchise modes, GameManager is not used - continue to DB load
        
        # ✅ PHASE 5.7: For franchise/tournament mode, try game doc first, fallback to master doc
        doc = None
        load_from_game_doc = False
        game_doc_team_id = None
        
        if mode in ["franchise", "tournament"] and game_id:
            # Try to load from game doc first
            try:
                game_doc = games_collection.find_one(
                    {"_id": game_id},
                    {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                )
                if not game_doc:
                    try:
                        game_doc = games_collection.find_one(
                            {"_id": ObjectId(game_id)},
                            {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                        )
                    except:
                        pass
                
                if game_doc:
                    # Verify game belongs to this franchise/tournament
                    game_mode = game_doc.get("mode")
                    game_franchise_id = game_doc.get("franchise_id")
                    game_tournament_id = game_doc.get("tournament_id")
                    
                    if (mode == "franchise" and game_mode == "franchise" and str(game_franchise_id) == str(franchise_id)) or \
                       (mode == "tournament" and game_mode == "tournament" and str(game_tournament_id) == str(tournament_id)):
                        # Game belongs to this franchise/tournament - check if it has settings
                        game_teams = game_doc.get("teams", {})
                        # Get user team name from master doc to find matching team_id in game doc
                        master_doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"franchise_teams": 1 if mode == "franchise" else None, 
                             "teams": 1 if mode == "tournament" else None,
                             "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                        )
                        if master_doc:
                            user_team_name = None
                            if mode == "franchise":
                                user_team_name, _ = get_user_team_from_franchise(master_doc)
                            elif mode == "tournament":
                                user_team_name, _ = get_user_team_from_tournament(master_doc)
                            
                            # Find matching team_id in game doc
                            for tid, team_obj in game_teams.items():
                                if team_obj.get("name") == user_team_name:
                                    game_doc_team_id = tid
                                    # Check if game doc has strategy_settings for this team
                                    if team_obj.get("strategy_settings"):
                                        # Game doc has settings - use it
                                        doc = game_doc
                                        load_from_game_doc = True
                                        logger.warning(f"✅ [PHASE 5.7] Loading gameplan from game doc (game_id={game_id}, team_id={game_doc_team_id})")
                                        break
            except Exception as e:
                logger.warning(f"⚠️ [PHASE 5.7] Error checking game doc, falling back to master: {e}")
        
        # If not loading from game doc, load from master doc (existing logic)
        if not load_from_game_doc:
            # ✅ SS&S: Use document's user_team_object_id as authoritative source (aligns with Franchise pattern)
            # ✅ PERFORMANCE: Load document with projection (only needed fields) - reduces from 402KB to ~10KB (98% reduction)
            if mode == "franchise":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {
                        "user_team_id": 1,
                        "user_team_object_id": 1,
                        "franchise_teams": 1,
                        "_id": 1
                    }
                )
                if not doc:
                    raise HTTPException(status_code=404, detail="Franchise document not found")
            elif mode == "tournament":
                # ✅ PERFORMANCE: Load document with projection (only needed fields)
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {
                        "user_team_id": 1,
                        "user_team_object_id": 1,
                        "teams": 1,
                        "_id": 1
                    }
                )
                if not doc:
                    raise HTTPException(status_code=404, detail="Tournament document not found")
            else:
                # Single mode - handled below
                pass
        
        # ✅ PHASE 5.7: Resolve team_id - use game_doc_team_id if loading from game doc, otherwise use master doc team_id
        if load_from_game_doc and game_doc_team_id:
            # Loading from game doc - use game doc team_id
            authoritative_team_id = game_doc_team_id
            team_obj = doc.get("teams", {}).get(authoritative_team_id, {})
            logger.warning(f"✅ [PHASE 5.7] Using game doc team_id: {authoritative_team_id}")
        elif mode == "franchise":
            # ✅ SS&S: Always use franchise document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [GET GAMEPLAN] URL team_id ({team_id}) doesn't match franchise document user_team_object_id ({authoritative_team_id}). Using franchise document value.")
            
            # ✅ PERFORMANCE: Ensure team objects exist (only checks/creates the requested team, not all 8)
            # ✅ PHASE 5.3: Use returned teams dict directly - ensure_team_objects_exist() already reloads internally
            franchise_teams = ensure_team_objects_exist(mode, doc_id, authoritative_team_id, franchise_doc=doc)
            team_obj = franchise_teams.get(authoritative_team_id, {}) if isinstance(franchise_teams, dict) else {}
        elif mode == "tournament":
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [GET GAMEPLAN] URL team_id ({team_id}) doesn't match tournament document user_team_object_id ({authoritative_team_id}). Using tournament document value.")
            
            # ✅ PERFORMANCE: Ensure team objects exist (only checks/creates the requested team)
            # ✅ PHASE 5.3: Use returned teams dict directly - ensure_team_objects_exist() already reloads internally
            teams = ensure_team_objects_exist(mode, doc_id, authoritative_team_id, tournament_doc=doc)
            team_obj = teams.get(authoritative_team_id, {}) if isinstance(teams, dict) else {}
        else:
            # ✅ SS&S: For single mode, use load_team_settings_from_doc() (same as simulate_quarter_endpoint)
            # This ensures consistency and reuses the same loading logic that works at game start
            actual_team_id = None
            team_obj = {}
            
            # First check GameManager (if available)
            if use_gamemanager_settings and gm:
                # GameManager has settings - we'll use them directly later
                # Still need to get actual_team_id for logging purposes
                target_team = None
                if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                    actual_team_id = gm.home_team.team_id
                elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                    actual_team_id = gm.away_team.team_id
            else:
                # GameManager not available - use load_team_settings_from_doc() (same logic as game start)
                from BackEnd.api.api import load_team_settings_from_doc
                settings = load_team_settings_from_doc(mode, doc_id, team_id, team_id)
                
                # ✅ PHASE 5.1: Use normalization helper for single mode
                # This centralizes team_id resolution logic and ensures consistent format
                # Load document first (needed for normalization)
                doc = collection.find_one({"_id": doc_id})
                if not doc:
                    try:
                        doc = collection.find_one({"_id": ObjectId(doc_id)})
                    except:
                        pass
                if not doc:
                    raise HTTPException(status_code=404, detail="Game document not found")
                
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
                
                # Ensure team objects exist and get team_obj
                teams = ensure_team_objects_exist(mode, doc_id, actual_team_id)
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # ✅ PHASE 5.3: team_obj is already set from ensure_team_objects_exist() return value
        # No need to reload - ensure_team_objects_exist() already reloads internally
        
        # Get settings or return defaults
        # ✅ SS&S: Use GameManager settings if available (single source of truth during gameplay)
        defaults = get_default_settings()
        if mode == "single" and use_gamemanager_settings and gm:
            # Use GameManager settings (already verified above)
            target_team = None
            if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                target_team = gm.home_team
            elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                target_team = gm.away_team
            
            if target_team and hasattr(target_team, 'strategy_settings') and target_team.strategy_settings:
                strategy_settings = target_team.strategy_settings
                logger.warning(f"✅ [GET-GAMEPLAN] Using GameManager strategy_settings: inside={strategy_settings.get('inside')}")
            else:
                strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        elif mode == "single" and not use_gamemanager_settings:
            # ✅ SS&S: GameManager not available - use load_team_settings_from_doc() (same as simulate_quarter_endpoint)
            logger.warning(f"❌ [CACHE-TELEMETRY] Cache MISS: get_gameplan({game_id}) - GameManager not available, reading from DB")
            from BackEnd.api.api import load_team_settings_from_doc
            settings = load_team_settings_from_doc(mode, doc_id, team_id, team_id)
            strategy_settings = settings.get("strategy_settings") or team_obj.get("strategy_settings", defaults["strategy_settings"])
            if strategy_settings:
                inside_value = strategy_settings.get("inside")
                logger.warning(f"✅ [GET-GAMEPLAN] Using load_team_settings_from_doc() (same as game start): inside={inside_value}")
        else:
            strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        
        # ✅ TRACE: Log strategy_settings loaded from DB or GameManager
        trace_id = f"{mode}_{doc_id}_{team_id}"
        inside_value = strategy_settings.get("inside") if strategy_settings else None
        team_id_for_log = actual_team_id if mode == "single" and 'actual_team_id' in locals() else (authoritative_team_id if mode in ["franchise", "tournament"] else "N/A")
        source = "GameManager" if (mode == "single" and use_gamemanager_settings and gm) else "DB"
        logger.warning(f"🟢 [TRACE-LOAD] {trace_id} | GET-GAMEPLAN | team_id={team_id_for_log}, inside={inside_value}, has_settings={bool(strategy_settings)}, source={source}")
        
        # ✅ PHASE 1.3: Telemetry - Log state read
        source_type = "gameStore" if (mode == "single" and use_gamemanager_settings and gm) else "backend"
        logger.warning(f"🔵 [STATE-READ] [get_gameplan] strategy_settings from {source_type} | team_id={team_id_for_log}, inside={inside_value}")
        
        # ✅ FIX: Normalize legacy keys and ensure all required fields exist
        # Map old key names to new ones (for backward compatibility)
        if "half_court_trap" in strategy_settings and "hc_trap" not in strategy_settings:
            strategy_settings["hc_trap"] = strategy_settings.pop("half_court_trap")
        if "full_court_press" in strategy_settings and "fc_press" not in strategy_settings:
            strategy_settings["fc_press"] = strategy_settings.pop("full_court_press")
        
        # Ensure all required fields exist (merge with defaults)
        normalized_strategy_settings = defaults["strategy_settings"].copy()
        normalized_strategy_settings.update(strategy_settings)
        
        return {
            "strategy_settings": normalized_strategy_settings
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 Error in get_gameplan: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error getting game plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/gameplan")
def update_gameplan(request: GamePlanUpdateRequest):
    """Update game plan settings for a team in the specified mode."""
    try:
        # Validate settings
        validate_settings(request.strategy_settings)
        
        # Determine which collection to use
        if request.mode == "franchise":
            if not request.franchise_id:
                raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
            doc_id = request.franchise_id
            collection = db.franchises
        elif request.mode == "tournament":
            if not request.tournament_id:
                raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
            doc_id = request.tournament_id
            collection = db.tournaments
        elif request.mode == "single":
            if not request.game_id:
                raise HTTPException(status_code=400, detail="game_id required for single game mode")
            # ✅ PHASE 1.1: Normalize game_id at entry point (standardize to ObjectId format)
            from BackEnd.utils.game_id_utils import normalize_game_id
            original_game_id = request.game_id
            game_id = normalize_game_id(request.game_id)
            if original_game_id != game_id:
                logger.warning(f"🔍 [NORMALIZE] PUT /api/gameplan - Normalized game_id from '{original_game_id}' to '{game_id}'")
            doc_id = game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
        # ✅ PERFORMANCE: Load document with projection first (only needed fields)
        if request.mode == "single":
            # ✅ PHASE 1.1: Load teams, home_team_id, away_team_id for team ID resolution
            doc = collection.find_one(
                {"_id": doc_id},
                {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
            )
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                    )
                except:
                    pass
        else:
            # ✅ PERFORMANCE: Use projection for franchise/tournament modes
            if request.mode == "franchise":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            elif request.mode == "tournament":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        # ✅ SS&S: Resolve team_id to ObjectId if needed
        actual_team_id = request.team_id
        
        if request.mode == "franchise":
            # ✅ SS&S: Always use franchise document's user_team_object_id as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            actual_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if request.team_id and request.team_id != actual_team_id:
                logger.warning(f"⚠️ [GAME PLAN SAVE] URL team_id ({request.team_id}) doesn't match franchise document user_team_object_id ({actual_team_id}). Using franchise document value.")
        elif request.mode == "tournament":
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            actual_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if request.team_id and request.team_id != actual_team_id:
                logger.warning(f"⚠️ [GAME PLAN SAVE] URL team_id ({request.team_id}) doesn't match tournament document user_team_object_id ({actual_team_id}). Using tournament document value.")
        else:
            # ✅ PHASE 5.1: Use normalization helper for single mode
            # This centralizes team_id resolution logic and ensures consistent format
            actual_team_id = normalize_team_id_to_canonical(request.team_id, request.mode, doc)
            
            # ✅ PHASE 5.1: Verify resolved team_id is valid (sanity check)
            teams = doc.get("teams", {})
            if actual_team_id not in teams:
                logger.error(f"❌ [GAME PLAN SAVE] Resolved team_id '{actual_team_id}' not found in teams object!")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: Resolved team_id '{actual_team_id}' not found in game document"
                )
        
        # ✅ PERFORMANCE: Ensure team objects exist, passing pre-loaded doc to avoid double-load
        ensure_team_objects_exist(
            request.mode, doc_id, actual_team_id,
            franchise_doc=doc if request.mode == "franchise" else None,
            tournament_doc=doc if request.mode == "tournament" else None
        )
        
        # ✅ TRACE: Log what strategy_settings we're about to save (with trace ID)
        trace_id = f"{request.mode}_{doc_id}_{actual_team_id}"
        strategy_sample = dict(list(request.strategy_settings.items())[:5]) if request.strategy_settings else {}
        inside_value = request.strategy_settings.get("inside", "MISSING") if request.strategy_settings else "MISSING"
        logger.warning(f"🔵 [TRACE-SAVE] {trace_id} | SAVE-GAMEPLAN START | team={actual_team_id}, inside={inside_value}, sample={strategy_sample}")
        
        # ✅ PHASE 1.3: Telemetry - Log state write
        logger.warning(f"🟢 [STATE-WRITE] [update_gameplan] strategy_settings to backend | team_id={actual_team_id}, inside={inside_value}, endpoint=/api/gameplan")
        
        # ✅ PHASE 5.7: Determine save location for franchise/tournament mode
        # If game is active, save to game doc; otherwise save to master doc
        save_to_game_doc = False
        game_doc_team_id = actual_team_id  # Default to actual_team_id
        if request.mode in ["franchise", "tournament"]:
            save_collection, save_doc_id, save_to_game_doc = get_save_location_for_franchise_tournament(
                request.mode,
                request.game_id,
                request.franchise_id,
                request.tournament_id
            )
            # Update collection and doc_id if saving to game doc
            if save_to_game_doc:
                collection = save_collection
                doc_id = save_doc_id
                # ✅ PHASE 5.7: Resolve team_id from game document when saving to game doc
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
                        # Find team_id in game doc that matches the user team
                        user_team_name = None
                        if request.mode == "franchise":
                            user_team_name, _ = get_user_team_from_franchise(doc)
                        elif request.mode == "tournament":
                            user_team_name, _ = get_user_team_from_tournament(doc)
                        
                        # Find matching team_id in game doc
                        game_teams = game_doc.get("teams", {})
                        for tid, team_obj in game_teams.items():
                            if team_obj.get("name") == user_team_name:
                                game_doc_team_id = tid
                                break
                        
                        logger.warning(f"✅ [PHASE 5.7] Resolved game doc team_id: {game_doc_team_id} (from master team_id: {actual_team_id})")
                except Exception as e:
                    logger.warning(f"⚠️ [PHASE 5.7] Error resolving game doc team_id, using actual_team_id: {e}")
                    game_doc_team_id = actual_team_id
                
                logger.warning(f"✅ [PHASE 5.7] Saving gameplan to game doc (game_id={save_doc_id})")
            else:
                # Keep existing collection/doc_id (master doc)
                logger.warning(f"✅ [PHASE 5.7] Saving gameplan to master doc (franchise_id={request.franchise_id or request.tournament_id})")
        
        # ✅ PHASE 5.5: Use helper to get update path
        # If saving to game doc, use "teams" path with game doc team_id (like single mode)
        # If saving to master doc, use mode-specific path with master team_id
        if save_to_game_doc:
            update_path = f"teams.{game_doc_team_id}.strategy_settings"
        else:
            update_path = f"{get_team_settings_path(request.mode, actual_team_id)}.strategy_settings"
        
        update_fields = {
            update_path: request.strategy_settings
        }
        
        logger.warning(f"💾 [SAVE-GAMEPLAN] Update path: {update_path}, doc_id={doc_id}, mode={request.mode}, save_to_game_doc={save_to_game_doc}")
        
        # ✅ PHASE 1.3: Telemetry - Log state write
        inside_value = request.strategy_settings.get("inside", "MISSING") if request.strategy_settings else "MISSING"
        logger.warning(f"🟢 [STATE-WRITE] [update_gameplan] strategy_settings to backend | team_id={actual_team_id}, inside={inside_value}, endpoint=/api/gameplan")
        
        # Handle different ID formats for different modes
        if request.mode == "single":
            result = collection.update_one(
                {"_id": doc_id},
                {"$set": update_fields}
            )
            # If not found, try as ObjectId
            if result.matched_count == 0:
                try:
                    result = collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": update_fields}
                    )
                except:
                    pass
        else:
            # ✅ PHASE 5.7: For franchise/tournament, save to determined location (game doc or master doc)
            if save_to_game_doc:
                # Saving to game doc - use string ID (may need ObjectId conversion)
                result = collection.update_one(
                    {"_id": doc_id},
                    {"$set": update_fields}
                )
                if result.matched_count == 0:
                    try:
                        result = collection.update_one(
                            {"_id": ObjectId(doc_id)},
                            {"$set": update_fields}
                        )
                    except:
                        pass
            else:
                # Saving to master doc - use ObjectId
                result = collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": update_fields}
                )
        
        # ✅ PHASE 5.3: Removed verification reload - trust MongoDB update result
        # If update succeeded (matched_count > 0), settings are saved
        if result and result.matched_count > 0:
            logger.warning(f"🔵 [TRACE-SAVE] {trace_id} | DB WRITE SUCCESS | matched={result.matched_count}, modified={result.modified_count}")
        else:
            logger.error(f"❌ [SAVE-GAMEPLAN] DB write FAILED: matched={result.matched_count if result else 0}, doc_id={doc_id}")
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} not found")
        
        # ✅ SS&S: Apply settings immediately to GameManager if game is in cache
        # This ensures GameManager always reflects what's in DB (single source of truth)
        if request.mode == "single" and request.game_id and result and result.matched_count > 0:
            try:
                # Lazy import to avoid circular dependency
                from BackEnd.api.api import ongoing_games
                gm = ongoing_games.get(request.game_id)
                if gm:
                    # Verify game_id matches
                    if hasattr(gm, 'game_id') and str(gm.game_id) != str(request.game_id):
                        logger.warning(f"⚠️ [SAVE-GAMEPLAN] Game ID mismatch: cache={gm.game_id}, request={request.game_id}")
                    else:
                        # Determine which team to update
                        target_team = None
                        if actual_team_id == gm.home_team.team_id:
                            target_team = gm.home_team
                        elif actual_team_id == gm.away_team.team_id:
                            target_team = gm.away_team
                        
                        if target_team:
                            # Apply strategy_settings
                            before_inside = target_team.strategy_settings.get("inside", "MISSING") if target_team.strategy_settings else "MISSING"
                            default_settings = target_team._init_strategy_settings()
                            target_team.strategy_settings = {**default_settings, **request.strategy_settings}
                            after_inside = target_team.strategy_settings.get("inside", "MISSING")
                            logger.warning(f"🔵 [TRACE-SAVE] {trace_id} | APPLIED TO GAMEMANAGER | team={target_team.name}, before_inside={before_inside}, after_inside={after_inside}")
                        else:
                            logger.warning(f"⚠️ [SAVE-GAMEPLAN] Team {actual_team_id} not found in cached GameManager (home={gm.home_team.team_id}, away={gm.away_team.team_id})")
            except Exception as e:
                logger.warning(f"⚠️ [SAVE-GAMEPLAN] Error applying to cached GameManager (non-critical): {e}")
        
        logger.info(f"✅ Updated game plan for team {request.team_id} in {request.mode} mode")
        return {"success": True, "message": "Game plan saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating game plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/playbooks")
def get_playbooks(mode: str, team_id: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None, source: str = None):
    """
    Get plays for a team from the appropriate mode document.
    Returns plays organized by type (motion, set_play) and focus (inside, attack, outside).
    
    PERFORMANCE DIAGNOSTIC: This endpoint is instrumented with timing logs.
    """
    import time
    endpoint_start = time.time()
    
    try:
        # ✅ PERFORMANCE: Removed debug logging - only log errors and critical events
        # ✅ PHASE 5.5: Use helper to get collection and doc_id (simplifies mode handling)
        collection, doc_id = get_collection_and_doc_id(mode, franchise_id, tournament_id, game_id)
        
        # ✅ PHASE 1.1: Log normalization if game_id was changed
        if mode == "single" and game_id and game_id != doc_id:
            logger.warning(f"🔍 [NORMALIZE] GET /api/playbooks - Normalized game_id from '{game_id}' to '{doc_id}'")
        
        # ✅ PHASE 5.5: Use normalized doc_id for single mode cache lookup
        if mode == "single":
            game_id = doc_id  # Use normalized game_id for cache lookup
            
            # ✅ PHASE 3.2: Cache is performance mirror, DB is always available as fallback
            # If source=db, skip cache and always read from database (for lineup screen consistency)
            # Otherwise, check cache first for performance during active gameplay, but DB is always available as fallback
            force_db_read = source == "db"
            gm = None
            use_gamemanager_settings = False
            
            # Only check cache if not forcing DB read
            if not force_db_read:
                try:
                    from BackEnd.api.api import ongoing_games
                    gm = ongoing_games.get(game_id)
                    if gm:
                        # Determine which team
                        target_team = None
                        if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                            target_team = gm.home_team
                        elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                            target_team = gm.away_team
                        
                        if target_team and hasattr(target_team, 'playbook_settings') and target_team.playbook_settings:
                            slot_count = len(target_team.playbook_settings.get("slot_assignments", {}))
                            logger.warning(f"✅ [GET-PLAYBOOKS] Found GameManager settings for single mode: team={target_team.name}, slot_assignments={slot_count}")
                            logger.warning(f"✅ [CACHE-TELEMETRY] Cache HIT: get_playbooks({game_id}) - using GameManager cache")
                            use_gamemanager_settings = True
                        else:
                            logger.warning(f"❌ [CACHE-TELEMETRY] Cache MISS: get_playbooks({game_id}) - GameManager found but no playbook_settings, reading from DB")
                    else:
                        logger.warning(f"❌ [CACHE-TELEMETRY] Cache MISS: get_playbooks({game_id}) - GameManager not available, reading from DB")
                except Exception as e:
                    logger.warning(f"⚠️ [GET-PLAYBOOKS] Error checking GameManager: {e}")
                    logger.warning(f"❌ [CACHE-TELEMETRY] Cache ERROR: get_playbooks({game_id}) - exception checking cache: {e}")
                    gm = None
                    use_gamemanager_settings = False
            else:
                logger.warning(f"🔄 [CACHE-TELEMETRY] Cache SKIP: get_playbooks({game_id}) - source=db, forcing DB read")
        # For tournament/franchise modes, GameManager is not used - continue to DB load
        
        # ✅ PERFORMANCE DIAGNOSTIC: Measure database query time
        query_start = time.time()
        
        # ✅ PHASE 5.7: For franchise/tournament mode, try game doc first, fallback to master doc
        doc = None
        load_from_game_doc = False
        game_doc_team_id = None
        
        if mode in ["franchise", "tournament"] and game_id:
            # Try to load from game doc first
            try:
                game_doc = games_collection.find_one(
                    {"_id": game_id},
                    {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                )
                if not game_doc:
                    try:
                        game_doc = games_collection.find_one(
                            {"_id": ObjectId(game_id)},
                            {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                        )
                    except:
                        pass
                
                if game_doc:
                    # Verify game belongs to this franchise/tournament
                    game_mode = game_doc.get("mode")
                    game_franchise_id = game_doc.get("franchise_id")
                    game_tournament_id = game_doc.get("tournament_id")
                    
                    if (mode == "franchise" and game_mode == "franchise" and str(game_franchise_id) == str(franchise_id)) or \
                       (mode == "tournament" and game_mode == "tournament" and str(game_tournament_id) == str(tournament_id)):
                        # Game belongs to this franchise/tournament - check if it has settings
                        game_teams = game_doc.get("teams", {})
                        # Get user team name from master doc to find matching team_id in game doc
                        master_doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"franchise_teams": 1 if mode == "franchise" else None, 
                             "teams": 1 if mode == "tournament" else None,
                             "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                        )
                        if master_doc:
                            user_team_name = None
                            if mode == "franchise":
                                user_team_name, _ = get_user_team_from_franchise(master_doc)
                            elif mode == "tournament":
                                user_team_name, _ = get_user_team_from_tournament(master_doc)
                            
                            # Find matching team_id in game doc
                            for tid, team_obj in game_teams.items():
                                if team_obj.get("name") == user_team_name:
                                    game_doc_team_id = tid
                                    # Check if game doc has playbook_settings for this team
                                    if team_obj.get("playbook_settings"):
                                        # Game doc has settings - use it
                                        doc = game_doc
                                        load_from_game_doc = True
                                        logger.warning(f"✅ [PHASE 5.7] Loading playbooks from game doc (game_id={game_id}, team_id={game_doc_team_id})")
                                        break
            except Exception as e:
                logger.warning(f"⚠️ [PHASE 5.7] Error checking game doc, falling back to master: {e}")
        
        # If not loading from game doc, load from master doc (existing logic)
        if not load_from_game_doc:
            # ✅ PERFORMANCE: Load document with projection (only needed fields) to reduce data transfer
            # For single game mode, try both UUID string and ObjectId formats
            if mode == "single":
                # ✅ PERFORMANCE: Add projection for Single Game mode - only fetch teams, home_team_id, away_team_id
                # This reduces data transfer by 70-90% for game documents (especially after Q1+)
                doc = collection.find_one(
                    {"_id": doc_id},
                    {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                )
                if not doc:
                    # Try as ObjectId if UUID string lookup failed
                    try:
                        doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                        )
                    except:
                        pass
            else:
                # ✅ PERFORMANCE: Use projection for franchise/tournament modes
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
            
            if not load_from_game_doc:
                logger.warning(f"✅ [PHASE 5.7] Loading playbooks from master doc (franchise_id={franchise_id or tournament_id})")
        
        query_time = (time.time() - query_start) * 1000  # Convert to ms
        doc_size = len(str(doc)) if doc else 0
        logger.warning(f"⏱️ [PERF] /api/playbooks - DB query: {query_time:.2f}ms, doc_size: {doc_size} bytes, mode: {mode}, load_from_game_doc={load_from_game_doc}")
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"{mode.capitalize()} document not found")
        
        # ⏱️ PERFORMANCE: Start timing processing phase
        process_start = time.time()
        
        # ✅ FIX: Get authoritative team_id FIRST, then ensure team objects exist
        # Get team plays
        # ✅ PHASE 5.7: If loading from game doc, use game_doc_team_id; otherwise use master doc team_id
        if load_from_game_doc and game_doc_team_id:
            # Loading from game doc - use game doc team_id
            authoritative_team_id = game_doc_team_id
            logger.warning(f"✅ [PHASE 5.7] Using game doc team_id: {authoritative_team_id}")
        elif mode == "franchise":
            # Always use franchise document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        elif mode == "tournament":
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        else:
            # For single mode, use the provided team_id
            authoritative_team_id = team_id
        
        # ✅ PHASE 5.7: If loading from game doc, skip ensure_team_objects_exist (team objects already exist)
        # Otherwise, ensure team objects exist in master doc
        if load_from_game_doc:
            # Loading from game doc - team objects already exist from init_game
            teams = doc.get("teams", {})
            team_obj = teams.get(authoritative_team_id, {})
            actual_team_id = authoritative_team_id
        else:
            # ✅ PERFORMANCE: Ensure team objects exist, passing pre-loaded doc to avoid double-load
            # The function returns the teams dict and updates the database if needed
            teams_dict = ensure_team_objects_exist(
                mode, doc_id, authoritative_team_id,
                franchise_doc=doc if mode == "franchise" else None,
                tournament_doc=doc if mode == "tournament" else None
            )
            
            # ✅ DEBUG: Log if plays were populated by ensure_team_objects_exist
            if mode == "franchise" and isinstance(teams_dict, dict):
                team_obj_check = teams_dict.get(authoritative_team_id, {})
                plays_count = len(team_obj_check.get("plays", {})) if team_obj_check else 0
                # ✅ PERFORMANCE: Removed debug logging
            
            # ✅ PHASE 5.3: Use returned teams dict from ensure_team_objects_exist() directly
            # This avoids unnecessary document reloads - ensure_team_objects_exist() already reloads internally
            if mode == "franchise":
                franchise_teams = teams_dict if isinstance(teams_dict, dict) else doc.get("franchise_teams", {})
                team_obj = franchise_teams.get(authoritative_team_id, {})
                actual_team_id = authoritative_team_id
            elif mode == "tournament":
                teams = teams_dict if isinstance(teams_dict, dict) else doc.get("teams", {})
                team_obj = teams.get(authoritative_team_id, {})
                actual_team_id = authoritative_team_id
            else:
                # ✅ PHASE 5.1: Use normalization helper for single mode
                # This centralizes team_id resolution logic and ensures consistent format
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
                
                # Get team_obj using returned teams dict or doc
                teams = teams_dict if isinstance(teams_dict, dict) else doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # ✅ PERFORMANCE: Removed debug logging
        # Ensure playbook_settings exists (even if ensure_team_objects_exist missed it)
        # Check if team_obj exists and playbook_settings is missing or falsy (None, empty dict, etc.)
        # Note: Key might exist but value could be None or empty dict
        if actual_team_id and (not team_obj or not team_obj.get("playbook_settings")):
            playbook_settings = initialize_playbook_settings()
            # ✅ PHASE 5.5: Use helper to get update path (same logic for all modes)
            team_key = get_team_settings_path(mode, actual_team_id)
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {f"{team_key}.playbook_settings": playbook_settings}}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}.playbook_settings": playbook_settings}}
                )
            # Reload document to get updated playbook_settings
            if mode == "single":
                doc = collection.find_one({"_id": doc_id})
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            # ✅ FIX: Reload team_obj from correct location based on mode
            if mode == "franchise":
                franchise_teams = doc.get("franchise_teams", {})
                team_obj = franchise_teams.get(actual_team_id, {}) if actual_team_id else {}
            elif mode == "tournament":
                teams = doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
            else:
                teams = doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # ✅ PERFORMANCE: Removed debug logging
        # Check if position filters need to be populated (after ensure_team_objects_exist and document reload)
        if team_obj and team_obj.get("playbook_settings"):
            existing_playbook_settings = team_obj.get("playbook_settings", {})
            position_filters = existing_playbook_settings.get("position_filters", {})
            
            # Check if all position filter arrays are empty
            all_empty = True
            if position_filters:
                for key in ["standard", "PG", "SG", "SF", "PF", "C"]:
                    arr = position_filters.get(key, [])
                    if arr and len(arr) > 0:
                        all_empty = False
                        break
            
            if not position_filters or all_empty:
                # Position filters are missing or empty, populate them
                new_playbook_settings = initialize_playbook_settings()
                existing_playbook_settings["position_filters"] = new_playbook_settings["position_filters"]
                
                # Update the database
                if mode == "franchise":
                    team_key = f"franchise_teams.{actual_team_id}"
                else:
                    team_key = f"teams.{actual_team_id}"
                
                if mode == "single":
                    result = collection.update_one(
                        {"_id": doc_id},
                        {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                    )
                else:
                    result = collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                    )
                
                # Reload document again to get the updated position filters
                if mode == "single":
                    doc = collection.find_one({"_id": doc_id})
                else:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                
                # Reload team_obj with updated position filters
                if mode == "franchise":
                    team_obj = doc.get("franchise_teams", {}).get(actual_team_id, {})
                elif mode == "tournament":
                    team_obj = doc.get("teams", {}).get(actual_team_id, {})
                else:
                    team_obj = doc.get("teams", {}).get(actual_team_id, {})
        
        # ✅ CRITICAL FIX: Ensure plays exist before reading them
        # This ensures plays are always available, even if ensure_team_objects_exist didn't populate them
        # or if they were lost during document reloads
        if actual_team_id and (not team_obj or not team_obj.get("plays") or len(team_obj.get("plays", {})) == 0):
            populated_plays = _get_cached_populated_plays(mode=mode)
            
            # Update the database
            if mode == "franchise":
                team_key = f"franchise_teams.{actual_team_id}"
            else:
                team_key = f"teams.{actual_team_id}"
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {f"{team_key}.plays": populated_plays}}
                )
                # Reload document
                doc = collection.find_one({"_id": doc_id})
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}.plays": populated_plays}}
                )
                # Reload document
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            
            # Reload team_obj with populated plays
            if mode == "franchise":
                franchise_teams = doc.get("franchise_teams", {})
                team_obj = franchise_teams.get(actual_team_id, {}) if actual_team_id else {}
            elif mode == "tournament":
                teams = doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
            else:
                teams = doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
            
            logger.warning(f"✅ [GET PLAYBOOKS] plays populated, reloaded team_obj has {len(team_obj.get('plays', {}))} plays")
        
        # ✅ SS&S: Always get plays from team_obj (DB) - same as game start
        # Playbook_settings come from GameManager (percentages/slot_assignments), but plays come from DB
        # This ensures consistency with game start flow
        plays = team_obj.get("plays", {})
        
        # ✅ PERFORMANCE: Removed debug logging
        
        # Organize plays by type and focus
        motion_plays = []
        set_plays_inside = []
        set_plays_attack = []
        set_plays_outside = []
        
        for play_name, play_data in plays.items():
            play_type = play_data.get("play_type", "")
            play_focus = play_data.get("play_focus", "")
            
            if play_type == "motion":
                motion_plays.append({
                    "name": play_name,
                    "play_id": play_data.get("play_id"),
                    "play_type": play_type,
                    "play_focus": play_focus
                })
            elif play_type == "set_play":
                if play_focus == "inside":
                    set_plays_inside.append({
                        "name": play_name,
                        "play_id": play_data.get("play_id"),
                        "play_type": play_type,
                        "play_focus": play_focus
                    })
                elif play_focus == "attack":
                    set_plays_attack.append({
                        "name": play_name,
                        "play_id": play_data.get("play_id"),
                        "play_type": play_type,
                        "play_focus": play_focus
                    })
                elif play_focus == "outside":
                    set_plays_outside.append({
                        "name": play_name,
                        "play_id": play_data.get("play_id"),
                        "play_type": play_type,
                        "play_focus": play_focus
                    })
        
        # Sort plays by name for consistency
        motion_plays.sort(key=lambda x: x["name"])
        set_plays_inside.sort(key=lambda x: x["name"])
        set_plays_attack.sort(key=lambda x: x["name"])
        set_plays_outside.sort(key=lambda x: x["name"])
        
        # ✅ FIX: Reload team_obj from latest doc to ensure we have fresh playbook_settings
        # This ensures slot_assignments and other settings are current after all document reloads
        if mode == "franchise":
            doc = collection.find_one({"_id": ObjectId(doc_id)})
            franchise_teams = doc.get("franchise_teams", {})
            team_obj = franchise_teams.get(actual_team_id, {}) if actual_team_id else {}
        elif mode == "tournament":
            doc = collection.find_one({"_id": ObjectId(doc_id)})
            teams = doc.get("teams", {})
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        else:
            # For single mode, try both formats
            doc = collection.find_one({"_id": doc_id})
            if not doc:
                try:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
            teams = doc.get("teams", {}) if doc else {}
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # Get playbook settings (percentages, slot assignments, motion dropdowns, and position filters)
        # ✅ SS&S: Use GameManager settings if available (single source of truth during gameplay)
        # If GameManager not available, use load_team_settings_from_doc() (same logic as game start)
        if mode == "single" and use_gamemanager_settings and gm:
            # Use GameManager settings (already verified above)
            target_team = None
            if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                target_team = gm.home_team
            elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                target_team = gm.away_team
            
            if target_team and hasattr(target_team, 'playbook_settings') and target_team.playbook_settings:
                playbook_settings = target_team.playbook_settings
                logger.warning(f"✅ [GET-PLAYBOOKS] Using GameManager playbook_settings: slot_assignments={len(playbook_settings.get('slot_assignments', {}))}")
                # ✅ CRITICAL FIX: Check if position_filters are empty (same issue as DB path)
                # GameManager's playbook_settings may have empty position_filters, which causes plays to not render
                position_filters = playbook_settings.get("position_filters", {})
                all_empty = True
                if position_filters:
                    for key in ["standard", "PG", "SG", "SF", "PF", "C"]:
                        if position_filters.get(key) and len(position_filters[key]) > 0:
                            all_empty = False
                            break
                
                if not position_filters or all_empty:
                    # Position filters are missing or empty, populate them
                    logger.warning(f"🔍 [GET-PLAYBOOKS] GameManager position_filters empty, populating...")
                    new_playbook_settings = initialize_playbook_settings()
                    playbook_settings["position_filters"] = new_playbook_settings["position_filters"]
                    logger.warning(f"✅ [GET-PLAYBOOKS] Populated GameManager position_filters")
                # ✅ DEBUG: Log GameManager playbook_settings structure
                logger.warning(f"🔍 [GET-PLAYBOOKS DEBUG] GameManager playbook_settings structure:")
                logger.warning(f"   - Type: {type(playbook_settings)}")
                logger.warning(f"   - Top-level keys: {list(playbook_settings.keys()) if isinstance(playbook_settings, dict) else 'NOT A DICT'}")
                if isinstance(playbook_settings, dict):
                    logger.warning(f"   - motion type: {type(playbook_settings.get('motion'))}, keys: {list(playbook_settings.get('motion', {}).keys())[:3]}")
                    logger.warning(f"   - set_play_inside type: {type(playbook_settings.get('set_play_inside'))}, keys: {list(playbook_settings.get('set_play_inside', {}).keys())[:3]}")
                    logger.warning(f"   - set_play_attack type: {type(playbook_settings.get('set_play_attack'))}, keys: {list(playbook_settings.get('set_play_attack', {}).keys())[:3]}")
                    logger.warning(f"   - set_play_outside type: {type(playbook_settings.get('set_play_outside'))}, keys: {list(playbook_settings.get('set_play_outside', {}).keys())[:3]}")
            else:
                playbook_settings = team_obj.get("playbook_settings", {})
        elif mode == "single" and not use_gamemanager_settings:
            # ✅ SS&S: GameManager not available - use load_team_settings_from_doc() (same as simulate_quarter_endpoint)
            # This function handles team_id resolution correctly, so use its result directly
            from BackEnd.api.api import load_team_settings_from_doc
            settings = load_team_settings_from_doc(mode, doc_id, team_id, team_id)
            playbook_settings = settings.get("playbook_settings")  # Use None if missing, don't fallback to team_obj
            if not playbook_settings:
                # Only fallback to team_obj if load_team_settings_from_doc() returned None (not empty dict)
                playbook_settings = team_obj.get("playbook_settings", {})
            if playbook_settings:
                slot_count = len(playbook_settings.get("slot_assignments", {}))
                logger.warning(f"✅ [GET-PLAYBOOKS] Using load_team_settings_from_doc() (same as game start): slot_assignments={slot_count}")
            else:
                logger.warning(f"⚠️ [GET-PLAYBOOKS] load_team_settings_from_doc() returned no playbook_settings, using empty dict")
        else:
            playbook_settings = team_obj.get("playbook_settings", {})
        
        # ✅ DEBUG: Log slot_assignments for diagnosis
        slot_count = len(playbook_settings.get("slot_assignments", {})) if playbook_settings else 0
        # ✅ REMOVED: Verbose GET-PLAYBOOKS logs - redundant with trace logs
        # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        
        # ✅ PHASE 5.3: Removed core teams collection fallback - game document is single source of truth
        
        slot_assignments = playbook_settings.get("slot_assignments", {}) if playbook_settings else {}
        motion_dropdowns = playbook_settings.get("motion_dropdowns", {}) if playbook_settings else {}
        
        # ✅ DEBUG: Log slot_assignments structure when returning to frontend
        if slot_assignments:
            logger.warning(f"🔍 [GET-PLAYBOOKS DEBUG] slot_assignments structure:")
            logger.warning(f"   - Type: {type(slot_assignments)}")
            logger.warning(f"   - Keys (slot numbers): {list(slot_assignments.keys())}")
            if isinstance(slot_assignments, dict):
                for slot_num, assignment in list(slot_assignments.items())[:2]:
                    logger.warning(f"   - Slot {slot_num}: {assignment}")
        else:
            logger.warning(f"🔍 [GET-PLAYBOOKS DEBUG] slot_assignments is empty or missing")
        
        # Get position filters (merge with defaults if missing)
        default_position_filters = {
            "standard": [],
            "PG": [],
            "SG": [],
            "SF": [],
            "PF": [],
            "C": []
        }
        position_filters = playbook_settings.get("position_filters", default_position_filters)
        
        # Ensure all position keys exist (backward compatibility)
        for key in default_position_filters:
            if key not in position_filters:
                position_filters[key] = []
        
        # ✅ DEBUG: Log extracted percentages to see what we're returning
        # Get saved playbook percentages (motion, set_play, zone_defense)
        motion_percentages = playbook_settings.get("motion", {}) if playbook_settings else {}
        set_play_inside_percentages = playbook_settings.get("set_play_inside", {}) if playbook_settings else {}
        set_play_attack_percentages = playbook_settings.get("set_play_attack", {}) if playbook_settings else {}
        set_play_outside_percentages = playbook_settings.get("set_play_outside", {}) if playbook_settings else {}
        zone_defense_percentages = playbook_settings.get("zone_defense", {}) if playbook_settings else {}
        man_defense_percentages = playbook_settings.get("man_defense", {}) if playbook_settings else {}
        
        # ✅ DEBUG: Log extracted percentages structure
        logger.warning(f"🔍 [GET-PLAYBOOKS DEBUG] Extracted percentages structure:")
        logger.warning(f"   - motion_percentages type: {type(motion_percentages)}, keys: {list(motion_percentages.keys())[:3] if isinstance(motion_percentages, dict) else 'NOT A DICT'}")
        logger.warning(f"   - set_play_inside_percentages type: {type(set_play_inside_percentages)}, keys: {list(set_play_inside_percentages.keys())[:3] if isinstance(set_play_inside_percentages, dict) else 'NOT A DICT'}")
        logger.warning(f"   - set_play_attack_percentages type: {type(set_play_attack_percentages)}, keys: {list(set_play_attack_percentages.keys())[:3] if isinstance(set_play_attack_percentages, dict) else 'NOT A DICT'}")
        logger.warning(f"   - set_play_outside_percentages type: {type(set_play_outside_percentages)}, keys: {list(set_play_outside_percentages.keys())[:3] if isinstance(set_play_outside_percentages, dict) else 'NOT A DICT'}")
        
        # Get even_distribution_all flag (defaults to False if not set)
        even_distribution_all = playbook_settings.get("even_distribution_all", False)
        
        # ✅ PHASE 1.3: Telemetry - Log state read
        source_type = "gameStore" if (mode == "single" and use_gamemanager_settings and gm) else "backend"
        slot_count = len(playbook_settings.get("slot_assignments", {})) if playbook_settings else 0
        team_id_for_log = actual_team_id if mode == "single" and 'actual_team_id' in locals() else (authoritative_team_id if mode in ["franchise", "tournament"] else team_id)
        logger.warning(f"🔵 [STATE-READ] [get_playbooks] playbook_settings from {source_type} | team_id={team_id_for_log}, slot_assignments={slot_count}, endpoint=/api/playbooks")
        
        return {
            "motion": motion_plays,
            "set_play_inside": set_plays_inside,
            "set_play_attack": set_plays_attack,
            "set_play_outside": set_plays_outside,
            "slot_assignments": slot_assignments,
            "motion_dropdowns": motion_dropdowns,
            "position_filters": position_filters,
            "even_distribution_all": even_distribution_all,
            "playbook_percentages": {
                "motion": motion_percentages,
                "set_play_inside": set_play_inside_percentages,
                "set_play_attack": set_play_attack_percentages,
                "set_play_outside": set_play_outside_percentages,
                "zone_defense": zone_defense_percentages,
                "man_defense": man_defense_percentages
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # ✅ PERFORMANCE DIAGNOSTIC: Log total endpoint time
        if 'endpoint_start' in locals():
            total_time = (time.time() - endpoint_start) * 1000  # Convert to ms
            process_time = (time.time() - process_start) * 1000 if 'process_start' in locals() else 0
            logger.warning(f"⏱️ [PERF] /api/playbooks - Processing: {process_time:.2f}ms, Total: {total_time:.2f}ms, mode: {mode}")


class PlaybookSettingsRequest(BaseModel):
    mode: str
    team_id: str
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None
    playbook_settings: dict  # { "motion": {...}, "set_play_inside": {...}, etc. }


@router.post("/api/playbooks")
def save_playbooks(request: PlaybookSettingsRequest):
    """
    Save playbook settings (percentages) for a team.
    Stores in teams.{team_id}.playbook_settings in the appropriate mode document.
    """
    try:
        # ✅ PHASE 5.5: Use helper to get collection and doc_id (simplifies mode handling)
        collection, doc_id = get_collection_and_doc_id(
            request.mode,
            request.franchise_id,
            request.tournament_id,
            request.game_id
        )
        
        # ✅ PERFORMANCE: Load document first with projection (only needed fields)
        if request.mode == "single":
            doc = collection.find_one({"_id": doc_id})
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
        else:
            # ✅ PERFORMANCE: Use projection for franchise/tournament modes
            if request.mode == "franchise":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            elif request.mode == "tournament":
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        # ✅ FIX: Resolve team_id FIRST (before ensure_team_objects_exist) to use correct team_id
        # This ensures we're using the authoritative team_id from the document
        actual_team_id = request.team_id
        
        if request.mode == "franchise":
            # ✅ SS&S: Always use franchise document's user_team_object_id as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            actual_team_id = user_team_object_id
            
            # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        elif request.mode == "tournament":
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            actual_team_id = user_team_object_id
            
            # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        else:
            # ✅ PHASE 5.1: Use normalization helper for single mode
            # This centralizes team_id resolution logic and ensures consistent format
            actual_team_id = normalize_team_id_to_canonical(request.team_id, request.mode, doc)
            
            # ✅ PHASE 5.1: Verify resolved team_id is valid (sanity check)
            teams = doc.get("teams", {})
            if actual_team_id not in teams:
                logger.error(f"❌ [PLAYBOOKS SAVE] Resolved team_id '{actual_team_id}' not found in teams object!")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: Resolved team_id '{actual_team_id}' not found in game document"
                )
        
        # ✅ REMOVED: Verbose resolved team_id log - redundant with trace logs
        
        # ✅ REMOVED: Verbose slot assignment logs - redundant with trace logs
        
        # ✅ DEBUG: Log playbook_settings structure being saved (before ensure_team_objects_exist)
        if request.playbook_settings:
            logger.warning(f"🔍 [SAVE-PLAYBOOKS DEBUG] playbook_settings structure BEFORE save:")
            logger.warning(f"   - Top-level keys: {list(request.playbook_settings.keys())}")
            logger.warning(f"   - motion keys: {list(request.playbook_settings.get('motion', {}).keys())}")
            logger.warning(f"   - set_play_inside keys: {list(request.playbook_settings.get('set_play_inside', {}).keys())}")
            logger.warning(f"   - set_play_attack keys: {list(request.playbook_settings.get('set_play_attack', {}).keys())}")
            logger.warning(f"   - set_play_outside keys: {list(request.playbook_settings.get('set_play_outside', {}).keys())}")
            logger.warning(f"   - slot_assignments count: {len(request.playbook_settings.get('slot_assignments', {}))}")
            slot_sample = dict(list(request.playbook_settings.get('slot_assignments', {}).items())[:2])
            logger.warning(f"   - slot_assignments sample: {slot_sample}")
        
        # ✅ FIX: Ensure team objects exist AFTER resolving actual_team_id
        # This ensures we're using the correct team_id when creating/updating team objects
        ensure_team_objects_exist(
            request.mode, doc_id, actual_team_id,
            franchise_doc=doc if request.mode == "franchise" else None,
            tournament_doc=doc if request.mode == "tournament" else None
        )
        
        # ✅ FIX: Reload document after ensure_team_objects_exist to get latest data
        # ensure_team_objects_exist might have modified the document
        if request.mode == "franchise":
            doc = collection.find_one(
                {"_id": ObjectId(doc_id)},
                {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
            )
        elif request.mode == "tournament":
            doc = collection.find_one(
                {"_id": ObjectId(doc_id)},
                {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
            )
        elif request.mode == "single":
            # ✅ FIX: Reload game document with teams and home_team_id/away_team_id for Single Game mode
            doc = collection.find_one(
                {"_id": doc_id},
                {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
            )
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                    )
                except:
                    pass
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        # ✅ PHASE 5.7: Determine save location for franchise/tournament mode
        # If game is active, save to game doc; otherwise save to master doc
        save_to_game_doc = False
        game_doc_team_id = actual_team_id  # Default to actual_team_id
        if request.mode in ["franchise", "tournament"]:
            save_collection, save_doc_id, save_to_game_doc = get_save_location_for_franchise_tournament(
                request.mode,
                request.game_id,
                request.franchise_id,
                request.tournament_id
            )
            # Update collection and doc_id if saving to game doc
            if save_to_game_doc:
                collection = save_collection
                doc_id = save_doc_id
                # ✅ PHASE 5.7: Resolve team_id from game document when saving to game doc
                # The game doc uses different team_id keys than the franchise/tournament doc
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
                        # Find team_id in game doc that matches the user team
                        # Get user team name from franchise/tournament doc
                        user_team_name = None
                        if request.mode == "franchise":
                            user_team_name, _ = get_user_team_from_franchise(doc)
                        elif request.mode == "tournament":
                            user_team_name, _ = get_user_team_from_tournament(doc)
                        
                        # Find matching team_id in game doc
                        game_teams = game_doc.get("teams", {})
                        for tid, team_obj in game_teams.items():
                            if team_obj.get("name") == user_team_name:
                                game_doc_team_id = tid
                                break
                        
                        logger.warning(f"✅ [PHASE 5.7] Resolved game doc team_id: {game_doc_team_id} (from master team_id: {actual_team_id})")
                except Exception as e:
                    logger.warning(f"⚠️ [PHASE 5.7] Error resolving game doc team_id, using actual_team_id: {e}")
                    game_doc_team_id = actual_team_id
                
                logger.warning(f"✅ [PHASE 5.7] Saving playbooks to game doc (game_id={save_doc_id})")
            else:
                # Keep existing collection/doc_id (master doc)
                logger.warning(f"✅ [PHASE 5.7] Saving playbooks to master doc (franchise_id={request.franchise_id or request.tournament_id})")
        
        # ✅ PHASE 5.5: Use helper to get update path
        # If saving to game doc, use "teams" path with game doc team_id (like single mode)
        # If saving to master doc, use mode-specific path with master team_id
        if save_to_game_doc:
            update_path = f"teams.{game_doc_team_id}.playbook_settings"
        else:
            update_path = f"{get_team_settings_path(request.mode, actual_team_id)}.playbook_settings"
        
        # ✅ REMOVED: Verbose save logs - redundant with trace logs
        
        # For single game mode, try both UUID string and ObjectId formats
        if request.mode == "single":
            # ✅ PHASE 5.3: Simplified save flow - save to game document only (single source of truth)
            result = collection.update_one(
                {"_id": doc_id},
                {"$set": {update_path: request.playbook_settings}}
            )
            # If not found, try as ObjectId
            if result.matched_count == 0:
                try:
                    result = collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {update_path: request.playbook_settings}}
                    )
                except:
                    pass
        else:
            # ✅ PHASE 5.7: For franchise/tournament, save to determined location (game doc or master doc)
            # ✅ REMOVED: Verbose motion plays logs - redundant with trace logs
            
            if save_to_game_doc:
                # Saving to game doc - use string ID (may need ObjectId conversion)
                result = collection.update_one(
                    {"_id": doc_id},
                    {"$set": {update_path: request.playbook_settings}}
                )
                if result.matched_count == 0:
                    try:
                        result = collection.update_one(
                            {"_id": ObjectId(doc_id)},
                            {"$set": {update_path: request.playbook_settings}}
                        )
                    except:
                        pass
            else:
                # Saving to master doc - use ObjectId
                result = collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {update_path: request.playbook_settings}}
                )
        # ✅ REMOVED: Verbose MongoDB update result log - redundant with trace logs
            
            if result.matched_count == 0:
                logger.error(f"❌ [PLAYBOOKS SAVE] Document not found: mode={request.mode}, doc_id={doc_id}, save_to_game_doc={save_to_game_doc}")
                raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
            
            if result.modified_count == 0:
                logger.warning(f"⚠️ [PLAYBOOKS SAVE] Update matched but did not modify - document may already have identical data")
        
        if request.mode != "single" and result.matched_count == 0:
            logger.error(f"❌ [PLAYBOOKS SAVE] Document not found: mode={request.mode}, doc_id={doc_id}")
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        # ✅ PHASE 5.3: Removed verification reload - trust MongoDB update result
        # If update succeeded (matched_count > 0), settings are saved
        # ✅ SS&S: Apply settings immediately to GameManager if game is in cache
        # This ensures GameManager always reflects what's in DB (single source of truth)
        if request.mode == "single" and request.game_id and result and result.matched_count > 0:
            try:
                # Lazy import to avoid circular dependency
                from BackEnd.api.api import ongoing_games
                gm = ongoing_games.get(request.game_id)
                if gm:
                    # Verify game_id matches
                    if hasattr(gm, 'game_id') and str(gm.game_id) != str(request.game_id):
                        logger.warning(f"⚠️ [SAVE-PLAYBOOKS] Game ID mismatch: cache={gm.game_id}, request={request.game_id}")
                    else:
                        # Determine which team to update
                        target_team = None
                        if actual_team_id == gm.home_team.team_id:
                            target_team = gm.home_team
                        elif actual_team_id == gm.away_team.team_id:
                            target_team = gm.away_team
                        
                        if target_team:
                            # Apply playbook_settings
                            target_team.playbook_settings = request.playbook_settings
                            slot_count = len(request.playbook_settings.get("slot_assignments", {}))
                            logger.warning(f"✅ [SAVE-PLAYBOOKS] Applied playbook_settings to cached GameManager: team={target_team.name}, slot_assignments={slot_count}")
                        else:
                            logger.warning(f"⚠️ [SAVE-PLAYBOOKS] Team {actual_team_id} not found in cached GameManager (home={gm.home_team.team_id}, away={gm.away_team.team_id})")
            except Exception as e:
                logger.warning(f"⚠️ [SAVE-PLAYBOOKS] Error applying to cached GameManager (non-critical): {e}")
        
        logger.warning(f"✅ Saved playbook settings for team {actual_team_id} in {request.mode} mode")
        
        # ✅ PHASE 1.3: Telemetry - Log state write (after successful save)
        slot_count = len(request.playbook_settings.get("slot_assignments", {})) if request.playbook_settings else 0
        logger.warning(f"🟢 [STATE-WRITE] [save_playbooks] playbook_settings to backend | team_id={actual_team_id}, slot_assignments={slot_count}, endpoint=/api/playbooks")
        
        return {"success": True, "message": "Playbook settings saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

