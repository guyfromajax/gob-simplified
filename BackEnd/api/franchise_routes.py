from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pathlib import Path
from bson import ObjectId
import logging
import random
from typing import Any, Optional
from datetime import datetime
from BackEnd.main import run_simulation

from BackEnd.db import db, franchise_state_collection
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.utils.team_stats_aggregator import aggregate_team_stats_from_players
from BackEnd.models.franchise_manager import FranchiseManager
from BackEnd.tournament.eos_tournament import (
    initialize_eos_tournament,
    advance_tournament_round,
    save_tournament_game_result,
    get_round_name
)
from BackEnd.utils.db_utils import build_lineup_from_mongo
from BackEnd.utils.game_id_utils import generate_game_id

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


def get_user_team_from_franchise(franchise_doc: dict) -> tuple[str | None, str | None]:
    """
    Get user team identifiers from franchise document with backward compatibility.
    
    Returns:
        tuple: (user_team_id: team name, user_team_object_id: ObjectId string)
        Falls back to franchise_state_collection if not found in franchise document.
    """
    # Try franchise document first (new approach)
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    
    if user_team_id and user_team_object_id:
        return (user_team_id, user_team_object_id)
    
    # Fallback to state collection (backward compatibility for old franchises)
    # Note: This is deprecated - new franchises should use franchise document fields
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if team_name:
            logger.warning(f"⚠️ [DEPRECATED] Using franchise_state fallback for team: {team_name}. "
                         f"Franchise should have user_team_id and user_team_object_id in document.")
            team_doc = db.teams.find_one({"name": team_name})
            if team_doc:
                return (team_name, str(team_doc["_id"]))
    except Exception as e:
        logger.debug(f"franchise_state collection not available (expected for new franchises): {e}")
    
    return (None, None)


def generate_random_training_allocations(total_points: int) -> dict:
    """
    Generate random training allocations similar to auto-train logic.
    
    Logic:
    - Set all 20 sliders to 1 (20 points)
    - Randomly pick (total_points - 20) sliders to set to 2
    
    Args:
        total_points: Total training points (30 for first training, 24 otherwise)
    
    Returns:
        Dict with player_drills, team_drills, general structure
    """
    # Initialize all to 1
    allocations = {
        "player_drills": {
            "offense": {"inside": 1, "outside": 1},
            "defense": {"inside": 1, "outside": 1},
            "technical": {"passing": 1, "ball_handling": 1, "rebounding": 1},
            "weight_room": {"strength": 1, "agility": 1}
        },
        "team_drills": {
            "team_offense": {"install": 1},
            "team_defense": {"install": 1},
            "fast_breaks": {"offense_install": 1, "defense_install": 1},
            "scrimmages": 1,
            "presses_traps": {"defense_install": 1, "offense_install": 1}
        },
        "general": {
            "conditioning": 1,
            "free_throws": 1,
            "film_study": 1,
            "breaks": 1
        }
    }
    
    # Define all 20 sliders for random selection
    sliders = [
        # Player Drills (9 sliders)
        ("player_drills", "offense", "inside"),
        ("player_drills", "offense", "outside"),
        ("player_drills", "defense", "inside"),
        ("player_drills", "defense", "outside"),
        ("player_drills", "technical", "passing"),
        ("player_drills", "technical", "ball_handling"),
        ("player_drills", "technical", "rebounding"),
        ("player_drills", "weight_room", "strength"),
        ("player_drills", "weight_room", "agility"),
        # Team Drills (7 sliders)
        ("team_drills", "team_offense", "install"),
        ("team_drills", "team_defense", "install"),
        ("team_drills", "fast_breaks", "offense_install"),
        ("team_drills", "fast_breaks", "defense_install"),
        ("team_drills", "scrimmages", None),
        ("team_drills", "presses_traps", "defense_install"),
        ("team_drills", "presses_traps", "offense_install"),
        # General (4 sliders)
        ("general", None, "conditioning"),
        ("general", None, "free_throws"),
        ("general", None, "film_study"),
        ("general", None, "breaks"),
    ]
    
    # Randomly pick (total_points - 20) sliders to set to 2
    remaining_points = total_points - 20
    shuffled = sliders.copy()
    random.shuffle(shuffled)
    
    for i in range(min(remaining_points, len(shuffled))):
        category, subcategory, key = shuffled[i]
        
        if category == "player_drills":
            allocations[category][subcategory][key] = 2
        elif category == "team_drills":
            if subcategory == "scrimmages":
                allocations[category][subcategory] = 2
            else:
                allocations[category][subcategory][key] = 2
        elif category == "general":
            allocations[category][key] = 2
    
    return allocations


def generate_random_coaching_focus() -> str:
    """
    Randomly select a coaching focus from all available options.
    
    Returns:
        String value matching the radio button value (e.g., "authoritarian-discipline")
    """
    coaching_focus_options = [
        "authoritarian",
        "authoritarian-discipline",
        "authoritarian-rebounding",
        "authoritarian-execution",
        "authoritarian-teamwork",
        "systems-coach",
        "systems-coach-offense",
        "systems-coach-defense",
        "systems-coach-fast-breaks",
        "systems-coach-press-trap",
        "player-maximizer",
        "player-maximizer-top-3",
        "player-maximizer-attributes-4-6",
        "player-maximizer-custom",
        "player-maximizer-opportunity",
        "culture-builder",
        "culture-builder-inspire",
        "culture-builder-community",
        "culture-builder-teamwork",
        "culture-builder-confidence",
    ]
    
    return random.choice(coaching_focus_options)


@router.get("/court.html")
def serve_court_html():
    """Return the court page so query params work in production."""
    return FileResponse(STATIC_DIR / "court.html")

# @router.get("/franchise/start")
# def franchise_start():
#     state = franchise_state_collection.find_one({"_id": "state"}) or {}
#     if not state.get("team"):
#         return RedirectResponse(url="/franchise/select-team")
#     return RedirectResponse(url="/franchise/command-center")
@router.get("/franchise/start")
def franchise_start():
    return RedirectResponse(url="/franchise/select-team")


@router.get("/franchise/select-team")
def get_select_team_page():
    return FileResponse(STATIC_DIR / "franchise-select-team.html")

class TeamSelection(BaseModel):
    team_name: str

class PlayGameRequest(BaseModel):
    franchise_id: str


class FranchiseResultRequest(BaseModel):
    franchise_id: str
    game_id: str
    winner: str


class GameResult(BaseModel):
    team1_id: str
    team2_id: str
    team1_score: int
    team2_score: int


class CompleteWeekRequest(BaseModel):
    franchise_id: str
    week: int
    result: GameResult
    game_id: str | None = None  # Optional: actual gameplay game_id (ObjectId format)
    game_document: dict | None = None  # Optional: complete game document from simulate-quarter (eliminates race condition)


def _normalize_team_id(team_id: str):
    try:
        return ObjectId(team_id)
    except Exception:
        doc = db.teams.find_one(
            {"$or": [{"_id": team_id}, {"name": team_id}, {"code": team_id}]}
        )
        if not doc:
            raise HTTPException(status_code=400, detail=f"Unknown team id {team_id}")
        return doc["_id"]


def _apply_team_result(team1_id, team2_id, team1_score, team2_score, sign=1):
    db.teams.update_one({"_id": team1_id}, {"$inc": {"PF": sign * team1_score, "PA": sign * team2_score, "record.W": 0, "record.L": 0}})
    db.teams.update_one({"_id": team2_id}, {"$inc": {"PF": sign * team2_score, "PA": sign * team1_score, "record.W": 0, "record.L": 0}})
    if team1_score > team2_score:
        db.teams.update_one({"_id": team1_id}, {"$inc": {"record.W": sign}})
        db.teams.update_one({"_id": team2_id}, {"$inc": {"record.L": sign}})
    elif team2_score > team1_score:
        db.teams.update_one({"_id": team2_id}, {"$inc": {"record.W": sign}})
        db.teams.update_one({"_id": team1_id}, {"$inc": {"record.L": sign}})


def _save_game_result(team1_id, team2_id, team1_score, team2_score, week, franchise_id=None, game_id=None):
    """
    Save or update game result in games collection.
    
    Args:
        team1_id: Team 1 ObjectId
        team2_id: Team 2 ObjectId
        team1_score: Team 1 score
        team2_score: Team 2 score
        week: Week number
        franchise_id: Optional franchise ID
        game_id: Optional game_id (ObjectId format). If provided, updates that specific game document.
                 If None, uses legacy lookup by week + team IDs.
    
    Returns:
        Dictionary with team IDs and scores
    """
    # ✅ SS&S: If game_id is provided, use it directly (this is the actual gameplay document)
    if game_id:
        try:
            # Try as ObjectId first
            game_oid = ObjectId(game_id) if isinstance(game_id, str) else game_id
            existing = db.games.find_one({"_id": game_oid})
            if existing:
                # Update existing game document with result fields
                _apply_team_result(existing.get("team1_id"), existing.get("team2_id"), existing.get("team1_score", 0), existing.get("team2_score", 0), sign=-1)
                filter_doc = {"_id": game_oid}
            else:
                # Game document doesn't exist yet, create it
                filter_doc = {"_id": game_oid}
        except Exception as e:
            logger.warning(f"⚠️ [_SAVE_GAME_RESULT] Invalid game_id format: {game_id}, error: {e}. Falling back to legacy lookup.")
            game_id = None  # Fall through to legacy logic
    
    # Legacy lookup (when game_id not provided or invalid)
    if not game_id:
        existing = db.games.find_one({
            "week": week,
            "$or": [
                {"team1_id": team1_id, "team2_id": team2_id},
                {"team1_id": team2_id, "team2_id": team1_id},
            ],
        })

        if existing:
            _apply_team_result(existing["team1_id"], existing["team2_id"], existing["team1_score"], existing["team2_score"], sign=-1)
            filter_doc = {"_id": existing["_id"]}
        else:
            filter_doc = {"week": week, "team1_id": team1_id, "team2_id": team2_id}

    _apply_team_result(team1_id, team2_id, team1_score, team2_score, sign=1)

    update_fields = {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "team1_score": team1_score,
        "team2_score": team2_score,
        "week": week,
    }
    
    if franchise_id:
        update_fields["franchise_id"] = str(franchise_id)

    db.games.update_one(
        filter_doc,
        {"$set": update_fields},
        upsert=True,
    )

    return {
        "team1_id": str(team1_id),
        "team2_id": str(team2_id),
        "team1_score": team1_score,
        "team2_score": team2_score,
    }

@router.options("/franchise/select-team")
async def select_team_options():
    """
    Explicit OPTIONS handler for CORS preflight debugging.
    This bypasses CORSMiddleware to see if requests reach FastAPI at all.
    """
    import sys
    print(f"🔵 [DEBUG] select_team_options: OPTIONS /franchise/select-team called", file=sys.stderr, flush=True)
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "https://gob-test.netlify.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )

@router.post("/franchise/select-team")
def select_team(selection: TeamSelection):
    import sys
    print(f"🔵 [DEBUG] select_team: POST /franchise/select-team called with team: {selection.team_name}", file=sys.stderr, flush=True)
    try:
        # Resolve team name to ObjectId
        print(f"🔵 [DEBUG] select_team: Looking up team in database: {selection.team_name}", file=sys.stderr, flush=True)
        team_doc = db.teams.find_one({"name": selection.team_name})
        if not team_doc:
            print(f"❌ [ERROR] select_team: Team not found in database: {selection.team_name}", file=sys.stderr, flush=True)
            raise HTTPException(status_code=404, detail="Team not found")
        
        print(f"✅ [DEBUG] select_team: Team found, _id: {team_doc['_id']}", file=sys.stderr, flush=True)
        user_team_id = selection.team_name  # Team name (human-readable)
        user_team_object_id = str(team_doc["_id"])  # ObjectId string (database identifier)
        
        # Note: franchise_state_collection removed - using franchise document instead
        # Old franchises may still have data in franchise_state, but new ones won't create it
        
        print(f"🔵 [DEBUG] select_team: Initializing FranchiseManager...", file=sys.stderr, flush=True)
        manager = FranchiseManager(db)
        manager.initialize_season(user_team_id=user_team_id, user_team_object_id=user_team_object_id)
        print(f"✅ [DEBUG] select_team: Franchise initialized successfully, franchise_id: {manager.franchise_id}", file=sys.stderr, flush=True)
        result = {"status": "ok", "franchise_id": str(manager.franchise_id)}
        print(f"🔵 [DEBUG] select_team: Returning response: {result}", file=sys.stderr, flush=True)
        return result
    except HTTPException as e:
        print(f"❌ [ERROR] select_team: HTTPException raised: {e.status_code} - {e.detail}", file=sys.stderr, flush=True)
        raise
    except Exception as e:
        print(f"❌ [ERROR] select_team: Unexpected exception: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/franchise/command-center")
def command_center():
    return FileResponse(STATIC_DIR / "franchise-command-center.html")


@router.get("/animation")
def get_animation_page():
    return FileResponse(STATIC_DIR / "court.html")


@router.post("/franchise/play-next-game")
def play_next_game(req: PlayGameRequest):
    franchise_doc = db.franchises.find_one({"_id": ObjectId(req.franchise_id)})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get user team info (with backward compatibility)
    user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_name or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise")
    
    # Resolve user_team_object_id to ObjectId for matching
    try:
        user_team_id = ObjectId(user_team_object_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user team ObjectId")

    manager = FranchiseManager(db)
    manager.schedule = franchise_doc.get("schedule", [])
    manager.week = franchise_doc.get("week", 1)
    manager.franchise_id = franchise_doc.get("_id")

    # ✅ EOS TOURNAMENT: Check if tournament is active (weeks 15-17)
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    eos_tournament = franchise_doc.get("eos_tournament", {})
    
    matchup = None
    
    if eos_tournament_active and eos_tournament and manager.week >= 15:
        # ✅ SS&S: Reuse Tournament mode's bracket lookup pattern
        # Get current round and round name
        current_round = eos_tournament.get("current_round", 1)
        round_name = get_round_name(current_round)
        bracket = eos_tournament.get("bracket", {})
        matchups = bracket.get(round_name, [])
        
        # Find user's matchup in bracket (reusing Tournament mode pattern)
        user_matchup = None
        for matchup_data in matchups:
            # Matchups use ObjectId strings, compare with user_team_id as string
            if str(user_team_id) in [matchup_data.get("home_team"), matchup_data.get("away_team")]:
                user_matchup = matchup_data
                break
        
        if user_matchup:
            # Get team names from ObjectIds
            home_id = ObjectId(user_matchup["home_team"])
            away_id = ObjectId(user_matchup["away_team"])
            home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
            away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
            
            matchup = {
                "home": home_doc.get("name", "") if home_doc else "",
                "away": away_doc.get("name", "") if away_doc else "",
                "home_id": str(home_id),
                "away_id": str(away_id),
                "week": manager.week,
            }
    else:
        # Regular season (weeks 1-14)
        if manager.week - 1 < len(manager.schedule):
            for away_id, home_id in manager.schedule[manager.week - 1]:
                # Compare ObjectIds (schedule uses ObjectIds, user_team_id is now ObjectId)
                if away_id == user_team_id or home_id == user_team_id:
                    away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
                    home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
                    matchup = {
                        "home": home_doc.get("name", ""),
                        "away": away_doc.get("name", ""),
                        "home_id": str(home_id),
                        "away_id": str(away_id),
                        "week": manager.week,
                    }
                    break

    if not matchup:
        raise HTTPException(status_code=404, detail="User matchup not found")
    return matchup


@router.post("/franchise/save-result")
def save_result(req: FranchiseResultRequest):
    try:
        franchise_id = ObjectId(req.franchise_id)
        game_id = ObjectId(req.game_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    game_doc = db.games.find_one({"_id": game_id})
    if not game_doc:
        raise HTTPException(status_code=404, detail="Game not found")

    home = game_doc.get("homeTeam", {}) or {}
    away = game_doc.get("awayTeam", {}) or {}
    home_name = home.get("name") or game_doc.get("home_team")
    away_name = away.get("name") or game_doc.get("away_team")
    home_id = home.get("team_id") or game_doc.get("home_team_id")
    away_id = away.get("team_id") or game_doc.get("away_team_id")
    score_map = game_doc.get("score") or game_doc.get("final_score") or {}
    home_score = home.get("score", score_map.get(home_name, 0))
    away_score = away.get("score", score_map.get(away_name, 0))

    if req.winner == home_name:
        winner_id, loser_id = home_id, away_id
        winner_score, loser_score = home_score, away_score
    else:
        winner_id, loser_id = away_id, home_id
        winner_score, loser_score = away_score, home_score

    db.teams.update_one(
        {"_id": winner_id}, {"$inc": {"record.W": 1, "PF": winner_score, "PA": loser_score}}
    )
    db.teams.update_one(
        {"_id": loser_id}, {"$inc": {"record.L": 1, "PF": loser_score, "PA": winner_score}}
    )

    week = franchise_doc.get("week", 1) - 1
    if week < 1:
        week = 1

    db.games.delete_many(
        {
            "week": week,
            "$or": [
                {"team1_id": away_id, "team2_id": home_id},
                {"team1_id": home_id, "team2_id": away_id},
            ],
            "_id": {"$ne": game_id},
        }
    )

    db.games.update_one(
        {"_id": game_id},
        {
            "$set": {
                "franchise_id": str(franchise_id),
                "team1_id": away_id,
                "team2_id": home_id,
                "team1_score": away_score,
                "team2_score": home_score,
                "week": week,
            }
        },
        upsert=True,
    )
    
    # ✅ FIX: Verify box_score exists before finalize_game()
    # box_score should already exist from summarize_game_state() which calls game.get_box_score()
    # (includes all players: lineup + bench). If it's missing/incomplete, log error but don't rebuild
    # from players array (which only has final 5 players per team).
    game_doc_updated = db.games.find_one({"_id": game_id})
    if game_doc_updated:
        box_score = game_doc_updated.get("box_score", {})
        home_team_obj = game_doc_updated.get("home_team", {})
        away_team_obj = game_doc_updated.get("away_team", {})
        
        # Check if box_score exists in nested structure (where summarize_game_state stores it)
        if not box_score:
            if isinstance(home_team_obj, dict) and "box_score" in home_team_obj:
                home_team_name = home_team_obj.get("name")
                if home_team_name:
                    box_score[home_team_name] = home_team_obj.get("box_score", {})
            if isinstance(away_team_obj, dict) and "box_score" in away_team_obj:
                away_team_name = away_team_obj.get("name")
                if away_team_name:
                    box_score[away_team_name] = away_team_obj.get("box_score", {})
        
        # Verify box_score is complete (has reasonable number of players per team)
        # Expected: ~12 players per team (5 starters + 7 bench), minimum 5 (just starters)
        if box_score:
            for team_name, team_box in box_score.items():
                player_count = len(team_box) if isinstance(team_box, dict) else 0
                if player_count < 5:
                    logger.warning(f"⚠️ [SAVE-RESULT] box_score for {team_name} has only {player_count} players (expected 12). Game_id={game_id}")
        else:
            logger.error(f"❌ [SAVE-RESULT] No box_score found in game document (game_id={game_id}). finalize_game() may fail or produce incomplete stats.")
    
    stat_updater.finalize_game(
        req.game_id, mode="franchise", franchise_id=req.franchise_id
    )

    return {"status": "success"}


@router.post("/franchise/complete-week")
def complete_week(req: CompleteWeekRequest):
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    schedule = franchise_doc.get("schedule", [])
    if req.week < 1 or req.week > len(schedule):
        raise HTTPException(status_code=400, detail="Invalid week")

    week_games = schedule[req.week - 1]
    results = []

    user = req.result
    team1_id = _normalize_team_id(user.team1_id)
    team2_id = _normalize_team_id(user.team2_id)
    
    # ✅ SS&S: Use provided game_id if available (this is the actual gameplay document with box_score)
    user_game_id = req.game_id
    user_res = _save_game_result(team1_id, team2_id, user.team1_score, user.team2_score, req.week, franchise_id=req.franchise_id, game_id=user_game_id)
    results.append({
        "away_id": user_res["team1_id"],
        "home_id": user_res["team2_id"],
        "away_score": user_res["team1_score"],
        "home_score": user_res["team2_score"],
    })
    
    # ✅ SS&S: Call finalize_game() with the actual gameplay game_id (if provided)
    # ✅ FIX: Use game_document from request if provided (eliminates race condition)
    # This matches Tournament mode pattern where game document is already available
    if user_game_id:
        logger.info(f"🔍 [COMPLETE_WEEK] Calling finalize_game() for user's game with provided game_id: {user_game_id}")
        
        # ✅ FIX: Use game_document from request if provided (returned from simulate-quarter when is_final=True)
        # This eliminates race condition where complete_week() is called before Q4 save completes
        if req.game_document:
            logger.info(f"✅ [COMPLETE_WEEK] Using game_document from request (no database lookup needed)")
            summary = req.game_document
            quarter = summary.get("quarter", "N/A")
            is_final = summary.get("is_final", False)
            logger.info(f"🔍 [COMPLETE_WEEK] game_document details: quarter={quarter}, is_final={is_final}, game_id={summary.get('_id') or summary.get('game_id')}")
        else:
            # Fallback: Look up from database (for backward compatibility)
            logger.info(f"🔍 [COMPLETE_WEEK] game_document not provided, looking up from database...")
            
            # ✅ DEBUG: Check all game documents with this game_id to see what quarters exist
            logger.info(f"🔍 [COMPLETE_WEEK] Checking all game documents with game_id: {user_game_id}")
            try:
                # Try to find all documents that might match (different formats)
                all_docs = []
                for lookup_id in [user_game_id, ObjectId(user_game_id) if ObjectId.is_valid(user_game_id) else None]:
                    if lookup_id:
                        doc = db.games.find_one({"_id": lookup_id})
                        if doc:
                            all_docs.append((lookup_id, doc))
                if all_docs:
                    for lookup_id, doc in all_docs:
                        quarter = doc.get("quarter", "N/A")
                        is_final = doc.get("is_final", False)
                        week = doc.get("week", "N/A")
                        home = doc.get("home_team", {}).get("name") if isinstance(doc.get("home_team"), dict) else doc.get("home_team", "N/A")
                        away = doc.get("away_team", {}).get("name") if isinstance(doc.get("away_team"), dict) else doc.get("away_team", "N/A")
                        logger.info(f"🔍 [COMPLETE_WEEK] Found document with _id={lookup_id}: quarter={quarter}, is_final={is_final}, week={week}, home={home}, away={away}")
                else:
                    logger.warning(f"⚠️ [COMPLETE_WEEK] No documents found with game_id: {user_game_id}")
            except Exception as e:
                logger.error(f"❌ [COMPLETE_WEEK] Error checking game documents: {e}")
            
            # ✅ SS&S: Replicate Tournament mode game document lookup pattern (with multiple fallback attempts)
            gid = (
                ObjectId(user_game_id)
                if ObjectId.is_valid(user_game_id)
                else user_game_id
            )
            logger.info(f"🔍 [COMPLETE_WEEK] User game - game_id from request: {user_game_id} (type: {type(user_game_id)}), converted gid: {gid} (type: {type(gid)})")
            
            # Try multiple formats to find the game document (matches Tournament mode pattern)
            summary = None
            # First try: Use gid as-is (ObjectId if conversion succeeded, string otherwise)
            summary = db.games.find_one({"_id": gid}) or {}
            if summary and summary.get("_id"):
                quarter = summary.get("quarter", "N/A")
                is_final = summary.get("is_final", False)
                logger.info(f"🔍 [COMPLETE_WEEK] First try found document: quarter={quarter}, is_final={is_final}")
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [COMPLETE_WEEK] Game not found with gid={gid}, trying string format")
                # Second try: Use string format
                try:
                    summary = db.games.find_one({"_id": user_game_id}) or {}
                    if summary and summary.get("_id"):
                        quarter = summary.get("quarter", "N/A")
                        is_final = summary.get("is_final", False)
                        logger.info(f"🔍 [COMPLETE_WEEK] Second try found document: quarter={quarter}, is_final={is_final}")
                except Exception:
                    pass
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [COMPLETE_WEEK] Game not found with string format, trying ObjectId conversion")
                # Third try: Convert string to ObjectId
                try:
                    oid = ObjectId(user_game_id)
                    summary = db.games.find_one({"_id": oid}) or {}
                    if summary and summary.get("_id"):
                        gid = summary.get("_id")
                        quarter = summary.get("quarter", "N/A")
                        is_final = summary.get("is_final", False)
                        logger.info(f"✅ [COMPLETE_WEEK] Found game document using ObjectId conversion: {gid}, quarter={quarter}, is_final={is_final}")
                except Exception as e:
                    logger.error(f"❌ [COMPLETE_WEEK] Error converting game_id to ObjectId: {e}")
            
            logger.info(f"🔍 [COMPLETE_WEEK] User game - Final lookup result: Found={bool(summary and summary.get('_id'))}, _id={summary.get('_id') if summary else None}")
            if summary and summary.get("_id"):
                quarter = summary.get("quarter", "N/A")
                is_final = summary.get("is_final", False)
                logger.info(f"🔍 [COMPLETE_WEEK] Final document details: quarter={quarter}, is_final={is_final}, week={summary.get('week', 'N/A')}")
            
            if not summary or not summary.get("_id"):
                logger.error(f"❌ [COMPLETE_WEEK] Game document not found in games_collection after all attempts. game_id: {user_game_id}, gid: {gid}")
                logger.error(f"❌ [COMPLETE_WEEK] This likely means the game document was never saved to the database.")
                logger.error(f"❌ [COMPLETE_WEEK] Check if simulate_quarter_endpoint successfully saved the game document.")
                return  # Exit early if document not found
        
        # ✅ SS&S: Call finalize_game() directly (matches Tournament mode pattern)
        # Use game_id from summary or request
        if summary and summary.get("_id"):
            user_game_id_final = str(summary.get("_id"))
        else:
            user_game_id_final = user_game_id
        
        logger.info(f"🎯 [COMPLETE_WEEK] Finalizing user's game (matches Tournament pattern) - game_id: {user_game_id_final}")
        logger.info(f"🔍 [COMPLETE_WEEK] Document being passed to finalize_game: quarter={summary.get('quarter', 'N/A')}, is_final={summary.get('is_final', False)}")
        stat_updater.finalize_game(
            user_game_id_final,
            mode="franchise",
            franchise_id=req.franchise_id,
        )
        logger.info(f"✅ [COMPLETE_WEEK] User game - finalize_game completed for game_id: {user_game_id_final}")
    else:
        # Fallback: Try to find game by week + team IDs (legacy behavior)
        logger.warning(f"⚠️ [COMPLETE_WEEK] No game_id provided, attempting legacy lookup: week={req.week}, team1_id={team1_id}, team2_id={team2_id}, franchise_id={req.franchise_id}")
        user_game = db.games.find_one({
            "week": req.week,
            "$or": [
                {"team1_id": team1_id, "team2_id": team2_id},
                {"team1_id": team2_id, "team2_id": team1_id},
            ],
            "franchise_id": str(req.franchise_id)
        })
        if user_game:
            user_game_id = str(user_game.get("_id", ""))
            logger.info(f"✅ [COMPLETE_WEEK] Found user's game via legacy lookup: game_id={user_game_id}")
            if user_game_id:
                logger.info(f"🔍 [COMPLETE_WEEK] Calling finalize_game() for user's game: game_id={user_game_id}")
                stat_updater.finalize_game(
                    user_game_id, mode="franchise", franchise_id=req.franchise_id
                )
            else:
                logger.error(f"❌ [COMPLETE_WEEK] User game found but _id is empty: {user_game}")
        else:
            logger.error(f"❌ [COMPLETE_WEEK] User's game not found in games collection. Query: week={req.week}, team1_id={team1_id}, team2_id={team2_id}, franchise_id={req.franchise_id}")

    for away_id, home_id in week_games:
        if {str(away_id), str(home_id)} == {str(team1_id), str(team2_id)}:
            continue
        existing = db.games.find_one({
            "week": req.week,
            "$or": [
                {"team1_id": away_id, "team2_id": home_id},
                {"team1_id": home_id, "team2_id": away_id},
            ],
        })
        if existing:
            results.append({
                "away_id": str(existing["team1_id"]),
                "home_id": str(existing["team2_id"]),
                "away_score": existing["team1_score"],
                "home_score": existing["team2_score"],
            })
            continue

        away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
        home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")
        try:
            gm = run_simulation(home_name, away_name)
            away_score = gm.score.get(away_name, 0)
            home_score = gm.score.get(home_name, 0)
            summary = summarize_game_state(gm)
            # ✅ SS&S: Use ObjectId format for game_id (consistent with user games)
            from BackEnd.utils.game_id_utils import generate_game_id
            computer_game_id = generate_game_id()
            summary["_id"] = computer_game_id
            summary["franchise_id"] = str(req.franchise_id)
            summary["week"] = req.week
            db.games.update_one({"_id": computer_game_id}, {"$set": summary}, upsert=True)
            stat_updater.finalize_game(
                computer_game_id, mode="franchise", franchise_id=req.franchise_id
            )
            # ✅ SS&S: Pass computer_game_id to _save_game_result so schedule endpoint can find it
            sim_res = _save_game_result(away_id, home_id, away_score, home_score, req.week, franchise_id=req.franchise_id, game_id=computer_game_id)
        except Exception:
            away_score = random.randint(50, 90)
            home_score = random.randint(50, 90)
            sim_res = _save_game_result(away_id, home_id, away_score, home_score, req.week, franchise_id=req.franchise_id)
        results.append({
            "away_id": sim_res["team1_id"],
            "home_id": sim_res["team2_id"],
            "away_score": sim_res["team1_score"],
            "home_score": sim_res["team2_score"],
        })

    existing_results = franchise_doc.get("results", {})
    existing_results[str(req.week)] = results
    
    # Reset training status for next week
    next_week = req.week + 1
    
    # ✅ EOS TOURNAMENT: Initialize tournament after week 14 completion
    update_fields = {
        "results": existing_results,
        "week": next_week,
        "training_status.current_week": next_week,
        "training_status.training_completed": False,
        "training_status.session_type": "in-season"
    }
    
    if req.week == 14:
        # Week 14 complete - initialize EOS Tournament
        logger.info(f"🎯 [EOS TOURNAMENT] Week 14 complete, initializing tournament")
        tournament_state = initialize_eos_tournament(franchise_doc, db.teams)
        update_fields["eos_tournament"] = tournament_state
        update_fields["eos_tournament_active"] = True
        logger.info(f"✅ [EOS TOURNAMENT] Tournament initialized, week set to 15")
    elif req.week in [15, 16, 17]:
        # Tournament week - save game result and advance round if needed
        eos_tournament = franchise_doc.get("eos_tournament", {})
        if eos_tournament:
            current_round = eos_tournament.get("current_round", 1)
            bracket = eos_tournament.get("bracket", {})
            round_name = get_round_name(current_round)
            matchups = bracket.get(round_name, [])
            
            # Find which matchup this game belongs to
            matchup_index = None
            for i, matchup in enumerate(matchups):
                if (str(matchup.get("home_team")) == str(team1_id) and str(matchup.get("away_team")) == str(team2_id)) or \
                   (str(matchup.get("home_team")) == str(team2_id) and str(matchup.get("away_team")) == str(team1_id)):
                    matchup_index = i
                    break
            
            if matchup_index is not None and user_game_id:
                # Determine winner
                winner_id = team1_id if user.team1_score > user.team2_score else team2_id
                
                # Save tournament game result
                save_tournament_game_result(
                    franchise_doc,
                    current_round,
                    matchup_index,
                    user_game_id,
                    str(winner_id),
                    {"home": user.team1_score if str(team1_id) == str(matchup.get("home_team")) else user.team2_score,
                     "away": user.team2_score if str(team1_id) == str(matchup.get("home_team")) else user.team1_score}
                )
                
                # Reload franchise doc to get updated tournament state
                franchise_doc = db.franchises.find_one({"_id": franchise_id})
                eos_tournament = franchise_doc.get("eos_tournament", {})
                
                # Advance round if all matchups complete
                eos_tournament = advance_tournament_round(franchise_doc, db.teams)
                update_fields["eos_tournament"] = eos_tournament
                
                logger.info(f"✅ [EOS TOURNAMENT] Saved tournament game result for Round {current_round}, Matchup {matchup_index}")
    
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": update_fields},
    )

    id_to_name = {str(t["_id"]): t.get("name", "") for t in db.teams.find({}, {"name": 1})}
    scoreboard = []
    for r in results:
        scoreboard.append({
            "team1": id_to_name.get(r["away_id"], r["away_id"]),
            "team2": id_to_name.get(r["home_id"], r["home_id"]),
            "team1_score": r["away_score"],
            "team2_score": r["home_score"],
        })

    return {"week": req.week, "results": scoreboard}


@router.get("/franchise/command-center/data")
def command_center_data(franchise_id: str = None):
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/command-center/data START - franchise_id={franchise_id}")
    
    # Get user team info from franchise document (with backward compatibility)
    team_name = None
    team_id = None
    training_completed = False
    session_type = "in-season"
    
    if franchise_id:
        try:
            fid = ObjectId(franchise_id)
            db_query_start = time.time()
            # ✅ PERFORMANCE: Load once with projection (only needed fields) - reduces from 402KB to ~10KB (98% reduction)
            # Projection includes: franchise_teams, training_status, week, eos_tournament, user_team fields
            franchise_doc = db.franchises.find_one(
                {"_id": fid},
                {
                    "franchise_teams": 1,
                    "training_status": 1,
                    "week": 1,
                    "eos_tournament": 1,
                    "eos_tournament_active": 1,
                    "user_team_id": 1,
                    "user_team_object_id": 1,
                    "_id": 1
                }
            )
            db_query_time = time.time() - db_query_start
            logger.info(f"⏱️ [PERF] /franchise/command-center/data DB query: {db_query_time:.3f}s")
            if franchise_doc:
                # Get user team identifiers from franchise document
                team_name, team_id = get_user_team_from_franchise(franchise_doc)
                
                # Get training status
                training_status = franchise_doc.get("training_status", {})
                training_completed = training_status.get("training_completed", False)
                session_type = training_status.get("session_type", "in-season")
                
                # Get franchise-specific team stats if available
                if team_id:
                    franchise_teams = franchise_doc.get("franchise_teams", {})
                    # ✅ SS&S: Use EXACT same logic as /franchise/team-data endpoint (Team tab line 1483-1484)
                    # This ensures 100% consistency between top bar and Team tab displays
                    team_obj = franchise_teams.get(team_id, {})
                    
                    if team_obj and isinstance(team_obj, dict) and len(team_obj) > 0:
                        team_doc = team_obj.copy()  # Use franchise-specific stats
                    else:
                        # Fallback to universal team doc (but we'll override team_chemistry below)
                        team_doc = db.teams.find_one({"_id": ObjectId(team_id)}) or {}
                    
                    # ✅ SS&S: Get team_chemistry EXACTLY like Team tab does (lines 1494-1498 in get_franchise_team_data)
                    # Same logic: if key in team_obj, use it; otherwise default to 0
                    if team_obj and isinstance(team_obj, dict) and "team_chemistry" in team_obj:
                        team_doc["team_chemistry"] = team_obj["team_chemistry"]
                    else:
                        # Default to 0 if not present (same as Team tab line 1498)
                        team_doc["team_chemistry"] = 0
                else:
                    team_doc = {}
        except Exception:
            team_doc = {}
    else:
        # Fallback to state collection if no franchise_id (backward compatibility - deprecated)
        try:
            state = franchise_state_collection.find_one({"_id": "state"}) or {}
            team_name = state.get("team", "")
            if team_name:
                logger.warning(f"⚠️ [DEPRECATED] Using franchise_state fallback (no franchise_id provided). "
                             f"This is legacy behavior - new code should provide franchise_id.")
            team_doc = db.teams.find_one({"name": team_name}) or {}
            team_id = str(team_doc.get("_id", "")) if team_doc.get("_id") else None
        except Exception as e:
            logger.debug(f"franchise_state collection not available: {e}")
            team_doc = {}
            team_id = None
    
    # Get username and seed from state (backward compatibility)
    # Fallback to state collection (backward compatibility - deprecated)
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        if state.get("team"):
            logger.warning(f"⚠️ [DEPRECATED] Using franchise_state fallback in command_center(). "
                         f"This is legacy behavior - should use franchise document.")
    except Exception as e:
        logger.debug(f"franchise_state collection not available: {e}")
        state = {}
    
    # ✅ EOS TOURNAMENT: Include tournament data if active
    # ✅ PERFORMANCE: Reuse franchise_doc from above (already loaded with projection)
    eos_tournament = None
    eos_tournament_active = False
    week = None
    if franchise_id and franchise_doc:
        try:
            eos_tournament = franchise_doc.get("eos_tournament")
            eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
            week = franchise_doc.get("week", 1)
        except Exception:
            pass
    
    response = {
        "team": team_name,
        "team_id": team_id,  # ✅ SS&S: Include ObjectId for consistent navigation
        "username": state.get("username", "Coach"),
        "seed": state.get("seed", 1),
        "team_chemistry": team_doc.get("team_chemistry", 0),
        "offense": team_doc.get("offense", "-"),
        "defense": team_doc.get("defense", "-"),
        "athleticism": team_doc.get("athleticism", "-"),
        "intangibles": team_doc.get("intangibles", "-"),
        "prestige": team_doc.get("prestige", "-"),
        "rank": team_doc.get("rank", "-"),
        "training_completed": training_completed,
        "session_type": session_type,
        "week": week if week is not None else 1,  # ✅ Always include week (defaults to 1)
        "training_status": {
            "current_week": franchise_doc.get("training_status", {}).get("current_week", week if week is not None else 1),
            "training_completed": training_completed,
            "session_type": session_type
        } if franchise_id and franchise_doc else {}
    }
    
    # Add tournament data if active
    if eos_tournament_active and eos_tournament:
        response["eos_tournament"] = eos_tournament
        response["eos_tournament_active"] = True
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/command-center/data COMPLETE: {total_time:.3f}s")
    return response


@router.get("/franchise/standings")
def standings(franchise_id: str):
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/standings START - franchise_id={franchise_id}")
    
    # ✅ PERFORMANCE: Only fetch needed fields (reduces from 402KB to ~20KB, 95% reduction)
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one(
        {"_id": ObjectId(franchise_id)},
        {"schedule": 1, "week": 1, "eos_tournament": 1, "eos_tournament_active": 1, "results": 1, "_id": 1}
    )
    db_query_time = time.time() - db_query_start
    logger.info(f"⏱️ [PERF] /franchise/standings DB query: {db_query_time:.3f}s")
    
    found = franchise_doc is not None
    logger.info("standings franchise_id=%s found=%s", franchise_id, found)
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    schedule = franchise_doc.get("schedule", [])
    week = franchise_doc.get("week", 1)
    id_to_name = {t["_id"]: t["name"] for t in db.teams.find({}, {"name": 1})}

    matchup_map = {}
    
    # ✅ EOS TOURNAMENT: Check if tournament is active (weeks 15-17)
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    eos_tournament = franchise_doc.get("eos_tournament", {})
    
    if eos_tournament_active and eos_tournament and week >= 15:
        # ✅ SS&S: Reuse Tournament mode's bracket lookup pattern
        current_round = eos_tournament.get("current_round", 1)
        round_name = get_round_name(current_round)
        bracket = eos_tournament.get("bracket", {})
        matchups = bracket.get(round_name, [])
        
        # Build matchup_map from tournament bracket
        for matchup_data in matchups:
            home_id_str = matchup_data.get("home_team")
            away_id_str = matchup_data.get("away_team")
            
            if home_id_str and away_id_str:
                try:
                    home_id = ObjectId(home_id_str)
                    away_id = ObjectId(away_id_str)
                    home_name = id_to_name.get(home_id, "")
                    away_name = id_to_name.get(away_id, "")
                    
                    matchup_map[str(away_id)] = f"at {home_name}"
                    matchup_map[str(home_id)] = f"vs {away_name}"
                except Exception:
                    # Skip invalid ObjectIds
                    continue
    else:
        # Regular season (weeks 1-14)
        next_games = schedule[week - 1] if week - 1 < len(schedule) else []
        for away_id, home_id in next_games:
            home_name = id_to_name.get(home_id, "")
            away_name = id_to_name.get(away_id, "")
            matchup_map[away_id] = f"at {home_name}"
            matchup_map[home_id] = f"vs {away_name}"

    teams = list(db.teams.find({}, {"name": 1, "record": 1, "PF": 1, "PA": 1}))

    output = []
    for t in teams:
        rec = t.get("record", {"W": 0, "L": 0})
        wins = rec.get("W", 0)
        losses = rec.get("L", 0)
        games_played = wins + losses
        pct = round(wins / games_played, 3) if games_played else 0.0
        pf = t.get("PF", 0)
        pa = t.get("PA", 0)
        differential = pf - pa
        output.append({
            "team_id": str(t["_id"]),
            "name": t.get("name", ""),
            "W": wins,
            "L": losses,
            "pct": pct,
            "PF": pf,
            "PA": pa,
            "differential": differential,
            "next": matchup_map.get(str(t["_id"]), "")
        })

    output.sort(key=lambda x: (x["W"], x["differential"]), reverse=True)
    logger.info("standings returning franchise_id=%s found=%s", franchise_id, found)
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/standings COMPLETE: {total_time:.3f}s")
    return {"standings": output}


@router.get("/franchise/schedule")
def season_schedule(franchise_id: str):
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/schedule START - franchise_id={franchise_id}")
    
    # ✅ PERFORMANCE: Only fetch needed fields (reduces from 402KB to ~30KB, 92% reduction)
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one(
        {"_id": ObjectId(franchise_id)},
        {
            "schedule": 1,
            "results": 1,
            "franchise_teams": 1,
            "eos_tournament": 1,
            "eos_tournament_active": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
            "_id": 1
        }
    )
    db_query_time = time.time() - db_query_start
    logger.info(f"⏱️ [PERF] /franchise/schedule DB query: {db_query_time:.3f}s")
    
    found = franchise_doc is not None
    logger.info("season_schedule franchise_id=%s found=%s", franchise_id, found)
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    schedule = franchise_doc.get("schedule", [])

    # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id or not user_team_object_id:
        # Fallback: try to resolve from team name if user_team_object_id is missing
        team_name = user_team_id
        if team_name:
            team_doc = db.teams.find_one({"name": team_name})
            if team_doc:
                team_id = str(team_doc["_id"])
            else:
                team_id = None
        else:
            team_id = None
    else:
        # Use franchise document's user_team_object_id directly (authoritative)
        team_id = user_team_object_id
        team_name = user_team_id
    
    # Get training reports for user's team
    franchise_teams = franchise_doc.get("franchise_teams", {})
    training_reports = {}
    if team_id:
        team_data = franchise_teams.get(team_id, {})
        training_reports = team_data.get("training_reports", {})

    weeks = []
    results_by_week = franchise_doc.get("results", {})
    for idx, games in enumerate(schedule, start=1):
        week_games = []
        week_results = {
            (r["away_id"], r["home_id"]): (r["away_score"], r["home_score"])
            for r in results_by_week.get(str(idx), [])
        }
        for away_id, home_id in games:
            res = week_results.get((str(away_id), str(home_id))) or \
                  week_results.get((str(home_id), str(away_id)))
            game_doc = None  # ✅ SS&S: Initialize game_doc before conditional
            if res:
                away_score, home_score = res
                status = "complete"
                # ✅ SS&S: Try to find game_doc even when status comes from results
                game_doc = db.games.find_one({"week": idx, "team1_id": away_id, "team2_id": home_id}) or \
                           db.games.find_one({"week": idx, "team1_id": home_id, "team2_id": away_id})
            else:
                game_doc = db.games.find_one({"week": idx, "team1_id": away_id, "team2_id": home_id}) or \
                           db.games.find_one({"week": idx, "team1_id": home_id, "team2_id": away_id})
                if game_doc:
                    status = "complete"
                    if game_doc["team1_id"] == away_id:
                        away_score = game_doc.get("team1_score")
                        home_score = game_doc.get("team2_score")
                    else:
                        away_score = game_doc.get("team2_score")
                        home_score = game_doc.get("team1_score")
                else:
                    status = "scheduled"
                    away_score = None
                    home_score = None
            
            # Check if this is the user's team's game and if training report exists
            has_training_report = False
            if team_id and (str(away_id) == team_id or str(home_id) == team_id):
                has_training_report = str(idx) in training_reports
            
            # ✅ SS&S: Include game_id for completed games (needed for box score links)
            game_id = None
            if status == "complete" and game_doc:
                game_id = str(game_doc.get("_id", ""))
            
            week_games.append({
                "week": idx,
                "away_team_id": str(away_id),
                "home_team_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": str(away_id) == team_id or str(home_id) == team_id,
                "game_id": game_id  # ✅ SS&S: Include game_id for box score links
            })
        weeks.append(week_games)

    # ✅ EOS TOURNAMENT: Add tournament games (weeks 15-17) if tournament is active
    eos_tournament = franchise_doc.get("eos_tournament")
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    
    if eos_tournament_active and eos_tournament:
        bracket = eos_tournament.get("bracket", {})
        seeds = eos_tournament.get("seeds", {})
        
        # Week 15: Round 1 (Quarterfinals)
        round1 = bracket.get("round1", [])
        week15_games = []
        for matchup in round1:
            game_doc = None
            if matchup.get("game_id"):
                game_doc = db.games.find_one({"_id": ObjectId(matchup["game_id"])})
            
            score = matchup.get("score", {})
            away_score = score.get("away")
            home_score = score.get("home")
            status = "complete" if matchup.get("winner") else "scheduled"
            
            has_training_report = False
            if team_id and (str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id):
                # Check if training report exists for week 15
                has_training_report = "15" in training_reports
            
            week15_games.append({
                "week": 15,
                "away_team_id": str(matchup["away_team"]),
                "home_team_id": str(matchup["home_team"]),
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id,
                "game_id": matchup.get("game_id"),
                "is_tournament": True,
                "round": "Quarterfinals"
            })
        weeks.append(week15_games)
        
        # Week 16: Round 2 (Semifinals)
        round2 = bracket.get("round2", [])
        week16_games = []
        for matchup in round2:
            game_doc = None
            if matchup.get("game_id"):
                game_doc = db.games.find_one({"_id": ObjectId(matchup["game_id"])})
            
            score = matchup.get("score", {})
            away_score = score.get("away")
            home_score = score.get("home")
            status = "complete" if matchup.get("winner") else "scheduled"
            
            has_training_report = False
            if team_id and (str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id):
                has_training_report = "16" in training_reports
            
            week16_games.append({
                "week": 16,
                "away_team_id": str(matchup["away_team"]),
                "home_team_id": str(matchup["home_team"]),
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id,
                "game_id": matchup.get("game_id"),
                "is_tournament": True,
                "round": "Semifinals"
            })
        weeks.append(week16_games)
        
        # Week 17: Final (Championship)
        final = bracket.get("final", [])
        week17_games = []
        if final and len(final) > 0:
            matchup = final[0]
            game_doc = None
            if matchup.get("game_id"):
                game_doc = db.games.find_one({"_id": ObjectId(matchup["game_id"])})
            
            score = matchup.get("score", {})
            away_score = score.get("away")
            home_score = score.get("home")
            status = "complete" if matchup.get("winner") else "scheduled"
            
            has_training_report = False
            if team_id and (str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id):
                has_training_report = "17" in training_reports
            
            week17_games.append({
                "week": 17,
                "away_team_id": str(matchup["away_team"]),
                "home_team_id": str(matchup["home_team"]),
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": str(matchup["away_team"]) == team_id or str(matchup["home_team"]) == team_id,
                "game_id": matchup.get("game_id"),
                "is_tournament": True,
                "round": "Championship"
            })
        weeks.append(week17_games)
    
    logger.info("season_schedule returning franchise_id=%s found=%s", franchise_id, found)
    return {"schedule": weeks, "team_id": team_id}


def get_leaders(
    franchise_id: str,
    scope: str = "season",
    stat: str = "PTS",
    limit: int = 10,
):
    """Return the top players for a given stat within a franchise.

    Players are sourced from the franchise document to avoid cross-collection
    joins. For small rosters the sorting is performed in-memory. When the
    number of players grows large an aggregation pipeline is used so MongoDB
    can leverage indexes on the ``players`` subdocument.
    """
    import time
    start_time = time.time()

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    # ✅ PERFORMANCE: Skip initial find_one for franchise mode - go straight to aggregation
    # Franchise mode always has 96 players (12 per team × 8 teams), so we don't need to count first
    # Aggregation pipeline is faster because MongoDB sorts internally and only projects needed fields
    # This eliminates the wasteful ~1.5s load of the entire players object (300KB+) just to count
    
    # ✅ SS&S: Read stats directly from players.{pid}.season.{stat} (no totals wrapper)
    # ✅ FIX: Map TPM to 3PTM for aggregation pipeline
    stat_field = stat
    if stat == "TPM":
        stat_field = "3PTM"
    elif stat == "TPA":
        stat_field = "3PTA"
    
    # ✅ PERFORMANCE: Use MongoDB aggregation pipeline for large datasets
    aggregation_start = time.time()
    pipeline = [
        {"$match": {"_id": fid}},
        {"$project": {"players": {"$objectToArray": "$players"}}},
        {"$unwind": "$players"},
        {
            "$project": {
                "player_id": "$players.k",
                "meta": "$players.v.meta",
                "value": f"$players.v.{scope}.{stat_field}",  # Direct stat access, no totals wrapper
            }
        },
        {"$sort": {"value": -1}},
        {"$limit": limit},
    ]

    agg = list(db.franchises.aggregate(pipeline))
    aggregation_time = time.time() - aggregation_start
    logger.info(f"⏱️ [PERF] get_leaders('{stat}') Aggregation pipeline: {aggregation_time:.3f}s")
    results: list[dict[str, Any]] = []
    for p in agg:
        meta = p.get("meta", {})
        results.append(
            {
                "player_id": p.get("player_id"),
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "team": meta.get("team", meta.get("team_id", "")),
                "value": p.get("value", 0),
            }
        )
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] get_leaders('{stat}') COMPLETE (aggregation): {total_time:.3f}s")
    return results


@router.get("/franchise/leaders")
def leaders(
    franchise_id: str,
    scope: str = "season",
    limit: int = 10,
):
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/leaders START - franchise_id={franchise_id}, scope={scope}")
    
    categories = ["PTS", "AST", "TPM", "REB", "BLK", "STL"]
    result: dict[str, list[dict[str, Any]]] = {}
    for cat in categories:
        cat_start = time.time()
        top = get_leaders(franchise_id, scope=scope, stat=cat, limit=limit)
        cat_time = time.time() - cat_start
        logger.info(f"⏱️ [PERF] /franchise/leaders get_leaders('{cat}'): {cat_time:.3f}s")
        result[cat] = [
            {
                "player_id": p.get("player_id"),
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "team": p.get("team"),
                "value": p.get("value", 0),
            }
            for p in top
        ]
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/leaders COMPLETE: {total_time:.3f}s")
    return result


@router.get("/franchise/team-stats")
def team_stats(franchise_id: str):
    """Get team stats by aggregating player stats from franchise document.
    
    ✅ SS&S: Aggregates from franchise.players object (franchise-specific stats),
    not from universal players_collection.
    """
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/team-stats START - franchise_id={franchise_id}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id")
    
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": fid}, {"players": 1, "franchise_teams": 1})
    db_query_time = time.time() - db_query_start
    logger.info(f"⏱️ [PERF] /franchise/team-stats DB query: {db_query_time:.3f}s")
    
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    players = franchise_doc.get("players", {})
    franchise_teams = franchise_doc.get("franchise_teams", {})
    
    logger.info(f"⏱️ [PERF] /franchise/team-stats Found {len(players)} players, {len(franchise_teams)} teams")
    
    # ✅ SS&S: Use shared aggregator utility
    aggregation_start = time.time()
    output = aggregate_team_stats_from_players(
        players=players,
        team_ids=franchise_teams,
        teams_collection=db.teams,
        collection_type='franchise',
        logger=logger
    )
    aggregation_time = time.time() - aggregation_start
    logger.info(f"⏱️ [PERF] /franchise/team-stats Aggregation: {aggregation_time:.3f}s")
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/team-stats COMPLETE: {total_time:.3f}s")
    return {"teams": output}


def get_team_player_stats(
    franchise_id: str,
    team_id: str,
    scope: str = "season",
    *,
    sort: str | None = "PTS",
    direction: str = "desc",
    page: int = 1,
    limit: int | None = None,
):
    """Return players for ``team_id`` within ``franchise_id``.

    Filters franchise ``players`` by ``meta.team_id`` and returns the requested
    stat block (``season`` by default).  Results may be sorted and paginated for
    UI consumption.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    doc = db.franchises.find_one({"_id": fid}, {"players": 1}) or {}
    players = doc.get("players", {})
    team_id_str = str(team_id)
    results: list[dict] = []
    for pid, pdata in players.items():
        meta = pdata.get("meta", {})
        if str(meta.get("team_id")) != team_id_str:
            continue
        block = pdata.get(scope, {})
        results.append(
            {
                "player_id": pid,
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "stats": block,
            }
        )

    if sort:
        reverse = direction.lower() != "asc"
        results.sort(key=lambda x: x["stats"].get(sort, 0), reverse=reverse)

    if limit:
        start = max(page - 1, 0) * limit
        results = results[start : start + limit]

    return results


@router.get("/franchise/team-player-stats/{team_id}")
def team_player_stats_endpoint(
    team_id: str,
    franchise_id: str,
    scope: str = "season",
    page: int = 1,
    limit: int | None = None,
    sort: str | None = "PTS",
    direction: str = "desc",
):
    tid = _normalize_team_id(team_id)
    players = get_team_player_stats(
        franchise_id,
        str(tid),
        scope,
        sort=sort,
        direction=direction,
        page=page,
        limit=limit,
    )
    return {"players": players}


@router.get("/franchise/team-player-stats")
def user_team_player_stats_endpoint(
    franchise_id: str,
    scope: str = "season",
    page: int = 1,
    limit: int | None = None,
    sort: str | None = "PTS",
    direction: str = "desc",
):
    # Get user team info from franchise document (with backward compatibility)
    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    team_name = user_team_id
    if not team_name:
        raise HTTPException(status_code=404, detail="User team not selected")
    team_doc = db.teams.find_one({"name": team_name}, {"_id": 1})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    players = get_team_player_stats(
        franchise_id,
        str(team_doc["_id"]),
        scope,
        sort=sort,
        direction=direction,
        page=page,
        limit=limit,
    )
    return {"players": players}


@router.get("/franchise/recruits")
def recruits(franchise_id: str = Query(...)):
    """Get recruits for a specific franchise."""
    import time
    from bson import ObjectId
    
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/recruits START - franchise_id={franchise_id}")
    
    # ✅ PERFORMANCE: Get recruits from franchise document with projection (only recruits field)
    db_query_start = time.time()
    franchise = db.franchises.find_one(
        {"_id": ObjectId(franchise_id)}, 
        {"recruits": 1, "_id": 1}
    )
    db_query_time = time.time() - db_query_start
    logger.info(f"⏱️ [PERF] /franchise/recruits DB query: {db_query_time:.3f}s")
    
    if not franchise:
        total_time = time.time() - start_time
        logger.info(f"⏱️ [PERF] /franchise/recruits COMPLETE: {total_time:.3f}s (no franchise)")
        return {"recruits": []}
    
    recs = franchise.get("recruits", [])
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/recruits COMPLETE: {total_time:.3f}s ({len(recs)} recruits)")
    return {"recruits": recs}


@router.get("/franchise/debug-names")
def debug_names():
    """Debug endpoint to check if franchise names are loading correctly."""
    from BackEnd.models.franchise_manager import RecruitManager
    rm = RecruitManager(db)
    return {
        "first_names_count": len(rm.first_names),
        "last_names_count": len(rm.last_names),
        "sample_first_names": rm.first_names[:10],
        "sample_last_names": rm.last_names[:10],
        "using_fallback": len(rm.first_names) == 5 and len(rm.last_names) == 5
    }


@router.get("/franchise/latest-training")
def get_latest_training(franchise_id: str):
    """
    Get the latest training session results for display on Training tab.
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    franchise_doc = db.franchises.find_one({"_id": fid}, {"latest_training": 1})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    latest_training = franchise_doc.get("latest_training", {})
    return latest_training if latest_training else {
        "player_logs": {},
        "team_log": {},
        "session_type": "in-season",
        "week": 0
    }


@router.get("/franchise/state")
def get_franchise_state(franchise_id: str):
    """
    Get the full franchise document (for loading team data in Command Center).
    
    ✅ PERFORMANCE: Only returns players object (used for merging stats into roster).
    This reduces data transfer from ~402KB to ~300KB (25% reduction).
    """
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/state START - franchise_id={franchise_id}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # ✅ PERFORMANCE: Only fetch players object (frontend only uses franchiseDoc.players)
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": fid}, {"players": 1, "_id": 1})
    db_query_time = time.time() - db_query_start
    logger.info(f"⏱️ [PERF] /franchise/state DB query: {db_query_time:.3f}s")
    
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    players_count = len(franchise_doc.get("players", {}))
    logger.info(f"⏱️ [PERF] /franchise/state Loaded {players_count} players")
    
    # Convert ObjectId to string for JSON serialization
    franchise_doc["_id"] = str(franchise_doc["_id"])
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/state COMPLETE: {total_time:.3f}s")
    return jsonable_encoder(franchise_doc, custom_encoder={ObjectId: str})


@router.get("/franchise/team-data")
def get_franchise_team_data(franchise_id: str, team_id: str = None, team_name: str = None):
    """
    Get team data (attributes, plays, scouting_data) from franchise_teams.
    
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    
    ✅ PERFORMANCE: Only fetches franchise_teams field (reduces from 402KB to ~15KB, 96% reduction).
    """
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/team-data START - franchise_id={franchise_id}, team_id={team_id}, team_name={team_name}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    franchise_doc = None
    
    # ✅ SS&S: Prefer team_id (ObjectId) if provided
    if team_id:
        try:
            # Validate it's a valid ObjectId
            ObjectId(team_id)
            actual_team_id = team_id
        except Exception:
            # If not a valid ObjectId, try to resolve as team name
            team_doc = db.teams.find_one({"name": team_id})
            if not team_doc:
                raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
            actual_team_id = str(team_doc["_id"])
    elif team_name:
        # Fallback to team_name resolution for backward compatibility
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    else:
        # Get team name from franchise document if not provided (with backward compatibility)
        # ✅ PERFORMANCE: Load once with projection (only needed fields)
        franchise_doc = db.franchises.find_one(
            {"_id": ObjectId(franchise_id)},
            {"franchise_teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
        )
        if not franchise_doc:
            raise HTTPException(status_code=404, detail="Franchise not found")
        
        user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        team_name = user_team_id
        if not team_name:
            raise HTTPException(status_code=404, detail="Team not found")
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    
    # ✅ PERFORMANCE: Load franchise_doc with projection if not already loaded
    if not franchise_doc:
        franchise_doc = db.franchises.find_one(
            {"_id": fid},
            {"franchise_teams": 1, "_id": 1}
        )
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get team object from franchise_teams
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_obj = franchise_teams.get(actual_team_id, {})
    
    if not team_obj:
        raise HTTPException(status_code=404, detail=f"Team data not found in franchise for team_id: {actual_team_id}")
    
    # Extract team attributes
    team_attributes = {}
    attr_keys = ['shot_threshold', 'discipline', 'fight', 'rebound_modifier', 
                 'momentum_score', 'offensive_efficiency', 'team_chemistry', 'defensive_efficiency',
                 'fb_efficiency', 'pt_efficiency', 'fb_opp_modifier', 'pt_opp_modifier']
    for key in attr_keys:
        if key in team_obj:
            team_attributes[key] = team_obj[key]
        else:
            team_attributes[key] = 0  # Default to 0 if not present
    
    # Get plays data
    plays_data = team_obj.get("plays", {})
    
    # 🔍 DEBUG: Log plays with season_stats
    plays_with_season_stats = {name: play for name, play in plays_data.items() if play.get("season_stats", {}).get("times_run", 0) > 0}
    if plays_with_season_stats:
        logger.warning(f"🔍 [TEAM_DATA API] Team {actual_team_id} has {len(plays_with_season_stats)} plays with season_stats: {list(plays_with_season_stats.keys())}")
        for play_name, play_data in list(plays_with_season_stats.items())[:3]:  # Log first 3
            season_stats = play_data.get("season_stats", {})
            logger.warning(f"🔍 [TEAM_DATA API] Play '{play_name}': times_run={season_stats.get('times_run', 0)}, successes={season_stats.get('successes', 0)}, player_points={len(season_stats.get('player_points', {}))} players")
    else:
        logger.warning(f"⚠️ [TEAM_DATA API] Team {actual_team_id} has {len(plays_data)} plays but NONE have season_stats with times_run > 0")
        # Log sample play structure to see what we have
        if plays_data:
            sample_play_name = list(plays_data.keys())[0]
            sample_play = plays_data[sample_play_name]
            logger.warning(f"🔍 [TEAM_DATA API] Sample play '{sample_play_name}' keys: {list(sample_play.keys())}")
            if "season_stats" in sample_play:
                logger.warning(f"🔍 [TEAM_DATA API] Sample play '{sample_play_name}' season_stats keys: {list(sample_play['season_stats'].keys())}")
            else:
                logger.warning(f"⚠️ [TEAM_DATA API] Sample play '{sample_play_name}' has NO season_stats key!")
    
    # Get scouting data - initialize defense structure if missing
    scouting_data = team_obj.get("scouting_data", {})
    if not scouting_data.get("defense"):
        scouting_data["defense"] = {
            "Man": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "2-3 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "3-2 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "1-3-1 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0}
        }
    else:
        # Ensure each defense has effectiveness value
        defenses = ["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        for def_name in defenses:
            if def_name not in scouting_data["defense"]:
                scouting_data["defense"][def_name] = {"effectiveness": 0, "momentum": 0, "cloaking": 0}
            elif "effectiveness" not in scouting_data["defense"][def_name]:
                scouting_data["defense"][def_name]["effectiveness"] = 0
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/team-data COMPLETE: {total_time:.3f}s")
    return {
        "team_attributes": team_attributes,
        "plays_data": plays_data,
        "scouting_data": scouting_data
    }


@router.get("/franchise/roster")
def get_franchise_roster(franchise_id: str, team_name: str = None):
    """
    Get roster with franchise-specific player attributes.
    """
    import time
    start_time = time.time()
    logger.info(f"⏱️ [PERF] /franchise/roster START - franchise_id={franchise_id}, team_name={team_name}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # ✅ PERFORMANCE: Get team name from franchise document with projection (only user_team fields)
    if not team_name:
        db_query_start = time.time()
        franchise_doc = db.franchises.find_one(
            {"_id": fid},
            {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
        )
        db_query_time = time.time() - db_query_start
        logger.info(f"⏱️ [PERF] /franchise/roster DB query 1 (get team name): {db_query_time:.3f}s")
        if franchise_doc:
            user_team_id, _ = get_user_team_from_franchise(franchise_doc)
            team_name = user_team_id
    
    if not team_name:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team document
    team_query_start = time.time()
    team_doc = db.teams.find_one({"name": team_name})
    team_query_time = time.time() - team_query_start
    logger.info(f"⏱️ [PERF] /franchise/roster DB query (team doc): {team_query_time:.3f}s")
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # ✅ PERFORMANCE: Get franchise document with projection (only players field)
    franchise_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": fid}, {"players": 1, "_id": 1})
    franchise_query_time = time.time() - franchise_query_start
    logger.info(f"⏱️ [PERF] /franchise/roster DB query 2 (franchise players): {franchise_query_time:.3f}s")
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    franchise_players = franchise_doc.get("players", {})
    team_player_ids = team_doc.get("player_ids", [])
    
    # Build player list with franchise-specific attributes
    processing_start = time.time()
    players = []
    for pid in team_player_ids:
        pid_str = str(pid)
        franchise_player_data = franchise_players.get(pid_str, {})
        if not franchise_player_data:
            continue
        
        meta = franchise_player_data.get("meta", {})
        attributes = franchise_player_data.get("attributes", {})
        
        # Get franchise-specific position ratings (if available), otherwise use core ratings
        position_ratings = franchise_player_data.get("position_ratings", {})
        
        # Get additional data from core collection
        core_player = db.players.find_one({"_id": pid}, {
            "position_ratings": 1, "height": 1, "weight": 1, "jersey": 1, "year": 1, "attributes": 1
        })
        
        # Use franchise position ratings if available, otherwise fall back to core
        if not position_ratings and core_player:
            position_ratings = core_player.get("position_ratings", {})
        
        # Merge core attributes with franchise attributes (franchise overrides core)
        core_attributes = core_player.get("attributes", {}) if core_player else {}
        merged_attributes = {**core_attributes, **attributes}
        
        # Create anchor_ prefixed attributes (like Player class does)
        for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
            if attr_key in merged_attributes:
                merged_attributes[f"anchor_{attr_key}"] = merged_attributes[attr_key]
        
        first = meta.get("first_name", "")
        last = meta.get("last_name", "")
        
        player = {
            "_id": pid_str,  # Add _id for lineup tracking
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),  # Add combined name for display
            "team": team_name,
            "attributes": merged_attributes,
            "position_ratings": position_ratings,
            "height": core_player.get("height") if core_player else None,
            "weight": core_player.get("weight") if core_player else None,
            "jersey": core_player.get("jersey") if core_player else None,
            "year": core_player.get("year") if core_player else None
        }
        players.append(player)
    
    processing_time = time.time() - processing_start
    logger.info(f"⏱️ [PERF] /franchise/roster Processing ({len(players)} players): {processing_time:.3f}s")
    
    total_time = time.time() - start_time
    logger.info(f"⏱️ [PERF] /franchise/roster COMPLETE: {total_time:.3f}s")
    return {"players": players}


@router.get("/franchise/scouting-report")
def get_scouting_report(franchise_id: str, team_name: str):
    """
    Get scouting report for a team, including last game's play usage data.
    
    Returns:
    - team_attributes: Team attribute values
    - plays: Array of plays with game_stats from last completed game
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # Get franchise document
    franchise_doc = db.franchises.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get team document to resolve ObjectId
    team_doc = db.teams.find_one({"name": team_name})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_object_id = str(team_doc["_id"])
    
    # Get team_id field for querying games (e.g., "XAVIEN")
    team_id_field = team_doc.get("team_id")
    
    # Get team attributes from franchise document
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_obj = franchise_teams.get(team_object_id, {})
    team_attributes = team_obj.get("attributes", {})
    
    # Find last completed game for this team
    # Match against home_team_id and away_team_id (which are team_id strings like "XAVIEN")
    last_game = db.games.find_one(
        {
            "franchise_id": str(franchise_id),
            "$or": [
                {"home_team_id": team_id_field},
                {"away_team_id": team_id_field}
            ]
        },
        sort=[("_id", -1)]  # Most recent first
    )
    
    plays_data = []
    
    if last_game:
        # Extract play usage from game document
        teams_obj = last_game.get("teams", {})
        
        # Game documents use team_id strings (like "LITTLE_YORK") as keys, not ObjectIds
        # We need to find the team key by matching team name or team_id
        team_key = None
        
        # Try multiple matching strategies
        for key in teams_obj.keys():
            # Strategy 1: Match by team_id field (e.g., "LITTLE_YORK")
            if team_id_field and key == team_id_field:
                team_key = key
                break
            # Strategy 2: Match by team name
            if key == team_name:
                team_key = key
                break
            # Strategy 3: Try to match by ObjectId (if key is an ObjectId string)
            try:
                if len(key) == 24:  # ObjectId string length
                    key_obj_id = ObjectId(key)
                    if key_obj_id == ObjectId(team_object_id):
                        team_key = key
                        break
                    # Also check if this ObjectId matches our team
                    key_team_doc = db.teams.find_one({"_id": key_obj_id})
                    if key_team_doc and key_team_doc.get("name") == team_name:
                        team_key = key
                        break
            except Exception:
                pass
        
        if team_key:
            team_plays = teams_obj.get(team_key, {}).get("plays", {})
            
            # Calculate total playcalls for usage %
            total_playcalls = 0
            for play_name, play_data in team_plays.items():
                game_stats = play_data.get("game_stats", {})
                times_run = game_stats.get("times_run", 0)
                total_playcalls += times_run
            
            # Build plays array
            for play_name, play_data in team_plays.items():
                game_stats = play_data.get("game_stats", {})
                times_run = game_stats.get("times_run", 0)
                successes = game_stats.get("successes", 0)
                
                if times_run > 0:  # Only include plays that were actually run
                    plays_data.append({
                        "name": play_name,
                        "times_run": times_run,
                        "successes": successes,
                        "total_playcalls": total_playcalls
                    })
    
    return {
        "team_attributes": team_attributes,
        "plays": plays_data
    }


class FranchiseTrainingRequest(BaseModel):
    franchise_id: str
    team_id: Optional[str] = None
    training_data: dict  # Contains player_drills, team_drills, general, coaching_focus


@router.get("/franchise/training-points")
def get_training_points(franchise_id: str):
    """
    Get the number of training points available for a franchise.
    Returns 30 for first training (before first game), 24 otherwise.
    """
    try:
        franchise_id_obj = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id_obj})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    # Check if there are any completed games
    results = franchise_doc.get("results", {})
    has_completed_games = len(results) > 0
    
    # Also check games collection for any completed games
    if not has_completed_games:
        completed_game = db.games.find_one({
            "franchise_id": str(franchise_id),
            "is_final": True
        })
        has_completed_games = completed_game is not None
    
    # First training (before first game) gets 30 points, otherwise 24
    training_points = 30 if not has_completed_games else 24
    
    return {
        "training_points": training_points,
        "is_first_training": not has_completed_games
    }


@router.post("/franchise/run-training")
def run_franchise_training(req: FranchiseTrainingRequest):
    """
    Run training for a franchise team using franchise-specific player/team attributes.
    Updates only the franchise document, not the core collections.
    """
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID format")

    # Load franchise document
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    # Get training status and check for duplicate submission
    training_status = franchise_doc.get("training_status", {})
    current_week = franchise_doc.get("week", 0)
    
    # Check if it's first training (before first game) - validate training points
    results = franchise_doc.get("results", {})
    has_completed_games = len(results) > 0
    if not has_completed_games:
        completed_game = db.games.find_one({
            "franchise_id": str(franchise_id),
            "is_final": True
        })
        has_completed_games = completed_game is not None
    
    expected_points = 30 if not has_completed_games else 24
    
    # Validate total training points allocated
    training_data = req.training_data
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    
    # Calculate total points allocated
    total_allocated = 0
    for category in allocations.values():
        if isinstance(category, dict):
            for value in category.values():
                if isinstance(value, dict):
                    total_allocated += sum(value.values())
                elif isinstance(value, (int, float)):
                    total_allocated += value
    
    if total_allocated != expected_points:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid training points allocation. Expected {expected_points} points, got {total_allocated}."
        )
    if training_status.get("training_completed", False) and training_status.get("week") == current_week:
        # Training already completed for this week, redirect to report
        # ✅ SS&S: Use user_team_object_id from franchise document for redirect (authoritative)
        user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        redirect_team_id = user_team_object_id if user_team_object_id else req.team_id
        return {
            "status": "already_completed",
            "week": current_week,
            "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={redirect_team_id}&week={current_week}"
        }

    # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
    # This ensures we're always using the correct team, even if URL params are wrong
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise document")
    
    # Use franchise document's user_team_object_id as authoritative team_id
    team_id = user_team_object_id
    team_name = user_team_id
    
    # Verify team exists in teams collection
    team_doc = db.teams.find_one({"_id": ObjectId(team_id)})
    if not team_doc:
        raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
    
    # Log if req.team_id was provided but doesn't match (for debugging)
    if req.team_id and req.team_id != team_id:
        logger.warning(f"⚠️ [TRAINING] Request team_id ({req.team_id}) doesn't match franchise document user_team_object_id ({team_id}). Using franchise document value.")

    # Get franchise-specific player data for the user's team
    franchise_players = franchise_doc.get("players", {})
    
    # Get player_ids from team_doc if available, otherwise try to get from franchise_teams
    if team_doc:
        team_player_ids = team_doc.get("player_ids", [])
    else:
        # Fallback: try to get player_ids from franchise_teams structure
        franchise_teams = franchise_doc.get("franchise_teams", {})
        team_data = franchise_teams.get(team_id, {})
        team_player_ids = team_data.get("player_ids", [])
        
        # If still no player_ids, raise an error
        if not team_player_ids:
            raise HTTPException(status_code=404, detail=f"Team not found and no player_ids available for team_id: {team_id}")
    
    # Build player list with franchise-specific attributes
    players_for_training = []
    for pid in team_player_ids:
        pid_str = str(pid)
        franchise_player_data = franchise_players.get(pid_str, {})
        if not franchise_player_data:
            continue
        
        # Build player dict for training
        player = {
            "_id": pid_str,
            "first_name": franchise_player_data.get("meta", {}).get("first_name", ""),
            "last_name": franchise_player_data.get("meta", {}).get("last_name", ""),
            "team": team_name or team_id,  # Use team_name if available, otherwise use team_id
            "attributes": franchise_player_data.get("attributes", {})
        }
        players_for_training.append(player)

    if not players_for_training:
        raise HTTPException(status_code=404, detail="No players found for training")

    # Get franchise-specific team stats
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_data = franchise_teams.get(team_id, {})
    team_stats = team_data.copy()

    # Extract training data
    training_data = req.training_data
    
    # ✅ Get plays, game plan settings, and playbook settings for training
    # These are the LATEST settings saved from Game Plan and Playbooks screens
    # When playbook_training_mode == "current-playbooks", these settings will be used
    plays_data = team_data.get("plays", {})
    strategy_settings = team_data.get("strategy_settings", {})
    playbook_settings = team_data.get("playbook_settings", {})
    scouting_data = team_data.get("scouting_data", {})
    
    # 🔍 DEBUG: Log settings loaded for training
    logger.warning(f"🔍 [TRAINING DEBUG] team_id used: {team_id}")
    logger.warning(f"🔍 [TRAINING DEBUG] strategy_settings keys: {list(strategy_settings.keys()) if strategy_settings else 'EMPTY/NONE'}")
    logger.warning(f"🔍 [TRAINING DEBUG] strategy_settings['offense']: {strategy_settings.get('offense') if strategy_settings else 'N/A'}")
    logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings keys: {list(playbook_settings.keys()) if playbook_settings else 'EMPTY/NONE'}")
    if playbook_settings:
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['motion'] keys: {list(playbook_settings.get('motion', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_inside'] keys: {list(playbook_settings.get('set_play_inside', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_outside'] keys: {list(playbook_settings.get('set_play_outside', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_attack'] keys: {list(playbook_settings.get('set_play_attack', {}).keys())}")
    logger.warning(f"🔍 [TRAINING DEBUG] playbook_training_mode: {training_data.get('playbook_training_mode', 'not provided')}")
    
    # ✅ FIX: Initialize plays_data if empty (first time training for this team)
    # This ensures plays structure exists before training, preventing plays from being lost
    if not plays_data:
        logger.warning(f"📚 [API] plays_data is empty, populating from universal plays collection")
        from BackEnd.api.gameplan_routes import populate_team_plays
        plays_data = populate_team_plays(mode="franchise")
        # Save to database immediately to ensure structure exists
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {f"franchise_teams.{team_id}.plays": plays_data}}
        )
        logger.info(f"✅ [API] Initialized {len(plays_data)} plays for team {team_id}")
    else:
        logger.info(f"✅ [API] Found {len(plays_data)} existing plays for team {team_id}")
    
    # Initialize scouting_data if empty or missing defense structure
    if not scouting_data or "defense" not in scouting_data:
        logger.warning(f"📚 [API] scouting_data is empty or missing defense structure, initializing")
        from BackEnd.models.team_manager import TeamManager
        # Create a temporary TeamManager to use its initialization method
        temp_team = TeamManager(name=team_name or team_id, mode="franchise")
        scouting_data = temp_team.scouting_data
        # Save to database
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {f"franchise_teams.{team_id}.scouting_data": scouting_data}}
        )
    
    logger.warning(f"📚 [API] Loading plays_data: {len(plays_data)} plays")
    logger.warning(f"📚 [API] Loading scouting_data: {list(scouting_data.keys()) if scouting_data else 'None'}")
    logger.warning(f"📚 [API] playbook_training_mode: {training_data.get('playbook_training_mode', 'not provided')}")
    logger.warning(f"🔋 [API] training_data keys: {list(training_data.keys())}")
    logger.warning(f"🔋 [API] team_drills in training_data: {'team_drills' in training_data}")
    if "team_drills" in training_data:
        logger.warning(f"🔋 [API] team_drills content: {training_data['team_drills']}")
        logger.warning(f"🔋 [API] scrimmages in team_drills: {'scrimmages' in training_data.get('team_drills', {})}")
        if "scrimmages" in training_data.get("team_drills", {}):
            logger.warning(f"🔋 [API] scrimmages value: {training_data['team_drills']['scrimmages']}")
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    logger.warning(f"🔋 [API] allocations.team_drills: {allocations.get('team_drills', {})}")
    coaching_focus = training_data.get("coaching_focus")

    # Execute new training system
    # This applies pre-training conditions, then training points, and returns training report
    from BackEnd.models.training_execution_v2 import execute_training
    
    # Execute training (applies pre-training conditions, then training points)
    updated_players, updated_team, updated_plays, updated_scouting_data, training_report = execute_training(
        players_for_training,
        team_stats,
        allocations,
        coaching_focus,
        plays_data=plays_data,
        strategy_settings=strategy_settings,
        playbook_settings=playbook_settings,
        scouting_data=scouting_data,
        playbook_training_mode=training_data.get("playbook_training_mode", "current-playbooks")
    )
    
    # Update players_for_training and team_stats with results
    players_for_training = updated_players
    team_stats = updated_team

    # Recalculate position ratings for each player after training (with updated attributes)
    from BackEnd.utils.position_ratings import compute_position_ratings
    position_ratings_updates = {}
    
    for player in players_for_training:
        pid = player["_id"]
        # Get player's height (from core collection or franchise meta)
        # Try as string first (UUID), fall back to ObjectId if that fails
        core_player = db.players.find_one({"_id": pid}, {"height": 1})
        if not core_player:
            try:
                core_player = db.players.find_one({"_id": ObjectId(pid)}, {"height": 1})
            except:
                pass
        height = core_player.get("height") if core_player else None
        
        # Build player dict for position ratings calculation with updated attributes
        player_for_ratings = {
            "attributes": player.get("attributes", {}),  # Now contains updated values!
            "height": height,
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}"
        }
        
        # Compute new position ratings
        new_ratings = compute_position_ratings(player_for_ratings)
        position_ratings_updates[pid] = new_ratings

    # Use training report data for player and team changes
    # Support both old field names (player_changes, team_changes) and new standardized names (player_logs, team_log)
    player_logs = training_report.get("player_logs") or training_report.get("player_changes", {})
    team_log = training_report.get("team_log") or training_report.get("team_changes", {})

    # Update franchise document with new attribute values and position ratings
    franchise_update = {}
    for player in players_for_training:
        pid = player["_id"]
        attrs = player.get("attributes", {})
        
        # Update all anchor attributes and base attributes
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO"]:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                franchise_update[f"players.{pid}.attributes.{anchor_key}"] = attrs[anchor_key]
                franchise_update[f"players.{pid}.attributes.{attr}"] = attrs[attr]
        
        # NG doesn't have an anchor_key, save it directly if it exists
        if "NG" in attrs:
            franchise_update[f"players.{pid}.attributes.NG"] = attrs["NG"]
        
        # Update position ratings for this player
        if pid in position_ratings_updates:
            franchise_update[f"players.{pid}.position_ratings"] = position_ratings_updates[pid]

    # Update franchise team stats
    for field, value in team_stats.items():
        # Skip non-numeric fields
        if isinstance(value, dict):
            continue
        franchise_update[f"franchise_teams.{team_id}.{field}"] = value
    
    # ✅ FIX: Always save plays data (even if empty) to preserve structure after training
    # This ensures plays are not lost when playbooks page reloads
    if updated_plays is not None:
        franchise_update[f"franchise_teams.{team_id}.plays"] = updated_plays
        logger.info(f"✅ [TRAINING] Saving {len(updated_plays)} plays to database")
    else:
        logger.warning(f"⚠️ [TRAINING] updated_plays is None, preserving existing plays data")
    
    # ✅ FIX: Always save scouting_data (even if empty) to preserve structure after training
    if updated_scouting_data is not None:
        franchise_update[f"franchise_teams.{team_id}.scouting_data"] = updated_scouting_data
        logger.info(f"✅ [TRAINING] Saving scouting_data to database")
    else:
        logger.warning(f"⚠️ [TRAINING] updated_scouting_data is None, preserving existing scouting_data")

    # Mark training as completed and update status
    session_type = training_status.get("session_type", "in-season")
    franchise_update["training_status.training_completed"] = True
    franchise_update["training_status.week"] = current_week
    franchise_update["training_status.last_training_date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Store training report data
    training_report_data = {
        "week": current_week,
        "player_logs": player_logs,  # Standardized name (was player_changes)
        "team_log": team_log,  # Standardized name (was team_changes)
        "coaching_focus": training_report.get("coaching_focus", {}),
        "training_notes": training_report.get("training_notes", []),
        "plays_data": training_report.get("plays_data", {}),
        "scouting_data": training_report.get("scouting_data", {}),
        "plays_effectiveness_changes": training_report.get("plays_effectiveness_changes", {}),
        "defenses_effectiveness_changes": training_report.get("defenses_effectiveness_changes", {}),
        "session_type": session_type,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Store training report in franchise_teams.{team_id}.training_reports
    franchise_update[f"franchise_teams.{team_id}.training_reports.{current_week}"] = training_report_data
    
    # Also save latest training for quick access
    franchise_update["latest_training"] = training_report_data

    # ✅ Run training for all computer teams (in unison with user team training)
    # Each computer team gets random allocations and random coaching focus
    # Each team gets separate randomizations for pre-training decay and training
    computer_teams_update = {}
    
    for computer_team_id, computer_team_data in franchise_teams.items():
        # Skip user's team (already processed above)
        if str(computer_team_id) == str(team_id):
            continue
        
        try:
            # Get team document to get team name and player_ids
            computer_team_doc = db.teams.find_one({"_id": ObjectId(computer_team_id)})
            if not computer_team_doc:
                logger.warning(f"⚠️ [COMPUTER TRAINING] Team document not found for team_id: {computer_team_id}")
                continue
            
            computer_team_name = computer_team_doc.get("name", "")
            computer_team_player_ids = computer_team_doc.get("player_ids", [])
            
            if not computer_team_player_ids:
                logger.warning(f"⚠️ [COMPUTER TRAINING] No player_ids found for team_id: {computer_team_id}")
                continue
            
            # Build player list with franchise-specific attributes
            computer_players_for_training = []
            for pid in computer_team_player_ids:
                pid_str = str(pid)
                computer_franchise_player_data = franchise_players.get(pid_str, {})
                if not computer_franchise_player_data:
                    continue
                
                # Build player dict for training
                player = {
                    "_id": pid_str,
                    "first_name": computer_franchise_player_data.get("meta", {}).get("first_name", ""),
                    "last_name": computer_franchise_player_data.get("meta", {}).get("last_name", ""),
                    "team": computer_team_name or computer_team_id,
                    "attributes": computer_franchise_player_data.get("attributes", {})
                }
                computer_players_for_training.append(player)
            
            if not computer_players_for_training:
                logger.warning(f"⚠️ [COMPUTER TRAINING] No players found for training for team_id: {computer_team_id}")
                continue
            
            # Get franchise-specific team stats
            computer_team_stats = computer_team_data.copy()
            
            # Get plays, game plan settings, and playbook settings for computer team
            computer_plays_data = computer_team_data.get("plays", {})
            computer_strategy_settings = computer_team_data.get("strategy_settings", {})
            computer_playbook_settings = computer_team_data.get("playbook_settings", {})
            computer_scouting_data = computer_team_data.get("scouting_data", {})
            
            # Initialize plays_data if empty
            if not computer_plays_data:
                from BackEnd.api.gameplan_routes import populate_team_plays
                computer_plays_data = populate_team_plays(mode="franchise")
                computer_teams_update[f"franchise_teams.{computer_team_id}.plays"] = computer_plays_data
            
            # Initialize scouting_data if empty or missing defense structure
            if not computer_scouting_data or "defense" not in computer_scouting_data:
                from BackEnd.models.team_manager import TeamManager
                temp_team = TeamManager(name=computer_team_name or computer_team_id, mode="franchise")
                computer_scouting_data = temp_team.scouting_data
                computer_teams_update[f"franchise_teams.{computer_team_id}.scouting_data"] = computer_scouting_data
            
            # Generate random training allocations and coaching focus
            computer_allocations = generate_random_training_allocations(expected_points)
            computer_coaching_focus = generate_random_coaching_focus()
            
            # Execute training for computer team (includes pre-training conditions and effectiveness decay)
            # Each team gets separate randomizations (handled by execute_training internally)
            updated_computer_players, updated_computer_team, updated_computer_plays, updated_computer_scouting_data, _ = execute_training(
                computer_players_for_training,
                computer_team_stats,
                computer_allocations,
                computer_coaching_focus,
                plays_data=computer_plays_data,
                strategy_settings=computer_strategy_settings,
                playbook_settings=computer_playbook_settings,
                scouting_data=computer_scouting_data,
                playbook_training_mode="all-plays-even"  # Use even distribution for computer teams
            )
            
            # Recalculate position ratings for each computer player after training
            for player in updated_computer_players:
                pid = player["_id"]
                core_player = db.players.find_one({"_id": pid}, {"height": 1})
                if not core_player:
                    try:
                        core_player = db.players.find_one({"_id": ObjectId(pid)}, {"height": 1})
                    except:
                        pass
                height = core_player.get("height") if core_player else None
                
                player_for_ratings = {
                    "attributes": player.get("attributes", {}),
                    "height": height,
                    "name": f"{player.get('first_name', '')} {player.get('last_name', '')}"
                }
                
                new_ratings = compute_position_ratings(player_for_ratings)
                computer_teams_update[f"players.{pid}.position_ratings"] = new_ratings
            
            # Update computer team players' attributes
            for player in updated_computer_players:
                pid = player["_id"]
                attrs = player.get("attributes", {})
                
                # Update all anchor attributes and base attributes
                for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO"]:
                    anchor_key = f"anchor_{attr}"
                    if anchor_key in attrs:
                        computer_teams_update[f"players.{pid}.attributes.{anchor_key}"] = attrs[anchor_key]
                        computer_teams_update[f"players.{pid}.attributes.{attr}"] = attrs[attr]
                
                # NG doesn't have an anchor_key, save it directly if it exists
                if "NG" in attrs:
                    computer_teams_update[f"players.{pid}.attributes.NG"] = attrs["NG"]
            
            # Update computer team stats
            for field, value in updated_computer_team.items():
                # Skip non-numeric fields
                if isinstance(value, dict):
                    continue
                computer_teams_update[f"franchise_teams.{computer_team_id}.{field}"] = value
            
            # Update computer team plays and scouting data
            if updated_computer_plays:
                computer_teams_update[f"franchise_teams.{computer_team_id}.plays"] = updated_computer_plays
            
            if updated_computer_scouting_data:
                computer_teams_update[f"franchise_teams.{computer_team_id}.scouting_data"] = updated_computer_scouting_data
            
            logger.info(f"✅ [COMPUTER TRAINING] Completed training for computer team: {computer_team_name} ({computer_team_id})")
        
        except Exception as e:
            logger.error(f"❌ [COMPUTER TRAINING] Error training computer team {computer_team_id}: {str(e)}")
            continue
    
    # Merge computer teams updates with user team updates
    franchise_update.update(computer_teams_update)
    
    # Save to franchise document (includes both user team and computer teams)
    db.franchises.update_one({"_id": franchise_id}, {"$set": franchise_update})
    
    return {
        "status": "success",
        "week": current_week,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "session_type": session_type,
        "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={team_id}&week={current_week}"
    }


@router.get("/franchise/training-report")
def get_training_report(franchise_id: str = None, tournament_id: str = None, team_id: str = None, week: int = None, round: int = None):
    """
    Get training report data for display on training-report.html page.
    Supports both franchise and tournament modes.
    
    SS&S Approach:
    - For franchise mode: 'week' parameter is required
    - For tournament mode: 'round' parameter is optional - if not provided, backend determines from training_status.round or latest_training.round
    - This allows direct navigation after training without needing round in URL
    - Historical reports from schedule links can still pass round parameter
    """
    try:
        mode = "franchise" if franchise_id else "tournament"
        doc_id = franchise_id if franchise_id else tournament_id
        
        if not doc_id or not team_id:
            raise HTTPException(status_code=400, detail="Missing required parameters (doc_id, team_id)")
        
        # For tournament mode, determine round from backend state if not provided
        if mode == "tournament":
            from BackEnd.db import tournaments_collection
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            doc_id_obj = ObjectId(doc_id)
            doc = tournaments_collection.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match tournament document user_team_object_id ({authoritative_team_id}). Using tournament document value.")
            
            if round is not None:
                week = round  # Use round parameter if provided (for historical reports)
            elif week is not None:
                week = week  # Use week parameter if provided (backward compatibility)
            else:
                # SS&S: Determine round from backend state (training_status or latest_training)
                # Try training_status.round first, then latest_training.round
                training_status = doc.get("training_status", {})
                week = training_status.get("round")
                if week is None:
                    latest_training = doc.get("latest_training", {})
                    week = latest_training.get("round")
                
                if week is None:
                    raise HTTPException(status_code=400, detail="No training round found. Please specify 'round' parameter or complete training first.")
        
        # For franchise mode, week is required
        if mode == "franchise" and week is None:
            raise HTTPException(status_code=400, detail="Missing required parameter: 'week'")
        
        if mode == "franchise":
            doc_id_obj = ObjectId(doc_id)
            doc = db.franchises.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Franchise not found")
            
            # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match franchise document user_team_object_id ({authoritative_team_id}). Using franchise document value.")
            
            # Get team data from franchise_teams using authoritative team_id
            franchise_teams = doc.get("franchise_teams", {})
            team_data = franchise_teams.get(authoritative_team_id, {})
            
            # Get training report for this week
            training_reports = team_data.get("training_reports", {})
            report_data = training_reports.get(str(week)) or doc.get("latest_training", {})
            
            # Get schedule to find upcoming opponent
            schedule = doc.get("schedule", [])
            current_week = doc.get("week", 1)
            upcoming_opponent = None
            
            if current_week - 1 < len(schedule):
                week_games = schedule[current_week - 1]
                for away_id, home_id in week_games:
                    if str(away_id) == authoritative_team_id or str(home_id) == authoritative_team_id:
                        opponent_id = str(home_id) if str(away_id) == authoritative_team_id else str(away_id)
                        opponent_team = db.teams.find_one({"_id": ObjectId(opponent_id)}, {"name": 1})
                        if opponent_team:
                            upcoming_opponent = opponent_team.get("name", "")
                        break
            
            # Get current player attributes (after training)
            # Players are stored at franchise level, not in franchise_teams
            players = []
            franchise_players = doc.get("players", {})
            
            # Use authoritative team_id for player filtering
            team_id_str = str(authoritative_team_id)
            logger.info(f"🔍 [TRAINING REPORT] Resolved team_id: {team_id} -> {team_id_str}")
            logger.info(f"🔍 [TRAINING REPORT] Total franchise players: {len(franchise_players)}")
            
            for player_id, player_data in franchise_players.items():
                # Check if player belongs to this team
                meta = player_data.get("meta", {})
                player_team_id = meta.get("team_id")
                
                # Handle different formats: ObjectId, string, or None
                if player_team_id is None:
                    # Try to get team from team name in meta
                    player_team_name = meta.get("team", "")
                    if player_team_name:
                        player_team_doc = db.teams.find_one({"name": player_team_name})
                        if player_team_doc:
                            player_team_id = str(player_team_doc["_id"])
                        else:
                            continue
                    else:
                        continue
                else:
                    player_team_id = str(player_team_id)
                
                # Compare team IDs
                if player_team_id != team_id_str:
                    continue
                
                # Get attributes (after training)
                attrs = player_data.get("attributes", {})
                
                # Extract anchor attributes (current values after training)
                # Use anchor_ values if available (post-training), otherwise fallback to base values
                player_attrs = {}
                # First, collect all anchor_ attributes
                for k, v in attrs.items():
                    if k.startswith("anchor_"):
                        attr_name = k.replace("anchor_", "")
                        player_attrs[attr_name] = v
                
                # For attributes that don't have anchor_ keys, use base values as fallback
                # This ensures SC, SH, and other attributes are included even if they haven't been modified
                standard_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
                for attr in standard_attrs:
                    if attr not in player_attrs and attr in attrs:
                        player_attrs[attr] = attrs[attr]
                
                # NG, EM, MO don't have anchor_ keys, add them directly
                if "NG" in attrs:
                    player_attrs["NG"] = attrs["NG"]
                if "EM" in attrs:
                    player_attrs["EM"] = attrs["EM"]
                if "MO" in attrs:
                    player_attrs["MO"] = attrs["MO"]
                
                first_name = meta.get("first_name", "")
                last_name = meta.get("last_name", "")
                player_name = f"{first_name} {last_name}".strip()
                
                if player_name:  # Only add if we have a name
                    players.append({
                        "id": player_id,
                        "name": player_name,
                        "attributes": player_attrs
                    })
            
            logger.info(f"🔍 [TRAINING REPORT] Found {len(players)} players for team {team_id_str}")
            
            # Get current team attributes (after training)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 0),
                "rebound_modifier": team_data.get("rebound_modifier", 0.2),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "fight": team_data.get("fight", 0),
                "discipline": team_data.get("discipline", 0),
                "momentum_score": team_data.get("momentum_score", 0),
                "team_chemistry": team_data.get("team_chemistry", 7),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0)
            }
            
        else:  # tournament mode
            from BackEnd.db import tournaments_collection, teams_collection
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            doc_id_obj = ObjectId(doc_id)
            doc = tournaments_collection.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match tournament document user_team_object_id ({authoritative_team_id}). Using tournament document value.")
            
            team_id_str = str(authoritative_team_id)
            current_round = week  # week parameter is used as round for tournament
            
            # Get training report for this round (matches Franchise pattern: try per-round storage first, then fallback)
            tournament_teams = doc.get("teams", {})
            team_data = tournament_teams.get(team_id_str, {})
            training_reports = team_data.get("training_reports", {})
            report_data = training_reports.get(str(current_round)) or doc.get("latest_training", {})
            
            # Verify round matches if using latest_training fallback
            if report_data and report_data.get("round") != current_round:
                report_data = {}
            
            # Get upcoming opponent from bracket
            current_round = doc.get("current_round", 1)
            round_key = "final" if current_round == 3 else f"round{current_round}"
            matchups = doc.get("bracket", {}).get(round_key, [])
            upcoming_opponent = None
            
            user_team_id = doc.get("user_team_id")
            for matchup in matchups:
                if user_team_id in [matchup.get("home_team"), matchup.get("away_team")]:
                    upcoming_opponent = matchup.get("away_team") if matchup.get("home_team") == user_team_id else matchup.get("home_team")
                    break
            
            # Get current player attributes (after training)
            players = []
            # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
            tournament_players = doc.get("players", {}) or doc.get("player_stats", {})  # Backward compatibility
            
            # ✅ MIGRATION: Use authoritative_team_id (already resolved from tournament document)
            # No need to resolve again - we already have the correct ObjectId
            team_doc = teams_collection.find_one({"_id": ObjectId(team_id_str)})
            if not team_doc:
                raise HTTPException(status_code=404, detail="Team not found")
            
            team_player_ids = team_doc.get("player_ids", [])
            for pid in team_player_ids:
                pid_str = str(pid)
                tournament_player_data = tournament_players.get(pid_str, {})
                if not tournament_player_data:
                    continue
                
                # Get attributes (after training)
                attrs = tournament_player_data.get("attributes", {})
                
                # For backward compatibility: if tournament only has EM, CH, MO (old format),
                # merge with core attributes. New tournaments will have all attributes stored.
                standard_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
                has_all_attrs = all(attr in attrs for attr in standard_attrs)
                
                if not has_all_attrs:
                    # Merge with core collection for backward compatibility
                    from BackEnd.db import players_collection
                    core_player = players_collection.find_one({"_id": ObjectId(pid_str)}, {"attributes": 1})
                    if core_player:
                        core_attributes = core_player.get("attributes", {})
                        attrs = {**core_attributes, **attrs}  # Tournament attributes override core
                        logger.info(f"📊 [TRAINING REPORT] Merged core attributes for player {pid_str} (backward compatibility)")
                
                # Extract anchor attributes (current values after training)
                # Use anchor_ values if available (post-training), otherwise fallback to base values
                player_attrs = {}
                # First, collect all anchor_ attributes
                for k, v in attrs.items():
                    if k.startswith("anchor_"):
                        attr_name = k.replace("anchor_", "")
                        player_attrs[attr_name] = v
                
                # For attributes that don't have anchor_ keys, use base values as fallback
                # This ensures SC, SH, and other attributes are included even if they haven't been modified
                for attr in standard_attrs:
                    if attr not in player_attrs and attr in attrs:
                        player_attrs[attr] = attrs[attr]
                
                # NG, EM, MO don't have anchor_ keys, add them directly
                if "NG" in attrs:
                    player_attrs["NG"] = attrs["NG"]
                if "EM" in attrs:
                    player_attrs["EM"] = attrs["EM"]
                if "MO" in attrs:
                    player_attrs["MO"] = attrs["MO"]
                
                # Get player metadata (with meta wrapper support and backward compatibility)
                meta = tournament_player_data.get("meta", {})
                first_name = meta.get("first_name") or tournament_player_data.get("first_name", "")
                last_name = meta.get("last_name") or tournament_player_data.get("last_name", "")
                player_name = f"{first_name} {last_name}".strip()
                
                if player_name:
                    players.append({
                        "id": pid_str,
                        "name": player_name,
                        "attributes": player_attrs
                    })
            
            # Get current team attributes from tournament teams (matches Franchise pattern)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 0),
                "rebound_modifier": team_data.get("rebound_modifier", 0.2),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "fight": team_data.get("fight", 0),
                "discipline": team_data.get("discipline", 0),
                "momentum_score": team_data.get("momentum_score", 0),
                "team_chemistry": team_data.get("team_chemistry", 0),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0)
            }
        
        if not report_data:
            raise HTTPException(status_code=404, detail="Training report not found")

        return {
            "status": "success",
            "week": week if mode == "franchise" else None,  # Only for franchise mode
            "round": current_round if mode == "tournament" else None,  # Only for tournament mode
            "upcoming_opponent": upcoming_opponent,
            "coaching_focus": report_data.get("coaching_focus", {}),
            # Support both old field names (player_changes, team_changes) and new standardized names (player_logs, team_log)
            "player_changes": report_data.get("player_logs") or report_data.get("player_changes", {}),
            "team_changes": report_data.get("team_log") or report_data.get("team_changes", {}),
            "training_notes": report_data.get("training_notes", []),
            "plays_data": report_data.get("plays_data", {}),
            "scouting_data": report_data.get("scouting_data", {}),
            "plays_effectiveness_changes": report_data.get("plays_effectiveness_changes", {}),
            "defenses_effectiveness_changes": report_data.get("defenses_effectiveness_changes", {}),
            "players": players,
            "team_attributes": team_attrs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching training report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class SimRestOfTournamentRequest(BaseModel):
    franchise_id: str


class SimChampionshipRequest(BaseModel):
    franchise_id: str


class FinishSeasonRequest(BaseModel):
    franchise_id: str


@router.post("/franchise/sim-rest-of-tournament")
def sim_rest_of_tournament(req: SimRestOfTournamentRequest):
    """Simulate all remaining games in the current tournament round."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")
    
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    eos_tournament = franchise_doc.get("eos_tournament", {})
    if not eos_tournament:
        raise HTTPException(status_code=400, detail="EOS Tournament not initialized")
    
    current_round = eos_tournament.get("current_round", 1)
    bracket = eos_tournament.get("bracket", {})
    round_name = get_round_name(current_round)
    matchups = bracket.get(round_name, [])
    
    # Get current week (15, 16, or 17)
    week = franchise_doc.get("week", 15)
    
    # Simulate all incomplete matchups in current round
    for i, matchup in enumerate(matchups):
        if matchup.get("winner"):
            continue  # Already completed
        
        home_id = ObjectId(matchup["home_team"])
        away_id = ObjectId(matchup["away_team"])
        
        home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
        away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")
        
        if not home_name or not away_name:
            logger.error(f"❌ [EOS TOURNAMENT] Could not find team names for matchup {i}")
            continue
        
        try:
            # Run simulation
            gm = run_simulation(home_name, away_name)
            home_score = gm.score.get(home_name, 0)
            away_score = gm.score.get(away_name, 0)
            summary = summarize_game_state(gm)
            
            # Save game to database
            from BackEnd.utils.game_id_utils import generate_game_id
            game_id = generate_game_id()
            summary["_id"] = game_id
            summary["franchise_id"] = str(franchise_id)
            summary["week"] = week
            db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
            
            # Finalize game stats
            stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
            
            # Determine winner
            winner_id = home_id if home_score > away_score else away_id
            
            # Save result to bracket
            save_tournament_game_result(
                franchise_doc,
                current_round,
                i,
                str(game_id),
                str(winner_id),
                {"home": home_score, "away": away_score}
            )
            
            # Update franchise document
            db.franchises.update_one(
                {"_id": franchise_id},
                {"$set": {"eos_tournament": eos_tournament}}
            )
            
            logger.info(f"✅ [EOS TOURNAMENT] Simulated Round {current_round}, Matchup {i}: {home_name} vs {away_name}")
        
        except Exception as e:
            logger.error(f"❌ [EOS TOURNAMENT] Error simulating matchup {i}: {e}", exc_info=True)
            continue
    
    # Advance round if all matchups complete
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    eos_tournament = advance_tournament_round(franchise_doc, db.teams)
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {"eos_tournament": eos_tournament}}
    )
    
    return {"status": "success", "round": current_round}


@router.post("/franchise/sim-championship")
def sim_championship(req: SimChampionshipRequest):
    """Simulate the championship game (Final round)."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")
    
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    eos_tournament = franchise_doc.get("eos_tournament", {})
    if not eos_tournament:
        raise HTTPException(status_code=400, detail="EOS Tournament not initialized")
    
    bracket = eos_tournament.get("bracket", {})
    final = bracket.get("final", [])
    
    if not final or len(final) == 0:
        raise HTTPException(status_code=400, detail="Final round not ready")
    
    if final[0].get("winner"):
        raise HTTPException(status_code=400, detail="Championship already completed")
    
    matchup = final[0]
    home_id = ObjectId(matchup["home_team"])
    away_id = ObjectId(matchup["away_team"])
    
    home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
    away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
    home_name = home_doc.get("name", "")
    away_name = away_doc.get("name", "")
    
    if not home_name or not away_name:
        raise HTTPException(status_code=400, detail="Could not find team names")
    
    week = 17  # Championship is always week 17
    
    try:
        # Run simulation
        gm = run_simulation(home_name, away_name)
        home_score = gm.score.get(home_name, 0)
        away_score = gm.score.get(away_name, 0)
        summary = summarize_game_state(gm)
        
        # Save game to database
        from BackEnd.utils.game_id_utils import generate_game_id
        game_id = generate_game_id()
        summary["_id"] = game_id
        summary["franchise_id"] = str(franchise_id)
        summary["week"] = week
        db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
        
        # Finalize game stats
        stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
        
        # Determine winner
        winner_id = home_id if home_score > away_score else away_id
        
        # Save result to bracket
        save_tournament_game_result(
            franchise_doc,
            3,  # Final round
            0,  # Only one matchup
            str(game_id),
            str(winner_id),
            {"home": home_score, "away": away_score}
        )
        
        # Mark tournament as complete
        eos_tournament["completed"] = True
        eos_tournament["champion"] = str(winner_id)
        
        # Update franchise document
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {"eos_tournament": eos_tournament}}
        )
        
        logger.info(f"✅ [EOS TOURNAMENT] Championship complete! Winner: {str(winner_id)}")
        
        return {
            "status": "success",
            "winner": str(winner_id),
            "home_score": home_score,
            "away_score": away_score
        }
    
    except Exception as e:
        logger.error(f"❌ [EOS TOURNAMENT] Error simulating championship: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/franchise/finish-season")
def finish_season(req: FinishSeasonRequest):
    """Finish current season and start new season."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")
    
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get current season
    current_season = franchise_doc.get("current_season", 1)
    next_season = current_season + 1
    
    # Initialize new season (same logic as initial season initialization)
    from BackEnd.models.franchise_manager import FranchiseManager
    fm = FranchiseManager(db)
    
    # Get user team info
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    
    # Initialize new season
    fm.initialize_season(
        user_team_id=user_team_id,
        user_team_object_id=user_team_object_id
    )
    
    # Update franchise document
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {
            "current_season": next_season,
            "week": 1,
            "eos_tournament_active": False,
            "training_status.current_week": 1,
            "training_status.training_completed": False,
            "training_status.session_type": "preseason"
        }}
    )
    
    logger.info(f"✅ [FINISH SEASON] Started season {next_season}")
    
    return {"status": "success", "season": next_season, "week": 1}


# ============================================================================
# 🛠️ DEV MODE: Simulate Entire Regular Season (Temporary Development Feature)
# ============================================================================
# ⚠️  THIS IS A TEMPORARY DEVELOPMENT FEATURE
# ⚠️  To disable: Comment out the endpoint below (lines 2995-3150)
# ⚠️  To re-enable: Uncomment the endpoint
# ============================================================================

# ⚠️ DISABLED: Dev sim functionality commented out for testing
# class DevSimRegularSeasonRequest(BaseModel):
#     franchise_id: str


# @router.post("/franchise/dev-sim-regular-season")
# def dev_sim_regular_season(req: DevSimRegularSeasonRequest):
#     """
#     🛠️ DEV MODE ONLY: Simulate entire regular season (weeks 1-14) with auto-training and auto-lineups.
    
#     This endpoint streams progress updates via Server-Sent Events (SSE):
#     1. Loops through weeks 1-14
#     2. For each week:
#        - Auto-trains all teams (including user team) with default training allocations
#        - Auto-sets lineups for all teams from roster
#        - Simulates all games (user game + computer games)
#     3. Stops before week 15 (tournament)
#     
#     ⚠️  TEMPORARY DEVELOPMENT FEATURE - Comment out to disable
#     """
# #     import json
    # 
# #     def generate_progress():
# #         """Generator that yields SSE events with progress updates"""
# #         try:
            # franchise_id = ObjectId(req.franchise_id)
        # except Exception:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid franchise_id format'})}\n\n"
            # return
        # 
        # franchise_doc = db.franchises.find_one({"_id": franchise_id})
        # if not franchise_doc:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Franchise not found'})}\n\n"
            # return
        # 
        # # Get user team info
        # user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        # if not user_team_name or not user_team_object_id:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'User team not found in franchise'})}\n\n"
            # return
        # 
        # try:
            # user_team_id = ObjectId(user_team_object_id)
        # except Exception:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid user team ObjectId'})}\n\n"
            # return
        # 
        # schedule = franchise_doc.get("schedule", [])
        # franchise_teams = franchise_doc.get("franchise_teams", {})
        # 
        # # Get all team IDs in franchise
        # all_team_ids = [ObjectId(tid) for tid in franchise_teams.keys() if ObjectId.is_valid(tid)]
        # all_team_docs = {str(t["_id"]): t for t in db.teams.find({"_id": {"$in": all_team_ids}}, {"name": 1, "_id": 1})}
        # 
        # yield f"data: {json.dumps({'type': 'start', 'message': f'Starting regular season simulation for {user_team_name}', 'total_weeks': 14})}\n\n"
        # logger.info(f"🛠️ [DEV SIM] Starting regular season simulation for franchise {req.franchise_id}")
        # logger.info(f"🛠️ [DEV SIM] User team: {user_team_name} ({user_team_object_id})")
        # logger.info(f"🛠️ [DEV SIM] Total teams: {len(all_team_ids)}")
        # 
        # # Helper function to generate training data with correct point allocation
        # def get_training_data_for_week(week_num, franchise_doc):
            # """Generate training data with 30 points for first training, 24 for subsequent"""
            # # Check if this is the first training (week 1, no completed games)
            # results = franchise_doc.get("results", {})
            # has_completed_games = len(results) > 0
            # if not has_completed_games:
                # completed_game = db.games.find_one({
                    # "franchise_id": str(franchise_id),
                    # "is_final": True
                # })
                # has_completed_games = completed_game is not None
            # 
            # is_first_training = (week_num == 1 and not has_completed_games)
            # total_points = 30 if is_first_training else 24
            # 
            # # Balanced allocation: 30 points = 18 player + 8 team + 4 general
            # # Balanced allocation: 24 points = 14 player + 7 team + 3 general
            # if is_first_training:
                # # 30 points: 18 player + 8 team + 4 general
                # return {
                    # "player_drills": {
                        # "shooting": {"SC": 3, "SH": 3},  # 6 points
                        # "ball_handling": {"BH": 3},  # 3 points
                        # "defense": {"ID": 3, "OD": 3},  # 6 points
                        # "rebounding": {"RB": 3},  # 3 points
                        # # Total player: 18 points
                    # },
                    # "team_drills": {
                        # "offense": {"offensive_efficiency": 2},  # 2 points
                        # "defense": {"defensive_efficiency": 2},  # 2 points
                        # "fast_break": {"fb_efficiency": 2},  # 2 points
                        # "press_trap": {"pt_efficiency": 2},  # 2 points
                        # # Total team: 8 points
                    # },
                    # "general": {
                        # "team_chemistry": 2,  # 2 points
                        # "discipline": 1,  # 1 point
                        # "fight": 1  # 1 point
                        # # Total general: 4 points
                    # },
                    # "coaching_focus": "balanced",
                    # "playbook_training_mode": "current-playbooks"
                # }
            # else:
                # # 24 points: 14 player + 7 team + 3 general
                # return {
                    # "player_drills": {
                        # "shooting": {"SC": 2, "SH": 2},  # 4 points
                        # "ball_handling": {"BH": 2},  # 2 points
                        # "defense": {"ID": 2, "OD": 2},  # 4 points
                        # "rebounding": {"RB": 2},  # 2 points
                        # "athleticism": {"AG": 1, "ST": 1},  # 2 points
                        # # Total player: 14 points
                    # },
                    # "team_drills": {
                        # "offense": {"offensive_efficiency": 2},  # 2 points
                        # "defense": {"defensive_efficiency": 2},  # 2 points
                        # "fast_break": {"fb_efficiency": 2},  # 2 points
                        # "press_trap": {"pt_efficiency": 1},  # 1 point
                        # # Total team: 7 points
                    # },
                    # "general": {
                        # "team_chemistry": 1,  # 1 point
                        # "discipline": 1,  # 1 point
                        # "fight": 1  # 1 point
                        # # Total general: 3 points
                    # },
                    # "coaching_focus": "balanced",
                    # "playbook_training_mode": "current-playbooks"
                # }
        # 
        # # Simulate weeks 1-14
        # for week in range(1, 15):
            # yield f"data: {json.dumps({'type': 'week_start', 'week': week, 'message': f'Processing Week {week}...'})}\n\n"
            # logger.info(f"🛠️ [DEV SIM] Processing Week {week}...")
            # 
            # # Reload franchise doc to get latest state
            # franchise_doc = db.franchises.find_one({"_id": franchise_id})
            # current_week = franchise_doc.get("week", 1)
            # 
            # # Skip if already past this week
            # if current_week > week:
                # yield f"data: {json.dumps({'type': 'week_skip', 'week': week, 'message': f'Week {week} already completed, skipping'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week} already completed (current_week={current_week}), skipping")
                # continue
            # 
            # # Step 1: Auto-train all teams (including user team)
            # # Check if training already completed for this week (training_status is global)
            # franchise_doc = db.franchises.find_one({"_id": franchise_id})
            # training_status = franchise_doc.get("training_status", {})
            # if not (training_status.get("training_completed") and training_status.get("current_week") == week):
                # yield f"data: {json.dumps({'type': 'training_start', 'week': week, 'message': f'Week {week}: Training all teams...'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Auto-training all teams...")
                # trained_count = 0
                # for team_id_str, team_doc in all_team_docs.items():
                    # team_name = team_doc.get("name", "")
                    # if not team_name:
                        # continue
                    # 
                    # try:
                        # # Get training data with correct point allocation for this week
                        # training_data = get_training_data_for_week(week, franchise_doc)
                        # 
                        # # Create training request
                        # training_req = FranchiseTrainingRequest(
                            # franchise_id=req.franchise_id,
                            # team_id=team_id_str,
                            # training_data=training_data
                        # )
                        # 
                        # # Run training (reuse existing endpoint logic)
                        # training_result = run_franchise_training(training_req)
                        # trained_count += 1
                        # yield f"data: {json.dumps({'type': 'training_progress', 'week': week, 'team': team_name, 'message': f'Trained {team_name}'})}\n\n"
                        # logger.info(f"🛠️ [DEV SIM] Week {week}: Trained {team_name} - {training_result.get('status', 'unknown')}")
                        # 
                    # except Exception as e:
                        # logger.error(f"🛠️ [DEV SIM] Week {week}: Error training {team_name}: {e}")
                        # import traceback
                        # logger.error(f"🛠️ [DEV SIM] Traceback: {traceback.format_exc()}")
                        # yield f"data: {json.dumps({'type': 'training_error', 'week': week, 'team': team_name, 'message': f'Error training {team_name}: {str(e)}'})}\n\n"
                        # # Continue with other teams even if one fails
                # yield f"data: {json.dumps({'type': 'training_complete', 'week': week, 'message': f'Week {week}: Training complete ({trained_count} teams)'})}\n\n"
            # else:
                # yield f"data: {json.dumps({'type': 'training_skip', 'week': week, 'message': f'Week {week}: Training already completed, skipping'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Training already completed, skipping")
            # 
            # # Step 2: Get user's matchup for this week
            # week_games = schedule[week - 1] if week - 1 < len(schedule) else []
            # user_matchup = None
            # for away_id, home_id in week_games:
                # if away_id == user_team_id or home_id == user_team_id:
                    # away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
                    # home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
                    # user_matchup = {
                        # "home": home_doc.get("name", ""),
                        # "away": away_doc.get("name", ""),
                        # "home_id": str(home_id),
                        # "away_id": str(away_id),
                    # }
                    # break
            # 
            # if not user_matchup:
                # yield f"data: {json.dumps({'type': 'week_error', 'week': week, 'message': f'Week {week}: User matchup not found, skipping'})}\n\n"
                # logger.warning(f"🛠️ [DEV SIM] Week {week}: User matchup not found, skipping user game")
                # continue
            # 
            # # Step 3: Simulate user's game (with auto-lineup)
            # game_msg = f"Week {week}: Simulating {user_matchup['away']} @ {user_matchup['home']}..."
            # yield f"data: {json.dumps({'type': 'game_start', 'week': week, 'home': user_matchup['home'], 'away': user_matchup['away'], 'message': game_msg})}\n\n"
            # logger.info(f"🛠️ [DEV SIM] Week {week}: Simulating user game ({user_matchup['away']} @ {user_matchup['home']})...")
            # try:
                # # Build auto-lineups for both teams
                # from BackEnd.models.team_manager import TeamManager
                # home_team_manager = TeamManager(user_matchup["home"])
                # away_team_manager = TeamManager(user_matchup["away"])
                # 
                # home_lineup = build_lineup_from_mongo(home_team_manager)
                # away_lineup = build_lineup_from_mongo(away_team_manager)
                # 
                # # Convert lineups to player ID format
                # home_lineup_ids = {pos: player.player_id for pos, player in home_lineup.items()}
                # away_lineup_ids = {pos: player.player_id for pos, player in away_lineup.items()}
                # 
                # yield f"data: {json.dumps({'type': 'game_simulating', 'week': week, 'message': 'Running game simulation...'})}\n\n"
                # 
                # # Run full game simulation
                # gm = run_simulation(
                    # user_matchup["home"],
                    # user_matchup["away"],
                    # home_lineup_ids,
                    # away_lineup_ids
                # )
                # 
                # # Get final scores
                # home_score = gm.score.get(user_matchup["home"], 0)
                # away_score = gm.score.get(user_matchup["away"], 0)
                # 
                # result_msg = f"Final: {user_matchup['away']} {away_score}, {user_matchup['home']} {home_score}"
                # yield f"data: {json.dumps({'type': 'game_result', 'week': week, 'home': user_matchup['home'], 'away': user_matchup['away'], 'home_score': home_score, 'away_score': away_score, 'message': result_msg})}\n\n"
                # 
                # # Save game to database
                # summary = summarize_game_state(gm)
                # game_id = generate_game_id()
                # summary["_id"] = game_id
                # summary["franchise_id"] = str(franchise_id)
                # summary["week"] = week
                # summary["is_final"] = True
                # db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
                # 
                # # Finalize game stats
                # yield f"data: {json.dumps({'type': 'game_finalizing', 'week': week, 'message': 'Finalizing game stats...'})}\n\n"
                # stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
                # 
                # # Determine winner
                # winner_id = user_matchup["home_id"] if home_score > away_score else user_matchup["away_id"]
                # 
                # # Complete week (this will simulate computer games and advance week)
                # yield f"data: {json.dumps({'type': 'week_completing', 'week': week, 'message': 'Completing week (simulating computer games)...'})}\n\n"
                # complete_week_req = CompleteWeekRequest(
                    # franchise_id=req.franchise_id,
                    # week=week,
                    # result=GameResult(
                        # team1_id=user_matchup["away_id"],
                        # team2_id=user_matchup["home_id"],
                        # team1_score=away_score,
                        # team2_score=home_score
                    # ),
                    # game_id=str(game_id),
                    # game_document=summary
                # )
                # 
                # complete_week(complete_week_req)
                # yield f"data: {json.dumps({'type': 'week_complete', 'week': week, 'message': f'Week {week} complete!'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Completed user game and all computer games")
                # 
            # except Exception as e:
                # error_msg = f"Week {week}: Error simulating user game: {str(e)}"
                # yield f"data: {json.dumps({'type': 'week_error', 'week': week, 'message': error_msg})}\n\n"
                # logger.error(f"🛠️ [DEV SIM] Week {week}: Error simulating user game: {e}")
                # import traceback
                # logger.error(f"🛠️ [DEV SIM] Traceback: {traceback.format_exc()}")
                # # Continue to next week even if this one fails
        # 
        # # Reload franchise doc to get final state
        # franchise_doc = db.franchises.find_one({"_id": franchise_id})
        # final_week = franchise_doc.get("week", 1)
        # 
        # logger.info(f"🛠️ [DEV SIM] Regular season simulation complete! Final week: {final_week}")
        # yield f"data: {json.dumps({'type': 'complete', 'status': 'success', 'final_week': final_week, 'message': f'Simulation complete! Current week: {final_week}'})}\n\n"
    # 
    # return StreamingResponse(
        # generate_progress(),
        # media_type="text/event-stream",
        # headers={
            # "Cache-Control": "no-cache",
            # "Connection": "keep-alive",
            # "X-Accel-Buffering": "no"  # Disable nginx buffering
        # }
    # )

# ============================================================================
# 🛠️ END DEV MODE FEATURE
# ============================================================================
