from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db, games_collection, franchise_team_data_collection, players_collection, tournaments_collection, franchises_collection
from BackEnd.api.franchise_routes import get_user_team_from_franchise
from BackEnd.api.tournament_routes import get_user_team_from_tournament
from BackEnd.utils.team_id_resolver import resolve_team_id_to_canonical as unified_resolve_team_id_to_canonical
from BackEnd.utils.defense_identity import (
    PLAYBOOK_MAN_KEY_TO_DEFENSE_ID,
    PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID,
    read_scouting_defense_row,
)
from BackEnd.utils.playbook_settings_utils import (
    PLAYBOOK_PERCENTAGE_KEYS,
    MAN_DEFENSE_ID_TO_NAME,
    ZONE_DEFENSE_ID_TO_NAME,
    build_legacy_playbook_settings_view,
    build_play_lookups_from_team_plays,
    build_play_lookups_from_universal_plays,
    build_simplified_playbook_settings,
    empty_playbook_locks,
    normalize_motion_dropdowns_to_play_ids,
    normalize_pc_order,
    normalize_percentage_map_to_play_ids,
    normalize_playbook_locks,
    normalize_string_keyed_map,
    normalize_slot_assignments_to_play_ids,
)
from BackEnd.utils.team_play_utils import iter_team_plays
from BackEnd.constants.shot_threshold_scale import MID as SHOT_THRESHOLD_MID
from BackEnd.utils.playbook_weights_utils import (
    compute_position_shot_weights,
    weights_cache_is_stale,
)
from BackEnd.utils.debug_flags import debug_pc_enabled as _debug_pc_on
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


def _franchise_playbook_snapshot_meaningful(pb: dict | None) -> bool:
    """True if game-doc playbook_settings is worth treating as the gameplay snapshot (non-trivial)."""
    if not pb or not isinstance(pb, dict):
        return False
    pc = pb.get("pc_order") or {}
    if isinstance(pc, dict) and (pc.get("offense") or pc.get("defense")):
        return True
    if len(pb.get("slot_assignments") or {}) > 0:
        return True
    pf = pb.get("position_filters") or {}
    if isinstance(pf, dict):
        for arr in pf.values():
            if isinstance(arr, list) and len(arr) > 0:
                return True
    simp = pb.get("simple_playbook_percentages")
    if isinstance(simp, dict):
        for section in simp.values():
            if not isinstance(section, dict):
                continue
            if any(isinstance(x, (int, float)) and x for x in section.values()):
                return True
    for sec in ("motion", "set_plays", "man_defense", "zone_defense", "fast_breaks", "hc_traps"):
        m = pb.get(sec)
        if isinstance(m, dict) and any(isinstance(v, (int, float)) and v for v in m.values()):
            return True
        if isinstance(m, list) and len(m) > 0:
            return True
    for k in ("set_play_inside", "set_play_attack", "set_play_outside"):
        v = pb.get(k)
        if isinstance(v, dict) and v:
            return True
    return False


def _franchise_playbook_has_pc_order(pb: dict | None) -> bool:
    """True when a playbook snapshot has Playcall Center slot identity."""
    if not pb or not isinstance(pb, dict):
        return False
    pc = pb.get("pc_order") or {}
    if isinstance(pc, dict) and (pc.get("offense") or pc.get("defense")):
        return True
    return len(pb.get("slot_assignments") or {}) > 0


def _franchise_offense_pc_nonempty(pb: dict | None) -> bool:
    """True when offensive Playcall Center order has at least one slot."""
    if not pb or not isinstance(pb, dict):
        return False
    pc = pb.get("pc_order") or {}
    off = pc.get("offense") if isinstance(pc, dict) else None
    return isinstance(off, list) and len(off) > 0

# Stable play identity for seeded defaults and legacy position filters.
# These must use play_id, not name, so play renames do not break initialization.
SEEDED_OFFENSE_PLAY_IDS = {
    "68fa43953a0eec681847f8e4",  # 3-2 Motion
    "68f919f9065f78d452557809",  # 4-1 Motion
    "68fa42c33a0eec681847f886",  # 5-0 Motion
    "68fa7cc53a0eec6818481681",  # Base Post Play
    "68fa7b883a0eec68184815dc",  # Pick & Roll (Lower Wing)
    "68fa7c513a0eec681848164f",  # Double Screen For SG
    "695ac54cffd7a778902eb6d0",  # SF Back Door
    "695ac373ffd7a778902eb5fe",  # SF Isolation
    "695ac732ffd7a778902eb7c7",  # SF Misdirection Three
}

POSITION_FILTER_PLAY_IDS = {
    "standard": [
        "68fa43953a0eec681847f8e4",  # 3-2 Motion
        "68f919f9065f78d452557809",  # 4-1 Motion
        "68fa42c33a0eec681847f886",  # 5-0 Motion
        "68fa7cc53a0eec6818481681",  # Base Post Play
        "68fa7b883a0eec68184815dc",  # Pick & Roll (Lower Wing)
        "68fa7c513a0eec681848164f",  # Double Screen For SG
    ],
    "PF": [
        "694b3377ffd7a77890233ed3",  # PF Post Motion
        "694c1b65ffd7a77890240286",  # PF Post Up
        "694c1717ffd7a77890240095",  # PF High Post Drive
        "694be9afffd7a7789023ec66",  # PF Corner Shot
        "694b371dffd7a77890234084",  # PF Quick Jumper
    ],
    "PG": [
        "695a9dedffd7a778902ea508",  # PG Post Up
        "695a9ae5ffd7a778902ea3b6",  # PG Wrap-Around
        "695a9f2effd7a778902ea5a0",  # PG Wing Three
    ],
    "SG": [
        "695ab891ffd7a778902eb11a",  # SG Pass & Cut
        "695aba39ffd7a778902eb1d1",  # SG Pick & Roll
        "695ab738ffd7a778902eb07b",  # SG Wheel Three
    ],
    "SF": [
        "695ac54cffd7a778902eb6d0",  # SF Back Door
        "695ac373ffd7a778902eb5fe",  # SF Isolation
        "695ac732ffd7a778902eb7c7",  # SF Misdirection Three
    ],
    "C": [
        "695abf8effd7a778902eb447",  # C Post Iso
        "695ac0ecffd7a778902eb4e4",  # C High Post Clear Out
        "695ac24cffd7a778902eb578",  # C Screen & Three
    ],
}


def _get_player_display_name(player_doc: dict) -> str:
    if not isinstance(player_doc, dict):
        return "Unknown"
    return (
        player_doc.get("name")
        or f"{player_doc.get('first_name', '')} {player_doc.get('last_name', '')}".strip()
        or "Unknown"
    )


def _build_player_name_lookup(team_obj: dict | None) -> dict[str, str]:
    player_lookup: dict[str, str] = {}
    unresolved_ids: set[str] = set()

    raw_players = (team_obj or {}).get("players")
    player_candidates = []
    if isinstance(raw_players, list):
        player_candidates = raw_players
    elif isinstance(raw_players, dict):
        player_candidates = list(raw_players.values())

    for raw_player in player_candidates:
        if isinstance(raw_player, dict):
            player_id = raw_player.get("_id") or raw_player.get("id") or raw_player.get("player_id")
            if player_id:
                display_name = _get_player_display_name(raw_player)
                if display_name and display_name != "Unknown":
                    player_lookup[str(player_id)] = display_name
                else:
                    unresolved_ids.add(str(player_id))
        elif raw_player is not None:
            unresolved_ids.add(str(raw_player))

    query_object_ids = []
    for raw_id in unresolved_ids:
        try:
            query_object_ids.append(ObjectId(raw_id))
        except Exception:
            continue

    if unresolved_ids:
        for player_doc in players_collection.find(
            {"_id": {"$in": list(unresolved_ids)}},
            {"name": 1, "first_name": 1, "last_name": 1}
        ):
            player_lookup[str(player_doc["_id"])] = _get_player_display_name(player_doc)

    if query_object_ids:
        for player_doc in players_collection.find({"_id": {"$in": query_object_ids}}, {"name": 1, "first_name": 1, "last_name": 1}):
            player_lookup[str(player_doc["_id"])] = _get_player_display_name(player_doc)

    return player_lookup


def _get_top_scorer_label(play_data: dict, player_lookup: dict[str, str]) -> str | None:
    season_stats = (play_data or {}).get("season_stats", {})
    player_points = season_stats.get("player_points", {}) if isinstance(season_stats, dict) else {}
    top_player_id = None
    top_points = 0

    for player_id, points in player_points.items():
        try:
            numeric_points = int(points or 0)
        except Exception:
            numeric_points = 0
        if numeric_points > top_points:
            top_points = numeric_points
            top_player_id = str(player_id)

    if top_player_id and top_points > 0:
        player_name = player_lookup.get(top_player_id, "Unknown")
        return f"{player_name} ({top_points})"
    return None


def _load_current_team_plays_for_save(
    mode: str,
    team_id: str,
    franchise_id: str | None = None,
    tournament_id: str | None = None,
    game_id: str | None = None,
) -> tuple[dict, str]:
    """Load the current team-owned plays object from the same save target used for playbooks."""
    if mode == "single":
        doc = games_collection.find_one({"_id": game_id}, {"teams": 1})
        if not doc and game_id:
            try:
                doc = games_collection.find_one({"_id": ObjectId(game_id)}, {"teams": 1})
            except Exception:
                doc = None
        if not doc:
            raise HTTPException(status_code=404, detail="Game document not found")
        actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
        plays = doc.get("teams", {}).get(actual_team_id, {}).get("plays", {})
        return dict(plays or _get_cached_populated_plays(mode="single")), actual_team_id

    if mode == "franchise":
        collection, doc_id, is_game_doc = get_save_location_for_franchise_tournament(
            mode=mode,
            game_id=game_id,
            franchise_id=franchise_id,
            tournament_id=tournament_id,
        )
        if is_game_doc:
            actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
            doc = games_collection.find_one({"_id": doc_id}, {"teams": 1}) or games_collection.find_one({"_id": ObjectId(doc_id)}, {"teams": 1})
            plays = (doc or {}).get("teams", {}).get(actual_team_id, {}).get("plays")
            if plays:
                return dict(plays), actual_team_id

        franchise_doc = franchises_collection.find_one(
            {"_id": ObjectId(franchise_id)},
            {"user_team_id": 1, "user_team_object_id": 1},
        )
        _, user_team_object_id = get_user_team_from_franchise(franchise_doc or {})
        if not user_team_object_id:
            raise HTTPException(status_code=404, detail="User team not found in franchise")
        ftd_doc = franchise_team_data_collection.find_one(
            {"franchise_id": ObjectId(franchise_id), "team_id": ObjectId(user_team_object_id)},
            {"plays": 1},
        )
        return dict((ftd_doc or {}).get("plays") or _get_cached_populated_plays(mode="franchise")), user_team_object_id

    if mode == "tournament":
        collection, doc_id, is_game_doc = get_save_location_for_franchise_tournament(
            mode=mode,
            game_id=game_id,
            franchise_id=franchise_id,
            tournament_id=tournament_id,
        )
        if is_game_doc:
            actual_team_id = normalize_team_id_to_canonical(team_id, mode, None)
            doc = games_collection.find_one({"_id": doc_id}, {"teams": 1}) or games_collection.find_one({"_id": ObjectId(doc_id)}, {"teams": 1})
            plays = (doc or {}).get("teams", {}).get(actual_team_id, {}).get("plays")
            if plays:
                return dict(plays), actual_team_id

        tournament_doc = tournaments_collection.find_one(
            {"_id": ObjectId(tournament_id)},
            {"user_team_id": 1, "user_team_object_id": 1, "teams": 1},
        )
        _, user_team_object_id = get_user_team_from_tournament(tournament_doc or {})
        if not user_team_object_id:
            raise HTTPException(status_code=404, detail="User team not found in tournament")
        plays = (tournament_doc or {}).get("teams", {}).get(user_team_object_id, {}).get("plays", {})
        return dict(plays or _get_cached_populated_plays(mode="tournament")), user_team_object_id

    raise HTTPException(status_code=400, detail=f"Unsupported mode for team plays save: {mode}")

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

@router.get("/playbook-report.html")
def serve_playbook_report_html():
    """Return the playbook report page so query params work in production."""
    return FileResponse(STATIC_DIR / "playbook-report.html")

@router.get("/tutorial.html")
def serve_tutorial_html():
    """Return the tutorials page."""
    return FileResponse(STATIC_DIR / "tutorial.html")

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
            "rebounding": 2,
            "tempo": 2,  # Offense tempo slider (Game Plan); feeds STRATEGY_CALL_DICTS["tempo"]
            "alterations": 2,  # Play alteration slider (Game Plan); gameplay wiring TBD
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
    elif mode in ("single", "tutorial"):
        # FTE v2 tutorial games are stored in the games collection like single
        # mode (throwaway, deleted on completion). They use the same lookup
        # by game_id. apply_tutorial_initial_state writes playbook_settings
        # to the game doc so this endpoint returns the Coach-specified
        # 8-playcall preloads.
        if not game_id:
            raise HTTPException(status_code=400, detail=f"game_id required for {mode} mode")
        from BackEnd.utils.game_id_utils import normalize_game_id
        normalized_game_id = normalize_game_id(game_id)
        return db.games, normalized_game_id
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")


def get_team_settings_path(mode: str, team_id: str) -> str:
    """
    ✅ PHASE 5.5: Helper to get the MongoDB update path for team settings.
    Franchise master uses FTD (no doc path); when updating game/tournament docs we use "teams".
    """
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
    
    # Check if game exists and is active (franchise/tournament games use ObjectId _id; try that first)
    try:
        game_doc = None
        if isinstance(game_id, str) and len(game_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in game_id):
            try:
                game_doc = games_collection.find_one(
                    {"_id": ObjectId(game_id)},
                    {"quarter": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "_id": 1}
                )
            except Exception:
                pass
        if not game_doc:
            game_doc = games_collection.find_one(
                {"_id": game_id},
                {"quarter": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "_id": 1}
            )
        if not game_doc:
            try:
                game_doc = games_collection.find_one(
                    {"_id": ObjectId(game_id)},
                    {"quarter": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "_id": 1}
                )
            except Exception:
                pass
        
        if game_doc:
            # Verify game belongs to this franchise/tournament
            game_mode = game_doc.get("mode")
            game_franchise_id = game_doc.get("franchise_id")
            game_tournament_id = game_doc.get("tournament_id")
            
            if mode == "franchise":
                if game_mode == "franchise" and str(game_franchise_id) == str(franchise_id):
                    # Save to game doc whenever game exists (including quarter=0 so lineup saves persist)
                    return games_collection, game_id, True
            elif mode == "tournament":
                if game_mode == "tournament" and str(game_tournament_id) == str(tournament_id):
                    # Save to game doc whenever game exists (including quarter=0 so lineup saves persist)
                    return games_collection, game_id, True
        
        # Game doesn't exist or doesn't match - save to master
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
            detail="Invalid request"
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
                "target_shooter": play.get("target_shooter"),
                "motion_focus": None if play.get("play_type") == "motion" else None,
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


def get_play_ids_by_names(play_names, plays_map=None):
    """
    Get play_id (ObjectId strings) for a list of play names.
    
    ✅ PERFORMANCE: Uses batch query or pre-loaded map to avoid N+1 queries.
    
    Args:
        play_names: List of play name strings
        plays_map: Optional dict mapping play_name -> play dict (to avoid DB query)
        
    Returns:
        List of play_id strings (ObjectId as string), or empty list if play not found
    """
    try:
        logger.info(f"🔍 [POSITION FILTERS] Looking up {len(play_names)} play names: {play_names}")
        play_ids = []
        
        # ✅ PERFORMANCE: Use pre-loaded map if provided (avoids DB query entirely)
        if plays_map:
            for play_name in play_names:
                play = plays_map.get(play_name)
                if play and play.get("_id"):
                    play_id_str = str(play["_id"])
                    play_ids.append(play_id_str)
                    logger.info(f"✅ [POSITION FILTERS] Found play '{play_name}' → play_id: {play_id_str}")
                else:
                    logger.warning(f"⚠️ [POSITION FILTERS] Play '{play_name}' not found in plays_map")
        else:
            # ✅ PERFORMANCE: Batch query instead of N+1 individual queries
            from BackEnd.db import plays_collection
            plays = list(plays_collection.find({"name": {"$in": play_names}}))
            plays_by_name = {play["name"]: play for play in plays}
            
            for play_name in play_names:
                play = plays_by_name.get(play_name)
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
    Initialize simplified playbook_settings with alpha-friendly defaults.
    """
    try:
        from BackEnd.db import plays_collection
        
        # Get all plays from universal collection
        all_plays = list(plays_collection.find({}))
        
        # ✅ PERFORMANCE: Build name -> play map for efficient lookup (avoids redundant DB queries)
        plays_by_name = {play.get("name", ""): play for play in all_plays}
        
        # Initialize structure
        playbook_settings = {
            "motion": {},
            "set_plays": {},
            "fast_breaks": {},
            "hc_traps": {},
            "zone_defense": {},
            "man_defense": {},
            "pc_order": {"offense": [], "defense": []},
            "position_filters": {
                "standard": [],  # Empty = show all plays when selected
                "PG": [],        # Point Guard plays (play_id ObjectId strings)
                "SG": [],        # Shooting Guard plays (play_id ObjectId strings)
                "SF": [],        # Small Forward plays (play_id ObjectId strings)
                "PF": [],        # Power Forward plays (play_id ObjectId strings)
                "C": []          # Center plays (play_id ObjectId strings)
            },
            "even_distribution_all": True,  # Macro toggle for Even Distribution - All
            "locks": empty_playbook_locks(),
            "_meta": {
                "user_saved": False,
                "schema_version": 2,
            },
        }
        
        # Group seeded offense plays by type.
        motion_plays = []
        set_plays = []
        
        for play in all_plays:
            play_name = play.get("name", "")
            play_type = play.get("play_type", "")
            
            # Skip "To Be Added" placeholder plays
            if play_name == "To Be Added":
                continue
            
            if play_type == "motion":
                if str(play.get("_id")) in SEEDED_OFFENSE_PLAY_IDS:
                    motion_plays.append(play)
            elif play_type == "set_play" and str(play.get("_id")) in SEEDED_OFFENSE_PLAY_IDS:
                set_plays.append(play)
        
        available_play_ids = {
            str(play["_id"])
            for play in plays_by_name.values()
            if play.get("_id")
        }

        def _filter_existing_play_ids(play_ids: list[str] | set[str]) -> list[str]:
            return [play_id for play_id in play_ids if play_id in available_play_ids]

        def _apply_even_distribution(target: dict, eligible_plays: list[dict]) -> None:
            if not eligible_plays:
                return
            eligible_plays = sorted(
                [play for play in eligible_plays if play.get("_id")],
                key=lambda play: play.get("name", ""),
            )
            count = len(eligible_plays)
            base = 100 // count
            remainder = 100 - (base * count)
            for idx, play in enumerate(eligible_plays):
                target[str(play["_id"])] = base + (1 if idx < remainder else 0)

        _apply_even_distribution(playbook_settings["motion"], motion_plays)
        _apply_even_distribution(playbook_settings["set_plays"], set_plays)

        playbook_settings["fast_breaks"] = {
            "covert_release": 33,
            "rim_runner": 33,
            "triangle": 34,
        }

        # HCT traps (defensive play family). All three plays are built → user-team
        # default splits evenly across them.
        playbook_settings["hc_traps"] = {
            "standard_trap": 34,
            "straight_pressure": 33,
            "standard_diamond": 33,
        }
        
        # Zone defense: Even distribution across supported zone IDs.
        zone_defenses = ["zone_23", "zone_32", "zone_131"]
        if zone_defenses:
            percentage_per_defense = 100.0 / len(zone_defenses)
            remainder = 100.0
            for i, defense_name in enumerate(zone_defenses):
                if i == len(zone_defenses) - 1:
                    playbook_settings["zone_defense"][defense_name] = round(remainder)
                else:
                    playbook_settings["zone_defense"][defense_name] = round(percentage_per_defense)
                    remainder -= round(percentage_per_defense)
        
        # Man defense: only normal is active for now.
        playbook_settings["man_defense"]["man_normal"] = 100
        playbook_settings["man_defense"]["man_pressure"] = 0
        playbook_settings["man_defense"]["man_loose"] = 0
        
        # Initialize position filters with play assignments
        logger.info("🔍 [INITIALIZE PLAYBOOK] Starting position filter population...")
        
        # Keep legacy position filters stable by play_id so UI labels can change safely.
        standard_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["standard"])
        playbook_settings["position_filters"]["standard"] = standard_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] Standard position filter populated with {len(standard_play_ids)} play_ids")
        
        # PF: Power Forward specific plays
        pf_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["PF"])
        playbook_settings["position_filters"]["PF"] = pf_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] PF position filter populated with {len(pf_play_ids)} play_ids")
        
        # PG: Point Guard specific plays
        pg_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["PG"])
        playbook_settings["position_filters"]["PG"] = pg_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] PG position filter populated with {len(pg_play_ids)} play_ids")
        
        # SG: Shooting Guard specific plays
        sg_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["SG"])
        playbook_settings["position_filters"]["SG"] = sg_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] SG position filter populated with {len(sg_play_ids)} play_ids")
        
        # SF: Small Forward specific plays
        sf_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["SF"])
        playbook_settings["position_filters"]["SF"] = sf_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] SF position filter populated with {len(sf_play_ids)} play_ids")
        
        # C: Center specific plays
        c_play_ids = _filter_existing_play_ids(POSITION_FILTER_PLAY_IDS["C"])
        playbook_settings["position_filters"]["C"] = c_play_ids
        logger.info(f"✅ [INITIALIZE PLAYBOOK] C position filter populated with {len(c_play_ids)} play_ids")
        
        return playbook_settings
        
    except Exception as e:
        logger.error(f"🚨 Error in initialize_playbook_settings: {e}", exc_info=True)
        # Return minimal defaults on error
        return {
            "motion": {},
            "set_plays": {},
            "fast_breaks": {
                "covert_release": 33,
                "rim_runner": 33,
                "triangle": 34,
            },
            "hc_traps": {
                "standard_trap": 34,
                "straight_pressure": 33,
                "standard_diamond": 33,
            },
            "zone_defense": {"zone_23": 100, "zone_32": 0, "zone_131": 0},
            "man_defense": {"man_normal": 100, "man_pressure": 0, "man_loose": 0},
            "pc_order": {"offense": [], "defense": []},
            "position_filters": {
                "standard": [],
                "PG": [],
                "SG": [],
                "SF": [],
                "PF": [],
                "C": []
            },
            "even_distribution_all": True,
            "locks": empty_playbook_locks(),
            "_meta": {
                "user_saved": False,
                "schema_version": 2,
            },
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
            "man": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "2-3-zone": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "3-2-zone": {
                "used": 0,
                "success": 0,
                "effectiveness": random.randint(0, 80),
                "momentum": random.randint(0, 10),
                "cloaking": random.randint(0, 10),
                "game_stats": defense_template["game_stats"].copy(),
                "season_stats": defense_template["season_stats"].copy()
            },
            "1-3-1-zone": {
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
            "man": deepcopy(defense_template),
            "2-3-zone": deepcopy(defense_template),
            "3-2-zone": deepcopy(defense_template),
            "1-3-1-zone": deepcopy(defense_template),
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
            # ✅ PERFORMANCE: Load with minimal projection. Franchise uses FTD only; we only need doc to exist.
            if mode == "franchise":
                doc = collection.find_one({"_id": ObjectId(doc_id)}, {"_id": 1})
            elif mode == "tournament":
                doc = collection.find_one({"_id": ObjectId(doc_id)}, {"teams": 1, "_id": 1})
            else:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"{mode.capitalize()} not found")
    
    # FTD: For franchise mode, check/update FTD collection only
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
                "shot_threshold": ftd_doc.get("team_attributes", {}).get("shot_threshold", SHOT_THRESHOLD_MID),
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
    # FTE v2 tutorial games are structurally identical to single-mode games
    # (same games_collection doc, same ongoing_games cache, same game_id
    # format). Aliasing to "single" lets every downstream mode == "single"
    # branch in this function work for tutorial too. Saving is gated on the
    # frontend (tutorial mode hides the Save button + disables sliders).
    if mode == "tutorial":
        mode = "single"
    try:
        logger.warning(f"🔍 [GET GAMEPLAN] query: mode={mode!r}, team_id={team_id!r}, franchise_id={franchise_id!r}, tournament_id={tournament_id!r}, game_id={game_id!r}")
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
            # Try to load from game doc first (ObjectId first for franchise/tournament games)
            try:
                proj = {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                game_doc = None
                if isinstance(game_id, str) and len(game_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in game_id):
                    try:
                        game_doc = games_collection.find_one({"_id": ObjectId(game_id)}, proj)
                    except Exception:
                        pass
                if not game_doc:
                    game_doc = games_collection.find_one({"_id": game_id}, proj)
                if not game_doc:
                    try:
                        game_doc = games_collection.find_one({"_id": ObjectId(game_id)}, proj)
                    except Exception:
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
                        master_proj = {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                        if mode == "tournament":
                            master_proj["teams"] = 1
                        master_doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            master_proj
                        )
                        if master_doc:
                            user_team_name = None
                            if mode == "franchise":
                                user_team_name, _ = get_user_team_from_franchise(master_doc)
                            elif mode == "tournament":
                                user_team_name, _ = get_user_team_from_tournament(master_doc)
                            
                            # Find matching team_id in the game doc (active gameplay snapshot)
                            for tid, team_obj in game_teams.items():
                                doc_name = (team_obj.get("name") or "").strip()
                                master_name = (user_team_name or "").strip()
                                if doc_name.lower() == master_name.lower():
                                    game_doc_team_id = tid
                                    doc = game_doc
                                    load_from_game_doc = True
                                    break
                            if not load_from_game_doc:
                                _candidates_gp: list[str] = []
                                try:
                                    if mode == "franchise":
                                        _, _uto_gp = get_user_team_from_franchise(master_doc)
                                        if _uto_gp:
                                            _candidates_gp.append(str(_uto_gp))
                                    elif mode == "tournament":
                                        _, _uto_gp = get_user_team_from_tournament(master_doc)
                                        if _uto_gp:
                                            _candidates_gp.append(str(_uto_gp))
                                except Exception:
                                    pass
                                if team_id:
                                    _ts_gp = str(team_id).strip()
                                    if _ts_gp and _ts_gp not in _candidates_gp:
                                        _candidates_gp.append(_ts_gp)
                                for _cand_gp in _candidates_gp:
                                    if not _cand_gp:
                                        continue
                                    _canon_gp = None
                                    try:
                                        _canon_gp = unified_resolve_team_id_to_canonical(
                                            _cand_gp, mode="single", doc=game_doc
                                        )
                                    except (ValueError, Exception):
                                        try:
                                            _canon_gp = unified_resolve_team_id_to_canonical(
                                                _cand_gp, mode="single", doc=None
                                            )
                                        except (ValueError, Exception):
                                            _canon_gp = None
                                    if _canon_gp and _canon_gp in game_teams:
                                        game_doc_team_id = _canon_gp
                                        doc = game_doc
                                        load_from_game_doc = True
                                        logger.warning(
                                            "🔍 [GET GAMEPLAN] Matched game doc team by canonical key=%s (name match failed; user_team_name=%r)",
                                            _canon_gp,
                                            user_team_name,
                                        )
                                        break
            except Exception as e:
                logger.warning(f"🔍 [GET GAMEPLAN] Game doc path failed: {e!r}")
        
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
            if mode == "franchise":
                _ss_gp = team_obj.get("strategy_settings")
                if not _ss_gp or not isinstance(_ss_gp, dict) or len(_ss_gp) == 0:
                    try:
                        _fr_gp = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"user_team_object_id": 1},
                        )
                        if _fr_gp:
                            _, _uto_gp = get_user_team_from_franchise(_fr_gp)
                            if _uto_gp:
                                _ftd_gp = franchise_team_data_collection.find_one(
                                    {
                                        "franchise_id": ObjectId(doc_id),
                                        "team_id": ObjectId(str(_uto_gp)),
                                    },
                                    {"strategy_settings": 1},
                                )
                                if _ftd_gp and _ftd_gp.get("strategy_settings"):
                                    team_obj = dict(team_obj)
                                    team_obj["strategy_settings"] = dict(
                                        _ftd_gp["strategy_settings"]
                                    )
                                    logger.warning(
                                        "⚠️ [GET GAMEPLAN] franchise+game_doc: merged FTD strategy_settings "
                                        "(game snapshot missing) franchise=%s game_id=%s",
                                        doc_id,
                                        game_id,
                                    )
                    except Exception as _gp_merge_exc:
                        logger.warning(
                            "⚠️ [GET GAMEPLAN] FTD strategy merge failed: %s",
                            _gp_merge_exc,
                        )
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
            
            logger.warning(f"🔍 [GET GAMEPLAN] franchise FTD lookup: doc_id={doc_id!r}, authoritative_team_id={authoritative_team_id!r}, team_object_id={team_object_id}")
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                {"strategy_settings": 1}
            )
            
            if ftd_doc:
                ss = ftd_doc.get("strategy_settings", {})
                logger.warning(f"🔍 [GET GAMEPLAN] FTD found: strategy_settings keys={list(ss.keys()) if ss else []}")
                team_obj = {
                    "strategy_settings": ss
                }
            else:
                # FTD doesn't exist - initialize with defaults
                defaults = get_default_settings()
                team_obj = {
                    "strategy_settings": defaults["strategy_settings"].copy()
                }
                logger.warning(f"⚠️ [GET GAMEPLAN] FTD not found for franchise_id={doc_id!r} team_id={authoritative_team_id!r}, using defaults")
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
        if mode in ("single", "tutorial") and use_gamemanager_settings and gm:
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
        elif mode in ("single", "tutorial") and not use_gamemanager_settings:
            # ✅ SS&S: GameManager not available - use load_team_settings_from_doc() (same as simulate_quarter_endpoint)
            from BackEnd.api.api import load_team_settings_from_doc
            settings = load_team_settings_from_doc(mode, doc_id, team_id, team_id)
            strategy_settings = settings.get("strategy_settings") or team_obj.get("strategy_settings", defaults["strategy_settings"])
        else:
            # ✅ UNIFIED: For tournament/franchise modes, use unified extract function for consistent team_id resolution
            if mode == "franchise":
                # ✅ FTD: Strategy settings already loaded from FTD above
                strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
            elif load_from_game_doc and team_obj:
                # ✅ FIX: Loading from game doc (canonical keys); team_obj already set - use it directly.
                # extract_team_settings would look up by ObjectId and fail (game doc has FOUR_CORNERS/MORRISTOWN).
                logger.warning(f"🔍 [GET GAMEPLAN] Using game doc team_obj for strategy_settings (load_from_game_doc=True, canonical key)")
                strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
            else:
                # Tournament master doc - use extract (doc has ObjectId keys)
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/api/gameplan")
def update_gameplan(request: GamePlanUpdateRequest):
    """Update game plan settings for a team in the specified mode."""
    from BackEnd.utils.team_settings_manager import save_team_settings

    # FTE v2 tutorial: defense-in-depth alias. The Save button is hidden in
    # tutorial mode on the frontend, but if any code path triggers this PUT
    # (auto-save, dirty-state flush, etc.), treat tutorial like single — the
    # write goes to the throwaway game doc and disappears on completion.
    if request.mode == "tutorial":
        request.mode = "single"

    logger.warning(
        f"🔍 [UPDATE GAMEPLAN] request: mode={request.mode!r}, team_id={request.team_id!r}, "
        f"franchise_id={request.franchise_id!r}, tournament_id={request.tournament_id!r}, game_id={request.game_id!r}"
    )
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/playbooks")
def get_playbooks(
    mode: str,
    team_id: str,
    franchise_id: str = None,
    tournament_id: str = None,
    game_id: str = None,
    source: str = None,
    profile: bool = False,
    debug_pc: Optional[str] = Query(None),
):
    """
    Get plays for a team from the appropriate mode document.
    Add profile=1 to get profile_summary in the response.
    """
    import time
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = get_playbooks(
                mode,
                team_id,
                franchise_id,
                tournament_id,
                game_id,
                source,
                profile=False,
                debug_pc=debug_pc,
            )
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        result["profile_summary"] = profile_summary
        return result
    endpoint_start = time.time()
    # FTE v2 tutorial games are structurally identical to single-mode games
    # (same games_collection doc, same ongoing_games cache, same game_id
    # format). Normalize to "single" so we don't have to extend every
    # `mode == "single"` branch in this 1000-line function. The cleanups
    # specific to tutorial (game doc deletion, tutorial-complete, debut
    # publish) happen in other endpoints, not here.
    if mode == "tutorial":
        mode = "single"
    try:
        use_gamemanager_settings = False  # set True in single-mode cache branch; franchise/tournament stay False here
        _dpc_log = debug_pc if isinstance(debug_pc, str) else None
        logger.warning(
            "🔍 [GET PLAYBOOKS] query: mode=%r, team_id=%r, franchise_id=%r, tournament_id=%r, game_id=%r, debug_pc=%r",
            mode,
            team_id,
            franchise_id,
            tournament_id,
            game_id,
            _dpc_log,
        )
        if _dpc_log and _dpc_log.strip():
            logger.warning(
                "🔍 [DEBUG_PC] GET /api/playbooks client trace flag debug_pc=%r resolved_on=%s",
                _dpc_log.strip(),
                _debug_pc_on(debug_pc),
            )
        # ✅ PHASE 5.5: Use helper to get collection and doc_id (simplifies mode handling)
        collection, doc_id = get_collection_and_doc_id(mode, franchise_id, tournament_id, game_id)
        
        # ✅ PHASE 1.1: Log normalization if game_id was changed
        if mode == "single" and game_id and game_id != doc_id:
            logger.warning(f"🔍 [NORMALIZE] GET /api/playbooks - Normalized game_id from '{game_id}' to '{doc_id}'")
        
        # ✅ PHASE 5.5: Use normalized doc_id for single/tutorial mode cache lookup
        # (tutorial games are stored in games_collection like single mode and
        # the ongoing_games cache holds the same gm reference.)
        if mode in ("single", "tutorial"):
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
            # Try to load from game doc first (during gameplay, game doc has in-game playbook/slot_assignments)
            try:
                proj = {"teams": 1, "mode": 1, "franchise_id": 1, "tournament_id": 1, "home_team": 1, "away_team": 1, "_id": 1}
                game_doc = None
                # Franchise/tournament games typically use ObjectId _id; try that first when game_id looks like 24-char hex
                if isinstance(game_id, str) and len(game_id) == 24 and all(c in "0123456789abcdefABCDEF" for c in game_id):
                    try:
                        game_doc = games_collection.find_one({"_id": ObjectId(game_id)}, proj)
                    except Exception:
                        pass
                if not game_doc:
                    game_doc = games_collection.find_one({"_id": game_id}, proj)
                if not game_doc:
                    try:
                        game_doc = games_collection.find_one({"_id": ObjectId(game_id)}, proj)
                    except Exception:
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
                        master_proj = {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                        if mode == "tournament":
                            master_proj["teams"] = 1
                        master_doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            master_proj
                        )
                        if master_doc:
                            user_team_name = None
                            if mode == "franchise":
                                user_team_name, _ = get_user_team_from_franchise(master_doc)
                            elif mode == "tournament":
                                user_team_name, _ = get_user_team_from_tournament(master_doc)
                            
                            # Find matching team_id in the game doc. Franchise gameplay should
                            # read the frozen game snapshot once the game exists.
                            for tid, team_obj in game_teams.items():
                                doc_name = (team_obj.get("name") or "").strip()
                                master_name = (user_team_name or "").strip()
                                if doc_name.lower() == master_name.lower():
                                    game_doc_team_id = tid
                                    doc = game_doc
                                    load_from_game_doc = True
                                    break
                            # If franchise/tournament name drifted vs game snapshot, resolve ObjectId → canonical team_id key.
                            if not load_from_game_doc:
                                _candidates: list[str] = []
                                try:
                                    if mode == "franchise":
                                        _, _uto = get_user_team_from_franchise(master_doc)
                                        if _uto:
                                            _candidates.append(str(_uto))
                                    elif mode == "tournament":
                                        _, _uto = get_user_team_from_tournament(master_doc)
                                        if _uto:
                                            _candidates.append(str(_uto))
                                except Exception:
                                    pass
                                if team_id:
                                    _ts = str(team_id).strip()
                                    if _ts and _ts not in _candidates:
                                        _candidates.append(_ts)
                                for _cand in _candidates:
                                    if not _cand:
                                        continue
                                    _canon = None
                                    try:
                                        _canon = unified_resolve_team_id_to_canonical(
                                            _cand, mode="single", doc=game_doc
                                        )
                                    except (ValueError, Exception):
                                        try:
                                            _canon = unified_resolve_team_id_to_canonical(
                                                _cand, mode="single", doc=None
                                            )
                                        except (ValueError, Exception):
                                            _canon = None
                                    if _canon and _canon in game_teams:
                                        game_doc_team_id = _canon
                                        doc = game_doc
                                        load_from_game_doc = True
                                        logger.warning(
                                            "🔍 [GET PLAYBOOKS] Matched game doc team by canonical key=%s (name match failed; user_team_name=%r)",
                                            _canon,
                                            user_team_name,
                                        )
                                        break
            except Exception as e:
                logger.warning(f"🔍 [GET PLAYBOOKS] Game doc path failed: {e!r}")
        
        # If not loading from game doc, load from master doc (existing logic)
        if not load_from_game_doc:
            # ✅ PERFORMANCE: Load document with projection (only needed fields) to reduce data transfer
            # For single game / tutorial mode, try both UUID string and ObjectId formats
            # (tutorial docs are structured like single — playbook_settings on
            # summary["teams"][team_id] populated by apply_tutorial_initial_state)
            if mode in ("single", "tutorial"):
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
        # logger.warning(f"⏱️ [PERF] /api/playbooks - DB query: {query_time:.2f}ms, doc_size: {doc_size} bytes, mode: {mode}, load_from_game_doc={load_from_game_doc}")
        
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
            ftd_merged_playbook_settings = None
            # Franchise gameplay should read only from the game snapshot once the
            # game exists. Do not silently merge FTD or cached populated plays here,
            # because that masks init/snapshot bugs and causes UI/runtime drift.
            if mode == "franchise":
                current_plays = team_obj.get("plays") or {}
                if not isinstance(current_plays, dict):
                    current_plays = {}
                    team_obj["plays"] = current_plays
                if len(current_plays) == 0:
                    logger.warning(
                        "⚠️ [GET PLAYBOOKS] franchise+game_doc missing plays snapshot for team_id=%s game_id=%s",
                        authoritative_team_id,
                        game_id,
                    )
                # Game doc snapshot can lose playbook_settings / plays while FTD still has the user's book.
                # Game plan reads FTD; playbooks must not show empty UI when master data exists.
                _pb_snap = team_obj.get("playbook_settings")
                _need_ftd_pb = not _franchise_playbook_snapshot_meaningful(
                    _pb_snap if isinstance(_pb_snap, dict) else None
                )
                # Need FTD PC merge when snapshot has no PC identity OR defense/slots exist but offense list is empty
                # (otherwise set-lineup shows FTD book but GET with game_id returns empty offense PC — user sees wrong Playcall).
                _need_ftd_pc_order = (not _franchise_playbook_has_pc_order(
                    _pb_snap if isinstance(_pb_snap, dict) else None
                )) or (not _franchise_offense_pc_nonempty(
                    _pb_snap if isinstance(_pb_snap, dict) else None
                ))
                _pl_snap = team_obj.get("plays") or {}
                _need_ftd_plays = (not isinstance(_pl_snap, dict)) or len(_pl_snap) == 0
                if _need_ftd_pb or _need_ftd_pc_order or _need_ftd_plays:
                    try:
                        _fr_doc = collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"user_team_id": 1, "user_team_object_id": 1},
                        )
                        if _fr_doc:
                            _, _uto = get_user_team_from_franchise(_fr_doc)
                            _ftd_team_candidates: list[str] = []
                            # Prefer game-doc canonical team key first — request team_id can differ
                            # from franchise_team_data.team_id while still matching teams{} in the game.
                            if authoritative_team_id:
                                _aid = str(authoritative_team_id)
                                if _aid:
                                    _ftd_team_candidates.append(_aid)
                            if team_id:
                                _ts = str(team_id)
                                if _ts and _ts not in _ftd_team_candidates:
                                    _ftd_team_candidates.append(_ts)
                            if _uto and str(_uto) not in _ftd_team_candidates:
                                _ftd_team_candidates.append(str(_uto))

                            _ftd_row = None
                            _fallback_ftd_row = None
                            for _ftd_team_id in _ftd_team_candidates:
                                try:
                                    _candidate_row = franchise_team_data_collection.find_one(
                                        {
                                            "franchise_id": ObjectId(doc_id),
                                            "team_id": ObjectId(str(_ftd_team_id)),
                                        },
                                        {"playbook_settings": 1, "plays": 1},
                                    )
                                except Exception:
                                    continue
                                if not _candidate_row:
                                    continue
                                if _fallback_ftd_row is None:
                                    _fallback_ftd_row = _candidate_row
                                _candidate_pb = _candidate_row.get("playbook_settings") or {}
                                _candidate_plays = _candidate_row.get("plays") or {}
                                if (
                                    (
                                        _need_ftd_pc_order
                                        and (
                                            _franchise_playbook_has_pc_order(_candidate_pb)
                                            or _franchise_offense_pc_nonempty(_candidate_pb)
                                        )
                                    )
                                    or (_need_ftd_pb and _franchise_playbook_snapshot_meaningful(_candidate_pb))
                                    or (_need_ftd_plays and isinstance(_candidate_plays, dict) and len(_candidate_plays) > 0)
                                ):
                                    _ftd_row = _candidate_row
                                    logger.warning(
                                        "⚠️ [GET PLAYBOOKS] franchise+game_doc: selected FTD fallback row "
                                        "team_id=%s (request team_id=%s, franchise user_team_object_id=%s)",
                                        _ftd_team_id,
                                        team_id,
                                        _uto,
                                    )
                                    break
                            if _ftd_row is None:
                                _ftd_row = _fallback_ftd_row

                            if _ftd_row:
                                team_obj = dict(team_obj)
                                _fb_pb = _ftd_row.get("playbook_settings") or {}
                                # Do not chain with elif: _need_ftd_pb can be True while FTD is not
                                # "meaningful" by snapshot rules — we must still run PC-order merge.
                                if _need_ftd_pb and _franchise_playbook_snapshot_meaningful(_fb_pb):
                                    ftd_merged_playbook_settings = dict(_fb_pb)
                                    team_obj["playbook_settings"] = ftd_merged_playbook_settings
                                    logger.warning(
                                        "⚠️ [GET PLAYBOOKS] franchise+game_doc: using FTD playbook_settings "
                                        "(game snapshot empty or non-meaningful) franchise=%s game_id=%s team=%s",
                                        doc_id,
                                        game_id,
                                        authoritative_team_id,
                                    )
                                if (not ftd_merged_playbook_settings) and _need_ftd_pc_order and (
                                    _franchise_playbook_has_pc_order(_fb_pb)
                                    or _franchise_offense_pc_nonempty(_fb_pb)
                                ):
                                    _merged_pb = dict(_pb_snap or {})
                                    _fb_pc = (_fb_pb.get("pc_order") or {}) if isinstance(_fb_pb.get("pc_order"), dict) else {}
                                    _snap_pc = dict((_merged_pb.get("pc_order") or {})) if isinstance(_merged_pb.get("pc_order"), dict) else {}
                                    _fb_off = _fb_pc.get("offense") if isinstance(_fb_pc.get("offense"), list) else []
                                    _snap_off = _snap_pc.get("offense") if isinstance(_snap_pc.get("offense"), list) else []
                                    if (
                                        _franchise_playbook_has_pc_order(_pb_snap if isinstance(_pb_snap, dict) else None)
                                        and len(_snap_off) == 0
                                        and len(_fb_off) > 0
                                    ):
                                        _snap_pc["offense"] = list(_fb_off)
                                        _merged_pb["pc_order"] = _snap_pc
                                        for _pc_key in ("slot_assignments", "motion_dropdowns"):
                                            if _fb_pb.get(_pc_key):
                                                _merged_pb[_pc_key] = _fb_pb.get(_pc_key)
                                        logger.warning(
                                            "⚠️ [GET PLAYBOOKS] franchise+game_doc: merged FTD offense PC only "
                                            "(game snapshot had defense/slots but empty offense) franchise=%s game_id=%s team=%s",
                                            doc_id,
                                            game_id,
                                            authoritative_team_id,
                                        )
                                    else:
                                        for _pc_key in ("pc_order", "slot_assignments", "motion_dropdowns"):
                                            if _fb_pb.get(_pc_key):
                                                _merged_pb[_pc_key] = _fb_pb.get(_pc_key)
                                        logger.warning(
                                            "⚠️ [GET PLAYBOOKS] franchise+game_doc: merged FTD Playcall Center order "
                                            "(game snapshot missing PC order) franchise=%s game_id=%s team=%s",
                                            doc_id,
                                            game_id,
                                            authoritative_team_id,
                                        )
                                    ftd_merged_playbook_settings = _merged_pb
                                    team_obj["playbook_settings"] = ftd_merged_playbook_settings
                                if _need_ftd_plays:
                                    _fb_pl = _ftd_row.get("plays") or {}
                                    if isinstance(_fb_pl, dict) and len(_fb_pl) > 0:
                                        team_obj["plays"] = dict(_fb_pl)
                                        logger.warning(
                                            "⚠️ [GET PLAYBOOKS] franchise+game_doc: using FTD plays "
                                            "(game snapshot missing) franchise=%s game_id=%s team=%s",
                                            doc_id,
                                            game_id,
                                            authoritative_team_id,
                                        )
                    except Exception as _merge_exc:
                        logger.warning(
                            "⚠️ [GET PLAYBOOKS] franchise+game_doc FTD fallback failed: %s",
                            _merge_exc,
                        )
                    if _need_ftd_pc_order and not ftd_merged_playbook_settings:
                        logger.warning(
                            "⚠️ [GET PLAYBOOKS] franchise+game_doc: FTD Playcall merge was needed but "
                            "playbook_settings was not updated (no FTD row, FTD has no pc_order/slots, or "
                            "only _need_ftd_plays ran). game_id=%s authoritative_team_id=%s request_team_id=%s",
                            game_id,
                            authoritative_team_id,
                            team_id,
                        )
        elif mode == "franchise":
            # Franchise FCC / pregame reads use FTD as the authoritative master source.
            # Gameplay with game_id should use the game doc snapshot instead of mixing sources.
            from BackEnd.db import franchise_team_data_collection
            try:
                team_object_id = ObjectId(authoritative_team_id)
            except:
                raise HTTPException(status_code=400, detail=f"Invalid team_id format: {authoritative_team_id}")
            
            logger.warning(f"🔍 [GET PLAYBOOKS] franchise FTD lookup: doc_id={doc_id!r}, authoritative_team_id={authoritative_team_id!r}, team_object_id={team_object_id}")
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                {"playbook_settings": 1, "plays": 1, "scouting_data": 1, "players": 1}
            )
            
            if ftd_doc:
                pb = ftd_doc.get("playbook_settings", {})
                pl = ftd_doc.get("plays", {})
                logger.warning(f"🔍 [GET PLAYBOOKS] FTD found: playbook_settings keys={list(pb.keys())[:12] if pb else []}, plays count={len(pl)}")
                team_obj = {
                    "playbook_settings": pb,
                    "plays": pl,
                    "scouting_data": ftd_doc.get("scouting_data", {}),
                    "players": ftd_doc.get("players", []),
                }
            else:
                logger.warning(f"🔍 [GET PLAYBOOKS] FTD not found for franchise_id={doc_id!r} team_id={authoritative_team_id!r}, creating new FTD entry")
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
                    "plays": populated_plays,
                    "scouting_data": scouting_data,
                    "players": [],
                }
            
            actual_team_id = authoritative_team_id
            ftd_merged_playbook_settings = None
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
                ftd_merged_playbook_settings = None
            else:
                # ✅ PHASE 5.1: Use normalization helper for single mode
                actual_team_id = normalize_team_id_to_canonical(team_id, mode, doc)
                teams = teams_dict if isinstance(teams_dict, dict) else doc.get("teams", {})
                team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
                ftd_merged_playbook_settings = None
        
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
                    # Else branch: updating game or tournament doc (both use "teams")
                    team_key = f"teams.{actual_team_id}"
                    update_coll = games_collection if (load_from_game_doc and mode == "franchise") else collection
                    update_id = game_doc["_id"] if (load_from_game_doc and mode == "franchise") else (ObjectId(doc_id) if mode != "single" else doc_id)
                    if mode == "single":
                        result = collection.update_one(
                            {"_id": doc_id},
                            {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                        )
                        doc = collection.find_one({"_id": doc_id})
                    else:
                        result = update_coll.update_one(
                            {"_id": update_id},
                            {"$set": {f"{team_key}.playbook_settings": existing_playbook_settings}}
                        )
                        doc = update_coll.find_one({"_id": update_id})
                        if mode == "franchise" and load_from_game_doc:
                            if doc is None:
                                logger.warning(f"🔍 [GET PLAYBOOKS] franchise+game_doc: position_filters reload got doc=None, update_id={update_id!r}; falling back to game_doc")
                                doc = game_doc
                            else:
                                logger.warning(f"🔍 [GET PLAYBOOKS] franchise+game_doc: position_filters reload doc ok, update_id={update_id!r}")
                    
                    # Reload team_obj (game/tournament doc both have "teams")
                    # Franchise in-game: game doc has no plays; preserve FTD-merged plays
                    preserved_plays = (team_obj.get("plays") or {}) if (mode == "franchise" and load_from_game_doc) else None
                    if mode == "franchise":
                        team_obj = doc.get("teams", {}).get(actual_team_id, {}) if doc else {}
                        if preserved_plays and (not team_obj.get("plays") or len(team_obj.get("plays", {})) == 0):
                            team_obj["plays"] = preserved_plays
                    elif mode == "tournament":
                        team_obj = doc.get("teams", {}).get(actual_team_id, {})
                    else:
                        team_obj = doc.get("teams", {}).get(actual_team_id, {})
        
        # Ensure plays exist before reading them (FTD for franchise master; game/tournament doc for else)
        if actual_team_id and (not team_obj or not team_obj.get("plays") or len(team_obj.get("plays", {})) == 0):
            populated_plays = _get_cached_populated_plays(mode=mode)
            
            if mode == "franchise" and not load_from_game_doc:
                franchise_team_data_collection.update_one(
                    {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                    {"$set": {"plays": populated_plays}}
                )
                team_obj["plays"] = populated_plays
            else:
                # Else branch: updating game or tournament doc (both use "teams")
                team_key = f"teams.{actual_team_id}"
                update_coll = games_collection if (load_from_game_doc and mode == "franchise") else collection
                update_id = game_doc["_id"] if (load_from_game_doc and mode == "franchise") else (ObjectId(doc_id) if mode != "single" else doc_id)
                if mode == "single":
                    collection.update_one(
                        {"_id": doc_id},
                        {"$set": {f"{team_key}.plays": populated_plays}}
                    )
                    doc = collection.find_one({"_id": doc_id})
                else:
                    update_coll.update_one(
                        {"_id": update_id},
                        {"$set": {f"{team_key}.plays": populated_plays}}
                    )
                    doc = update_coll.find_one({"_id": update_id})
                    if mode == "franchise" and load_from_game_doc and doc is None:
                        logger.warning(f"🔍 [GET PLAYBOOKS] franchise+game_doc: Ensure-plays reload got doc=None, update_id={update_id!r}; falling back to game_doc")
                        doc = game_doc
                
                # Reload team_obj (game/tournament doc both have "teams")
                if mode == "franchise":
                    team_obj = doc.get("teams", {}).get(actual_team_id, {}) if (actual_team_id and doc) else {}
                    # Plays write + reload can restore stale game-doc playbook_settings (FTD merge is in-memory only).
                    if load_from_game_doc and ftd_merged_playbook_settings:
                        _tm = dict(team_obj or {})
                        _tm["playbook_settings"] = dict(ftd_merged_playbook_settings)
                        team_obj = _tm
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
        if mode == "franchise" and load_from_game_doc:
            logger.warning(f"🔍 [GET PLAYBOOKS] franchise+game_doc: before response build, team_obj plays count={len(plays)}, response built from team_obj")
        
        # Organize plays by type and focus.
        motion_plays = []
        set_plays = []
        legacy_set_plays_inside = []
        legacy_set_plays_attack = []
        legacy_set_plays_outside = []
        
        player_name_lookup = _build_player_name_lookup(team_obj)
        scouting_data = (team_obj or {}).get("scouting_data", {})
        defense_scouting = scouting_data.get("defense", {}) if isinstance(scouting_data, dict) else {}

        for play_key, play_data, display_name in iter_team_plays(plays):
            play_type = play_data.get("play_type", "")
            play_focus = play_data.get("play_focus", "")
            play_summary = {
                "name": display_name,
                "play_id": play_data.get("play_id"),
                "play_type": play_type,
                "play_focus": play_focus,
                "effectiveness": play_data.get("effectiveness", 0),
                "momentum": play_data.get("momentum", 0),
                "cloaking": play_data.get("cloaking", 0),
                "top_scorer": _get_top_scorer_label(play_data, player_name_lookup),
            }
            
            if play_type == "motion":
                play_summary["motion_focus"] = play_data.get("motion_focus")
                motion_plays.append(play_summary)
            elif play_type == "set_play":
                play_summary["target_shooter"] = play_data.get("target_shooter")
                set_plays.append(play_summary)
                if play_focus == "inside":
                    legacy_set_plays_inside.append(play_summary)
                elif play_focus == "attack":
                    legacy_set_plays_attack.append(play_summary)
                elif play_focus == "outside":
                    legacy_set_plays_outside.append(play_summary)
        
        # Sort plays by name for consistency
        motion_plays.sort(key=lambda x: x["name"])
        set_plays.sort(key=lambda x: x["name"])
        legacy_set_plays_inside.sort(key=lambda x: x["name"])
        legacy_set_plays_attack.sort(key=lambda x: x["name"])
        legacy_set_plays_outside.sort(key=lambda x: x["name"])
        
        # Reload team_obj from latest doc so playbook_settings/plays are current.
        if mode == "franchise" and not load_from_game_doc:
            pass  # team_obj already from FTD
        elif mode == "franchise" and load_from_game_doc:
            # Franchise in-game: team_obj already has game doc team + plays merged from FTD; game doc does not store full plays.
            pass
        elif mode == "franchise":
            team_obj = (doc.get("teams", {}).get(actual_team_id, {}) if actual_team_id else {}) if doc else {}
        elif mode == "tournament" and not load_from_game_doc:
            # ✅ FIX: Only reload from tournament doc when NOT loading from game doc.
            # When load_from_game_doc we already have doc=game_doc and team_obj; overwriting doc lost game data.
            logger.warning("🔍 [GET PLAYBOOKS] Reloading doc from tournament master (load_from_game_doc=False)")
            doc = collection.find_one({"_id": ObjectId(doc_id)})
            teams = doc.get("teams", {})
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        elif mode == "tournament" and load_from_game_doc:
            logger.warning("🔍 [GET PLAYBOOKS] Keeping game doc (load_from_game_doc=True), skipping tournament reload")
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

        if mode == "franchise" and load_from_game_doc and ftd_merged_playbook_settings:
            current_pb = (team_obj or {}).get("playbook_settings") or {}
            ftd_pb = ftd_merged_playbook_settings
            ftd_pc = (ftd_pb.get("pc_order") or {}) if isinstance(ftd_pb, dict) else {}
            cur_pc = (current_pb.get("pc_order") or {}) if isinstance(current_pb, dict) else {}
            ftd_off = ftd_pc.get("offense") if isinstance(ftd_pc.get("offense"), list) else []
            cur_off = cur_pc.get("offense") if isinstance(cur_pc.get("offense"), list) else []
            # Full restore when game snapshot has no Playcall identity at all.
            missing_pc_identity = _franchise_playbook_has_pc_order(ftd_pb) and not _franchise_playbook_has_pc_order(
                current_pb
            )
            # Game doc can have defense pc_order and/or slot_assignments so has_pc_order is True,
            # but offense list empty — FTD still has the user's offensive PC order; merge it in.
            missing_offense_pc_only = (
                _franchise_playbook_has_pc_order(ftd_pb)
                and len(ftd_off) > 0
                and len(cur_off) == 0
            )
            if missing_pc_identity or missing_offense_pc_only:
                restored_pb = dict(current_pb)
                if missing_offense_pc_only and not missing_pc_identity:
                    merged_pc = dict(cur_pc)
                    merged_pc["offense"] = list(ftd_off)
                    restored_pb["pc_order"] = merged_pc
                    for _pc_key in ("slot_assignments", "motion_dropdowns"):
                        if ftd_pb.get(_pc_key):
                            restored_pb[_pc_key] = ftd_pb.get(_pc_key)
                    logger.warning(
                        "⚠️ [GET PLAYBOOKS] franchise+game_doc: merged FTD offense PC (game doc had empty offense; "
                        "defense/slots satisfied has_pc_order) franchise=%s game_id=%s team=%s",
                        doc_id,
                        game_id,
                        actual_team_id,
                    )
                else:
                    for _pc_key in ("pc_order", "slot_assignments", "motion_dropdowns"):
                        if ftd_pb.get(_pc_key):
                            restored_pb[_pc_key] = ftd_pb.get(_pc_key)
                    logger.warning(
                        "⚠️ [GET PLAYBOOKS] franchise+game_doc: restored FTD Playcall Center order after doc reload "
                        "franchise=%s game_id=%s team=%s",
                        doc_id,
                        game_id,
                        actual_team_id,
                    )
                team_obj = dict(team_obj or {})
                team_obj["playbook_settings"] = restored_pb
        
        # Get playbook settings.
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
            # FTD: Playbook settings come from FTD team_obj
            playbook_settings = (team_obj or {}).get("playbook_settings", {})
        elif load_from_game_doc and team_obj:
            # ✅ FIX: Loading from game doc - team_obj already has playbook_settings; doc has canonical keys.
            # Using extract_team_settings with request team_id (ObjectId) would fail.
            pb = team_obj.get("playbook_settings") or {}
            pc_order_count = len((pb.get("pc_order", {}) or {}).get("offense", []))
            logger.warning(f"🔍 [GET PLAYBOOKS] Using game doc team_obj for playbook_settings (load_from_game_doc=True), pc_order.offense={pc_order_count}")
            playbook_settings = team_obj.get("playbook_settings", {})
        else:
            # Tournament/franchise master doc - use extract (doc has ObjectId keys)
            from BackEnd.utils.team_settings_manager import extract_team_settings
            team_identifier = (
                actual_team_id if (mode == "franchise" and load_from_game_doc and actual_team_id)
                else (team_id or (team_obj.get("name") if team_obj else None))
            )
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
        
        plays_by_id, plays_by_name = build_play_lookups_from_team_plays(plays)
        # Team play snapshots can omit catalog entries still referenced in pc_order /
        # slot_assignments; merge universal plays so normalize_pc_order does not drop every slot.
        if load_from_game_doc:
            try:
                from BackEnd.db import plays_collection

                _univ_plays = list(
                    plays_collection.find({}, {"_id": 1, "name": 1, "play_id": 1})
                )
                u_by_id, u_by_name = build_play_lookups_from_universal_plays(_univ_plays)
                plays_by_id = {**u_by_id, **plays_by_id}
                plays_by_name = {**u_by_name, **plays_by_name}
            except Exception:
                pass

        fresh_position_shot_weights = compute_position_shot_weights(
            playbook_settings,
            plays,
        )
        cached_position_shot_weights = (
            playbook_settings.get("position_shot_weights")
            if isinstance(playbook_settings, dict)
            else None
        )
        position_shot_weights = cached_position_shot_weights
        if not position_shot_weights or weights_cache_is_stale(
            cached_position_shot_weights,
            fresh_position_shot_weights,
        ):
            position_shot_weights = fresh_position_shot_weights
            if isinstance(playbook_settings, dict):
                playbook_settings["position_shot_weights"] = position_shot_weights
            try:
                from BackEnd.utils.team_settings_manager import save_team_settings
                save_team_settings(
                    settings_type="playbook_settings",
                    settings_data=playbook_settings,
                    team_id=team_id,
                    mode=mode,
                    game_id=game_id,
                    franchise_id=franchise_id,
                    tournament_id=tournament_id,
                    validate_fn=None,
                    apply_to_gamemanager=False,
                )
            except Exception:
                logger.warning(
                    "⚠️ [GET PLAYBOOKS] Failed to persist refreshed position_shot_weights cache",
                    exc_info=True,
                )
            if mode == "single" and use_gamemanager_settings and gm:
                target_team = None
                if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                    target_team = gm.home_team
                elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                    target_team = gm.away_team
                if target_team and hasattr(target_team, "playbook_settings"):
                    target_team.playbook_settings = dict(playbook_settings)

        simplified_playbook_settings = build_simplified_playbook_settings(
            playbook_settings,
            plays_by_id,
            plays_by_name,
        )
        legacy_playbook_settings = build_legacy_playbook_settings_view(
            simplified_playbook_settings,
            plays_by_id,
            plays_by_name,
        )
        motion_dropdowns = normalize_motion_dropdowns_to_play_ids(
            playbook_settings.get("motion_dropdowns", {}) if playbook_settings else {},
            plays_by_id,
            plays_by_name,
        )
        for play_summary in motion_plays:
            if play_summary.get("motion_focus") is None:
                play_summary["motion_focus"] = motion_dropdowns.get(str(play_summary.get("play_id") or ""))
        
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
        
        motion_percentages = simplified_playbook_settings.get("motion", {})
        set_play_percentages = simplified_playbook_settings.get("set_plays", {})
        fast_break_percentages = simplified_playbook_settings.get("fast_breaks", {})
        hc_trap_percentages = simplified_playbook_settings.get("hc_traps", {})
        zone_defense_percentages = simplified_playbook_settings.get("zone_defense", {})
        man_defense_percentages = simplified_playbook_settings.get("man_defense", {})
        pc_order = simplified_playbook_settings.get("pc_order", {"offense": [], "defense": []})
        even_distribution_all = playbook_settings.get("even_distribution_all", False) if playbook_settings else False
        playbook_meta = simplified_playbook_settings.get("_meta", {})
        locks = simplified_playbook_settings.get("locks") or empty_playbook_locks()
        
        if _debug_pc_on(debug_pc):
            _off = (pc_order or {}).get("offense") or []
            _def = (pc_order or {}).get("defense") or []
            _slots = (playbook_settings or {}).get("slot_assignments") if isinstance(playbook_settings, dict) else {}
            _slot_n = len(_slots) if isinstance(_slots, dict) else 0
            try:
                from BackEnd.api.api import ongoing_games

                _gm_hit = bool(game_id and ongoing_games.get(str(game_id)))
            except Exception:
                _gm_hit = False
            logger.warning(
                "[DEBUG_PC] GET /api/playbooks OUT mode=%r request_team_id=%r game_id=%r franchise_id=%r "
                "tournament_id=%r load_from_game_doc=%s authoritative_team_id=%r game_doc_team_id=%r "
                "actual_team_id=%r pc_offense_len=%s pc_defense_len=%s slot_assignments_count=%s "
                "use_gamemanager_settings=%s ongoing_games_hit=%s",
                mode,
                team_id,
                game_id,
                franchise_id,
                tournament_id,
                load_from_game_doc,
                authoritative_team_id,
                game_doc_team_id,
                actual_team_id if "actual_team_id" in locals() else None,
                len(_off) if isinstance(_off, list) else None,
                len(_def) if isinstance(_def, list) else None,
                _slot_n,
                use_gamemanager_settings,
                _gm_hit,
            )

        return {
            "motion": motion_plays,
            "set_plays": set_plays,
            "fast_breaks": [
                {"id": "triangle", "name": "Triangle"},
                {"id": "rim_runner", "name": "Rim Runner"},
                {"id": "covert_release", "name": "Covert Release"},
            ],
            "hc_traps": [
                {"id": "standard_trap", "name": "Standard Trap"},
                {"id": "straight_pressure", "name": "Straight Pressure"},
                {"id": "standard_diamond", "name": "Standard Diamond"},
            ],
            "man_defense_rows": [
                {
                    "id": defense_id,
                    "name": defense_name,
                    "effectiveness": float(
                        read_scouting_defense_row(
                            defense_scouting,
                            PLAYBOOK_MAN_KEY_TO_DEFENSE_ID.get(defense_id, "man"),
                        ).get("effectiveness", 0)
                        or 0
                    ),
                    "is_active": defense_id == "man_normal",
                }
                for defense_id, defense_name in MAN_DEFENSE_ID_TO_NAME.items()
            ],
            "zone_defense_rows": [
                {
                    "id": defense_id,
                    "name": defense_name,
                    "effectiveness": float(
                        read_scouting_defense_row(
                            defense_scouting,
                            PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID.get(defense_id) or "",
                        ).get("effectiveness", 0)
                        or 0
                    ),
                    "is_active": True,
                }
                for defense_id, defense_name in ZONE_DEFENSE_ID_TO_NAME.items()
            ],
            "pc_order": pc_order,
            "locks": locks,
            "position_shot_weights": position_shot_weights,
            "motion_dropdowns": motion_dropdowns,
            "position_filters": position_filters,
            "even_distribution_all": even_distribution_all,
            "playbook_meta": playbook_meta,
            "simple_playbook_percentages": {
                "motion": motion_percentages,
                "set_plays": set_play_percentages,
                "fast_breaks": fast_break_percentages,
                "hc_traps": hc_trap_percentages,
                "zone_defense": zone_defense_percentages,
                "man_defense": man_defense_percentages,
            },
            "playbook_percentages": {
                "motion": legacy_playbook_settings.get("motion", {}),
                "set_play_inside": legacy_playbook_settings.get("set_play_inside", {}),
                "set_play_attack": legacy_playbook_settings.get("set_play_attack", {}),
                "set_play_outside": legacy_playbook_settings.get("set_play_outside", {}),
                "fast_break": legacy_playbook_settings.get("fast_break", {}),
                "zone_defense": legacy_playbook_settings.get("zone_defense", {}),
                "man_defense": legacy_playbook_settings.get("man_defense", {}),
            },
            # Backward-compatible fields for the old Playbooks frontend until the UI rewrite lands.
            "set_play_inside": legacy_set_plays_inside,
            "set_play_attack": legacy_set_plays_attack,
            "set_play_outside": legacy_set_plays_outside,
            "slot_assignments": legacy_playbook_settings.get("slot_assignments", {}),
            "legacy_playbook_percentages": {
                "motion": legacy_playbook_settings.get("motion", {}),
                "set_play_inside": legacy_playbook_settings.get("set_play_inside", {}),
                "set_play_attack": legacy_playbook_settings.get("set_play_attack", {}),
                "set_play_outside": legacy_playbook_settings.get("set_play_outside", {}),
                "fast_break": legacy_playbook_settings.get("fast_break", {}),
                "zone_defense": legacy_playbook_settings.get("zone_defense", {}),
                "man_defense": legacy_playbook_settings.get("man_defense", {}),
            },
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading playbooks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # ✅ PERFORMANCE DIAGNOSTIC: Log total endpoint time
        if 'endpoint_start' in locals():
            total_time = (time.time() - endpoint_start) * 1000  # Convert to ms
            process_time = (time.time() - process_start) * 1000 if 'process_start' in locals() else 0
            # logger.warning(f"⏱️ [PERF] /api/playbooks - Processing: {process_time:.2f}ms, Total: {total_time:.2f}ms, mode: {mode}")


class PlaybookSettingsRequest(BaseModel):
    mode: str
    team_id: str
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None
    playbook_settings: dict
    play_updates: Optional[dict] = None


def _apply_play_updates_to_plays(plays: dict, play_updates: dict | None) -> dict:
    """Return a copy of team plays with draft motion_focus / target_shooter applied (no persistence)."""
    updated = dict(plays or {})
    if not isinstance(play_updates, dict) or not play_updates:
        return updated

    for _play_key, play_data, _display_name in iter_team_plays(updated):
        if not isinstance(play_data, dict):
            continue
        play_id = str(play_data.get("play_id") or "")
        if not play_id or play_id not in play_updates:
            continue
        update_data = play_updates.get(play_id) or {}
        if play_data.get("play_type") == "motion" and "motion_focus" in update_data:
            next_focus = update_data.get("motion_focus")
            play_data["motion_focus"] = next_focus if next_focus in {"inside", "attack", "outside"} else None
        if play_data.get("play_type") == "set_play" and "target_shooter" in update_data:
            next_target = update_data.get("target_shooter")
            if next_target in {"PG", "SG", "SF", "PF", "C"}:
                play_data["target_shooter"] = next_target
    return updated


def _normalize_playbook_settings_payload(
    incoming_playbook_settings: dict,
    plays_by_id: dict,
    plays_by_name: dict,
) -> dict:
    """Canonicalize an incoming playbook_settings dict for save or preview."""
    playbook_settings = build_simplified_playbook_settings(
        incoming_playbook_settings,
        plays_by_id,
        plays_by_name,
    )
    playbook_settings["motion"] = normalize_percentage_map_to_play_ids(
        playbook_settings.get("motion", {}),
        plays_by_id,
        plays_by_name,
    )
    playbook_settings["set_plays"] = normalize_percentage_map_to_play_ids(
        playbook_settings.get("set_plays", {}),
        plays_by_id,
        plays_by_name,
    )
    playbook_settings["fast_breaks"] = normalize_string_keyed_map(
        playbook_settings.get("fast_breaks", {}),
        {"Triangle": "triangle", "Rim Runner": "rim_runner", "Covert Release": "covert_release"},
    )
    playbook_settings["hc_traps"] = normalize_string_keyed_map(
        playbook_settings.get("hc_traps", {}),
        {"Standard Trap": "standard_trap", "Straight Pressure": "straight_pressure", "Standard Diamond": "standard_diamond", "Diamond": "standard_diamond"},
    )
    playbook_settings["zone_defense"] = normalize_string_keyed_map(
        playbook_settings.get("zone_defense", {}),
        {"2-3 Zone": "zone_23", "3-2 Zone": "zone_32", "1-3-1 Zone": "zone_131"},
    )
    playbook_settings["man_defense"] = normalize_string_keyed_map(
        playbook_settings.get("man_defense", {}),
        {"Man": "man_normal", "Man Pressure": "man_pressure", "Man Loose": "man_loose"},
    )
    playbook_settings["pc_order"] = normalize_pc_order(
        playbook_settings.get("pc_order", {}),
        plays_by_id,
        plays_by_name,
    )
    playbook_settings["locks"] = normalize_playbook_locks(
        incoming_playbook_settings.get("locks", playbook_settings.get("locks")),
        plays_by_id,
        plays_by_name,
    )
    if isinstance(incoming_playbook_settings.get("position_filters"), dict):
        playbook_settings["position_filters"] = incoming_playbook_settings.get("position_filters", {})
    playbook_settings["even_distribution_all"] = bool(
        incoming_playbook_settings.get("even_distribution_all", False)
    )
    return playbook_settings


@router.post("/api/playbooks/preview-shot-weights")
def preview_playbook_shot_weights(request: PlaybookSettingsRequest):
    """
    Compute position_shot_weights for a draft playbook without saving.

    Same payload shape as POST /api/playbooks. Intended for debounced live
    preview on the Playbooks page (fire on settle, not per pointermove).
    """
    try:
        incoming_playbook_settings = dict(request.playbook_settings or {})
        from BackEnd.db import plays_collection

        universal_plays = list(plays_collection.find({}, {"_id": 1, "name": 1}))
        plays_by_id, plays_by_name = build_play_lookups_from_universal_plays(universal_plays)

        playbook_settings = _normalize_playbook_settings_payload(
            incoming_playbook_settings,
            plays_by_id,
            plays_by_name,
        )

        current_plays, _plays_team_id = _load_current_team_plays_for_save(
            request.mode,
            request.team_id,
            franchise_id=request.franchise_id,
            tournament_id=request.tournament_id,
            game_id=request.game_id,
        )
        draft_plays = _apply_play_updates_to_plays(current_plays, request.play_updates)

        return {
            "success": True,
            "position_shot_weights": compute_position_shot_weights(
                playbook_settings,
                draft_plays,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing playbook shot weights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/playbooks")
def save_playbooks(request: PlaybookSettingsRequest):
    """
    Save playbook settings (percentages) for a team.
    Stores in teams.{team_id}.playbook_settings in the appropriate mode document.
    """
    from BackEnd.utils.team_settings_manager import save_team_settings
    
    try:
        # Normalize incoming data to the simplified canonical structure.
        incoming_playbook_settings = dict(request.playbook_settings or {})
        from BackEnd.db import plays_collection

        universal_plays = list(plays_collection.find({}, {"_id": 1, "name": 1}))
        plays_by_id, plays_by_name = build_play_lookups_from_universal_plays(universal_plays)

        playbook_settings = _normalize_playbook_settings_payload(
            incoming_playbook_settings,
            plays_by_id,
            plays_by_name,
        )
        playbook_meta = playbook_settings.get("_meta", {})
        if not isinstance(playbook_meta, dict):
            playbook_meta = {}
        playbook_meta["user_saved"] = True
        playbook_meta["schema_version"] = 2
        if request.mode == "franchise" and request.franchise_id and not request.game_id:
            from BackEnd.db import franchises_collection
            franchise_doc = franchises_collection.find_one(
                {"_id": ObjectId(request.franchise_id)},
                {"week": 1}
            ) or {}
            playbook_meta["saved_for_week"] = int(franchise_doc.get("week", 1) or 1)
        playbook_settings["_meta"] = playbook_meta

        current_plays, plays_team_id = _load_current_team_plays_for_save(
            request.mode,
            request.team_id,
            franchise_id=request.franchise_id,
            tournament_id=request.tournament_id,
            game_id=request.game_id,
        )
        play_updates = request.play_updates or {}
        plays_changed = False
        if isinstance(play_updates, dict) and play_updates:
            for _play_key, play_data, _display_name in iter_team_plays(current_plays):
                play_id = str(play_data.get("play_id") or "")
                if not play_id or play_id not in play_updates:
                    continue
                update_data = play_updates.get(play_id) or {}
                if play_data.get("play_type") == "motion" and "motion_focus" in update_data:
                    next_focus = update_data.get("motion_focus")
                    normalized_focus = next_focus if next_focus in {"inside", "attack", "outside"} else None
                    if play_data.get("motion_focus") != normalized_focus:
                        play_data["motion_focus"] = normalized_focus
                        plays_changed = True
                if play_data.get("play_type") == "set_play" and "target_shooter" in update_data:
                    next_target = update_data.get("target_shooter")
                    normalized_target = next_target if next_target in {"PG", "SG", "SF", "PF", "C"} else play_data.get("target_shooter")
                    if play_data.get("target_shooter") != normalized_target:
                        play_data["target_shooter"] = normalized_target
                        plays_changed = True

        if plays_changed:
            plays_success, _, _ = save_team_settings(
                settings_type="plays",
                settings_data=current_plays,
                team_id=request.team_id,
                mode=request.mode,
                game_id=request.game_id,
                franchise_id=request.franchise_id,
                tournament_id=request.tournament_id,
                validate_fn=None,
                apply_to_gamemanager=False,
            )
            if not plays_success:
                raise HTTPException(status_code=500, detail="Failed to save play configuration")

            if request.game_id:
                try:
                    from BackEnd.api.api import ongoing_games
                    gm = ongoing_games.get(request.game_id)
                    if gm:
                        if gm.home_team.team_id == plays_team_id or gm.home_team.name == request.team_id:
                            gm.home_team.plays = dict(current_plays)
                        elif gm.away_team.team_id == plays_team_id or gm.away_team.name == request.team_id:
                            gm.away_team.plays = dict(current_plays)
                except Exception:
                    pass

        playbook_settings["position_shot_weights"] = compute_position_shot_weights(
            playbook_settings,
            current_plays,
        )

        # ✅ UNIFIED: Use unified save function for consistent team_id resolution
        success, actual_team_id, collection_name = save_team_settings(
            settings_type="playbook_settings",
            settings_data=playbook_settings,
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
        offense_pc_count = len((playbook_settings.get("pc_order", {}) or {}).get("offense", []))
        defense_pc_count = len((playbook_settings.get("pc_order", {}) or {}).get("defense", []))
        logger.warning(
            f"🟢 [STATE-WRITE] [save_playbooks] playbook_settings to backend | "
            f"team_id={actual_team_id}, pc_order.offense={offense_pc_count}, pc_order.defense={defense_pc_count}, endpoint=/api/playbooks"
        )
        
        return {
            "success": True,
            "message": "Playbook settings saved successfully",
            "position_shot_weights": playbook_settings.get("position_shot_weights"),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving playbook settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
