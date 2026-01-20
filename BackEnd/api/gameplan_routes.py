from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db
from BackEnd.api.franchise_routes import get_user_team_from_franchise
from BackEnd.api.tournament_routes import get_user_team_from_tournament

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

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
def get_gameplan(mode: str, team_id: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None):
    """Get game plan settings for a team in the specified mode."""
    try:
        # ✅ PERFORMANCE: Removed verbose debug print
        # Determine which collection to use
        if mode == "franchise":
            if not franchise_id:
                raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
            doc_id = franchise_id
            collection = db.franchises
        elif mode == "tournament":
            if not tournament_id:
                raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
            doc_id = tournament_id
            collection = db.tournaments
        elif mode == "single":
            if not game_id:
                raise HTTPException(status_code=400, detail="game_id required for single game mode")
            doc_id = game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        
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
            franchise_teams = ensure_team_objects_exist(mode, doc_id, authoritative_team_id, franchise_doc=doc)
            team_obj = franchise_teams.get(authoritative_team_id, {})
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
            teams = ensure_team_objects_exist(mode, doc_id, authoritative_team_id, tournament_doc=doc)
            team_obj = teams.get(authoritative_team_id, {})
        else:
            # For single mode, try ObjectId first, then resolve name
            teams = ensure_team_objects_exist(mode, doc_id, team_id)
            actual_team_id = None
            
            # Strategy 1: Try direct ObjectId lookup
            if team_id in teams:
                actual_team_id = team_id
            else:
                # Strategy 2: Try to resolve as ObjectId
                try:
                    test_oid = ObjectId(team_id)
                    if str(test_oid) in teams:
                        actual_team_id = str(test_oid)
                except:
                    pass
                
                # Strategy 3: Resolve team name to ObjectId
                if not actual_team_id:
                    for tid in teams.keys():
                        try:
                            team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                            if team_doc and (team_doc["name"] == team_id or str(team_doc["_id"]) == team_id):
                                actual_team_id = tid
                                break
                        except:
                            continue
                
                # Strategy 4: Try teams collection lookup by name
                if not actual_team_id:
                    team_doc = db.teams.find_one({"name": team_id})
                    if team_doc:
                        team_oid = str(team_doc["_id"])
                        if team_oid in teams:
                            actual_team_id = team_oid
            
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # Get settings or return defaults
        defaults = get_default_settings()
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
            doc_id = request.game_id
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
            # ✅ PHASE 1.1: Simplified team ID resolution for Single Game mode (same as save_playbooks)
            # Game document stores teams using team_id as keys (e.g., "SOUTH_LANCASTER")
            # Frontend may send team name (e.g., "South Lancaster") or team_id
            # Resolution strategy: Try direct key match first, then name match, then fail loudly
            teams = doc.get("teams", {})
            home_team_id = doc.get("home_team_id")
            away_team_id = doc.get("away_team_id")
            
            actual_team_id = None
            
            # Step 1: Try direct key match (if request.team_id is already a team_id key)
            # ✅ CRITICAL: Only match if it looks like a team_id (uppercase, underscores)
            # This prevents matching legacy team name keys (e.g., "South Lancaster")
            if request.team_id in teams and (request.team_id.isupper() and "_" in request.team_id):
                actual_team_id = request.team_id
            
            # Step 2: If not found, iterate through teams to find by name match
            # ✅ FIX: Also check if key itself matches (handles legacy team name keys)
            if not actual_team_id:
                for tid in teams.keys():
                    team_obj = teams.get(tid, {})
                    # Match if key equals team name OR team_obj.name equals team name (case-insensitive)
                    if tid == request.team_id or (team_obj.get("name") or "").lower() == (request.team_id or "").lower():
                        actual_team_id = tid
                        break
            
            # Step 3: If still not found, try home/away fallback (only if they exist in teams)
            # ✅ FIX: Also check if key itself matches (handles legacy team name keys)
            if not actual_team_id:
                if home_team_id and home_team_id in teams:
                    home_team_obj = teams.get(home_team_id, {})
                    # Match if key equals team name OR team_obj.name equals team name
                    if home_team_id == request.team_id or home_team_obj.get("name") == request.team_id:
                        actual_team_id = home_team_id
                if not actual_team_id and away_team_id and away_team_id in teams:
                    away_team_obj = teams.get(away_team_id, {})
                    # Match if key equals team name OR team_obj.name equals team name
                    if away_team_id == request.team_id or away_team_obj.get("name") == request.team_id:
                        actual_team_id = away_team_id
            
            # Step 4: Fail loudly if resolution failed
            if not actual_team_id:
                available_teams = {tid: teams.get(tid, {}).get("name", "unknown") for tid in teams.keys()}
                logger.error(f"❌ [GAME PLAN SAVE] Could not resolve team '{request.team_id}' to team_id. Available teams: {available_teams}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not resolve team '{request.team_id}' to team_id in game document. Available teams: {list(available_teams.keys())}"
                )
            
            # ✅ PHASE 1.1: Verify resolved team_id is valid (sanity check)
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
        
        # ✅ DIAGNOSTIC: Log what strategy_settings we're about to save
        strategy_sample = dict(list(request.strategy_settings.items())[:5]) if request.strategy_settings else {}
        logger.warning(f"💾 [SAVE-GAMEPLAN] About to save strategy_settings for team {actual_team_id}: sample={strategy_sample}")
        
        # Update settings in the appropriate document
        if request.mode == "franchise":
            update_path = f"franchise_teams.{actual_team_id}.strategy_settings"
            update_fields = {
                update_path: request.strategy_settings
            }
        else:
            update_path = f"teams.{actual_team_id}.strategy_settings"
            update_fields = {
                update_path: request.strategy_settings
            }
        
        logger.warning(f"💾 [SAVE-GAMEPLAN] Update path: {update_path}, doc_id={doc_id}, mode={request.mode}")
        
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
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_fields}
            )
        
        # ✅ DIAGNOSTIC: Log DB write result
        if result and result.matched_count > 0:
            logger.warning(f"✅ [SAVE-GAMEPLAN] DB write SUCCESS: matched={result.matched_count}, modified={result.modified_count}")
            
            # ✅ DIAGNOSTIC: Verify settings were actually saved
            verify_doc = collection.find_one({"_id": doc_id if request.mode == "single" else ObjectId(doc_id)}, {update_path: 1})
            if verify_doc:
                if request.mode == "franchise":
                    saved_settings = verify_doc.get("franchise_teams", {}).get(actual_team_id, {}).get("strategy_settings")
                else:
                    saved_settings = verify_doc.get("teams", {}).get(actual_team_id, {}).get("strategy_settings")
                
                if saved_settings:
                    saved_sample = dict(list(saved_settings.items())[:5])
                    logger.warning(f"✅ [SAVE-GAMEPLAN] VERIFIED: Settings saved to DB: sample={saved_sample}")
                    # Verify key values match
                    if saved_settings.get("inside") == request.strategy_settings.get("inside"):
                        logger.warning(f"✅ [SAVE-GAMEPLAN] VERIFIED: inside value matches: {saved_settings.get('inside')}")
                    else:
                        logger.error(f"❌ [SAVE-GAMEPLAN] VERIFICATION FAILED: inside mismatch! saved={saved_settings.get('inside')}, requested={request.strategy_settings.get('inside')}")
                else:
                    logger.error(f"❌ [SAVE-GAMEPLAN] VERIFICATION FAILED: No strategy_settings found in saved document")
            else:
                logger.error(f"❌ [SAVE-GAMEPLAN] VERIFICATION FAILED: Could not read back saved document")
        else:
            logger.error(f"❌ [SAVE-GAMEPLAN] DB write FAILED: matched={result.matched_count if result else 0}, doc_id={doc_id}")
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} not found")
        
        logger.info(f"✅ Updated game plan for team {request.team_id} in {request.mode} mode")
        return {"success": True, "message": "Game plan saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating game plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/playbooks")
def get_playbooks(mode: str, team_id: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None):
    """
    Get plays for a team from the appropriate mode document.
    Returns plays organized by type (motion, set_play) and focus (inside, attack, outside).
    
    PERFORMANCE DIAGNOSTIC: This endpoint is instrumented with timing logs.
    """
    import time
    endpoint_start = time.time()
    
    try:
        # ✅ PERFORMANCE: Removed debug logging - only log errors and critical events
        # Determine which collection to use
        if mode == "franchise":
            if not franchise_id:
                raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
            doc_id = franchise_id
            collection = db.franchises
        elif mode == "tournament":
            if not tournament_id:
                raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
            doc_id = tournament_id
            collection = db.tournaments
        elif mode == "single":
            if not game_id:
                raise HTTPException(status_code=400, detail="game_id required for single game mode")
            doc_id = game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        
        # ✅ PERFORMANCE DIAGNOSTIC: Measure database query time
        query_start = time.time()
        
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
        
        query_time = (time.time() - query_start) * 1000  # Convert to ms
        doc_size = len(str(doc)) if doc else 0
        logger.warning(f"⏱️ [PERF] /api/playbooks - DB query: {query_time:.2f}ms, doc_size: {doc_size} bytes, mode: {mode}")
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"{mode.capitalize()} document not found")
        
        # ⏱️ PERFORMANCE: Start timing processing phase
        process_start = time.time()
        
        # ✅ FIX: Get authoritative team_id FIRST, then ensure team objects exist
        # Get team plays
        # ✅ SS&S: Use document's user_team_object_id as authoritative source (aligns with Franchise pattern)
        if mode == "franchise":
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
        
        # ✅ PERFORMANCE: Update in-memory doc with returned teams dict if needed
        # This ensures we have the latest data without reloading from database
        if mode == "franchise" and isinstance(teams_dict, dict):
            doc["franchise_teams"] = teams_dict
        elif mode == "tournament" and isinstance(teams_dict, dict):
            doc["teams"] = teams_dict
        elif mode == "single" and isinstance(teams_dict, dict):
            doc["teams"] = teams_dict
        
        # Get team_obj using authoritative team_id
        if mode == "franchise":
            franchise_teams = doc.get("franchise_teams", {})
            team_obj = franchise_teams.get(authoritative_team_id, {})
            actual_team_id = authoritative_team_id
        elif mode == "tournament":
            teams = doc.get("teams", {})
            team_obj = teams.get(authoritative_team_id, {})
            actual_team_id = authoritative_team_id
        else:
            teams = doc.get("teams", {})
            # ✅ PERFORMANCE: Removed debug logging - only log errors
            # For tournament/single mode, try to resolve team name to team_id
            actual_team_id = None
            # First try direct lookup
            if team_id in teams:
                actual_team_id = team_id
            else:
                # Try to find by team name - iterate through teams to find match
                for tid in teams.keys():
                    # Find the team that matches our input team_id (could be name or ObjectId)
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                    except:
                        # If tid is not a valid ObjectId, try as team_id string
                        team_doc = db.teams.find_one({"team_id": tid})
                    if team_doc and (team_doc.get("name") == team_id or str(team_doc.get("_id")) == team_id or team_doc.get("team_id") == team_id):
                        actual_team_id = tid
                        break
                # If still not found, try teams collection lookup by name
                if not actual_team_id:
                    team_doc = db.teams.find_one({"name": team_id})
                    if team_doc:
                        team_id_from_doc = team_doc.get("team_id")
                        # Try to find this team_id in the document's teams
                        for tid in teams.keys():
                            if tid == team_id_from_doc or str(tid) == str(team_doc.get("_id")):
                                actual_team_id = tid
                                break
            
            if not actual_team_id:
                logger.error(f"⚠️ [PLAYBOOKS] Could not resolve team_id '{team_id}' to a team in the document")
            
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # ✅ PERFORMANCE: Removed debug logging
        # Ensure playbook_settings exists (even if ensure_team_objects_exist missed it)
        # Check if team_obj exists and playbook_settings is missing or falsy (None, empty dict, etc.)
        # Note: Key might exist but value could be None or empty dict
        if actual_team_id and (not team_obj or not team_obj.get("playbook_settings")):
            playbook_settings = initialize_playbook_settings()
            # ✅ FIX: Use correct path based on mode (franchise_teams for franchise, teams for tournament/single)
            if mode == "franchise":
                team_key = f"franchise_teams.{actual_team_id}"
            else:
                team_key = f"teams.{actual_team_id}"
            
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
        
        # Get playbook settings (percentages, slot assignments, motion dropdowns, and position filters)
        playbook_settings = team_obj.get("playbook_settings", {})
        # ✅ PERFORMANCE: Removed debug logging - only log actual errors
        
        # ✅ SINGLE GAME CROSS-INSTANCE PERSISTENCE: Check core teams collection if game document has no settings
        if mode == "single" and (not playbook_settings or len(playbook_settings) == 0 or not any(playbook_settings.get(k) for k in ["motion", "set_play_inside", "set_play_attack", "set_play_outside", "zone_defense", "man_defense", "slot_assignments"])):
            try:
                # Try to load from core teams collection
                team_doc = db.teams.find_one({"name": team_id})
                if not team_doc:
                    team_doc = db.teams.find_one({"team_id": team_id})
                if not team_doc:
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(team_id)})
                    except:
                        pass
                
                if team_doc:
                    core_playbook_settings = team_doc.get("playbook_settings", {})
                    if core_playbook_settings and any(core_playbook_settings.get(k) for k in ["motion", "set_play_inside", "set_play_attack", "set_play_outside", "zone_defense", "man_defense", "slot_assignments"]):
                        playbook_settings = core_playbook_settings
                        # Also update the game document with these settings for consistency
                        try:
                            if mode == "single":
                                from BackEnd.db import games_collection
                                games_collection.update_one(
                                    {"_id": doc_id},
                                    {"$set": {f"teams.{actual_team_id}.playbook_settings": playbook_settings}}
                                )
                        except:
                            pass  # Non-critical
            except Exception as e:
                logger.warning(f"⚠️ Error loading from core teams collection (non-critical): {e}")
        
        slot_assignments = playbook_settings.get("slot_assignments", {})
        motion_dropdowns = playbook_settings.get("motion_dropdowns", {})
        
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
        
        # ✅ PERFORMANCE: Removed debug logging
        # Get saved playbook percentages (motion, set_play, zone_defense)
        motion_percentages = playbook_settings.get("motion", {})
        set_play_inside_percentages = playbook_settings.get("set_play_inside", {})
        set_play_attack_percentages = playbook_settings.get("set_play_attack", {})
        set_play_outside_percentages = playbook_settings.get("set_play_outside", {})
        zone_defense_percentages = playbook_settings.get("zone_defense", {})
        man_defense_percentages = playbook_settings.get("man_defense", {})
        
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
    try:
        logger.warning(f"🔍 [PLAYBOOKS SAVE] Received save request: mode={request.mode}, team_id={request.team_id}")
        logger.warning(f"🔍 [PLAYBOOKS SAVE] playbook_settings keys: {list(request.playbook_settings.keys()) if request.playbook_settings else 'EMPTY'}")
        if request.playbook_settings:
            logger.warning(f"🔍 [PLAYBOOKS SAVE] motion keys: {list(request.playbook_settings.get('motion', {}).keys())}")
            logger.warning(f"🔍 [PLAYBOOKS SAVE] set_play_inside keys: {list(request.playbook_settings.get('set_play_inside', {}).keys())}")
            logger.warning(f"🔍 [PLAYBOOKS SAVE] set_play_attack keys: {list(request.playbook_settings.get('set_play_attack', {}).keys())}")
            logger.warning(f"🔍 [PLAYBOOKS SAVE] set_play_outside keys: {list(request.playbook_settings.get('set_play_outside', {}).keys())}")
            logger.warning(f"🔍 [PLAYBOOKS SAVE] zone_defense keys: {list(request.playbook_settings.get('zone_defense', {}).keys())}")
            logger.warning(f"🔍 [PLAYBOOKS SAVE] man_defense keys: {list(request.playbook_settings.get('man_defense', {}).keys())}")
            # Log sample percentages
            if request.playbook_settings.get('motion'):
                sample_motion = dict(list(request.playbook_settings.get('motion', {}).items())[:3])
                logger.warning(f"🔍 [PLAYBOOKS SAVE] Sample motion percentages: {sample_motion}")
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
            doc_id = request.game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
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
            # ✅ PHASE 1.1: Simplified team ID resolution for Single Game mode
            # Game document stores teams using team_id as keys (e.g., "BENTLEY_TRUMAN")
            # Frontend may send team name (e.g., "Bentley-Truman") or team_id
            # Resolution strategy: Try direct key match first, then name match, then fail loudly
            teams = doc.get("teams", {})
            home_team_id = doc.get("home_team_id")
            away_team_id = doc.get("away_team_id")
            
            actual_team_id = None
            
            # Step 1: Try direct key match (if request.team_id is already a team_id key)
            # ✅ CRITICAL: Only match if it looks like a team_id (uppercase, underscores)
            # This prevents matching legacy team name keys (e.g., "South Lancaster")
            if request.team_id in teams and (request.team_id.isupper() and "_" in request.team_id):
                actual_team_id = request.team_id
            
            # Step 2: If not found, iterate through teams to find by name match
            # ✅ FIX: Also check if key itself matches (handles legacy team name keys)
            if not actual_team_id:
                for tid in teams.keys():
                    team_obj = teams.get(tid, {})
                    # Match if key equals team name OR team_obj.name equals team name (case-insensitive)
                    if tid == request.team_id or (team_obj.get("name") or "").lower() == (request.team_id or "").lower():
                        actual_team_id = tid
                        break
            
            # Step 3: If still not found, try home/away fallback (only if they exist in teams)
            # ✅ FIX: Also check if key itself matches (handles legacy team name keys)
            if not actual_team_id:
                if home_team_id and home_team_id in teams:
                    home_team_obj = teams.get(home_team_id, {})
                    # Match if key equals team name OR team_obj.name equals team name
                    if home_team_id == request.team_id or home_team_obj.get("name") == request.team_id:
                        actual_team_id = home_team_id
                if not actual_team_id and away_team_id and away_team_id in teams:
                    away_team_obj = teams.get(away_team_id, {})
                    # Match if key equals team name OR team_obj.name equals team name
                    if away_team_id == request.team_id or away_team_obj.get("name") == request.team_id:
                        actual_team_id = away_team_id
            
            # Step 4: Fail loudly if resolution failed
            if not actual_team_id:
                available_teams = {tid: teams.get(tid, {}).get("name", "unknown") for tid in teams.keys()}
                logger.error(f"❌ [PLAYBOOKS SAVE] Could not resolve team '{request.team_id}' to team_id. Available teams: {available_teams}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not resolve team '{request.team_id}' to team_id in game document. Available teams: {list(available_teams.keys())}"
                )
            
            # ✅ PHASE 1.1: Verify resolved team_id is valid (sanity check)
            if actual_team_id not in teams:
                logger.error(f"❌ [PLAYBOOKS SAVE] Resolved team_id '{actual_team_id}' not found in teams object!")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: Resolved team_id '{actual_team_id}' not found in game document"
                )
        
        logger.warning(f"🔍 [PLAYBOOKS SAVE] Resolved actual_team_id: {actual_team_id} (from request.team_id: {request.team_id})")
        
        # ✅ DIAGNOSTIC: Log slot_assignments being saved
        if request.playbook_settings and request.playbook_settings.get("slot_assignments"):
            slot_count = len(request.playbook_settings.get("slot_assignments", {}))
            logger.warning(f"📋 [SAVE-PLAYBOOKS] Saving {slot_count} slot assignments for team {actual_team_id}")
            # Log sample slot assignment
            sample_slot = next(iter(request.playbook_settings.get("slot_assignments", {}).values()), None)
            if sample_slot:
                logger.warning(f"📋 [SAVE-PLAYBOOKS] Sample slot assignment: section={sample_slot.get('section')}, playId={sample_slot.get('playId')}, playName={sample_slot.get('playName')}")
        
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
        
        # Update playbook_settings in the appropriate document
        if request.mode == "franchise":
            update_path = f"franchise_teams.{actual_team_id}.playbook_settings"
        else:
            update_path = f"teams.{actual_team_id}.playbook_settings"
        
        logger.warning(f"🔍 [PLAYBOOKS SAVE] Update path: {update_path}")
        logger.warning(f"🔍 [PLAYBOOKS SAVE] actual_team_id: {actual_team_id}")
        logger.warning(f"🔍 [PLAYBOOKS SAVE] doc_id: {doc_id}")
        
        # ✅ DIAGNOSTIC: Log what we're about to write to DB
        logger.warning(f"💾 [SAVE-PLAYBOOKS] About to write to DB: update_path={update_path}, doc_id={doc_id}, mode={request.mode}")
        logger.warning(f"💾 [SAVE-PLAYBOOKS] Settings structure: slot_assignments={bool(request.playbook_settings.get('slot_assignments'))}, motion={bool(request.playbook_settings.get('motion'))}, set_play_inside={bool(request.playbook_settings.get('set_play_inside'))}")
        
        # For single game mode, try both UUID string and ObjectId formats
        if request.mode == "single":
            # ✅ SINGLE GAME CROSS-INSTANCE PERSISTENCE: Save to both game document AND core teams collection
            # This ensures settings persist across Single Game instances
            
            # 1. Save to game document (for current game instance)
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
            
            # ✅ DIAGNOSTIC: Log DB write result
            if result and result.matched_count > 0:
                logger.warning(f"✅ [SAVE-PLAYBOOKS] DB write SUCCESS: matched={result.matched_count}, modified={result.modified_count}")
            else:
                logger.error(f"❌ [SAVE-PLAYBOOKS] DB write FAILED: matched={result.matched_count if result else 0}, doc_id={doc_id}")
            
            # 2. Save to core teams collection (for cross-instance persistence)
            # Resolve team_id to ObjectId for teams collection lookup
            team_obj_id = actual_team_id
            try:
                # Try to find team in core teams collection
                team_doc = db.teams.find_one({"name": request.team_id})
                if not team_doc:
                    # Try by team_id
                    team_doc = db.teams.find_one({"team_id": request.team_id})
                if not team_doc:
                    # Try as ObjectId
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(actual_team_id)})
                    except:
                        pass
                
                if team_doc:
                    team_obj_id = str(team_doc.get("_id"))
                    db.teams.update_one(
                        {"_id": ObjectId(team_obj_id)},
                        {"$set": {"playbook_settings": request.playbook_settings}},
                        upsert=False  # Don't create if doesn't exist
                    )
                    logger.warning(f"✅ Saved playbook settings to core teams collection for team {team_obj_id} (cross-instance persistence)")
                else:
                    logger.warning(f"⚠️ Could not find team in core teams collection for cross-instance persistence: {request.team_id}")
            except Exception as e:
                logger.warning(f"⚠️ Error saving to core teams collection (non-critical): {e}")
        else:
            # ✅ CRITICAL: Log the exact data being saved before the update
            logger.warning(f"🔍 [PLAYBOOKS SAVE] About to save playbook_settings with {len(request.playbook_settings.get('motion', {}))} motion plays")
            if request.playbook_settings.get('motion'):
                sample_motion = dict(list(request.playbook_settings.get('motion', {}).items())[:3])
                logger.warning(f"🔍 [PLAYBOOKS SAVE] Sample motion percentages being saved: {sample_motion}")
            
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {update_path: request.playbook_settings}}
            )
            logger.warning(f"🔍 [PLAYBOOKS SAVE] MongoDB update result: matched={result.matched_count}, modified={result.modified_count}")
            
            if result.matched_count == 0:
                logger.error(f"❌ [PLAYBOOKS SAVE] Document not found: mode={request.mode}, doc_id={doc_id}")
                raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
            
            if result.modified_count == 0:
                logger.warning(f"⚠️ [PLAYBOOKS SAVE] Update matched but did not modify - document may already have identical data")
        
        if request.mode != "single" and result.matched_count == 0:
            logger.error(f"❌ [PLAYBOOKS SAVE] Document not found: mode={request.mode}, doc_id={doc_id}")
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        # Verify the save by reading it back
        try:
            if request.mode == "franchise":
                verify_doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"franchise_teams": 1, "_id": 1}
                )
                if verify_doc:
                    saved_settings = verify_doc.get("franchise_teams", {}).get(actual_team_id, {}).get("playbook_settings", {})
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - motion keys: {list(saved_settings.get('motion', {}).keys())}")
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - set_play_inside keys: {list(saved_settings.get('set_play_inside', {}).keys())}")
                    if saved_settings.get('motion'):
                        sample = dict(list(saved_settings.get('motion', {}).items())[:3])
                        logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - sample motion percentages: {sample}")
                        # ✅ CRITICAL: Log ALL motion percentages to verify they match what was sent
                        all_motion = saved_settings.get('motion', {})
                        logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - ALL motion percentages: {all_motion}")
                    else:
                        logger.error(f"❌ [PLAYBOOKS SAVE] Verified save - motion is EMPTY or MISSING!")
                else:
                    logger.error(f"❌ [PLAYBOOKS SAVE] Verification failed - document not found")
            elif request.mode == "tournament":
                verify_doc = collection.find_one(
                    {"_id": ObjectId(doc_id)},
                    {"teams": 1, "_id": 1}
                )
                if verify_doc:
                    saved_settings = verify_doc.get("teams", {}).get(actual_team_id, {}).get("playbook_settings", {})
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - motion keys: {list(saved_settings.get('motion', {}).keys())}")
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - set_play_inside keys: {list(saved_settings.get('set_play_inside', {}).keys())}")
            else:
                verify_doc = collection.find_one({"_id": doc_id}, {"teams": 1, "_id": 1})
                if verify_doc:
                    saved_settings = verify_doc.get("teams", {}).get(actual_team_id, {}).get("playbook_settings", {})
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - motion keys: {list(saved_settings.get('motion', {}).keys())}")
                    logger.warning(f"✅ [PLAYBOOKS SAVE] Verified save - set_play_inside keys: {list(saved_settings.get('set_play_inside', {}).keys())}")
            
            if not verify_doc:
                logger.warning(f"⚠️ [PLAYBOOKS SAVE] Could not verify save - document not found")
        except Exception as e:
            logger.warning(f"⚠️ [PLAYBOOKS SAVE] Error during verification (non-critical): {e}")
        
        logger.warning(f"✅ Saved playbook settings for team {actual_team_id} in {request.mode} mode")
        return {"success": True, "message": "Playbook settings saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

