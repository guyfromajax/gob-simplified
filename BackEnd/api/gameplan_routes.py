from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db, games_collection, franchise_team_data_collection
from BackEnd.api.franchise_routes import get_user_team_from_franchise
from BackEnd.api.tournament_routes import get_user_team_from_tournament
from BackEnd.utils.team_id_resolver import resolve_team_id_to_canonical as unified_resolve_team_id_to_canonical
from datetime import datetime

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
    ✅ UNIFIED: Normalize team_id to canonical format using unified resolver.
    
    This is a wrapper around the unified team_id_resolver that maintains backward
    compatibility with existing code (raises HTTPException instead of ValueError).
    
    Args:
        team_id: Team identifier (could be team name, ObjectId, or canonical team_id)
        mode: Game mode ("single", "franchise", "tournament")
        doc: Game/franchise/tournament document (required for single mode)
    
    Returns:
        Canonical team_id string (e.g., "MORRISTOWN", "OCEAN_CITY")
    
    Raises:
        HTTPException: If team_id cannot be resolved to canonical format
    """
    if not team_id:
        raise HTTPException(status_code=400, detail="team_id is required")
    
    try:
        # Use unified resolver
        canonical_id = unified_resolve_team_id_to_canonical(
            team_id,
            mode=mode,
            doc=doc
        )
        return canonical_id
    except ValueError as e:
        # Convert ValueError to HTTPException for API compatibility
        raise HTTPException(
            status_code=400,
            detail=str(e)
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
    
    # ✅ FTD: For franchise mode, check/update FTD collection instead of franchise_teams
    if mode == "franchise":
        # ✅ FTD: Check if FTD entry exists for this team
        try:
            team_object_id = ObjectId(team_id)
        except:
            logger.error(f"❌ [ENSURE-TEAM-OBJECTS] Invalid team_id format: {team_id}")
            raise HTTPException(status_code=400, detail=f"Invalid team_id format: {team_id}")
        
        ftd_doc = franchise_team_data_collection.find_one(
            {"franchise_id": ObjectId(doc_id), "team_id": team_object_id}
        )
        
        if not ftd_doc:
            # FTD entry doesn't exist, create it
            defaults = _get_cached_default_settings()
            populated_plays = _get_cached_populated_plays(mode="franchise")
            playbook_settings = _get_cached_playbook_settings()
            scouting_data = populate_scouting_data(mode="franchise")
            
            from BackEnd.models.team_manager import TeamManager
            team_attrs = TeamManager.init_team_attributes(mode="franchise")
            
            ftd_entry = {
                "franchise_id": ObjectId(doc_id),
                "team_id": team_object_id,
                "team_attributes": {
                    "shot_threshold": team_attrs["shot_threshold"],
                    "rebound_modifier": team_attrs["rebound_modifier"],
                    "team_chemistry": team_attrs["team_chemistry"],
                    "momentum_score": 0,
                    "offensive_efficiency": team_attrs["offensive_efficiency"],
                    "defensive_efficiency": team_attrs["defensive_efficiency"],
                    "discipline": team_attrs["discipline"],
                    "fight": team_attrs["fight"],
                    "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                    "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                    "fb_efficiency": team_attrs["fb_efficiency"],
                    "pt_efficiency": team_attrs["pt_efficiency"],
                },
                "strategy_settings": defaults["strategy_settings"].copy(),
                "playbook_settings": playbook_settings.copy(),
                "plays": populated_plays.copy(),
                "scouting_data": scouting_data,
                "training_reports": {},
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            franchise_team_data_collection.insert_one(ftd_entry)
            logger.info(f"✅ [ENSURE-TEAM-OBJECTS] Created FTD entry for team {team_id}")
            
            # Return the team data in expected format
            return {team_id: {
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
            }}
        else:
            # FTD entry exists, check if it has all required fields
            ftd_update = {}
            defaults = _get_cached_default_settings()
            
            if "strategy_settings" not in ftd_doc or not ftd_doc.get("strategy_settings"):
                ftd_update["strategy_settings"] = defaults["strategy_settings"].copy()
            if not ftd_doc.get("plays"):
                ftd_update["plays"] = _get_cached_populated_plays(mode="franchise").copy()
            if "playbook_settings" not in ftd_doc or not ftd_doc.get("playbook_settings"):
                ftd_update["playbook_settings"] = _get_cached_playbook_settings().copy()
            
            if ftd_update:
                franchise_team_data_collection.update_one(
                    {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                    {"$set": ftd_update}
                )
                # Update local copy
                for key, value in ftd_update.items():
                    ftd_doc[key] = value
            
            # Return the team data in expected format
            return {team_id: {
                "team_chemistry": ftd_doc.get("team_attributes", {}).get("team_chemistry", 0),
                "offensive_efficiency": ftd_doc.get("team_attributes", {}).get("offensive_efficiency", 0),
                "shot_threshold": ftd_doc.get("team_attributes", {}).get("shot_threshold", 100),
                "discipline": ftd_doc.get("team_attributes", {}).get("discipline", 0),
                "fight": ftd_doc.get("team_attributes", {}).get("fight", 0),
                "rebound_modifier": ftd_doc.get("team_attributes", {}).get("rebound_modifier", 1.0),
                "defensive_efficiency": ftd_doc.get("team_attributes", {}).get("defensive_efficiency", 0),
                "fb_efficiency": ftd_doc.get("team_attributes", {}).get("fb_efficiency", 0),
                "pt_efficiency": ftd_doc.get("team_attributes", {}).get("pt_efficiency", 0),
                "fb_opp_modifier": ftd_doc.get("team_attributes", {}).get("fb_opp_modifier", 0),
                "pt_opp_modifier": ftd_doc.get("team_attributes", {}).get("pt_opp_modifier", 0),
                "strategy_settings": ftd_doc.get("strategy_settings", {}),
                "plays": ftd_doc.get("plays", {}),
                "playbook_settings": ftd_doc.get("playbook_settings", {})
            }}
    
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
                        use_gamemanager_settings = True
                    else:
                        use_gamemanager_settings = False
                else:
                    use_gamemanager_settings = False
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
                                        break
            except Exception as e:
                pass
        
        # If not loading from game doc, load from master doc (existing logic)
        if not load_from_game_doc:
            # ✅ SS&S: Use document's user_team_object_id as authoritative source (aligns with Franchise pattern)
            # ✅ PERFORMANCE: Load document with projection (only needed fields) - reduces from 402KB to ~10KB (98% reduction)
            if mode == "franchise":
                # ✅ FTD: For franchise mode, only need user_team info (strategy_settings comes from FTD)
                doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {
                        "user_team_id": 1,
                        "user_team_object_id": 1,
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
            
            # ✅ FTD: Load strategy_settings from FTD collection instead of franchise doc
            try:
                team_object_id = ObjectId(authoritative_team_id)
            except:
                raise HTTPException(status_code=400, detail=f"Invalid team_id format: {authoritative_team_id}")
            
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                {"strategy_settings": 1}
            )
            
            if ftd_doc:
                team_obj = {
                    "strategy_settings": ftd_doc.get("strategy_settings", {})
                }
            else:
                # FTD doesn't exist - initialize with defaults
                defaults = get_default_settings()
                team_obj = {
                    "strategy_settings": defaults["strategy_settings"].copy()
                }
                # Create FTD entry (will be created by initialize_season, but handle missing case)
                logger.warning(f"⚠️ [GET GAMEPLAN] FTD not found for team {team_object_id}, using defaults")
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
            else:
                strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        elif mode == "single" and not use_gamemanager_settings:
            # ✅ SS&S: GameManager not available - use load_team_settings_from_doc() (same as simulate_quarter_endpoint)
            from BackEnd.api.api import load_team_settings_from_doc
            settings = load_team_settings_from_doc(mode, doc_id, team_id, team_id)
            strategy_settings = settings.get("strategy_settings") or team_obj.get("strategy_settings", defaults["strategy_settings"])
        else:
            # ✅ UNIFIED: For tournament/franchise modes, use unified extract function for consistent team_id resolution
            if mode == "franchise":
                # ✅ FTD: Strategy settings already loaded from FTD above
                strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
            else:
                # Tournament mode - use existing extract logic
                from BackEnd.utils.team_settings_manager import extract_team_settings
                team_identifier = team_id or (team_obj.get("name") if team_obj else None)
                if team_identifier:
                    strategy_settings = extract_team_settings(
                        saved_doc=doc,
                        team_identifier=team_identifier,
                        settings_type="strategy_settings",
                        mode=mode,
                        game_doc=None
                    )
                    if not strategy_settings:
                        strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
                else:
                    strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        
        
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
    from BackEnd.utils.team_settings_manager import save_team_settings
    
    try:
        # ✅ UNIFIED: Use unified save function for consistent team_id resolution
        # Note: validate_settings raises HTTPException on failure, so we validate first
        validate_settings(request.strategy_settings)
        
        success, actual_team_id, collection_name = save_team_settings(
            settings_type="strategy_settings",
            settings_data=request.strategy_settings,
            team_id=request.team_id,
            mode=request.mode,
            game_id=request.game_id,
            franchise_id=request.franchise_id,
            tournament_id=request.tournament_id,
            validate_fn=None,  # Already validated above (raises HTTPException)
            apply_to_gamemanager=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save game plan settings")
        
        logger.info(f"✅ Updated game plan for team {actual_team_id} in {request.mode} mode")
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
                            use_gamemanager_settings = True
                        else:
                            use_gamemanager_settings = False
                    else:
                        use_gamemanager_settings = False
                except Exception as e:
                    gm = None
                    use_gamemanager_settings = False
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
                                        break
            except Exception as e:
                pass
        
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
                    # ✅ FTD: For franchise mode, only need user_team info (playbook_settings comes from FTD)
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                    )
                elif mode == "tournament":
                    doc = collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                    )
                else:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
        
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
        # Otherwise, load from FTD (franchise) or ensure team objects exist (tournament/single)
        if load_from_game_doc:
            # Loading from game doc - team objects already exist from init_game
            teams = doc.get("teams", {})
            team_obj = teams.get(authoritative_team_id, {})
            actual_team_id = authoritative_team_id
        elif mode == "franchise":
            # ✅ FTD: Load playbook_settings from FTD collection instead of franchise doc
            from BackEnd.db import franchise_team_data_collection
            try:
                team_object_id = ObjectId(authoritative_team_id)
            except:
                raise HTTPException(status_code=400, detail=f"Invalid team_id format: {authoritative_team_id}")
            
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                {"playbook_settings": 1, "plays": 1}
            )
            
            if ftd_doc:
                # Load playbook_settings from FTD
                team_obj = {
                    "playbook_settings": ftd_doc.get("playbook_settings", {}),
                    "plays": ftd_doc.get("plays", {})
                }
            else:
                # FTD doesn't exist yet - initialize playbook_settings and create FTD entry
                playbook_settings = initialize_playbook_settings()
                populated_plays = _get_cached_populated_plays(mode="franchise")
                
                # Create FTD entry with default playbook_settings
                from BackEnd.models.team_manager import TeamManager
                team_attrs = TeamManager.init_team_attributes(mode="franchise")
                scouting_data = populate_scouting_data(mode="franchise")
                
                ftd_entry = {
                    "franchise_id": ObjectId(doc_id),
                    "team_id": team_object_id,
                    "team_attributes": {
                        "shot_threshold": team_attrs["shot_threshold"],
                        "rebound_modifier": team_attrs["rebound_modifier"],
                        "team_chemistry": team_attrs["team_chemistry"],
                        "momentum_score": 0,
                        "offensive_efficiency": team_attrs["offensive_efficiency"],
                        "defensive_efficiency": team_attrs["defensive_efficiency"],
                        "discipline": team_attrs["discipline"],
                        "fight": team_attrs["fight"],
                        "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                        "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                        "fb_efficiency": team_attrs["fb_efficiency"],
                        "pt_efficiency": team_attrs["pt_efficiency"],
                    },
                    "strategy_settings": {
                        "offense": 2, "inside": 2, "attack": 2, "outside": 2,
                        "tempo": 2, "defense": 2, "aggression": 2,
                        "hc_trap": 2, "fc_press": 2, "rebounding": 2
                    },
                    "playbook_settings": playbook_settings,
                    "plays": populated_plays,
                    "scouting_data": scouting_data,
                    "training_reports": {},
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                
                franchise_team_data_collection.update_one(
                    {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                    {"$set": ftd_entry},
                    upsert=True
                )
                
                team_obj = {
                    "playbook_settings": playbook_settings,
                    "plays": populated_plays
                }
            
            actual_team_id = authoritative_team_id
        else:
            # Tournament or single mode - use existing logic
            teams_dict = ensure_team_objects_exist(
                mode, doc_id, authoritative_team_id,
                franchise_doc=None,
                tournament_doc=doc if mode == "tournament" else None
            )
            
            if mode == "tournament":
                teams = teams_dict if isinstance(teams_dict, dict) else doc.get("teams", {})
                team_obj = teams.get(authoritative_team_id, {})
                actual_team_id = authoritative_team_id
            else:
                # ✅ PHASE 5.1: Use normalization helper for single mode
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
                teams = teams_dict if isinstance(teams_dict, dict) else doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # ✅ FTD: For franchise mode, ensure playbook_settings exists in FTD (not franchise doc)
        if mode == "franchise" and not load_from_game_doc:
            if not team_obj or not team_obj.get("playbook_settings"):
                playbook_settings = initialize_playbook_settings()
                # Update FTD
                franchise_team_data_collection.update_one(
                    {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                    {"$set": {"playbook_settings": playbook_settings}}
                )
                team_obj["playbook_settings"] = playbook_settings
        elif actual_team_id and (not team_obj or not team_obj.get("playbook_settings")):
            # Tournament/single mode - existing logic
            playbook_settings = initialize_playbook_settings()
            team_key = get_team_settings_path(mode, actual_team_id)
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {f"{team_key}.playbook_settings": playbook_settings}}
                )
                doc = collection.find_one({"_id": doc_id})
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}.playbook_settings": playbook_settings}}
                )
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            
            # Reload team_obj
            if mode == "tournament":
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
                if mode == "franchise" and not load_from_game_doc:
                    # ✅ FTD: Update FTD collection
                    franchise_team_data_collection.update_one(
                        {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                        {"$set": {"playbook_settings": existing_playbook_settings}}
                    )
                    team_obj["playbook_settings"] = existing_playbook_settings
                else:
                    team_key = f"teams.{actual_team_id}" if mode != "franchise" else f"franchise_teams.{actual_team_id}"
                    
                    if mode == "single":
                        result = collection.update_one(
                            {"_id": doc_id},
                            {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                        )
                        doc = collection.find_one({"_id": doc_id})
                    else:
                        result = collection.update_one(
                            {"_id": ObjectId(doc_id)},
                            {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                        )
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
            if mode == "franchise" and not load_from_game_doc:
                # ✅ FTD: Update FTD collection
                franchise_team_data_collection.update_one(
                    {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                    {"$set": {"plays": populated_plays}}
                )
                team_obj["plays"] = populated_plays
            else:
                team_key = f"teams.{actual_team_id}" if mode != "franchise" else f"franchise_teams.{actual_team_id}"
                
                if mode == "single":
                    collection.update_one(
                        {"_id": doc_id},
                        {"$set": {f"{team_key}.plays": populated_plays}}
                    )
                    doc = collection.find_one({"_id": doc_id})
                else:
                    collection.update_one(
                        {"_id": ObjectId(doc_id)},
                        {"$set": {f"{team_key}.plays": populated_plays}}
                    )
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
        # This ensures slot_assignments and other settings are current after all document reloads.
        # ✅ FTD: Skip for franchise when not loading from game doc – team_obj already from FTD;
        # franchise_teams is empty, so reload would overwrite with {} and break position_filters/plays.
        if mode == "franchise" and not load_from_game_doc:
            pass  # keep team_obj from FTD
        elif mode == "franchise":
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
                    new_playbook_settings = initialize_playbook_settings()
                    playbook_settings["position_filters"] = new_playbook_settings["position_filters"]
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
        elif mode == "franchise" and not load_from_game_doc:
            # ✅ FTD: Playbook settings (incl. position_filters) come from FTD team_obj; skip extract (reads franchise_teams).
            playbook_settings = (team_obj or {}).get("playbook_settings", {})
        else:
            # ✅ UNIFIED: For tournament/franchise (game doc) modes, use unified extract for consistent team_id resolution
            from BackEnd.utils.team_settings_manager import extract_team_settings
            team_identifier = team_id or (team_obj.get("name") if team_obj else None)
            if team_identifier and doc:
                playbook_settings = extract_team_settings(
                    saved_doc=doc,
                    team_identifier=team_identifier,
                    settings_type="playbook_settings",
                    mode=mode,
                    game_doc=None
                )
                if not playbook_settings:
                    playbook_settings = team_obj.get("playbook_settings", {})
            else:
                playbook_settings = team_obj.get("playbook_settings", {})
        
        slot_assignments = playbook_settings.get("slot_assignments", {}) if playbook_settings else {}
        motion_dropdowns = playbook_settings.get("motion_dropdowns", {}) if playbook_settings else {}
        
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
        
        # Get even_distribution_all flag (defaults to False if not set)
        even_distribution_all = playbook_settings.get("even_distribution_all", False)
        
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
    from BackEnd.utils.team_settings_manager import save_team_settings
    
    try:
        # ✅ UNIFIED: Use unified save function for consistent team_id resolution
        success, actual_team_id, collection_name = save_team_settings(
            settings_type="playbook_settings",
            settings_data=request.playbook_settings,
            team_id=request.team_id,
            mode=request.mode,
            game_id=request.game_id,
            franchise_id=request.franchise_id,
            tournament_id=request.tournament_id,
            validate_fn=None,  # Playbooks don't have required keys validation
            apply_to_gamemanager=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save playbook settings")
        
        logger.warning(f"✅ Saved playbook settings for team {actual_team_id} in {request.mode} mode")
        
        # ✅ PHASE 1.3: Telemetry - Log state write (after successful save)
        slot_count = len(request.playbook_settings.get("slot_assignments", {})) if request.playbook_settings else 0
        logger.warning(f"🟢 [STATE-WRITE] [save_playbooks] playbook_settings to backend | team_id={actual_team_id}, slot_assignments={slot_count}, endpoint=/api/playbooks")
        
        return {"success": True, "message": "Playbook settings saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving playbook settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

