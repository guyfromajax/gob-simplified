from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db

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
    playcall_settings: dict[str, int]
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
    playcall_settings: dict[str, int]
    strategy_settings: dict[str, int]
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None


def validate_settings(playcall_settings: dict, strategy_settings: dict):
    """Validate that settings are integers 0-4 and offense not all zero."""
    # Validate playcall_settings (offense)
    for key, value in playcall_settings.items():
        if not isinstance(value, int) or value < 0 or value > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Playcall setting '{key}' must be an integer between 0 and 4"
            )
    
    # Validate strategy_settings (defense/general)
    for key, value in strategy_settings.items():
        if not isinstance(value, int) or value < 0 or value > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy setting '{key}' must be an integer between 0 and 4"
            )
    
    # Ensure at least one offense setting is above 0
    if all(v == 0 for v in playcall_settings.values()):
        raise HTTPException(
            status_code=400,
            detail="At least one Offense setting must be above 'Never'. Please increase any Offense slider."
        )


def get_default_settings():
    """Return default settings (all set to 2 = Normal)."""
    return {
        "playcall_settings": {
            "Base": 2,
            "Freelance": 2,
            "Inside": 2,
            "Attack": 2,
            "Outside": 2,
            "Set": 2
        },
        "strategy_settings": {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "half_court_trap": 2,
            "full_court_press": 2
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
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
                    "effectiveness": 0.0  # Calculated effectiveness from stats
                }
            }
            
            # Add season_stats for tournament and franchise modes
            if mode in ["tournament", "franchise"]:
                play_data["season_stats"] = {
                    "times_run": 0,
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
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
    Initialize playbook_settings with defaults (Option B: first play = 100%, others = 0%).
    
    Returns:
        dict: playbook_settings structure with defaults:
        - motion: {first_play_name: 100}
        - set_play_inside: {first_play_name: 100}
        - set_play_attack: {first_play_name: 100}
        - set_play_outside: {first_play_name: 100}
        - zone_defense: {"2-3 Zone": 100}
        - man_defense: {"Man": 100}
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
            }
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
        
        # Sort plays by name for consistency, then set first play to 100%
        if motion_plays:
            motion_plays.sort()
            playbook_settings["motion"][motion_plays[0]] = 100
        
        if set_plays_inside:
            set_plays_inside.sort()
            playbook_settings["set_play_inside"][set_plays_inside[0]] = 100
        
        if set_plays_attack:
            set_plays_attack.sort()
            playbook_settings["set_play_attack"][set_plays_attack[0]] = 100
        
        if set_plays_outside:
            set_plays_outside.sort()
            playbook_settings["set_play_outside"][set_plays_outside[0]] = 100
        
        # Zone defense: first zone gets 100%
        # Zone defenses are hardcoded: "2-3 Zone", "3-2 Zone", "1-3-1 Zone"
        zone_defenses = ["2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        if zone_defenses:
            playbook_settings["zone_defense"][zone_defenses[0]] = 100
        
        # Man defense: "Man" gets 100%
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
        
        # PG, SG, SF, C remain empty for now (can be populated later)
        
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
            }
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


def ensure_team_objects_exist(mode: str, doc_id: str, team_id: str):
    """Ensure team objects exist in the mode document. Create with defaults if missing."""
    collection = None
    
    if mode == "franchise":
        collection = db.franchises
    elif mode == "tournament":
        collection = db.tournaments
    elif mode == "single":
        collection = db.games
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    
    # Handle different ID formats for different modes
    if mode == "single":
        # For single game mode, try both UUID string and ObjectId formats
        doc = collection.find_one({"_id": doc_id})
        if not doc:
            # Try as ObjectId if UUID string lookup failed
            try:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            except:
                pass
    else:
        # For franchise/tournament modes, use ObjectId
        doc = collection.find_one({"_id": ObjectId(doc_id)})
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"{mode.capitalize()} not found")
    
    # For franchise mode, ensure all 8 teams have objects
    if mode == "franchise":
        franchise_teams = doc.get("franchise_teams", {})
        teams = list(db.teams.find())
        defaults = get_default_settings()
        updated = False
        
        # Get populated plays for all teams
        populated_plays = populate_team_plays()
        # Initialize playbook_settings with defaults
        playbook_settings = initialize_playbook_settings()
        
        from BackEnd.models.team_manager import TeamManager
        for team in teams:
            tid = str(team["_id"])
            if tid not in franchise_teams:
                # Use mode initialization system for new franchise teams
                team_attrs = TeamManager.init_team_attributes(mode="franchise")
                franchise_teams[tid] = {
                    "team_chemistry": team_attrs["team_chemistry"],
                    "offensive_efficiency": team_attrs["offensive_efficiency"],
                    "shot_threshold": team_attrs["shot_threshold"],
                    "turnover_modifier": team_attrs["turnover_modifier"],
                    "foul_modifier": team_attrs["foul_modifier"],
                    "rebound_modifier": team_attrs["rebound_modifier"],
                    "defensive_efficiency": team_attrs["defensive_efficiency"],
                    "fb_efficiency": team_attrs["fb_efficiency"],
                    "pt_efficiency": team_attrs["pt_efficiency"],
                    "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                    "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                    "playcall_settings": defaults["playcall_settings"].copy(),
                    "strategy_settings": defaults["strategy_settings"].copy(),
                    "plays": populated_plays.copy(),
                    "playbook_settings": playbook_settings.copy()
                }
                updated = True
            elif "playcall_settings" not in franchise_teams[tid] or "strategy_settings" not in franchise_teams[tid] or not franchise_teams[tid].get("plays") or "playbook_settings" not in franchise_teams[tid]:
                # Add missing settings to existing team object
                if "playcall_settings" not in franchise_teams[tid]:
                    franchise_teams[tid]["playcall_settings"] = defaults["playcall_settings"].copy()
                if "strategy_settings" not in franchise_teams[tid]:
                    franchise_teams[tid]["strategy_settings"] = defaults["strategy_settings"].copy()
                if not franchise_teams[tid].get("plays"):
                    franchise_teams[tid]["plays"] = populated_plays.copy()
                if "playbook_settings" not in franchise_teams[tid]:
                    franchise_teams[tid]["playbook_settings"] = playbook_settings.copy()
                updated = True
        
        if updated:
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"franchise_teams": franchise_teams}}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {"franchise_teams": franchise_teams}}
                )
        
        return franchise_teams
    
    # For tournament and single game modes
    else:
        # Normalize team_id to ObjectId - try name first, then ObjectId
        team = db.teams.find_one({"name": team_id})
        if not team:
            try:
                team = db.teams.find_one({"_id": ObjectId(team_id)})
            except:
                pass
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        actual_team_id = str(team["_id"])
        
        # Check if team object exists
        team_key = f"teams.{actual_team_id}"
        team_obj = doc.get("teams", {}).get(actual_team_id)
        
        if not team_obj:
            # Create team object with defaults
            defaults = get_default_settings()
            # Pass mode to populate_team_plays for tournament randomization
            populated_plays = populate_team_plays(mode=mode)
            # Initialize scouting_data with randomized values for tournament mode
            scouting_data = populate_scouting_data(mode=mode)
            # Initialize playbook_settings with defaults (first play = 100% per section)
            playbook_settings = initialize_playbook_settings()
            
            # ✅ SS&S: Use mode initialization system for tournament teams (matches Franchise pattern)
            # This randomizes team attributes per Mode Initialization System documentation
            from BackEnd.models.team_manager import TeamManager
            team_attrs = TeamManager.init_team_attributes(mode=mode)
            
            team_obj = {
                "team_chemistry": team_attrs["team_chemistry"],
                "offensive_efficiency": team_attrs["offensive_efficiency"],
                "shot_threshold": team_attrs["shot_threshold"],
                "turnover_modifier": team_attrs["turnover_modifier"],
                "foul_modifier": team_attrs["foul_modifier"],
                "rebound_modifier": team_attrs["rebound_modifier"],
                "defensive_efficiency": team_attrs["defensive_efficiency"],
                "fb_efficiency": team_attrs["fb_efficiency"],
                "pt_efficiency": team_attrs["pt_efficiency"],
                "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                "playcall_settings": defaults["playcall_settings"].copy(),
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
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}": team_obj}}
                )
        elif "playcall_settings" not in team_obj or "strategy_settings" not in team_obj or not team_obj.get("plays") or "shot_threshold" not in team_obj or "playbook_settings" not in team_obj:
            # Add missing settings
            defaults = get_default_settings()
            # Pass mode to populate_team_plays for tournament randomization
            populated_plays = populate_team_plays(mode=mode)
            # Initialize playbook_settings if missing
            if "playbook_settings" not in team_obj:
                playbook_settings = initialize_playbook_settings()
                logger.warning(f"⚠️ [ENSURE TEAM OBJECTS] playbook_settings missing for team {actual_team_id}, initializing...")
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
            if "playcall_settings" not in team_obj:
                updates[f"{team_key}.playcall_settings"] = defaults["playcall_settings"].copy()
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
                updates[f"{team_key}.turnover_modifier"] = team_attrs["turnover_modifier"]
                updates[f"{team_key}.foul_modifier"] = team_attrs["foul_modifier"]
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
        print(f"🔍 Gameplan API called with: mode={mode}, team_id={team_id}, franchise_id={franchise_id}, tournament_id={tournament_id}, game_id={game_id}")
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
        
        # ✅ SS&S: Prefer ObjectId directly, resolve name only if needed
        # Ensure team objects exist (creates if missing)
        if mode == "franchise":
            # For franchise mode, team_id should be ObjectId string
            franchise_teams = ensure_team_objects_exist(mode, doc_id, team_id)
            team_obj = franchise_teams.get(team_id, {})
        else:
            # For tournament/single mode, try ObjectId first, then resolve name
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
        playcall_settings = team_obj.get("playcall_settings", defaults["playcall_settings"])
        strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        
        return {
            "playcall_settings": playcall_settings,
            "strategy_settings": strategy_settings
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
        validate_settings(request.playcall_settings, request.strategy_settings)
        
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
        
        # ✅ SS&S: Resolve team_id to ObjectId if needed (for tournament/single mode)
        actual_team_id = request.team_id
        if request.mode != "franchise":
            # For tournament/single mode, resolve team_id to ObjectId
            try:
                # Try as ObjectId first
                test_oid = ObjectId(request.team_id)
                actual_team_id = str(test_oid)
            except:
                # If not ObjectId, resolve by name
                team_doc = db.teams.find_one({"name": request.team_id})
                if team_doc:
                    actual_team_id = str(team_doc["_id"])
                # If not found, use original (will fail in ensure_team_objects_exist if invalid)
        
        # Ensure team objects exist first
        ensure_team_objects_exist(request.mode, doc_id, actual_team_id)
        
        # Update settings in the appropriate document
        if request.mode == "franchise":
            update_fields = {
                f"franchise_teams.{actual_team_id}.playcall_settings": request.playcall_settings,
                f"franchise_teams.{actual_team_id}.strategy_settings": request.strategy_settings
            }
        else:
            update_fields = {
                f"teams.{actual_team_id}.playcall_settings": request.playcall_settings,
                f"teams.{actual_team_id}.strategy_settings": request.strategy_settings
            }
        
        # Handle different ID formats for different modes
        if request.mode == "single":
            result = collection.update_one(
                {"_id": doc_id},
                {"$set": update_fields}
            )
        else:
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_fields}
            )
        
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
    """
    try:
        logger.info(f"🔍 [GET PLAYBOOKS] Called with mode={mode}, team_id={team_id}, franchise_id={franchise_id}, tournament_id={tournament_id}, game_id={game_id}")
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
        
        # Load the document
        # For single game mode, try both UUID string and ObjectId formats
        if mode == "single":
            doc = collection.find_one({"_id": doc_id})
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
        else:
            doc = collection.find_one({"_id": ObjectId(doc_id)})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"{mode.capitalize()} document not found")
        
        # Ensure team objects exist first (this will create them if missing)
        ensure_team_objects_exist(mode, doc_id, team_id)
        
        # Reload document to get updated team objects (including any position filter updates)
        if mode == "single":
            doc = collection.find_one({"_id": doc_id})
        else:
            doc = collection.find_one({"_id": ObjectId(doc_id)})
        
        # Get team plays
        # ✅ Handle team name resolution (team_id might be a name, need to find actual team_id)
        if mode == "franchise":
            franchise_teams = doc.get("franchise_teams", {})
            logger.info(f"🔍 [PLAYBOOKS] Looking for team_id='{team_id}' in franchise document with {len(franchise_teams)} teams")
            logger.info(f"🔍 [PLAYBOOKS] Available franchise team keys: {list(franchise_teams.keys())[:5]}...")  # Log first 5 keys
            
            # Try to resolve team name to team_id (same logic as tournament/single mode)
            actual_team_id = None
            # First try direct lookup
            if team_id in franchise_teams:
                actual_team_id = team_id
                logger.info(f"✅ [PLAYBOOKS] Found franchise team_id directly: {actual_team_id}")
            else:
                # Try to find by team name - iterate through franchise_teams to find match
                for tid in franchise_teams.keys():
                    # Find the team that matches our input team_id (could be name or ObjectId)
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                    except:
                        # If tid is not a valid ObjectId, try as team_id string
                        team_doc = db.teams.find_one({"team_id": tid})
                    if team_doc and (team_doc.get("name") == team_id or str(team_doc.get("_id")) == team_id or team_doc.get("team_id") == team_id):
                        actual_team_id = tid
                        logger.info(f"✅ [PLAYBOOKS] Found franchise team by name lookup: {actual_team_id} (team name: {team_doc.get('name')})")
                        break
                # If still not found, try teams collection lookup by name
                if not actual_team_id:
                    team_doc = db.teams.find_one({"name": team_id})
                    if team_doc:
                        team_id_from_doc = team_doc.get("team_id")
                        logger.info(f"🔍 [PLAYBOOKS] Found franchise team in teams collection: {team_doc.get('name')}, team_id={team_id_from_doc}, _id={team_doc.get('_id')}")
                        # Try to find this team_id in the document's franchise_teams
                        for tid in franchise_teams.keys():
                            if tid == team_id_from_doc or str(tid) == str(team_doc.get("_id")):
                                actual_team_id = tid
                                logger.info(f"✅ [PLAYBOOKS] Matched franchise team in document: {actual_team_id}")
                                break
            
            if not actual_team_id:
                logger.warning(f"⚠️ [PLAYBOOKS] Could not resolve franchise team_id '{team_id}' to a team in the document")
                logger.warning(f"⚠️ [PLAYBOOKS] Available franchise teams in document: {list(franchise_teams.keys())}")
            
            team_obj = franchise_teams.get(actual_team_id, {}) if actual_team_id else {}
        else:
            teams = doc.get("teams", {})
            logger.info(f"🔍 [PLAYBOOKS] Looking for team_id='{team_id}' in document with {len(teams)} teams")
            logger.info(f"🔍 [PLAYBOOKS] Available team keys: {list(teams.keys())[:5]}...")  # Log first 5 keys
            
            # For tournament/single mode, try to resolve team name to team_id
            actual_team_id = None
            # First try direct lookup
            if team_id in teams:
                actual_team_id = team_id
                logger.info(f"✅ [PLAYBOOKS] Found team_id directly: {actual_team_id}")
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
                        logger.info(f"✅ [PLAYBOOKS] Found team by name lookup: {actual_team_id} (team name: {team_doc.get('name')})")
                        break
                # If still not found, try teams collection lookup by name
                if not actual_team_id:
                    team_doc = db.teams.find_one({"name": team_id})
                    if team_doc:
                        team_id_from_doc = team_doc.get("team_id")
                        logger.info(f"🔍 [PLAYBOOKS] Found team in teams collection: {team_doc.get('name')}, team_id={team_id_from_doc}, _id={team_doc.get('_id')}")
                        # Try to find this team_id in the document's teams
                        for tid in teams.keys():
                            if tid == team_id_from_doc or str(tid) == str(team_doc.get("_id")):
                                actual_team_id = tid
                                logger.info(f"✅ [PLAYBOOKS] Matched team in document: {actual_team_id}")
                                break
            
            if not actual_team_id:
                logger.warning(f"⚠️ [PLAYBOOKS] Could not resolve team_id '{team_id}' to a team in the document")
                logger.warning(f"⚠️ [PLAYBOOKS] Available teams in document: {list(teams.keys())}")
            
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # Ensure playbook_settings exists (even if ensure_team_objects_exist missed it)
        if team_obj and "playbook_settings" not in team_obj:
            logger.warning(f"⚠️ [GET PLAYBOOKS] playbook_settings missing for team {actual_team_id}, adding now...")
            playbook_settings = initialize_playbook_settings()
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
            # Reload team_obj
            teams = doc.get("teams", {})
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
            logger.warning(f"⚠️ [GET PLAYBOOKS] playbook_settings added, reloaded team_obj has playbook_settings: {bool(team_obj.get('playbook_settings'))}")
        
        # Check if position filters need to be populated (after ensure_team_objects_exist and document reload)
        logger.warning(f"⚠️ [GET PLAYBOOKS] Checking position filters for team {actual_team_id}, team_obj has playbook_settings: {bool(team_obj and team_obj.get('playbook_settings'))}")
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
                logger.warning(f"⚠️ [GET PLAYBOOKS] Position filters empty, populating now for team {actual_team_id}...")
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
                logger.warning(f"⚠️ [GET PLAYBOOKS] Position filters populated, update result: matched={result.matched_count}, modified={result.modified_count}")
                
                # Reload document again to get the updated position filters
                if mode == "single":
                    doc = collection.find_one({"_id": doc_id})
                else:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                
                # Reload team_obj with updated position filters
                if mode == "franchise":
                    team_obj = doc.get("franchise_teams", {}).get(actual_team_id, {})
                else:
                    team_obj = doc.get("teams", {}).get(actual_team_id, {})
        
        plays = team_obj.get("plays", {})
        logger.info(f"🔍 [PLAYBOOKS] Found {len(plays)} plays for team")
        
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
        logger.info(f"🔍 [GET PLAYBOOKS] Loaded position_filters from playbook_settings: {position_filters}")
        
        # Ensure all position keys exist (backward compatibility)
        for key in default_position_filters:
            if key not in position_filters:
                position_filters[key] = []
        
        # Log the counts for each position
        for key in ["standard", "PG", "SG", "SF", "PF", "C"]:
            count = len(position_filters.get(key, []))
            logger.info(f"🔍 [GET PLAYBOOKS] Position '{key}' has {count} play_ids")
        
        return {
            "motion": motion_plays,
            "set_play_inside": set_plays_inside,
            "set_play_attack": set_plays_attack,
            "set_play_outside": set_plays_outside,
            "slot_assignments": slot_assignments,
            "motion_dropdowns": motion_dropdowns,
            "position_filters": position_filters
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Ensure team objects exist first (this will resolve team_id if it's a name)
        ensure_team_objects_exist(request.mode, doc_id, request.team_id)
        
        # ✅ Resolve team_id (might be a name, need actual team_id for update path)
        actual_team_id = request.team_id
        
        # Load document for team resolution
        if request.mode == "single":
            doc = collection.find_one({"_id": doc_id})
            if not doc:
                # Try as ObjectId if UUID string lookup failed
                try:
                    doc = collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
        else:
            doc = collection.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        if request.mode == "franchise":
            # For franchise mode, resolve team name to team_id (same logic as get_playbooks)
            franchise_teams = doc.get("franchise_teams", {})
            logger.info(f"🔍 [PLAYBOOKS SAVE] Looking for franchise team_id='{request.team_id}' in document with {len(franchise_teams)} teams")
            
            # First try direct lookup
            if request.team_id in franchise_teams:
                actual_team_id = request.team_id
                logger.info(f"✅ [PLAYBOOKS SAVE] Found franchise team_id directly: {actual_team_id}")
            else:
                # Try to find by team name - iterate through franchise_teams to find match
                for tid in franchise_teams.keys():
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                    except:
                        team_doc = db.teams.find_one({"team_id": tid})
                    if team_doc and (team_doc.get("name") == request.team_id or str(team_doc.get("_id")) == request.team_id or team_doc.get("team_id") == request.team_id):
                        actual_team_id = tid
                        logger.info(f"✅ [PLAYBOOKS SAVE] Found franchise team by name lookup: {actual_team_id} (team name: {team_doc.get('name')})")
                        break
                # If still not found, try teams collection lookup by name
                if not actual_team_id:
                    team_doc = db.teams.find_one({"name": request.team_id})
                    if team_doc:
                        team_id_from_doc = team_doc.get("team_id")
                        logger.info(f"🔍 [PLAYBOOKS SAVE] Found franchise team in teams collection: {team_doc.get('name')}, team_id={team_id_from_doc}")
                        for tid in franchise_teams.keys():
                            if tid == team_id_from_doc or str(tid) == str(team_doc.get("_id")):
                                actual_team_id = tid
                                logger.info(f"✅ [PLAYBOOKS SAVE] Matched franchise team in document: {actual_team_id}")
                                break
            
            if not actual_team_id:
                logger.warning(f"⚠️ [PLAYBOOKS SAVE] Could not resolve franchise team_id '{request.team_id}' to a team in the document")
                logger.warning(f"⚠️ [PLAYBOOKS SAVE] Available franchise teams: {list(franchise_teams.keys())}")
        else:
            # For tournament/single mode, try to resolve team name to team_id
            teams = doc.get("teams", {})
            # First try direct lookup
            if request.team_id not in teams:
                # Try to find by team name - iterate through teams to find match
                for tid in teams.keys():
                    # Find the team that matches our input team_id (could be name or ObjectId)
                    try:
                        team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                    except:
                        # If tid is not a valid ObjectId, try as team_id string
                        team_doc = db.teams.find_one({"team_id": tid})
                    if team_doc and (team_doc.get("name") == request.team_id or str(team_doc.get("_id")) == request.team_id or team_doc.get("team_id") == request.team_id):
                        actual_team_id = tid
                        break
                # If still not found, try teams collection lookup by name
                if actual_team_id == request.team_id:
                    team_doc = db.teams.find_one({"name": request.team_id})
                    if team_doc:
                        team_id_from_doc = team_doc.get("team_id")
                        # Try to find this team_id in the document's teams
                        for tid in teams.keys():
                            if tid == team_id_from_doc or str(tid) == str(team_doc.get("_id")):
                                actual_team_id = tid
                                break
            else:
                actual_team_id = request.team_id
        
        # Update playbook_settings in the appropriate document
        if request.mode == "franchise":
            update_path = f"franchise_teams.{actual_team_id}.playbook_settings"
        else:
            update_path = f"teams.{actual_team_id}.playbook_settings"
        
        # For single game mode, try both UUID string and ObjectId formats
        if request.mode == "single":
            # Try UUID string first
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
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {update_path: request.playbook_settings}}
            )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} document not found")
        
        logger.info(f"✅ Saved playbook settings for team {actual_team_id} in {request.mode} mode")
        return {"success": True, "message": "Playbook settings saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

