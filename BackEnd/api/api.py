# 1. Imports
import sys
# ✅ PERFORMANCE: Removed debug print statements - use logger instead

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from BackEnd.constants import POSITION_LIST
import uuid
from BackEnd.main import run_simulation, simulate_quarter
from BackEnd.models.game_manager import GameManager
# ✅ PERFORMANCE: Removed debug print statements
from BackEnd.db import (
    players_collection,
    teams_collection,
    games_collection,
    tournaments_collection,
    franchises_collection,
)
from BackEnd.utils.roster_loader import load_roster
from BackEnd.utils.game_summary_builder import build_game_summary
from BackEnd.utils.shared import clean_mongo_ids, summarize_game_state, format_height
from BackEnd.utils import stat_updater
from pydantic import BaseModel
from fastapi import HTTPException
import pprint
from bson.json_util import dumps
from bson import ObjectId
from fastapi.staticfiles import StaticFiles
from BackEnd.models.animator import Animator   
# ✅ PERFORMANCE: Removed debug print statements
from .tournament_routes import router as tournament_router
from .training_routes import router as training_router
from .franchise_routes import router as franchise_router
from .gameplan_routes import router as gameplan_router
from .play_routes import router as play_router
from .skeleton_routes import router as skeleton_router
import traceback
from unidecode import unidecode
from typing import Optional
import logging
import os
import json
import time
from datetime import datetime
from pathlib import Path
from BackEnd.models.player import Player

logger = logging.getLogger(__name__)

# ✅ PERFORMANCE: Removed debug print statements
app = FastAPI()

# ✅ CRITICAL: Register health endpoint FIRST (before any other routes or middleware)
# This ensures health checks work even if other parts of the app fail to initialize
@app.get("/health")
def health_check():
    """Simplest possible health check - no dependencies, no async, no logger"""
    # Use print instead of logger in case logger isn't configured yet
    print("🔵 [HEALTH] GET /health called", file=sys.stderr, flush=True)
    try:
        port = os.getenv("PORT", "NOT SET")
        print(f"🔵 [HEALTH] Returning response with port={port}", file=sys.stderr, flush=True)
        return {"status": "healthy", "port": port}
    except Exception as e:
        print(f"🔴 [HEALTH ERROR] Exception: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

# CORS Configuration - Must match actual testing domains, not just final ideal
# CRITICAL: Add CORS middleware BEFORE including routers to ensure it applies to all routes
def get_cors_origins():
    """
    Get CORS allowed origins based on environment.
    Includes default Railway/Netlify domains for initial deployment,
    custom domains when configured, and localhost for development.
    """
    origins = [
        "http://localhost:8000",  # Local development
        "http://localhost:3000",  # Alternative local port
        "https://gob-test.netlify.app",  # ✅ Explicitly add staging Netlify domain
    ]
    
    # Get custom origins from environment variable (comma-separated)
    custom_origins = os.getenv("CORS_ORIGINS", "")
    if custom_origins:
        origins.extend([origin.strip() for origin in custom_origins.split(",") if origin.strip()])
    
    return origins

# Get CORS origins and configure middleware BEFORE including routers
# ✅ PERFORMANCE: Removed debug print statements
cors_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.(railway|netlify)\.app",  # Allow default Railway/Netlify domains (fixed regex)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600  # Cache preflight requests for 1 hour
)

# Include routers AFTER CORS middleware is configured
app.include_router(tournament_router)
app.include_router(training_router)
app.include_router(franchise_router)
app.include_router(gameplan_router)
app.include_router(play_router)
app.include_router(skeleton_router)

templates = Jinja2Templates(directory="FrontEnd/static")

# Conditionally mount static files (only in development)
# In production, Netlify serves static files
environment = os.getenv("ENVIRONMENT", "development")
if environment == "development":
    app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")
    print("✅ Static files mounted (development mode)")

# ✅ PERFORMANCE: Removed debug print statements

# ✅ DEBUG: Add CORS logging middleware to trace CORS issues
@app.middleware("http")
async def cors_debug_middleware(request: Request, call_next):
    """Debug middleware to log all requests and catch exceptions early"""
    method = request.method
    path = request.url.path
    print(f"🔵 [DEBUG] cors_debug_middleware: {method} {path}", file=sys.stderr, flush=True)
    
    origin = request.headers.get("origin")
    if origin:
        print(f"🔵 [DEBUG] cors_debug_middleware: Origin: {origin}", file=sys.stderr, flush=True)
        logger.info(f"🔍 [CORS] Request from origin: {origin}")
    
    # Log all headers for debugging
    print(f"🔵 [DEBUG] cors_debug_middleware: Headers: {dict(request.headers)}", file=sys.stderr, flush=True)
    
    try:
        response = await call_next(request)
        if origin:
            cors_header = response.headers.get("access-control-allow-origin")
            print(f"🔵 [DEBUG] cors_debug_middleware: Response status: {response.status_code}, CORS header: {cors_header}", file=sys.stderr, flush=True)
            logger.info(f"🔍 [CORS] Response CORS header: {cors_header}")
        print(f"🔵 [DEBUG] cors_debug_middleware: {method} {path} - Status: {response.status_code}", file=sys.stderr, flush=True)
        return response
    except Exception as e:
        print(f"🔴 [ERROR] cors_debug_middleware: EXCEPTION on {method} {path}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

# ✅ PERFORMANCE: Removed debug print statements

# ✅ Add global exception handler to catch all unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"🔴 [ERROR] Global exception handler: {type(exc).__name__}: {str(exc)}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": type(exc).__name__, "message": str(exc)}
    )

# ✅ Add startup event to verify app is ready
@app.on_event("startup")
async def startup_event():
    print("🔵 [DEBUG] startup_event: FastAPI app is ready!", file=sys.stderr, flush=True)
    print(f"🔵 [DEBUG] startup_event: PORT env var: {os.getenv('PORT', 'NOT SET')}", file=sys.stderr, flush=True)
    print(f"🔵 [DEBUG] startup_event: App instance: {app}", file=sys.stderr, flush=True)
    print(f"🔵 [DEBUG] startup_event: Number of routes: {len(app.routes)}", file=sys.stderr, flush=True)
    
    # Log all route paths to verify routes are registered
    route_paths = []
    for route in app.routes[:20]:  # First 20 routes
        if hasattr(route, 'methods'):
            methods = list(route.methods) if route.methods else ['ANY']
            route_paths.append(f"{methods[0] if methods else 'ANY'} {route.path}")
        else:
            route_paths.append(f"ANY {route.path}")
    print(f"🔵 [DEBUG] startup_event: Registered routes (first 20): {route_paths}", file=sys.stderr, flush=True)
    
    # Check MongoDB connection status (non-blocking, don't crash if it fails)
    # MongoDB connections are lazy - this just verifies the client exists
    try:
        from BackEnd.db import client, DB_NAME
        print(f"🔵 [DEBUG] startup_event: MongoDB client exists: {client is not None}", file=sys.stderr, flush=True)
        print(f"🔵 [DEBUG] startup_event: Target database name: {DB_NAME}", file=sys.stderr, flush=True)
        print(f"🔵 [DEBUG] startup_event: MONGO_URI set: {bool(os.getenv('MONGO_URI'))}", file=sys.stderr, flush=True)
        print(f"🔵 [DEBUG] startup_event: MONGO_DB_NAME env var: {os.getenv('MONGO_DB_NAME', 'NOT SET')}", file=sys.stderr, flush=True)
        
        # NOTE: We don't test actual DB connection here to avoid blocking startup
        # MongoDB will connect on first real operation. If connection fails, 
        # the global exception handler will catch it.
    except Exception as e:
        print(f"⚠️ [WARNING] startup_event: Could not check MongoDB config: {e}", file=sys.stderr, flush=True)
        # Don't crash startup - MongoDB might connect later

class SimulationRequest(BaseModel):
    home_team: str
    away_team: str
    home_lineup: dict[str, str] | None = None
    away_lineup: dict[str, str] | None = None


class QuarterSimulationRequest(BaseModel):
    game_id: str | None = None
    home_team: str
    away_team: str
    quarter: int = 1
    home_lineup: dict[str, str] | None = None
    away_lineup: dict[str, str] | None = None
    # Game plan settings (for user's team in single game mode)
    user_team_side: str | None = None  # "home" or "away"
    strategy_settings: dict[str, int] | None = None
    # Starting possession control for quarters after Q1
    start_with_inbound: bool | None = None
    starting_possession: str | None = None  # "home" or "away"
    # Mode context for tournament/franchise games
    mode: str | None = None  # "single", "tournament", or "franchise"
    tournament_id: str | None = None
    franchise_id: str | None = None
    # ✅ FIX: Allow full simulation (without animation) for "simming" operations
    # When True, fully simulates the quarter instantly and increments quarter number
    # When False (default), uses turn-by-turn mode (for playing with animation)
    full_sim: bool = False  # If True, turn_by_turn_mode=False (fully simulate instantly)
    # ✅ TIMEOUT: Resume from timeout flag (reuse quarter break pattern)
    resume_from_timeout: bool = False


ongoing_games: dict[str, GameManager] = {}


class TurnSimulationRequest(BaseModel):
    game_id: str
    # Optional user overrides for this specific turn
    offense_override: str | None = None  # e.g., "Inside", "Attack", "Outside"
    defense_override: str | None = None  # e.g., "Zone", "Man"


class CallTimeoutRequest(BaseModel):
    game_id: str
    calling_team: str  # "home" or "away"
    offense_override: str | None = None  # e.g., "Inside", "Attack", "Outside"
    defense_override: str | None = None  # e.g., "Zone", "Man"
    # Mode context
    mode: str | None = None  # "single", "tournament", or "franchise"


class PlaycallOverrideRequest(BaseModel):
    """✅ SS&S: Request model for setting persistent playcall overrides"""
    game_id: str
    user_team_side: str  # "home" or "away"
    offense_override: str | None = None  # Play name (e.g., "3-2 Motion")
    defense_override: str | None = None  # "Man" or "Zone"
    aggression_override: str | None = None  # "normal", "aggressive", "passive"
    tempo_override: str | None = None  # "slow", "normal", "fast"


# Helper functions for tournament/franchise mode
def load_player_attributes_from_doc(mode: str, doc_id: str, player_id: str):
    """Load player attributes (EM, CH, MO) from tournament/franchise doc."""
    from BackEnd.db import franchises_collection
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
                tournament_players = doc.get("players", {}) or doc.get("player_stats", {})  # Backward compatibility
                player_data = tournament_players.get(player_id, {})
                attrs = player_data.get("attributes", {})
                if attrs:
                    return {
                        "EM": attrs.get("EM"),
                        "CH": attrs.get("CH"),
                        "MO": attrs.get("MO")
                    }
        except Exception as e:
            print(f"⚠️ Error loading player attributes from tournament doc: {e}")
    elif mode == "franchise":
        try:
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                players = doc.get("players", {}).get(player_id, {})
                attrs = players.get("attributes", {})
                if attrs:
                    return {
                        "EM": attrs.get("EM"),
                        "CH": attrs.get("CH"),
                        "MO": attrs.get("MO")
                    }
        except Exception as e:
            print(f"⚠️ Error loading player attributes from franchise doc: {e}")
    
    return None

def load_plays_from_doc(mode: str, doc_id: str, team_id: str):
    """Load plays data from tournament/franchise doc."""
    from BackEnd.db import franchises_collection
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                team_obj = doc.get("teams", {}).get(team_id, {})
                plays = team_obj.get("plays", [])
                if plays:
                    # Debug logging removed - was cluttering logs
                    # logging.debug(f"📋 Loaded {len(plays)} plays for team {team_id} from tournament doc")
                    return plays
        except Exception as e:
            print(f"⚠️ Error loading plays from tournament doc: {e}")
    elif mode == "franchise":
        try:
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                team_obj = doc.get("teams", {}).get(team_id, {})
                plays = team_obj.get("plays", [])
                if plays:
                    # Debug logging removed - was cluttering logs
                    # logging.debug(f"📋 Loaded {len(plays)} plays for team {team_id} from franchise doc")
                    return plays
        except Exception as e:
            print(f"⚠️ Error loading plays from franchise doc: {e}")
    
    return None

def load_team_attributes_from_doc(mode: str, doc_id: str, team_id: str, team_name: str):
    """Load team_attributes from tournament/franchise doc, fallback to core teams doc."""
    from BackEnd.db import franchises_collection
    
    # Resolve team_id from team_name if not provided
    if not team_id and team_name:
        team_doc = teams_collection.find_one({"name": team_name})
        if team_doc:
            team_id = str(team_doc.get("_id"))
    
    attrs = None
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc and team_id:
                team_obj = doc.get("teams", {}).get(team_id, {})
                # Extract team_attributes from team_obj (may include other fields)
                attrs = {}
                for key in ["shot_threshold", "discipline", "fight",
                           "rebound_modifier", "momentum_score", "offensive_efficiency",
                           "team_chemistry", "defensive_efficiency", "fb_efficiency",
                           "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"]:
                    if key in team_obj:
                        attrs[key] = team_obj[key]
        except Exception as e:
            print(f"⚠️ Error loading team_attributes from tournament doc: {e}")
    elif mode == "franchise":
        try:
            # ✅ PERFORMANCE: Only fetch franchise_teams field (reduces from 402KB to ~50KB, 87% reduction)
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)}, {"franchise_teams": 1})
            if doc and team_id:
                team_obj = doc.get("franchise_teams", {}).get(team_id, {})
                # Extract team_attributes from team_obj
                attrs = {}
                for key in ["shot_threshold", "discipline", "fight",
                           "rebound_modifier", "momentum_score", "offensive_efficiency",
                           "team_chemistry", "defensive_efficiency", "fb_efficiency",
                           "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"]:
                    if key in team_obj:
                        attrs[key] = team_obj[key]
        except Exception as e:
            print(f"⚠️ Error loading team_attributes from franchise doc: {e}")
    elif mode == "single":
        try:
            # For single game mode, try both UUID string and ObjectId formats
            doc = games_collection.find_one({"_id": doc_id})
            if not doc:
                try:
                    doc = games_collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
            if doc and team_id:
                teams_obj = doc.get("teams", {})
                team_obj = teams_obj.get(team_id, {})
                # Extract team_attributes from team_obj
                attrs = {}
                for key in ["shot_threshold", "discipline", "fight",
                           "rebound_modifier", "momentum_score", "offensive_efficiency",
                           "team_chemistry", "defensive_efficiency", "fb_efficiency",
                           "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"]:
                    if key in team_obj:
                        attrs[key] = team_obj[key]
        except Exception as e:
            print(f"⚠️ Error loading team_attributes from game doc: {e}")
    
    # If no attributes found, try core teams doc as fallback
    if not attrs:
        team_doc = teams_collection.find_one({"name": team_name})
        if team_doc:
            attrs = {}
            for key in ["shot_threshold", "discipline", "fight",
                       "rebound_modifier", "momentum_score", "offensive_efficiency",
                       "team_chemistry", "defensive_efficiency", "fb_efficiency",
                       "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"]:
                if key in team_doc:
                    attrs[key] = team_doc[key]
    
    return attrs if attrs else None

def load_team_settings_from_doc(mode: str, doc_id: str, team_id: str, team_name: str):
    """Load strategy_settings and playbook_settings from tournament/franchise doc."""
    from BackEnd.db import franchises_collection
    
    # Resolve team_id from team_name if not provided
    if not team_id and team_name:
        team_doc = teams_collection.find_one({"name": team_name})
        if team_doc:
            team_id = str(team_doc.get("_id"))
    
    strategy_settings = None
    playbook_settings = None
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc and team_id:
                team_obj = doc.get("teams", {}).get(team_id, {})
                strategy_settings = team_obj.get("strategy_settings")
                playbook_settings = team_obj.get("playbook_settings")
        except Exception as e:
            logging.warning(f"⚠️ Error loading team settings from tournament doc: {e}")
    elif mode == "franchise":
        try:
            # ✅ PERFORMANCE: Only fetch franchise_teams field (reduces from 402KB to ~50KB, 87% reduction)
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)}, {"franchise_teams": 1})
            if doc and team_id:
                team_obj = doc.get("franchise_teams", {}).get(team_id, {})
                strategy_settings = team_obj.get("strategy_settings")
                playbook_settings = team_obj.get("playbook_settings")
        except Exception as e:
            logging.warning(f"⚠️ Error loading team settings from franchise doc: {e}")
    elif mode == "single":
        try:
            # For single game mode, try both UUID string and ObjectId formats
            doc = games_collection.find_one({"_id": doc_id})
            if not doc:
                try:
                    doc = games_collection.find_one({"_id": ObjectId(doc_id)})
                except:
                    pass
            if doc and team_id:
                teams_obj = doc.get("teams", {})
                team_obj = teams_obj.get(team_id, {}) if teams_obj else {}
                strategy_settings = team_obj.get("strategy_settings")
                playbook_settings = team_obj.get("playbook_settings")
        except Exception as e:
            logging.warning(f"⚠️ Error loading team settings from game doc: {e}")
    
    return {
        "strategy_settings": strategy_settings,
        "playbook_settings": playbook_settings
    }

def load_game_from_nested_structure(mode: str, doc_id: str, game_id: str, round_key: str = None, week: int = None):
    """Load game data from tournament/franchise nested structure."""
    from BackEnd.db import franchises_collection
    
    game_data = None
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc and round_key:
                games = doc.get("games", {})
                round_games = games.get(round_key, {})
                game_data = round_games.get(str(game_id)) or round_games.get(ObjectId(game_id))
        except Exception as e:
            print(f"⚠️ Error loading game from tournament doc: {e}")
    elif mode == "franchise":
        try:
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
            if doc and week is not None:
                games = doc.get("games", {})
                week_games = games.get(f"week_{week}", {})
                game_data = week_games.get(str(game_id)) or week_games.get(ObjectId(game_id))
        except Exception as e:
            print(f"⚠️ Error loading game from franchise doc: {e}")
    
    return game_data

def save_game_to_nested_structure(mode: str, doc_id: str, game_id: str, game_data: dict, round_key: str = None, week: int = None):
    """Save game data to tournament/franchise nested structure."""
    from BackEnd.db import franchises_collection
    
    if mode == "tournament":
        try:
            if not round_key:
                raise ValueError("round_key required for tournament mode")
            
            update_path = f"games.{round_key}.{game_id}"
            tournaments_collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {update_path: game_data}},
                upsert=True
            )
            print(f"✅ Saved game {game_id} to tournament.{update_path}")
        except Exception as e:
            print(f"❌ Error saving game to tournament doc: {e}")
            traceback.print_exc()
    elif mode == "franchise":
        try:
            if week is None:
                raise ValueError("week required for franchise mode")
            
            update_path = f"games.week_{week}.{game_id}"
            franchises_collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {update_path: game_data}},
                upsert=True
            )
            print(f"✅ Saved game {game_id} to franchise.{update_path}")
        except Exception as e:
            print(f"❌ Error saving game to franchise doc: {e}")
            traceback.print_exc()

def restore_timeout_resume_state(game_id: str, request: QuarterSimulationRequest, games_collection) -> dict | None:
    """
    Unified function to restore timeout resume state from DB.
    Always loads from DB (single source of truth) regardless of memory state or URL parameter.
    Handles all three game modes with correct document locations:
    - Single Game: games_collection doc
    - Tournament Game: nested in tournament collection doc (with fallback to games_collection)
    - Franchise Game: nested in franchise collection doc (with fallback to games_collection)
    Returns saved document with timeout state, or None if not found.
    
    NOTE: This function now ALWAYS checks the database for timeout state, regardless of
    the resume_from_timeout URL parameter. The database state is the source of truth.
    """
    logging.info(f"🔍 restore_timeout_resume_state: Checking DB for timeout state (game_id={game_id}, mode={request.mode}, games_collection={games_collection is not None})")
    
    # Always check database - don't rely on URL parameter
    # If timeout_next_play_type exists in DB, we're resuming from a timeout
    
    saved = None
    
    try:
        # Determine which document location to check based on mode
        if request.mode == "tournament" and request.tournament_id:
            # Tournament mode: Check nested structure first, then fallback to games_collection
            try:
                from BackEnd.db import tournaments_collection
                from bson import ObjectId
                
                tournament_doc = tournaments_collection.find_one({"_id": ObjectId(request.tournament_id)})
                if tournament_doc:
                    # Extract round_key from saved game or use default
                    # Try to find the game in any round
                    games = tournament_doc.get("games", {})
                    for round_key, round_games in games.items():
                        if isinstance(round_games, dict):
                            game_data = round_games.get(str(game_id)) or round_games.get(ObjectId(game_id))
                            if game_data:
                                saved = game_data
                                # ✅ PERFORMANCE: Removed debug logging
                                break
            except Exception as e:
                logging.warning(f"⚠️ TIMEOUT RESUME: Error loading from tournament nested structure: {e}")
            
            # Fallback to games_collection if not found in nested structure
            if not saved and games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                # ✅ PERFORMANCE: Removed debug logging
        
        elif request.mode == "franchise" and request.franchise_id:
            # Franchise mode: Check nested structure first, then fallback to games_collection
            try:
                from BackEnd.db import franchises_collection
                from bson import ObjectId
                
                franchise_doc = franchises_collection.find_one({"_id": ObjectId(request.franchise_id)})
                if franchise_doc:
                    # Try to find the game in any week
                    games = franchise_doc.get("games", {})
                    for week_key, week_games in games.items():
                        if isinstance(week_games, dict):
                            game_data = week_games.get(str(game_id)) or week_games.get(ObjectId(game_id))
                            if game_data:
                                saved = game_data
                                # ✅ PERFORMANCE: Removed debug logging
                                break
            except Exception as e:
                logging.warning(f"⚠️ TIMEOUT RESUME: Error loading from franchise nested structure: {e}")
            
            # Fallback to games_collection if not found in nested structure
            if not saved and games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                if saved:
                    # ✅ PERFORMANCE: Removed debug logging
                    pass
        
        else:
            # Single game mode: Check games_collection
            if games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                # ✅ PERFORMANCE: Removed debug logging
        
        if not saved:
            logging.warning(f"⚠️ TIMEOUT RESUME: Game {game_id} not found in any document location (mode: {request.mode})")
            return None
        
        # Validate that timeout_next_play_type exists
        if "timeout_next_play_type" not in saved:
            logging.error(f"❌ TIMEOUT RESUME: timeout_next_play_type missing from saved game {game_id}")
            return None
        
        # ✅ PERFORMANCE: Removed debug logging
        return saved
    except Exception as e:
        logging.error(f"❌ TIMEOUT RESUME: Error loading from DB: {e}", exc_info=True)
        return None

def handle_timeout_save_and_response(gm: "GameManager", timeout_turn: dict, game_id: str, timeout_reason: str = "USER"):
    """
    Unified timeout save and response handler.
    Used by both user and computer timeouts to ensure identical behavior.
    
    Args:
        gm: GameManager instance
        timeout_turn: Timeout turn dictionary
        game_id: Game ID for database save
        timeout_reason: "USER", "COMPUTER", or "FOUL_OUT"
    
    Returns:
        dict: Consistent timeout response format with saved data from DB
    """
    from BackEnd.db import games_collection
    
    # Save to DB (same for both user and computer timeouts)
    db_summary = summarize_game_state(gm, exclude_animations=True)
    games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
    
    # 🔍 DEBUG: Log what was saved (for both user and computer)
    debug_prefix = "USER" if timeout_reason == "USER" else "COMPUTER"
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] db_summary timeout fields: timeout_next_play_type={db_summary.get('timeout_next_play_type')}, timeout_offense_team_id={db_summary.get('timeout_offense_team_id')}")
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] db_summary score={db_summary.get('score')}, clock={db_summary.get('clock')}, time_remaining={db_summary.get('time_remaining')}")
    
    # Verify what was saved to DB
    saved_doc = games_collection.find_one({"_id": game_id})
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] DB AFTER save - timeout_next_play_type={saved_doc.get('timeout_next_play_type') if saved_doc else 'DOC_NOT_FOUND'}, timeout_offense_team_id={saved_doc.get('timeout_offense_team_id') if saved_doc else 'DOC_NOT_FOUND'}")
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] DB AFTER save - score={saved_doc.get('score') if saved_doc else 'DOC_NOT_FOUND'}, clock={saved_doc.get('clock') if saved_doc else 'DOC_NOT_FOUND'}, time_remaining={saved_doc.get('time_remaining') if saved_doc else 'DOC_NOT_FOUND'}")
    
    # Return consistent response format (same for both user and computer)
    # Use saved data (db_summary) to ensure response matches what was saved to DB
    response = {
        "turn": timeout_turn,
        "next_offensive_state": gm.game_state.get("offensive_state", "HCO"),
        "time_remaining": db_summary.get("time_remaining", gm.game_state.get("time_remaining", 480)),
        "clock": db_summary.get("clock", gm.game_state.get("clock", "8:00")),
        "quarter_complete": False,  # ✅ CRITICAL: Always False for timeout (not quarter end)
        "quarter": db_summary.get("quarter", gm.quarter),
        "is_final": False,
        "home_score": db_summary.get("score", {}).get(gm.home_team.name, gm.score.get(gm.home_team.name, 0)),
        "away_score": db_summary.get("score", {}).get(gm.away_team.name, gm.score.get(gm.away_team.name, 0)),
        "home_team_fouls": gm.home_team.team_fouls,
        "away_team_fouls": gm.away_team.team_fouls,
        "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
        "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
        "offense_team": gm.offense_team.name,
        "defense_team": gm.defense_team.name,
        "game_id": game_id,
        "ineligible_players": gm.game_state.get("ineligible_players", []),
        "box_score": gm.get_box_score(),
        "team_totals": {
            gm.home_team.name: gm.home_team.get_team_game_stats(),
            gm.away_team.name: gm.away_team.get_team_game_stats()
        }
    }
    
    # 🔍 DEBUG: Log what's being returned in response
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT RESPONSE DEBUG] Response data: time_remaining={response['time_remaining']}, clock={response['clock']}, quarter={response['quarter']}, quarter_complete={response['quarter_complete']}")
    logging.warning(f"🔍 [{debug_prefix} TIMEOUT RESPONSE DEBUG] Response scores: home_score={response['home_score']}, away_score={response['away_score']}")
    
    logging.info(
        f"💾 {debug_prefix} TIMEOUT: Saved game state and returning response: "
        f"game_id={game_id}, quarter={db_summary.get('quarter')}, "
        f"clock={db_summary.get('clock')}, time_remaining={db_summary.get('time_remaining')}, "
        f"next_play_type={timeout_turn.get('next_play_type')}"
    )
    
    return response

def refresh_game_cache_from_db(gm: "GameManager", saved: dict):
    """
    Refresh ongoing_games cache from database after state changes (timeout saves, etc.).
    Updates critical game state in the existing GameManager instance to match saved document.
    This ensures cache stays fresh without requiring full GameManager reconstruction.
    
    Args:
        gm: GameManager instance in ongoing_games cache
        saved: Saved game document from database
    """
    if not saved or not gm:
        return
    
    # Update critical game state from saved document
    # This is similar to apply_timeout_resume_state_to_gm but for cache refresh
    
    # Update timeout state
    if "timeout_next_play_type" in saved:
        gm.game_state["timeout_next_play_type"] = saved["timeout_next_play_type"]
    if "timeout_offense_team_id" in saved:
        gm.game_state["timeout_offense_team_id"] = saved["timeout_offense_team_id"]
    
    # Update clock and time
    if "clock" in saved:
        gm.game_state["clock"] = saved["clock"]
    if "time_remaining" in saved:
        gm.game_state["time_remaining"] = saved["time_remaining"]
    
    # Update scores
    if "score" in saved and isinstance(saved["score"], dict):
        for team_name, score_value in saved["score"].items():
            if team_name in gm.score:
                gm.score[team_name] = score_value
    
    # Update team fouls and timeouts (support both old and new structure)
    # Try unified structure first (new), then fallback to old structure
    teams_obj = saved.get("teams", {})
    home_team_id = saved.get("home_team_id")
    away_team_id = saved.get("away_team_id")
    
    # Unified structure (new)
    if home_team_id and home_team_id in teams_obj:
        home_team_data = teams_obj[home_team_id]
        if "team_fouls" in home_team_data:
            gm.home_team.team_fouls = home_team_data["team_fouls"]
        if "timeouts" in home_team_data:
            gm.home_team.timeouts = home_team_data["timeouts"]
    # Old structure (backward compatibility)
    elif "home_team" in saved:
        home_team_data = saved["home_team"]
        if "team_fouls" in home_team_data:
            gm.home_team.team_fouls = home_team_data["team_fouls"]
        if "timeouts" in home_team_data:
            gm.home_team.timeouts = home_team_data["timeouts"]
    
    # Unified structure (new)
    if away_team_id and away_team_id in teams_obj:
        away_team_data = teams_obj[away_team_id]
        if "team_fouls" in away_team_data:
            gm.away_team.team_fouls = away_team_data["team_fouls"]
        if "timeouts" in away_team_data:
            gm.away_team.timeouts = away_team_data["timeouts"]
    # Old structure (backward compatibility)
    elif "away_team" in saved:
        away_team_data = saved["away_team"]
        if "team_fouls" in away_team_data:
            gm.away_team.team_fouls = away_team_data["team_fouls"]
        if "timeouts" in away_team_data:
            gm.away_team.timeouts = away_team_data["timeouts"]
    
    # Update quarter
    if "quarter" in saved:
        gm.quarter = saved["quarter"]

def apply_timeout_resume_state_to_gm(gm: "GameManager", saved: dict):
    """
    Apply restored timeout state to GameManager.
    Called after gm is loaded/created.
    Works for all modes (single, tournament, franchise).
    
    ✅ CRITICAL FIX (January 2025): When resuming from timeout, restore ALL critical game state
    from the saved document, not just timeout-specific fields. This ensures that if the game
    is still in ongoing_games with stale state, we overwrite it with the correct saved state.
    This fixes the bug where computer timeouts would resume with incorrect scores/clock.
    """
    if not saved or not gm:
        return
    
    # 🔍 DEBUG: Log state BEFORE restore
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] BEFORE restore - game_id={gm.game_id if hasattr(gm, 'game_id') else 'NO_GAME_ID'}, quarter={gm.quarter}")
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] gm.game_state timeout fields: timeout_next_play_type={gm.game_state.get('timeout_next_play_type')}, timeout_offense_team_id={gm.game_state.get('timeout_offense_team_id')}")
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] gm.score={gm.score}, clock={gm.game_state.get('clock')}, time_remaining={gm.game_state.get('time_remaining')}")
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] saved document timeout fields: timeout_next_play_type={saved.get('timeout_next_play_type')}, timeout_offense_team_id={saved.get('timeout_offense_team_id')}")
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] saved document score={saved.get('score')}, clock={saved.get('clock')}, time_remaining={saved.get('time_remaining')}")
    
    # ✅ CRITICAL FIX: Restore ALL critical game state from saved document
    # This ensures saved state (from timeout save) overwrites any stale in-memory state
    
    # Restore timeout-specific state
    old_timeout_next_play_type = gm.game_state.get("timeout_next_play_type")
    if "timeout_next_play_type" in saved:
        gm.game_state["timeout_next_play_type"] = saved["timeout_next_play_type"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] timeout_next_play_type: {old_timeout_next_play_type} → {saved['timeout_next_play_type']}")
        logging.info(f"🔄 TIMEOUT RESUME: Applied timeout_next_play_type={saved['timeout_next_play_type']}")
    
    if "timeout_offense_team_id" in saved:
        old_timeout_offense_team_id = gm.game_state.get("timeout_offense_team_id")
        gm.game_state["timeout_offense_team_id"] = saved["timeout_offense_team_id"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] timeout_offense_team_id: {old_timeout_offense_team_id} → {saved['timeout_offense_team_id']}")
    
    # Restore clock and time (critical for timeout resume)
    old_clock = gm.game_state.get("clock")
    if "clock" in saved:
        gm.game_state["clock"] = saved["clock"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] clock: {old_clock} → {saved['clock']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored clock={saved['clock']} from saved document")
    
    old_time_remaining = gm.game_state.get("time_remaining")
    if "time_remaining" in saved:
        gm.game_state["time_remaining"] = saved["time_remaining"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] time_remaining: {old_time_remaining} → {saved['time_remaining']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored time_remaining={saved['time_remaining']} from saved document")
    
    # ✅ CRITICAL FIX: Restore scores from saved document (overwrites stale in-memory scores)
    old_scores = dict(gm.score) if gm.score else {}
    if "score" in saved and isinstance(saved["score"], dict):
        # Restore scores for both teams
        for team_name, score_value in saved["score"].items():
            if team_name in gm.score:
                old_score = gm.score[team_name]
                gm.score[team_name] = score_value
                logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] score {team_name}: {old_score} → {score_value}")
                logging.info(f"🔄 TIMEOUT RESUME: Restored score {team_name}={score_value} from saved document")
    
    # ✅ CRITICAL FIX: Restore team fouls from saved document
    home_team_data = saved.get("home_team", {})
    away_team_data = saved.get("away_team", {})
    
    old_home_fouls = gm.home_team.team_fouls
    if "team_fouls" in home_team_data:
        gm.home_team.team_fouls = home_team_data["team_fouls"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] home team_fouls: {old_home_fouls} → {home_team_data['team_fouls']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored home team_fouls={home_team_data['team_fouls']} from saved document")
    
    old_away_fouls = gm.away_team.team_fouls
    if "team_fouls" in away_team_data:
        gm.away_team.team_fouls = away_team_data["team_fouls"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] away team_fouls: {old_away_fouls} → {away_team_data['team_fouls']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored away team_fouls={away_team_data['team_fouls']} from saved document")
    
    # ✅ CRITICAL FIX: Restore team timeouts from saved document
    old_home_timeouts = gm.home_team.timeouts
    if "timeouts" in home_team_data:
        gm.home_team.timeouts = home_team_data["timeouts"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] home timeouts: {old_home_timeouts} → {home_team_data['timeouts']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored home timeouts={home_team_data['timeouts']} from saved document")
    
    old_away_timeouts = gm.away_team.timeouts
    if "timeouts" in away_team_data:
        gm.away_team.timeouts = away_team_data["timeouts"]
        logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] away timeouts: {old_away_timeouts} → {away_team_data['timeouts']}")
        logging.info(f"🔄 TIMEOUT RESUME: Restored away timeouts={away_team_data['timeouts']} from saved document")
    
    # 🔍 DEBUG: Log state AFTER restore
    logging.warning(f"🔍 [TIMEOUT RESTORE DEBUG] AFTER restore - gm.score={gm.score}, clock={gm.game_state.get('clock')}, time_remaining={gm.game_state.get('time_remaining')}")

# 4. Routes
@app.get("/")
def root():
    print("🔵 [DEBUG] root endpoint: GET / called", file=sys.stderr, flush=True)
    return {"message": "GOB Simulation API is live"}

# Note: Health endpoint is registered at the top of the file (line 58) before CORS middleware
# This ensures it's available even if other initialization fails

# Note: FastAPI's CORSMiddleware automatically handles OPTIONS preflight requests
# We don't need an explicit OPTIONS handler - the middleware does this

@app.get("/teams")
def get_team_names():
    teams = teams_collection.find(
        {}, {"name": 1, "primary_color": 1, "secondary_color": 1, "_id": 0}
    )
    return sorted(
        [
            {
                "name": team.get("name"),
                "primary_color": team.get("primary_color"),
                "secondary_color": team.get("secondary_color"),
            }
            for team in teams
        ],
        key=lambda t: t["name"],
    )


@app.post("/api/simulate")
@app.post("/simulate")
def simulate_game(request: SimulationRequest):
    home_team = request.home_team
    away_team = request.away_team

    known_teams = [team["name"] for team in teams_collection.find({}, {"name": 1})]

    if home_team not in known_teams:
        raise HTTPException(status_code=400, detail=f"Unknown home_team: '{home_team}'")
    if away_team not in known_teams:
        raise HTTPException(status_code=400, detail=f"Unknown away_team: '{away_team}'")
    
    print("🔥 Simulate endpoint hit - BOOM!!")
    print(f"Home: {request.home_team}, Away: {request.away_team}")

    # ✅ Add this line to print the full request body
    # print("🔍 Full request body:", request)


    game = run_simulation(home_team, away_team, request.home_lineup, request.away_lineup)
    # print("Right before summarize_game_state")
    # print("🧪 Turns sample:", game.turns[:3])
    summary = summarize_game_state(game)

    # Build a consolidated score map from available sources
    score_map = summary.get("final_score") or summary.get("score") or {}

    # Ensure team objects exist for the frontend and populate scores
    summary["homeTeam"] = summary.get("homeTeam") or {
        "name": summary.get("home_team", home_team),
    }
    summary["homeTeam"]["score"] = score_map.get(summary["homeTeam"]["name"], 0)

    summary["awayTeam"] = summary.get("awayTeam") or {
        "name": summary.get("away_team", away_team),
    }
    summary["awayTeam"]["score"] = score_map.get(summary["awayTeam"]["name"], 0)

    # Expose the score map under a consistent key
    summary["score"] = score_map

    # ✅ Minimal debug visibility
    # print(f"✅ Game finished: {home_team} vs. {away_team}")
    # print(f"🏀 Final Score: {game.score}")
    # print(f"📊 Team Totals: {game.team_totals}")# show first few entries

    print("\n🔎 DEBUGGING SUMMARY BEFORE INSERT")
    pprint.pprint(summary)

    # Log keys and ensure no Player objects remain at the top level
    print("Summary top-level keys:", list(summary.keys()))
    for k, v in summary.items():
        if isinstance(v, Player):
            raise TypeError(f"Summary key '{k}' contains a Player instance")

    try:
        print("🔍 About to insert summary into Mongo...")
        inserted_id = games_collection.insert_one(summary).inserted_id
        summary["_id"] = str(inserted_id)
        # games_collection.insert_one(summary)
        # summary.pop("_id", None)
    except Exception as e:
        print("🚨 Mongo insert failed:", e)
        traceback.print_exc()
    
    print("Inside simulate_game()\nReturning summary keys:", summary.keys())

    return summary


@app.get("/api/game/{game_id}")
def get_game_state(game_id: str, quarter: int | None = None, source: str | None = None):
    # Fetch current game state for displaying accumulated stats and player energy
    # PERFORMANCE DIAGNOSTIC: This endpoint is instrumented with timing logs.
    # Args:
    #     game_id: Game ID
    #     quarter: Optional quarter query parameter. If quarter=1 and saved game is Q2+,
    #              returns empty stats (new game scenario)
    #     source: Optional source parameter. If "db", always reads from database (for lineup screen consistency).
    #             If None or "cache", uses ongoing_games cache if available (for performance during gameplay).
    import time
    endpoint_start = time.time()
    
    try:
        # ✅ HYBRID APPROACH: If source=db, skip cache and always read from database
        # This ensures lineup screen always gets fresh data (only ~13 reads per game: timeouts + quarter breaks)
        # During active gameplay, source is not specified, so we use cache for performance
        force_db_read = source == "db"
        
        # Check ongoing games first (unless forcing DB read)
        gm = None
        if not force_db_read:
            gm = ongoing_games.get(game_id)
        
        if gm:
            # ✅ PERFORMANCE DIAGNOSTIC: Log in-memory path and measure processing time
            process_start = time.time()
            logging.warning(f"⏱️ [PERF] /api/game/{game_id} - Using in-memory game (no DB query)")
            # Get players with current energy levels, stats, and attributes
            # Include ALL players (not just lineup) so roster merge works correctly
            players = []
            for team in [gm.home_team, gm.away_team]:
                # Get all players (lineup + bench) so all roster players can be matched
                for player in team.get_all_players():
                    players.append({
                        "_id": player.player_id,
                        "name": player.name,
                        "NG": player.attributes.get("NG", 1.0),
                        "team": team.name,
                        "stats": player.stats.get("game", {}),  # ✅ Add game stats
                        "attributes": {  # ✅ Add attributes (EM, MO, CH, NG)
                            "EM": player.attributes.get("EM", 50),
                            "MO": player.attributes.get("MO", 0),
                            "CH": player.attributes.get("CH", 50),
                            "NG": player.attributes.get("NG", 1.0)
                        }
                    })
            
            # Build team_stats structure (for S2 tab - playcall stats)
            team_stats = {
                gm.home_team.name: {
                    "offense": gm.home_team.scouting_data.get("offense", {}),
                    "defense": gm.home_team.scouting_data.get("defense", {})
                },
                gm.away_team.name: {
                    "offense": gm.away_team.scouting_data.get("offense", {}),
                    "defense": gm.away_team.scouting_data.get("defense", {})
                }
            }
            
            # ✅ PERFORMANCE DIAGNOSTIC: Log processing time for in-memory path
            process_time = (time.time() - process_start) * 1000  # Convert to ms
            logging.warning(f"⏱️ [PERF] /api/game/{game_id} - In-memory processing: {process_time:.2f}ms")
            
            response_data = {
                "game_id": game_id,
                "score": gm.score,
                "box_score": gm.get_box_score(),
                "quarter": gm.quarter,
                "clock": gm.game_state.get("clock", "8:00"),
                "players": players,
                # Team-level stats (for S1/S2/S3 tabs and scoreboard)
                "team_totals": gm.team_totals,
                "team_stats": team_stats,  # Playcall stats for S2 tab
                "points_by_quarter": gm.game_state.get("points_by_quarter", {}),
                "home_team": {
                    "name": gm.home_team.name,
                    "team_fouls": gm.home_team.team_fouls,
                    "timeouts": getattr(gm.home_team, 'timeouts', 4),
                    "attributes": gm.home_team.team_attributes  # Team attributes for S3 tab
                },
                "away_team": {
                    "name": gm.away_team.name,
                    "team_fouls": gm.away_team.team_fouls,
                    "timeouts": getattr(gm.away_team, 'timeouts', 4),
                    "attributes": gm.away_team.team_attributes  # Team attributes for S3 tab
                }
            }
            response_size = len(json.dumps(response_data))
            total_time = (time.time() - endpoint_start) * 1000
            logging.warning(f"⏱️ [PERF] /api/game/{game_id} - In-memory path: processing: {process_time:.2f}ms, response_size: {response_size} bytes, total: {total_time:.2f}ms")
            return response_data
        
        # Check database
        if games_collection is not None:
            # 🔍 DEBUG: Log when reading from DB (for lineup screen)
            if force_db_read:
                logging.warning(f"🔍 [GET_GAME_STATE DEBUG] Reading from DB (source=db) - game_id={game_id}, quarter={quarter}")
            # ✅ PERFORMANCE: Use projection to only load needed fields (80-95% reduction in data transfer)
            # Fields needed: players (energy/stats), ineligible_players, score, box_score, quarter, clock,
            # teams (name, team_id, box_score, totals, scouting, attributes, colors, score, timeouts, team_fouls, points_by_quarter),
            # home_team_id, away_team_id, team_totals, team_stats, points_by_quarter
            # NOT needed: turns (already empty), text_log, teams[].plays, teams[].strategy_settings, teams[].playbook_settings
            projection = {
                "players": 1,              # Player energy, stats, attributes
                "ineligible_players": 1,   # Fouled out players
                "score": 1,                # Current score
                "box_score": 1,            # Box score (may be in teams object, but include for backward compatibility)
                "quarter": 1,              # Current quarter
                "clock": 1,                # Game clock
                "home_team_id": 1,         # For unified teams structure
                "away_team_id": 1,         # For unified teams structure
                "teams": 1,                # Teams object (will project nested fields if needed)
                "points_by_quarter": 1,    # Points by quarter (may be in teams object, but include for backward compatibility)
                "_id": 1
            }
            
            # ✅ PERFORMANCE DIAGNOSTIC: Measure database query time
            import time
            query_start = time.time()
            
            # Try both string and ObjectId lookups with projection
            saved = games_collection.find_one({"_id": game_id}, projection)
            if not saved and isinstance(game_id, str):
                try:
                    saved = games_collection.find_one({"_id": ObjectId(game_id)}, projection)
                except Exception as e:
                    # Only log actual errors
                    pass
            
            query_time = (time.time() - query_start) * 1000  # Convert to ms
            doc_size = len(str(saved)) if saved else 0
            logging.warning(f"⏱️ [PERF] /api/game/{game_id} - DB query: {query_time:.2f}ms, doc_size: {doc_size} bytes")
            
            if saved:
                # 🔍 DEBUG: Log what's being read from DB
                if force_db_read:
                    logging.warning(f"🔍 [GET_GAME_STATE DEBUG] DB document - quarter={saved.get('quarter')}, clock={saved.get('clock')}, time_remaining={saved.get('time_remaining')}")
                    logging.warning(f"🔍 [GET_GAME_STATE DEBUG] DB document - score={saved.get('score')}, timeout_next_play_type={saved.get('timeout_next_play_type')}")
                
                saved_quarter = saved.get("quarter", 1)
                
                # Check if this is a "new game" scenario: user requesting Q1 but saved game is Q2+
                # In this case, return empty stats (Lineup Screen loads before simulate-quarter detects new game)
                is_new_game_from_get = (quarter == 1 and saved_quarter > 1)
                if is_new_game_from_get:
                    logging.info(
                        f"🆕 /api/game/{game_id} - New game: requested Q1 but saved game is Q{saved_quarter}. Returning empty stats."
                    )
                    # Return empty game state structure (energy levels, but no stats/scores)
                    home_team_data = saved.get("home_team", {})
                    away_team_data = saved.get("away_team", {})
                    
                    # Extract players with energy but no stats
                    players = saved.get("players", [])
                    players_with_energy = []
                    for p in players:
                        player_data = {
                            "_id": p.get("playerId") or p.get("player_id"),
                            "name": p.get("name"),
                            "NG": p.get("NG", 1.0),
                            "team": p.get("team"),
                            "stats": {},  # Empty stats for new game
                            "attributes": p.get("attributes", {})  # ✅ Add attributes (EM, MO, CH, NG) from saved doc
                        }
                        players_with_energy.append(player_data)
                    
                    # Return empty stats structure
                    response_data = {
                        "game_id": game_id,
                        "score": {home_team_data.get("name", ""): 0, away_team_data.get("name", ""): 0},
                        "box_score": {},
                        "quarter": 1,
                        "clock": "12:00",
                        "players": players_with_energy,
                        "team_totals": {
                            home_team_data.get("name", ""): {},
                            away_team_data.get("name", ""): {}
                        },
                        "team_stats": {
                            home_team_data.get("name", ""): {"offense": {}, "defense": {}},
                            away_team_data.get("name", ""): {"offense": {}, "defense": {}}
                        },
                        "points_by_quarter": {
                            home_team_data.get("name", ""): [0, 0, 0, 0],
                            away_team_data.get("name", ""): [0, 0, 0, 0]
                        },
                        "home_team": {
                            "name": home_team_data.get("name", ""),
                            "team_fouls": 0,
                            "attributes": home_team_data.get("attributes", {})
                        },
                        "away_team": {
                            "name": away_team_data.get("name", ""),
                            "team_fouls": 0,
                            "attributes": away_team_data.get("attributes", {})
                        }
                    }
                    response_size = len(json.dumps(response_data))
                    total_time = (time.time() - endpoint_start) * 1000
                    logging.warning(f"⏱️ [PERF] /api/game/{game_id} - New game path: response_size: {response_size} bytes, total: {total_time:.2f}ms")
                    return response_data
                
                # Extract player energy, stats, and attributes from saved game doc
                players = saved.get("players", [])
                # Map to include NG, stats, and attributes if available
                players_with_energy = []
                for p in players:
                    player_data = {
                        "_id": p.get("playerId") or p.get("player_id"),
                        "name": p.get("name"),
                        "NG": p.get("NG", 1.0),  # May be saved in game doc
                        "team": p.get("team"),
                        "stats": p.get("stats", {}),  # ✅ Add stats from saved doc
                        "attributes": p.get("attributes", {})  # ✅ Add attributes (EM, MO, CH, NG) from saved doc
                    }
                    players_with_energy.append(player_data)
                
                # ✅ UNIFIED STRUCTURE: Extract team data from teams object using home_team_id/away_team_id
                teams_obj = saved.get("teams", {})
                home_team_id = saved.get("home_team_id")
                away_team_id = saved.get("away_team_id")
                
                # Get team data from unified teams object
                home_team_data = teams_obj.get(home_team_id, {}) if home_team_id else {}
                away_team_data = teams_obj.get(away_team_id, {}) if away_team_id else {}
                
                # Fallback: if teams object is empty or structure is old, try old structure (backward compatibility)
                if not home_team_data and saved.get("home_team"):
                    home_team_data = saved.get("home_team", {})
                    logging.warning(f"⚠️ Using legacy home_team structure (teams object not found)")
                if not away_team_data and saved.get("away_team"):
                    away_team_data = saved.get("away_team", {})
                    logging.warning(f"⚠️ Using legacy away_team structure (teams object not found)")
                
                # Extract scouting data from teams object (contains playcall stats for S2 tab)
                home_scouting = home_team_data.get("scouting", {})
                away_scouting = away_team_data.get("scouting", {})
                
                # Build team_stats structure (for S2 tab - playcall stats)
                team_stats = {
                    home_team_data.get("name"): {
                        "offense": home_scouting.get("offense", {}),
                        "defense": home_scouting.get("defense", {})
                    },
                    away_team_data.get("name"): {
                        "offense": away_scouting.get("offense", {}),
                        "defense": away_scouting.get("defense", {})
                    }
                }
                
                # Build box_score from nested structure (unified structure stores it in teams[team_id].box_score)
                box_score = saved.get("box_score", {})
                if not box_score:
                    # Build from unified teams structure
                    home_team_name = home_team_data.get("name")
                    away_team_name = away_team_data.get("name")
                    if home_team_name and "box_score" in home_team_data:
                        box_score[home_team_name] = home_team_data.get("box_score", {})
                    if away_team_name and "box_score" in away_team_data:
                        box_score[away_team_name] = away_team_data.get("box_score", {})
                
                # ✅ UNIFIED STRUCTURE: Return unified teams object structure
                # Frontend should read from teams[home_team_id]/teams[away_team_id]
                # Keeping backward compatibility home_team/away_team for now (built from teams object)
                response_data = {
                    "game_id": game_id,
                    "score": saved.get("score", {}),
                    "box_score": box_score,
                    "quarter": saved.get("quarter", 1),
                    "clock": saved.get("clock", "8:00"),
                    "players": players_with_energy,
                    # Team IDs for unified structure access
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    # Unified teams object (single source of truth)
                    "teams": teams_obj,
                    # Team-level stats (for S1/S2/S3 tabs and scoreboard)
                    "team_totals": {
                        home_team_data.get("name"): home_team_data.get("totals", {}),
                        away_team_data.get("name"): away_team_data.get("totals", {})
                    },
                    "team_stats": team_stats,  # Playcall stats for S2 tab
                    "points_by_quarter": {
                        home_team_data.get("name"): home_team_data.get("points_by_quarter", [0, 0, 0, 0]),
                        away_team_data.get("name"): away_team_data.get("points_by_quarter", [0, 0, 0, 0])
                    },
                    # ✅ BACKWARD COMPATIBILITY: Keep home_team/away_team in response (built from teams object)
                    # TODO: Remove these after frontend is updated to use teams[home_team_id]/teams[away_team_id]
                    "home_team": {
                        "name": home_team_data.get("name"),
                        "team_fouls": home_team_data.get("team_fouls", 0),
                        "attributes": home_team_data.get("attributes", {}),  # Team attributes for S3 tab
                        "colors": home_team_data.get("colors", {}),
                        "score": home_team_data.get("score", 0),
                        "timeouts": home_team_data.get("timeouts", 4),
                        "points_by_quarter": home_team_data.get("points_by_quarter", [0, 0, 0, 0]),
                        "box_score": home_team_data.get("box_score", {}),
                        "totals": home_team_data.get("totals", {})
                    },
                    "away_team": {
                        "name": away_team_data.get("name"),
                        "team_fouls": away_team_data.get("team_fouls", 0),
                        "attributes": away_team_data.get("attributes", {}),  # Team attributes for S3 tab
                        "colors": away_team_data.get("colors", {}),
                        "score": away_team_data.get("score", 0),
                        "timeouts": away_team_data.get("timeouts", 4),
                        "points_by_quarter": away_team_data.get("points_by_quarter", [0, 0, 0, 0]),
                        "box_score": away_team_data.get("box_score", {}),
                        "totals": away_team_data.get("totals", {})
                    }
                }
                response_size = len(json.dumps(response_data))
                total_time = (time.time() - endpoint_start) * 1000
                logging.warning(f"⏱️ [PERF] /api/game/{game_id} - DB path: query: {query_time:.2f}ms, response_size: {response_size} bytes, total: {total_time:.2f}ms")
                return response_data
        
            logging.error(f"❌ [BOX_SCORE] Game not found in database: game_id={game_id}")
            # Try to find any games with similar IDs for debugging
            if isinstance(game_id, str) and len(game_id) > 10:
                similar = list(games_collection.find({"_id": {"$regex": game_id[:10]}}).limit(5))
                logging.info(f"🔍 [BOX_SCORE] Found {len(similar)} similar game IDs (first 10 chars): {[str(g.get('_id')) for g in similar]}")
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logging.exception(f"Error fetching game state for {game_id}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # ✅ PERFORMANCE DIAGNOSTIC: Log total endpoint time (if not already logged)
        if 'endpoint_start' in locals() and 'response_size' not in locals():
            total_time = (time.time() - endpoint_start) * 1000  # Convert to ms
            logging.warning(f"⏱️ [PERF] /api/game/{game_id} - Total endpoint time: {total_time:.2f}ms")

@app.post("/api/simulate-quarter")
def simulate_quarter_endpoint(request: QuarterSimulationRequest, debug: bool = False):
    import time
    start_time = time.time()
    game_id = request.game_id
    # ✅ PERFORMANCE: Removed debug logging - only log errors and critical events
    if debug:
        logging.debug(
            "simulate_quarter_endpoint request detail: %s",
            {
                "game_id": game_id,
                "home_team": request.home_team,
                "away_team": request.away_team,
                "quarter": request.quarter,
            },
        )
    source = "resume"
    # ✅ SS&S: Preserve user_team_side from in-memory game BEFORE any DB operations
    # This ensures user_team_side persists even if it's not in the saved document or request
    preserved_user_team_side = None
    if game_id:
        gm = ongoing_games.get(game_id)
        # ✅ DEBUG: Track ongoing_games state at start of simulate_quarter_endpoint
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] simulate_quarter_endpoint START: game_id={game_id}, full_sim={request.full_sim}, quarter={request.quarter}")
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game in ongoing_games: {gm is not None}")
        if gm:
            logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game object found - object_id={id(gm)}, current_quarter={gm.quarter}")
            # Preserve user_team_side from in-memory game
            if gm.game_state.get("user_team_side"):
                preserved_user_team_side = gm.game_state.get("user_team_side")
                logging.warning(f"✅ [USER_TEAM_SIDE] Preserved from in-memory game: {preserved_user_team_side}")
        else:
            logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game NOT in ongoing_games - will load from DB. Available games: {list(ongoing_games.keys())}")
        if gm is not None and (
            request.home_team != gm.home_team.name
            or request.away_team != gm.away_team.name
        ):
            if debug:
                logging.debug(
                    "simulate_quarter_endpoint team mismatch: game_id=%s expected=%s vs %s got=%s vs %s",
                    game_id,
                    gm.home_team.name,
                    gm.away_team.name,
                    request.home_team,
                    request.away_team,
                )
            raise HTTPException(
                status_code=400,
                detail="game_id belongs to a different matchup",
            )
        # Check if this is a "new game" scenario: user wants Q1 but saved game is Q2+
        # In this case, remove from memory and reload from DB (which will run new game detection)
        if gm is not None and request.quarter == 1 and gm.quarter > 1:
            logging.info(
                f"🆕 New game: game_id={game_id} in memory at Q{gm.quarter}, but user requested Q1. Removing from memory to reload from DB."
            )
            logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ⚠️ Removing game from ongoing_games (new game scenario): game_id={game_id}")
            del ongoing_games[game_id]
            gm = None  # Force reload from DB where new game detection will run
        
        # ✅ SS&S: Ensure user_team_side is set in in-memory game if missing
        # This fixes the case where user_team_side was never set or was lost
        if gm is not None and not gm.game_state.get("user_team_side"):
            if request.user_team_side:
                gm.game_state["user_team_side"] = request.user_team_side
                logging.warning(f"✅ [USER_TEAM_SIDE] Set in in-memory game from request: {request.user_team_side}")
            elif preserved_user_team_side:
                gm.game_state["user_team_side"] = preserved_user_team_side
                logging.warning(f"✅ [USER_TEAM_SIDE] Set in in-memory game from preserved value: {preserved_user_team_side}")
            else:
                logging.warning(f"⚠️ [USER_TEAM_SIDE] In-memory game missing user_team_side and no request/preserved value - override checking will not work!")
        
        # ✅ CRITICAL FIX: If game is already in memory, update strategy_settings if request has them
        # This ensures user's updated Game Plan settings are applied even if game is already loaded
        if gm is not None and request.strategy_settings and request.user_team_side:
            try:
                # Ensure strategy_settings is a dict before copying
                if not isinstance(request.strategy_settings, dict):
                    logging.error(f"⚠️ [STRATEGY SETTINGS] request.strategy_settings is not a dict: {type(request.strategy_settings)}")
                else:
                    if request.user_team_side == "home":
                        old_hct = gm.home_team.strategy_settings.get('hc_trap', 'MISSING') if hasattr(gm.home_team, 'strategy_settings') and gm.home_team.strategy_settings else 'MISSING'
                        old_fcp = gm.home_team.strategy_settings.get('fc_press', 'MISSING') if hasattr(gm.home_team, 'strategy_settings') and gm.home_team.strategy_settings else 'MISSING'
                        gm.home_team.strategy_settings = dict(request.strategy_settings)  # Use dict() constructor for safety
                        new_hct = request.strategy_settings.get('hc_trap', 'MISSING')
                        new_fcp = request.strategy_settings.get('fc_press', 'MISSING')
                        # ✅ COMMENTED OUT: Strategy settings logs (cluttering transition debugging)
                        # logging.warning(f"🔧 [STRATEGY SETTINGS] Updated home team (IN MEMORY) - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                        # logging.warning(f"   - Full strategy_settings: {gm.home_team.strategy_settings}")
                    elif request.user_team_side == "away":
                        old_hct = gm.away_team.strategy_settings.get('hc_trap', 'MISSING') if hasattr(gm.away_team, 'strategy_settings') and gm.away_team.strategy_settings else 'MISSING'
                        old_fcp = gm.away_team.strategy_settings.get('fc_press', 'MISSING') if hasattr(gm.away_team, 'strategy_settings') and gm.away_team.strategy_settings else 'MISSING'
                        gm.away_team.strategy_settings = dict(request.strategy_settings)  # Use dict() constructor for safety
                        new_hct = request.strategy_settings.get('hc_trap', 'MISSING')
                        new_fcp = request.strategy_settings.get('fc_press', 'MISSING')
                        # ✅ COMMENTED OUT: Strategy settings logs (cluttering transition debugging)
                        # logging.warning(f"🔧 [STRATEGY SETTINGS] Updated away team (IN MEMORY) - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                        # logging.warning(f"   - Full strategy_settings: {gm.away_team.strategy_settings}")
            except Exception as e:
                logging.error(f"❌ [STRATEGY SETTINGS] Error updating strategy_settings: {e}", exc_info=True)
        
        # ✅ TIMEOUT RESUME: Unified state restoration (works for all modes and all paths)
        # Only check database for timeout state if we have a game_id (existing game, not new game start)
        # Always check database for timeout state if we have a game_id
        # The database is the source of truth - if timeout_next_play_type exists, we're resuming from timeout
        # Validation (quarter match, etc.) happens later when applying the state
        timeout_saved_state = None
        # ✅ PERFORMANCE: Removed debug logging - only log errors
        
        # Check for timeout state if we have a game_id (existing game)
        # Don't skip Q1 - we could be resuming from a timeout in Q1!
        # The restore_timeout_resume_state function will validate quarter match to prevent stale data
        if game_id:
            timeout_saved_state = restore_timeout_resume_state(game_id, request, games_collection)
        
        if timeout_saved_state:
            # Validate quarter match to prevent stale data from affecting new games
            saved_quarter = timeout_saved_state.get("quarter", 0)
            timeout_next_play_type = timeout_saved_state.get("timeout_next_play_type")
            
            if timeout_next_play_type and saved_quarter == request.quarter:
                logging.info(f"✅ TIMEOUT RESUME: Found valid timeout state in DB, timeout_next_play_type={timeout_next_play_type}, quarter={saved_quarter}")
                # Override request.resume_from_timeout to ensure simulate_quarter() handles timeout resume
                request.resume_from_timeout = True
                logging.info(f"✅ TIMEOUT RESUME: Detected valid timeout state in DB, setting resume_from_timeout=True for simulate_quarter()")
                # ✅ CRITICAL FIX: Always force reload from DB when resuming from timeout
                # This ensures we use the latest saved state, not stale in-memory state
                # This fixes the bug where computer timeout → user timeout shows stale data
                if gm is not None:
                    logging.warning(f"🔍 TIMEOUT RESUME: Game in memory, but forcing DB reload to ensure latest state (game_id={game_id})")
                    del ongoing_games[game_id]
                    gm = None  # Force reload from DB
                logging.info(f"🔍 TIMEOUT RESUME: Will load fresh game from DB and apply timeout state")
            else:
                # Stale timeout data (quarter mismatch or missing next_play_type) - ignore it
                # logging.warning(f"⚠️ TIMEOUT RESUME: Found timeout state but quarter mismatch or missing next_play_type - treating as normal game (saved_quarter={saved_quarter}, requested_quarter={request.quarter}, next_play_type={timeout_next_play_type})")
                timeout_saved_state = None  # Clear invalid timeout state
                # ✅ QUARTER BREAK: Clear resume_from_timeout flag if no valid timeout state
                # This handles cases where resume_from_timeout was incorrectly preserved across quarter boundaries
                if request.resume_from_timeout:
                    logging.warning(f"⚠️ QUARTER BREAK: Clearing invalid resume_from_timeout flag (no valid timeout state for quarter {request.quarter})")
                    request.resume_from_timeout = False
        else:
            if request.resume_from_timeout:
                logging.warning(f"⚠️ TIMEOUT RESUME: URL has resume_from_timeout=true but no timeout state found in DB for game_id={game_id} - treating as normal quarter start")
                # ✅ QUARTER BREAK: Clear resume_from_timeout flag if no timeout state in DB
                # This handles cases where resume_from_timeout was incorrectly preserved across quarter boundaries
                request.resume_from_timeout = False
            else:
                # ✅ PERFORMANCE: Removed debug logging
                pass
        
        if gm is None:
            logging.warning(
                "simulate_quarter_endpoint unknown game_id=%s; active=%s",
                game_id,
                list(ongoing_games.keys()),
            )
            if games_collection is not None:
                logging.warning(
                    "🔍 simulate_quarter_endpoint querying DB for game_id=%s", game_id
                )
            else:
                logging.warning(
                    "🔍 simulate_quarter_endpoint skipping DB lookup for game_id=%s; no collection",
                    game_id,
                )
            saved = (
                games_collection.find_one({"_id": game_id})
                if games_collection is not None
                else None
            )
            if saved:
                try:
                    # ✅ UNIFIED STRUCTURE: Get team IDs from top level (unified structure)
                    home_team_id = saved.get("home_team_id")
                    away_team_id = saved.get("away_team_id")
                    teams_obj = saved.get("teams", {})
                    
                    # Get team data from unified teams object
                    home_team_data = teams_obj.get(home_team_id, {}) if home_team_id and teams_obj else {}
                    away_team_data = teams_obj.get(away_team_id, {}) if away_team_id and teams_obj else {}
                    
                    # Extract team names from teams object
                    home = home_team_data.get("name") if home_team_data else None
                    away = away_team_data.get("name") if away_team_data else None
                    
                    # ✅ BACKWARD COMPATIBILITY: Fallback to old structure if unified structure not found
                    if not home_team_data:
                        home_team_field = saved.get("home_team")
                        if isinstance(home_team_field, dict):
                            home = home_team_field.get("name") or home
                            if not home_team_id:
                                home_team_id = home_team_field.get("team_id")
                            # Use old structure data as fallback
                            home_team_data = home_team_field
                        elif isinstance(home_team_field, str):
                            home = home_team_field or home
                    
                    if not away_team_data:
                        away_team_field = saved.get("away_team")
                        if isinstance(away_team_field, dict):
                            away = away_team_field.get("name") or away
                            if not away_team_id:
                                away_team_id = away_team_field.get("team_id")
                            # Use old structure data as fallback
                            away_team_data = away_team_field
                        elif isinstance(away_team_field, str):
                            away = away_team_field or away
                    
                    if home and away:
                        # ✅ Extract team data from teams object (or fallback old structure)
                        home_plays = home_team_data.get("plays")
                        away_plays = away_team_data.get("plays")
                        home_attrs = home_team_data.get("attributes")
                        away_attrs = away_team_data.get("attributes")
                        home_scouting = home_team_data.get("scouting")
                        away_scouting = away_team_data.get("scouting")
                        home_strategy = home_team_data.get("strategy_settings")
                        away_strategy = away_team_data.get("strategy_settings")  # Fixed: was reading from home_team_data
                        # ✅ SS&S: Restore strategy_calls (playcall overrides) from database
                        home_strategy_calls = home_team_data.get("strategy_calls")
                        away_strategy_calls = away_team_data.get("strategy_calls")
                        # ✅ FIX: Extract playbook_settings from game document when resuming
                        # This ensures playbook_settings are available when resuming games (Q2-Q4)
                        home_playbook_settings = home_team_data.get("playbook_settings", {})
                        away_playbook_settings = away_team_data.get("playbook_settings", {})
                        
                        # Fallback to old flat structure if teams object doesn't exist (backwards compatibility)
                        if not home_plays and not teams_obj:
                            home_plays = saved.get("team_plays", {}).get(home)
                            away_plays = saved.get("team_plays", {}).get(away)
                            home_attrs = saved.get("team_attributes", {}).get(home)
                            away_attrs = saved.get("team_attributes", {}).get(away)
                            home_scouting = saved.get("scouting", {}).get(home)
                            away_scouting = saved.get("scouting", {}).get(away)
                        
                        # ✅ CRITICAL FIX: Always prioritize request.strategy_settings over DB for user's team
                        # This ensures user's current settings (from Game Plan screen) are applied, even if DB has old/wrong settings
                        # This fixes Q1 issues where DB might have tempo=1 but user set tempo=4
                        if request.strategy_settings and request.user_team_side:
                            try:
                                # Ensure strategy_settings is a dict
                                if not isinstance(request.strategy_settings, dict):
                                    logging.error(f"⚠️ [STRATEGY SETTINGS] request.strategy_settings is not a dict: {type(request.strategy_settings)}")
                                else:
                                    if request.user_team_side == "home":
                                        old_hct = home_strategy.get('hc_trap', 'MISSING') if home_strategy else 'MISSING'
                                        old_fcp = home_strategy.get('fc_press', 'MISSING') if home_strategy else 'MISSING'
                                        if home_strategy is None:
                                            home_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                            logging.warning(f"🔧 [STRATEGY SETTINGS] FALLBACK (DB LOAD) - Using request.strategy_settings for home team (DB had None)")
                                        else:
                                            # DB has settings, but prioritize request (user's current settings from Game Plan screen)
                                            home_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                            logging.warning(f"🔧 [STRATEGY SETTINGS] OVERRIDE (DB LOAD) - Using request.strategy_settings for home team")
                                        new_hct = request.strategy_settings.get('hc_trap', 'MISSING')
                                        new_fcp = request.strategy_settings.get('fc_press', 'MISSING')
                                        logging.warning(f"   - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                                        logging.warning(f"   - Full strategy_settings: {home_strategy}")
                                    elif request.user_team_side == "away":
                                        old_hct = away_strategy.get('hc_trap', 'MISSING') if away_strategy else 'MISSING'
                                        old_fcp = away_strategy.get('fc_press', 'MISSING') if away_strategy else 'MISSING'
                                        if away_strategy is None:
                                            away_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                            logging.warning(f"🔧 [STRATEGY SETTINGS] FALLBACK (DB LOAD) - Using request.strategy_settings for away team (DB had None)")
                                        else:
                                            # DB has settings, but prioritize request (user's current settings from Game Plan screen)
                                            away_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                            logging.warning(f"🔧 [STRATEGY SETTINGS] OVERRIDE (DB LOAD) - Using request.strategy_settings for away team")
                                        new_hct = request.strategy_settings.get('hc_trap', 'MISSING')
                                        new_fcp = request.strategy_settings.get('fc_press', 'MISSING')
                                        logging.warning(f"   - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                                        logging.warning(f"   - Full strategy_settings: {away_strategy}")
                            except Exception as e:
                                logging.error(f"❌ [STRATEGY SETTINGS] Error processing strategy_settings from request: {e}", exc_info=True)
                        
                        # Debug logging removed - was cluttering logs
                        # logging.debug(f"🔧 LOADING FROM DB - home_strategy={home_strategy}, away_strategy={away_strategy}")
                        
                        gm = GameManager(
                            home, 
                            away,
                            home_strategy_settings=home_strategy,
                            away_strategy_settings=away_strategy,
                            home_team_attributes=home_attrs,
                            away_team_attributes=away_attrs,
                            home_scouting_data=home_scouting,
                            away_scouting_data=away_scouting,
                            home_plays_data=home_plays,
                            away_plays_data=away_plays,
                            home_strategy_calls=home_strategy_calls,  # ✅ SS&S: Restore playcall overrides
                            away_strategy_calls=away_strategy_calls,  # ✅ SS&S: Restore playcall overrides
                            mode="single",  # Loaded games are always single mode from games_collection
                            user_team_side=request.user_team_side  # ✅ SS&S: Set is_user_team flags
                        )
                        
                        # Debug logging removed - was cluttering logs
                        # logging.debug(f"🔧 AFTER GAMEMANAGER - home.strategy_settings={gm.home_team.strategy_settings.get('tempo', 'MISSING')}, away.strategy_settings={gm.away_team.strategy_settings.get('tempo', 'MISSING')}")
                        # CRITICAL: Don't reset game_state when loading from database
                        # The GameManager constructor already initialized game_state with defaults
                        # Resetting it here wipes out FREE_THROW state that might be set during active gameplay
                        # Only update quarter - game_state is already initialized by GameManager.__init__
                        saved_quarter = saved.get("quarter", 1)
                        gm.quarter = saved_quarter
                        # 🔍 DEBUG: Log quarter mismatch
                        logging.warning(f"🔍 [QUARTER_DEBUG] Loaded from DB: saved_quarter={saved_quarter}, request.quarter={request.quarter}, gm.quarter set to={gm.quarter}")
                        if saved_quarter != request.quarter:
                            logging.warning(f"🔍 [QUARTER_DEBUG] ⚠️ QUARTER MISMATCH: saved_quarter ({saved_quarter}) != request.quarter ({request.quarter})")
                        
                        # ✅ SS&S: Restore user_team_side to game_state (persists override checking across game loads)
                        # Priority: 1) Saved document, 2) Preserved from in-memory, 3) Request, 4) Warn
                        if "user_team_side" in saved:
                            gm.game_state["user_team_side"] = saved["user_team_side"]
                            logging.warning(f"✅ Restored user_team_side from DB: {saved['user_team_side']}")
                        elif preserved_user_team_side:
                            gm.game_state["user_team_side"] = preserved_user_team_side
                            logging.warning(f"✅ Restored user_team_side from preserved in-memory value: {preserved_user_team_side}")
                        elif request.user_team_side:
                            gm.game_state["user_team_side"] = request.user_team_side
                            logging.warning(f"✅ Set user_team_side from request: {request.user_team_side}")
                        else:
                            logging.warning(f"⚠️ No user_team_side found in DB, preserved memory, or request - override checking will not work!")
                        
                        # 🔍 DEBUG: Log offense_play_type in saved state (if present)
                        if "offense_play_type" in saved:
                            gm.game_state["offense_play_type"] = saved["offense_play_type"]
                            logging.warning(f"🔍 [GAME LOAD DEBUG] Restored offense_play_type from DB: '{saved['offense_play_type']}'")
                        else:
                            logging.warning(f"🔍 [GAME LOAD DEBUG] offense_play_type NOT in saved state (will be set by set_playcalls())")
                        
                        # ✅ TIMEOUT RESUME: Check for timeout state BEFORE calculating should_restore_stats
                        # This ensures scores/fouls are restored when resuming from timeout
                        # Check if timeout state exists in saved document (regardless of URL parameter)
                        has_timeout_state = "timeout_next_play_type" in saved and saved.get("timeout_next_play_type") is not None
                        if has_timeout_state and saved_quarter == request.quarter:
                            # Timeout state found - ensure resume_from_timeout is set
                            if not request.resume_from_timeout:
                                request.resume_from_timeout = True
                                # ✅ PERFORMANCE: Removed debug logging
                        
                        # ✅ TIMEOUT RESUME: Check for timeout state in saved document BEFORE calculating should_restore_stats
                        # This ensures scores/fouls are restored when resuming from timeout
                        # Check if timeout state exists in saved document (regardless of URL parameter or timeout_saved_state)
                        has_timeout_state = "timeout_next_play_type" in saved and saved.get("timeout_next_play_type") is not None
                        if has_timeout_state and saved_quarter == request.quarter:
                            # Timeout state found in saved document - ensure resume_from_timeout is set
                            if not request.resume_from_timeout:
                                request.resume_from_timeout = True
                                # ✅ PERFORMANCE: Removed debug logging
                        
                        # Simple check: If requesting Q1 but saved game is at a later quarter, start fresh (new game)
                        # ✅ TIMEOUT: If resuming from timeout, always restore stats (we're continuing an existing game)
                        is_new_game = (request.quarter == 1 and saved_quarter > 1) and not request.resume_from_timeout
                        should_restore_stats = not is_new_game or request.resume_from_timeout
                        
                        # CRITICAL: Build lineups BEFORE restoring player stats
                        # Player stat restoration (below) looks up players in team.lineup, so lineups must exist
                        # If request has lineups, use them; otherwise build from MongoDB
                        if request.home_lineup:
                            from BackEnd.utils.db_utils import assign_lineup_from_ids
                            gm.home_team.lineup = assign_lineup_from_ids(gm.home_team, request.home_lineup)
                            # ✅ PERFORMANCE: Removed debug logging
                        elif not gm.home_team.lineup:
                            from BackEnd.utils.db_utils import build_lineup_from_mongo
                            gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
                        
                        if request.away_lineup:
                            from BackEnd.utils.db_utils import assign_lineup_from_ids
                            gm.away_team.lineup = assign_lineup_from_ids(gm.away_team, request.away_lineup)
                        elif not gm.away_team.lineup:
                            from BackEnd.utils.db_utils import build_lineup_from_mongo
                            gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)
                        
                        # Validate lineups are set
                        if not gm.home_team.lineup or not gm.away_team.lineup:
                            logging.error(f"❌ Loaded from DB: Lineups still empty after building. home_keys={list(gm.home_team.lineup.keys()) if gm.home_team.lineup else 'EMPTY'}, away_keys={list(gm.away_team.lineup.keys()) if gm.away_team.lineup else 'EMPTY'}")
                        
                        # Note: game_state is NOT persisted to database (it's in-memory only)
                        # So we can't restore offensive_state, free_throws, etc. from saved document
                        # But we also shouldn't reset them - they're set during turn simulation
                        # The default game_state from _init_game_state() is fine for a fresh load
                        
                        # Restore player stats and NG (energy) from saved game state
                        # Only restore if this is NOT a new Q1 game (fresh start)
                        # Players are stored as an array: [{"playerId": "...", "team": "home", "stats": {...}, "attributes": {...}}]
                        if should_restore_stats:
                            saved_players_list = saved.get("players", [])
                            # ✅ PERFORMANCE: Removed debug logging
                        else:
                            saved_players_list = []
                        
                        for saved_player_data in saved_players_list:
                            player_id = saved_player_data.get("playerId")
                            team_key = saved_player_data.get("team")  # "home" or "away"
                            
                            if not player_id or not team_key:
                                continue
                            
                            team = gm.home_team if team_key == "home" else gm.away_team
                            
                            # Find player in full roster by ID (not just lineup)
                            # Players might have stats from Q1 but not be in Q2 lineup
                            # So we need to look in team.players (full roster) not just team.lineup
                            player = team.get_player_by_id(player_id)
                            
                            if not player:
                                logging.warning(f"⚠️ Loaded from DB: Could not find player {player_id} in {team_key} roster to restore stats")
                                continue
                            
                            # Restore NG (energy)
                            if "attributes" in saved_player_data and "NG" in saved_player_data["attributes"]:
                                saved_ng = saved_player_data["attributes"]["NG"]
                                player.attributes["NG"] = saved_ng
                                player._rescale_attributes()  # Update scaled attributes based on NG
                            
                            # Restore game stats
                            if "stats" in saved_player_data:
                                player.stats["game"] = saved_player_data["stats"]
                                # ✅ PERFORMANCE: Removed debug logging
                        
                        # Restore team-level stats (score, fouls, totals, points by quarter)
                        # Only restore if this is NOT a new Q1 game (fresh start)
                        if should_restore_stats:
                            home_team_data = saved.get("home_team", {})
                            away_team_data = saved.get("away_team", {})
                            
                            # Restore team scores
                            # 🔍 DEBUG: Log score restoration
                            logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Before restore: gm.score={gm.score}, gm.quarter={gm.quarter}")
                            if "score" in home_team_data:
                                gm.score[gm.home_team.name] = home_team_data["score"]
                                logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Restored home score: {gm.home_team.name}={home_team_data['score']}")
                            if "score" in away_team_data:
                                gm.score[gm.away_team.name] = away_team_data["score"]
                                logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Restored away score: {gm.away_team.name}={away_team_data['score']}")
                            logging.warning(f"🔍 [SCORE_RESTORE DEBUG] After restore: gm.score={gm.score}, gm.quarter={gm.quarter}")
                            
                            # Restore team fouls
                            if "team_fouls" in home_team_data:
                                gm.home_team.team_fouls = home_team_data["team_fouls"]
                            if "team_fouls" in away_team_data:
                                gm.away_team.team_fouls = away_team_data["team_fouls"]
                            
                            # Restore team timeouts
                            if "timeouts" in home_team_data:
                                gm.home_team.timeouts = home_team_data["timeouts"]
                            else:
                                # Default to 4 if not in saved data (backward compatibility)
                                gm.home_team.timeouts = 4
                            if "timeouts" in away_team_data:
                                gm.away_team.timeouts = away_team_data["timeouts"]
                            else:
                                # Default to 4 if not in saved data (backward compatibility)
                                gm.away_team.timeouts = 4
                            
                            # Restore team totals (aggregated stats)
                            if "totals" in home_team_data:
                                gm.team_totals[gm.home_team.name] = home_team_data["totals"]
                            if "totals" in away_team_data:
                                gm.team_totals[gm.away_team.name] = away_team_data["totals"]
                            
                            # Restore points by quarter
                            if "points_by_quarter" in home_team_data:
                                gm.game_state["points_by_quarter"][gm.home_team.name] = home_team_data["points_by_quarter"]
                            if "points_by_quarter" in away_team_data:
                                gm.game_state["points_by_quarter"][gm.away_team.name] = away_team_data["points_by_quarter"]
                            # ✅ PERFORMANCE: Removed debug logging
                            
                            # Restore game_stats_initialized flag to prevent stats reset
                            if "game_stats_initialized" in saved:
                                gm.game_state["game_stats_initialized"] = saved["game_stats_initialized"]
                                logging.info(f"🔄 game_stats_initialized restored: {saved['game_stats_initialized']}")
                        else:
                            # New Q1 game - ensure stats are zeroed
                            gm.score = {gm.home_team.name: 0, gm.away_team.name: 0}
                            gm.home_team.team_fouls = 0
                            gm.away_team.team_fouls = 0
                            gm.home_team.timeouts = 4  # New game starts with 4 timeouts
                            gm.away_team.timeouts = 4  # New game starts with 4 timeouts
                        
                        # ✅ TIMEOUT RESUME: Apply unified timeout state restoration (if resuming from timeout)
                        # This uses the state we loaded earlier from DB (single source of truth)
                        # Only apply if we actually found timeout state and quarter matches (not stale data)
                        if timeout_saved_state:
                            # Validate that this is actually a timeout resume (not stale data from previous game)
                            # Check that timeout_next_play_type exists and quarter matches
                            saved_quarter = saved.get("quarter", 0)
                            if timeout_saved_state.get("timeout_next_play_type") and saved_quarter == request.quarter:
                                # ✅ CRITICAL FIX: Apply timeout state from the FULL saved document, not just timeout_saved_state
                                # This ensures we restore ALL game state (scores, clock, etc.) from the latest DB save
                                # Use 'saved' (the full document) instead of 'timeout_saved_state' (which might be partial)
                                apply_timeout_resume_state_to_gm(gm, saved)  # Use full saved document
                                # Override request.resume_from_timeout to ensure simulate_quarter() handles timeout resume
                                request.resume_from_timeout = True
                                logging.info(f"✅ TIMEOUT RESUME: Applied timeout state from full saved document (quarter matches), setting resume_from_timeout=True for simulate_quarter()")
                            else:
                                logging.warning(f"⚠️ TIMEOUT RESUME: Found timeout state but quarter mismatch or missing next_play_type - treating as normal game (saved_quarter={saved_quarter}, requested_quarter={request.quarter})")
                                timeout_saved_state = None  # Clear invalid timeout state
                        else:
                            # ✅ FIX: Don't restore time_remaining when starting a new quarter
                            # simulate_quarter() will reset it to 480 (for Q1-Q4) or 240 (for OT)
                            # Only restore clock/time_remaining when resuming mid-quarter (timeout resume)
                            # For new quarter starts, let simulate_quarter() reset them
                            saved_quarter = saved.get("quarter", 0)
                            if saved_quarter != request.quarter:
                                # Quarter mismatch - this shouldn't happen, but if it does, don't restore time
                                logging.warning(f"⚠️ Quarter mismatch: saved={saved_quarter}, requested={request.quarter} - not restoring time_remaining")
                            # Don't restore time_remaining here - simulate_quarter() will reset it for the new quarter
                        
                        # Restore opening_tip_winner for Q2-Q4 possession logic
                        # Only restore if this is NOT a new Q1 game (opening tip hasn't happened yet for new games)
                        if should_restore_stats and "opening_tip_winner" in saved:
                            gm.game_state["opening_tip_winner"] = saved["opening_tip_winner"]
                            if debug:
                                logging.debug(
                                    "Restored opening_tip_winner: %s",
                                    saved["opening_tip_winner"]
                                )
                        elif not should_restore_stats:
                            # New Q1 game - clear opening_tip_winner and old turns so opening tip can run
                            if "opening_tip_winner" in gm.game_state:
                                del gm.game_state["opening_tip_winner"]
                            # Clear any old turns from previous game - opening tip will be added in simulate_quarter
                            gm.turns = []
                        
                        # 🔍 DEBUG: Log time_remaining before calling simulate_quarter()
                        time_before_sim = gm.game_state.get("time_remaining", "NOT_SET")
                        logging.warning(f"🔍 [Q4 DEBUG] BEFORE simulate_quarter() call: quarter={request.quarter}, resume_from_timeout={request.resume_from_timeout}, time_remaining={time_before_sim}, saved_time_remaining={saved.get('time_remaining', 'NOT_SET') if saved else 'NO_SAVED_DOC'}")
                        # 🔍 DEBUG: Log quarter and score state before simulate_quarter()
                        logging.warning(f"🔍 [BEFORE_SIM_DEBUG] gm.quarter={gm.quarter}, request.quarter={request.quarter}, gm.score={gm.score}")
                        
                        ongoing_games[game_id] = gm
                        # ✅ DEBUG: Track when game is added to ongoing_games
                        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ✅ Added game to ongoing_games: game_id={game_id}, object_id={id(gm)}, quarter={gm.quarter}, full_sim={request.full_sim}")
                        if debug:
                            logging.debug(
                                "simulate_quarter_endpoint loaded from DB: %s vs %s",
                                home,
                                away,
                            )
                except Exception as e:
                    logging.exception("Failed to load game state for %s", game_id)
                    logging.error(f"❌ Exception loading game: {type(e).__name__}: {str(e)}")
            if gm is None:
                if request.quarter == 1:
                    # Determine which team gets the user's settings
                    home_strategy = None
                    away_strategy = None
                    
                    if request.user_team_side == "home" and request.strategy_settings:
                        try:
                            if isinstance(request.strategy_settings, dict):
                                home_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                # Only apply user's settings to their team, not the CPU team
                                away_strategy = None  # CPU team will use random defaults
                                logging.warning(f"🔧 [STRATEGY SETTINGS] CREATING NEW GAME - user_team_side=home")
                                logging.warning(f"   - Applied to HOME team only: HCT={request.strategy_settings.get('hc_trap')}, FCP={request.strategy_settings.get('fc_press')}")
                                logging.warning(f"   - AWAY team will use random defaults")
                            else:
                                logging.error(f"⚠️ [STRATEGY SETTINGS] request.strategy_settings is not a dict: {type(request.strategy_settings)}")
                        except Exception as e:
                            logging.error(f"❌ [STRATEGY SETTINGS] Error processing strategy_settings for new game: {e}", exc_info=True)
                    elif request.user_team_side == "away" and request.strategy_settings:
                        try:
                            if isinstance(request.strategy_settings, dict):
                                away_strategy = dict(request.strategy_settings)  # Use dict() constructor for safety
                                # Only apply user's settings to their team, not the CPU team
                                home_strategy = None  # CPU team will use random defaults
                                logging.warning(f"🔧 [STRATEGY SETTINGS] CREATING NEW GAME - user_team_side=away")
                                logging.warning(f"   - Applied to AWAY team only: HCT={request.strategy_settings.get('hc_trap')}, FCP={request.strategy_settings.get('fc_press')}")
                                logging.warning(f"   - HOME team will use random defaults")
                            else:
                                logging.error(f"⚠️ [STRATEGY SETTINGS] request.strategy_settings is not a dict: {type(request.strategy_settings)}")
                        except Exception as e:
                            logging.error(f"❌ [STRATEGY SETTINGS] Error processing strategy_settings for new game: {e}", exc_info=True)
                    else:
                        logging.warning(f"⚠️ [STRATEGY SETTINGS] CREATING NEW GAME - No strategy_settings provided!")
                        logging.warning(f"   - user_team_side={request.user_team_side}, has_strategy_settings={bool(request.strategy_settings)}")
                    
                    # Get mode from request (default to "single")
                    mode = request.mode or "single"
                    
                    # Load team attributes from tournament/franchise/single game documents if available
                    home_team_attributes = None
                    away_team_attributes = None
                    
                    if mode in ["tournament", "single"] and (request.tournament_id or request.game_id):
                        # Load team attributes from tournament or game document
                        home_attrs = load_team_attributes_from_doc(
                            mode, 
                            request.tournament_id or request.game_id, 
                            None,  # team_id will be resolved inside the function
                            request.home_team
                        )
                        away_attrs = load_team_attributes_from_doc(
                            mode,
                            request.tournament_id or request.game_id,
                            None,
                            request.away_team
                        )
                        if home_attrs:
                            home_team_attributes = home_attrs
                        if away_attrs:
                            away_team_attributes = away_attrs
                    elif mode == "franchise" and request.franchise_id:
                        # Load team attributes from franchise document
                        home_attrs = load_team_attributes_from_doc(
                            mode,
                            request.franchise_id,
                            None,
                            request.home_team
                        )
                        away_attrs = load_team_attributes_from_doc(
                            mode,
                            request.franchise_id,
                            None,
                            request.away_team
                        )
                        if home_attrs:
                            home_team_attributes = home_attrs
                        if away_attrs:
                            away_team_attributes = away_attrs
                    
                    gm = GameManager(
                        request.home_team, 
                        request.away_team,
                        home_strategy_settings=home_strategy,
                        away_strategy_settings=away_strategy,
                        home_team_attributes=home_team_attributes,
                        away_team_attributes=away_team_attributes,
                        mode=mode,  # Pass mode so teams can initialize plays with correct stats structure
                        user_team_side=request.user_team_side  # ✅ SS&S: Set is_user_team flags
                    )
                    
                    # ✅ SS&S: Ensure user_team_side is set in game_state (GameManager should set it, but double-check)
                    if request.user_team_side and not gm.game_state.get("user_team_side"):
                        gm.game_state["user_team_side"] = request.user_team_side
                        logging.warning(f"✅ [NEW GAME] Set user_team_side in game_state: {request.user_team_side}")
                    elif gm.game_state.get("user_team_side"):
                        logging.warning(f"✅ [NEW GAME] user_team_side already set in game_state: {gm.game_state.get('user_team_side')}")
                    else:
                        logging.warning(f"⚠️ [NEW GAME] No user_team_side set! request.user_team_side={request.user_team_side}")
                    
                    logging.warning(f"🔧 [STRATEGY SETTINGS] AFTER GAMEMANAGER (NEW)")
                    logging.warning(f"   - Home: HCT={gm.home_team.strategy_settings.get('hc_trap', 'MISSING')}, FCP={gm.home_team.strategy_settings.get('fc_press', 'MISSING')}")
                    logging.warning(f"   - Away: HCT={gm.away_team.strategy_settings.get('hc_trap', 'MISSING')}, FCP={gm.away_team.strategy_settings.get('fc_press', 'MISSING')}")
                    # Use the game_id from the request if provided, otherwise generate a new one
                    if request.game_id:
                        game_id = request.game_id
                    else:
                        game_id = str(uuid.uuid4())
                    gm.game_id = game_id  # Store game_id on the GameManager object
                    ongoing_games[game_id] = gm
                    logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ✅ Added game to ongoing_games (timeout resume path): game_id={game_id}, object_id={id(gm)}, quarter={gm.quarter}")
                    source = "new"
                    
                    # Save teams object to database for skeleton lookup during simulation
                    try:
                        from BackEnd.api.gameplan_routes import populate_team_plays
                        
                        # Get mode from request (default to "single")
                        mode = request.mode or "single"
                        
                        # Get populated plays for team objects (with game_stats and optionally season_stats)
                        populated_plays = populate_team_plays(mode=mode)
                        
                        # ✅ FIX: Load playbook_settings from tournament/franchise document for new Q1 games
                        # This ensures playbook_settings are stored in game document from the start
                        home_playbook_settings = {}
                        away_playbook_settings = {}
                        
                        if mode == "tournament" and request.tournament_id:
                            home_settings = load_team_settings_from_doc(
                                mode,
                                request.tournament_id,
                                None,
                                request.home_team
                            )
                            away_settings = load_team_settings_from_doc(
                                mode,
                                request.tournament_id,
                                None,
                                request.away_team
                            )
                            if home_settings:
                                home_playbook_settings = home_settings.get("playbook_settings", {})
                            if away_settings:
                                away_playbook_settings = away_settings.get("playbook_settings", {})
                        elif mode == "franchise" and request.franchise_id:
                            home_settings = load_team_settings_from_doc(
                                mode,
                                request.franchise_id,
                                None,
                                request.home_team
                            )
                            away_settings = load_team_settings_from_doc(
                                mode,
                                request.franchise_id,
                                None,
                                request.away_team
                            )
                            if home_settings:
                                home_playbook_settings = home_settings.get("playbook_settings", {})
                            if away_settings:
                                away_playbook_settings = away_settings.get("playbook_settings", {})
                        
                        # Create team objects with plays and playbook_settings for skeleton lookup
                        teams_obj = {
                            gm.home_team.team_id: {
                                "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                                "plays": populated_plays.copy(),
                                "playbook_settings": home_playbook_settings
                            },
                            gm.away_team.team_id: {
                                "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                                "plays": populated_plays.copy(),
                                "playbook_settings": away_playbook_settings
                            }
                        }
                        
                        # print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
                        # print(f"🔍 DEBUG: Home team plays: {len(teams_obj[gm.home_team.team_id]['plays'])}")
                        # print(f"🔍 DEBUG: Away team plays: {len(teams_obj[gm.away_team.team_id]['plays'])}")
                        
                        # Create a summary with new nested team structure
                        summary = summarize_game_state(gm)
                        
                        # ✅ FIX: Merge playbook_settings from teams_obj into summary before saving
                        # This ensures playbook_settings loaded from tournament/franchise document are preserved
                        # summarize_game_state tries to load from DB, but on first save (Q1), they're not there yet
                        if "teams" in summary and teams_obj:
                            for team_id, team_data in teams_obj.items():
                                if team_id in summary["teams"]:
                                    # Merge playbook_settings if they exist in teams_obj but not in summary
                                    if "playbook_settings" in team_data and team_data["playbook_settings"]:
                                        summary["teams"][team_id]["playbook_settings"] = team_data["playbook_settings"]
                        
                        # Save to database
                        games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
                        # print(f"🔍 DEBUG: Saved teams object to database with game_id: {game_id}")
                        
                    except Exception as e:
                        print(f"🚨 Failed to save teams object in simulate_quarter_endpoint (Q1): {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    if debug:
                        logging.debug("simulate_quarter_endpoint unknown game_id=%s", game_id)
                    raise HTTPException(status_code=400, detail="Unknown game_id")
    else:
        # Determine which team gets the user's settings
        home_strategy = None
        away_strategy = None
        
        if request.user_team_side == "home" and request.strategy_settings:
            home_strategy = request.strategy_settings
            # In single game mode, apply defensive strategy to BOTH teams for consistent pressure
            away_strategy = request.strategy_settings
        elif request.user_team_side == "away" and request.strategy_settings:
            away_strategy = request.strategy_settings
            # In single game mode, apply defensive strategy to BOTH teams for consistent pressure
            home_strategy = request.strategy_settings
        
        # Get mode from request (default to "single")
        mode = request.mode or "single"
        
        # Load team attributes from tournament/franchise/single game documents if available
        home_team_attributes = None
        away_team_attributes = None
        
        # ✅ FIX: Load strategy_settings and playbook_settings from tournament/franchise documents
        # This ensures settings persist from TCC to gameplay (matches Franchise mode pattern)
        home_settings = None
        away_settings = None
        
        if mode in ["tournament", "single"] and (request.tournament_id or request.game_id):
            # Load team attributes from tournament or game document
            home_attrs = load_team_attributes_from_doc(
                mode, 
                request.tournament_id or request.game_id, 
                None,  # team_id will be resolved inside the function
                request.home_team
            )
            away_attrs = load_team_attributes_from_doc(
                mode,
                request.tournament_id or request.game_id,
                None,
                request.away_team
            )
            if home_attrs:
                home_team_attributes = home_attrs
            if away_attrs:
                away_team_attributes = away_attrs
            
            # Load strategy_settings and playbook_settings from tournament document
            if request.tournament_id:
                home_settings = load_team_settings_from_doc(
                    mode,
                    request.tournament_id,
                    None,
                    request.home_team
                )
                away_settings = load_team_settings_from_doc(
                    mode,
                    request.tournament_id,
                    None,
                    request.away_team
                )
                # Override strategy_settings if loaded from tournament (unless request has them)
                if home_settings.get("strategy_settings") and not home_strategy:
                    home_strategy = home_settings.get("strategy_settings")
                if away_settings.get("strategy_settings") and not away_strategy:
                    away_strategy = away_settings.get("strategy_settings")
        elif mode == "franchise" and request.franchise_id:
            # Load team attributes from franchise document
            home_attrs = load_team_attributes_from_doc(
                mode,
                request.franchise_id,
                None,
                request.home_team
            )
            away_attrs = load_team_attributes_from_doc(
                mode,
                request.franchise_id,
                None,
                request.away_team
            )
            if home_attrs:
                home_team_attributes = home_attrs
            if away_attrs:
                away_team_attributes = away_attrs
            
            # Load strategy_settings and playbook_settings from franchise document
            home_settings = load_team_settings_from_doc(
                mode,
                request.franchise_id,
                None,
                request.home_team
            )
            away_settings = load_team_settings_from_doc(
                mode,
                request.franchise_id,
                None,
                request.away_team
            )
            # Override strategy_settings if loaded from franchise (unless request has them)
            if home_settings.get("strategy_settings") and not home_strategy:
                home_strategy = home_settings.get("strategy_settings")
            if away_settings.get("strategy_settings") and not away_strategy:
                away_strategy = away_settings.get("strategy_settings")
        
        gm = GameManager(
            request.home_team, 
            request.away_team,
            home_strategy_settings=home_strategy,
            away_strategy_settings=away_strategy,
            home_team_attributes=home_team_attributes,
            away_team_attributes=away_team_attributes,
            mode=mode,  # Pass mode so teams can initialize plays with correct stats structure
            user_team_side=request.user_team_side  # ✅ SS&S: Pass user_team_side to set is_user_team flags
        )
        # Use the game_id from the request if provided, otherwise generate a new one
        from BackEnd.utils.game_id_utils import generate_game_id, normalize_game_id
        
        if request.game_id:
            game_id = normalize_game_id(request.game_id)
        else:
            game_id = generate_game_id()
        gm.game_id = game_id  # Store game_id on the GameManager object
        ongoing_games[game_id] = gm
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ✅ Added game to ongoing_games (new game path): game_id={game_id}, object_id={id(gm)}, quarter={gm.quarter}")
        source = "new"
        
        # Save teams object to database for skeleton lookup during simulation
        try:
            from BackEnd.api.gameplan_routes import populate_team_plays
            
            # Get mode from request (default to "single")
            mode = request.mode or "single"
            
            # Get populated plays for team objects (with game_stats and optionally season_stats)
            populated_plays = populate_team_plays(mode=mode)
            
            # ✅ FIX: Load playbook_settings from tournament/franchise document for new Q1 games
            # This ensures playbook_settings are stored in game document from the start
            home_playbook_settings = {}
            away_playbook_settings = {}
            
            if mode == "tournament" and request.tournament_id:
                home_settings = load_team_settings_from_doc(
                    mode,
                    request.tournament_id,
                    None,
                    request.home_team
                )
                away_settings = load_team_settings_from_doc(
                    mode,
                    request.tournament_id,
                    None,
                    request.away_team
                )
                if home_settings:
                    home_playbook_settings = home_settings.get("playbook_settings", {})
                if away_settings:
                    away_playbook_settings = away_settings.get("playbook_settings", {})
            elif mode == "franchise" and request.franchise_id:
                home_settings = load_team_settings_from_doc(
                    mode,
                    request.franchise_id,
                    None,
                    request.home_team
                )
                away_settings = load_team_settings_from_doc(
                    mode,
                    request.franchise_id,
                    None,
                    request.away_team
                )
                if home_settings:
                    home_playbook_settings = home_settings.get("playbook_settings", {})
                if away_settings:
                    away_playbook_settings = away_settings.get("playbook_settings", {})
            
            # Create team objects with plays and playbook_settings for skeleton lookup
            teams_obj = {
                gm.home_team.team_id: {
                    "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                    "plays": populated_plays.copy(),
                    "playbook_settings": home_playbook_settings
                },
                gm.away_team.team_id: {
                    "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                    "plays": populated_plays.copy(),
                    "playbook_settings": away_playbook_settings
                }
            }
            
            # print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
            # print(f"🔍 DEBUG: Home team plays: {len(teams_obj[gm.home_team.team_id]['plays'])}")
            # print(f"🔍 DEBUG: Away team plays: {len(teams_obj[gm.away_team.team_id]['plays'])}")
            
            # 🔍 DEBUG: Log time_remaining before summarizing
            time_before_summarize = gm.game_state.get("time_remaining", "NOT_SET")
            logging.warning(f"🔍 [Q4 DEBUG] BEFORE summarize_game_state(): time_remaining={time_before_summarize}, quarter={gm.quarter}")
            
            # Create a summary with new nested team structure
            summary = summarize_game_state(gm)
            
            # 🔍 DEBUG: Log time_remaining in summary
            time_in_summary = summary.get("time_remaining", "NOT_SET")
            logging.warning(f"🔍 [Q4 DEBUG] AFTER summarize_game_state(): time_remaining in summary={time_in_summary}, quarter={summary.get('quarter', 'NOT_SET')}")
            
            # ✅ FIX: Merge playbook_settings from teams_obj into summary before saving
            # This ensures playbook_settings loaded from tournament/franchise document are preserved
            # summarize_game_state tries to load from DB, but on first save (Q1), they're not there yet
            if "teams" in summary and teams_obj:
                for team_id, team_data in teams_obj.items():
                    if team_id in summary["teams"]:
                        # Merge playbook_settings if they exist in teams_obj but not in summary
                        if "playbook_settings" in team_data and team_data["playbook_settings"]:
                            summary["teams"][team_id]["playbook_settings"] = team_data["playbook_settings"]
            
            # 🔍 DEBUG: Log time_remaining before saving
            time_being_saved = summary.get("time_remaining", "NOT_SET")
            logging.warning(f"🔍 [Q4 DEBUG] BEFORE saving to DB: time_remaining={time_being_saved}, quarter={summary.get('quarter', 'NOT_SET')}, game_id={game_id}")
            
            # Save to database
            games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
            logging.warning(f"🔍 [Q4 DEBUG] SAVED to DB: time_remaining={time_being_saved}, quarter={summary.get('quarter', 'NOT_SET')}, game_id={game_id}")
            # print(f"🔍 DEBUG: Saved teams object to database with game_id: {game_id}")
            
        except Exception as e:
            print(f"🚨 Failed to save teams object in simulate_quarter_endpoint (no game_id): {e}")
            import traceback
            traceback.print_exc()
    if debug and gm is not None:
        logging.debug(
            "simulate_quarter_endpoint using matchup: %s vs %s (quarter=%s)",
            gm.home_team.name,
            gm.away_team.name,
            gm.quarter,
        )

    logging.info(
        {
            "event": "simulate-quarter:start",
            "game_id": game_id,
            "home_team": request.home_team,
            "away_team": request.away_team,
            "quarter": request.quarter,
            "source": source,
        }
    )

    # If the requested quarter has already been simulated, return the existing state
    if request.quarter < gm.quarter:
        summary = summarize_game_state(gm)
        summary["start_box_score"] = gm.game_state.get("start_box_score")
        is_final = (
            gm.quarter > 4
            and summary["score"][gm.home_team.name] != summary["score"][gm.away_team.name]
        )
        summary.update(
            {
                "game_id": game_id,
                "quarter": gm.quarter - 1,
                "is_final": is_final,
                "next_lineup_needed": not is_final,
            }
        )
        return summary

    # Allow quarter progression: only prevent going backwards or skipping too far ahead
    if request.quarter < gm.quarter:
        if debug:
            logging.debug(
                "simulate_quarter_endpoint quarter regression: game_id=%s current=%s requested=%s",
                game_id,
                gm.quarter,
                request.quarter,
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot simulate previous quarter. Current quarter is {gm.quarter}, requested {request.quarter}",
        )
    elif request.quarter > gm.quarter + 1:
        if debug:
            logging.debug(
                "simulate_quarter_endpoint quarter skip: game_id=%s current=%s requested=%s",
                game_id,
                gm.quarter,
                request.quarter,
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot skip quarters. Current quarter is {gm.quarter}, requested {request.quarter}",
        )

    try:
        # ✅ FIX: Use full_sim parameter to determine turn_by_turn_mode
        # When full_sim=True (simming), fully simulate the quarter instantly (no animation)
        # When full_sim=False (playing), use turn-by-turn mode (for animation)
        turn_by_turn_mode = not request.full_sim
        logging.warning(f"🔍 [FULL_SIM DEBUG] simulate_quarter_endpoint START: full_sim={request.full_sim}, turn_by_turn_mode={turn_by_turn_mode}, quarter={request.quarter}, game_id={game_id}")
        if gm:
            current_flag = gm.game_state.get("_is_full_simulation", False)
            logging.warning(f"🔍 [FULL_SIM DEBUG] Game in memory - current _is_full_simulation={current_flag}")
        else:
            logging.warning(f"🔍 [FULL_SIM DEBUG] Game NOT in memory - will load from DB")
        logging.info(f"🎮 simulate_quarter_endpoint: full_sim={request.full_sim}, turn_by_turn_mode={turn_by_turn_mode}, quarter={request.quarter}, resume_from_timeout={request.resume_from_timeout}")
        
        # ⏱️ PERFORMANCE: Time the quarter simulation
        sim_start = time.time()
        simulate_quarter(
            gm,
            request.home_lineup,
            request.away_lineup,
            game_id,
            request.start_with_inbound,
            request.starting_possession,
            turn_by_turn_mode=turn_by_turn_mode,
            resume_from_timeout=request.resume_from_timeout,
        )
        sim_time = (time.time() - sim_start) * 1000
        
        # 🔍 DEBUG: Log time_remaining after simulate_quarter() returns
        time_after_sim = gm.game_state.get("time_remaining", "NOT_SET")
        logging.warning(f"🔍 [Q4 DEBUG] AFTER simulate_quarter() returns: quarter={gm.quarter}, time_remaining={time_after_sim}, resume_from_timeout={request.resume_from_timeout}")
        
    except ValueError as e:
        logging.error(
            "simulate_quarter lineup error for game_id=%s, home_team=%s, away_team=%s, quarter=%s: %s",
            game_id,
            request.home_team,
            request.away_team,
            request.quarter,
            e,
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.error(
            "simulate_quarter failed for game_id=%s, home_team=%s, away_team=%s, quarter=%s, home_lineup_keys=%s, away_lineup_keys=%s, full_sim=%s, turn_by_turn_mode=%s",
            game_id,
            request.home_team,
            request.away_team,
            request.quarter,
            list((request.home_lineup or {}).keys()),
            list((request.away_lineup or {}).keys()),
            request.full_sim,
            not request.full_sim,
        )
        logging.error(f"Full traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nFull traceback:\n{error_trace}")

    # Create TWO summaries:
    # 1. WITH animations for frontend (exclude_animations=False)
    # 2. WITHOUT animations for database save (exclude_animations=True)
    summary_start = time.time()
    frontend_summary = summarize_game_state(gm, exclude_animations=False)
    
    # Add start_box_score (only needed for Q2-Q4 frontend, not critical for saves)
    frontend_summary["start_box_score"] = gm.game_state.get("start_box_score")
    
    # Get is_final status
    is_final = frontend_summary.get("is_final", False)
    summary_time = (time.time() - summary_start) * 1000

    # ✅ DEBUG: Check ongoing_games state after simulate_quarter completes
    gm_after_sim = ongoing_games.get(game_id)
    logging.warning(f"🔍 [ONGOING_GAMES DEBUG] After simulate_quarter() completes: game_id={game_id}, in_ongoing_games={gm_after_sim is not None}")
    if gm_after_sim:
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game still in ongoing_games - object_id={id(gm_after_sim)}, quarter={gm_after_sim.quarter}, full_sim={request.full_sim}")
    else:
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ⚠️ Game NOT in ongoing_games after simulate_quarter! Available games: {list(ongoing_games.keys())}")
    
    # Save to database (WITHOUT animations to reduce document size)
    db_save_start = time.time()
    try:
        db_summary = summarize_game_state(gm, exclude_animations=True)
        # ✅ FIX: Log quarter before save to debug save/load issues
        logging.info(f"💾 Saving game state: game_id={game_id}, quarter={db_summary.get('quarter')}, gm.quarter={gm.quarter}")
        
        # ✅ TOURNAMENT MODE: Add mode and tournament_id to game document for consistency with Franchise mode
        # ✅ FIX: Prefer explicit mode from request over inferring from IDs
        # This prevents Single Game mode from being incorrectly set to "franchise" when franchise_id leaks from localStorage
        mode = request.mode
        if not mode:
            # Only infer mode if it's truly not set
            # Default to "single" if mode is not explicitly provided (even if IDs are present)
            if request.tournament_id:
                mode = "tournament"
            elif request.franchise_id:
                mode = "franchise"
            else:
                mode = "single"
        
        # Add mode to game document (for consistency with init_game() pattern)
        if mode:
            db_summary["mode"] = mode
        
        # Add tournament_id to game document when in tournament mode (matches Franchise mode pattern)
        if mode == "tournament" and request.tournament_id:
            db_summary["tournament_id"] = str(request.tournament_id)
        
        # ✅ FIX: Ensure game_id is converted to ObjectId for consistent database storage
        # This ensures the _id format matches when we try to find it later
        try:
            if isinstance(game_id, str) and ObjectId.is_valid(game_id):
                game_id_oid = ObjectId(game_id)
            else:
                game_id_oid = game_id
        except Exception:
            game_id_oid = game_id
        
        # Ensure _id is set in db_summary for upsert to work correctly
        db_summary["_id"] = game_id_oid
        
        # ✅ DEBUG: Log detailed save information for Q4 to diagnose finalize_game() issue
        quarter_saving = db_summary.get('quarter', 'N/A')
        is_final_saving = db_summary.get('is_final', False)
        logging.info(f"💾 [SAVE] About to save game document: game_id={game_id} (ObjectId: {game_id_oid}), quarter={quarter_saving}, is_final={is_final_saving}, mode={mode}")
        if quarter_saving == 4 or is_final_saving:
            logging.info(f"🎯 [SAVE] Q4/FINAL SAVE: game_id={game_id}, quarter={quarter_saving}, is_final={is_final_saving}, gm.quarter={gm.quarter}")
        
        games_collection.update_one({"_id": game_id_oid}, {"$set": db_summary}, upsert=True)
        
        # ✅ DEBUG: Verify what was actually saved
        saved_doc = games_collection.find_one({"_id": game_id_oid}, {"quarter": 1, "is_final": 1, "week": 1})
        if saved_doc:
            saved_quarter = saved_doc.get("quarter", "N/A")
            saved_is_final = saved_doc.get("is_final", False)
            saved_week = saved_doc.get("week", "N/A")
            logging.info(f"✅ [SAVE] Game state saved successfully: game_id={game_id} (ObjectId: {game_id_oid}), quarter={saved_quarter}, is_final={saved_is_final}, week={saved_week}, mode={mode}")
            if quarter_saving == 4 or is_final_saving:
                logging.info(f"🎯 [SAVE] Q4/FINAL VERIFIED: Saved document has quarter={saved_quarter}, is_final={saved_is_final}")
        else:
            logging.error(f"❌ [SAVE] Failed to verify saved document: game_id={game_id} (ObjectId: {game_id_oid})")
        db_save_time = (time.time() - db_save_start) * 1000
    except Exception as e:
        print("🚨 Mongo upsert failed:", e)
        traceback.print_exc()
        db_save_time = (time.time() - db_save_start) * 1000

    if is_final and game_id:
        # Scrimmage simulations should not generate aggregate stats.
        # Finalizing with ``mode="scrimmage"`` is a no-op but documents intent.
        stat_updater.finalize_game(game_id, mode="scrimmage")
    
    # Return frontend summary WITH animations for real-time play
    turns = frontend_summary.get("turns", [])
    
    # ✅ TIMEOUT: Return the SIP turn that was created in simulate_quarter() (same pattern as quarter breaks)
    # simulate_quarter() already created the SIP turn and added it to gm.turns when resume_from_timeout=True
    # We should return it just like we return BIP turns for quarter breaks
    if request.resume_from_timeout:
        logging.info(f"✅ TIMEOUT RESUME: Returning turns from simulate_quarter() (turns count: {len(turns)})")
        if turns:
            first_turn = turns[0]
            logging.info(f"✅ TIMEOUT RESUME: First turn result_type={first_turn.get('result_type')}, current_turn={first_turn.get('current_turn')}, quarter={first_turn.get('quarter')}")
        else:
            logging.error(f"🚨 TIMEOUT RESUME: No turns returned! This should not happen - SIP turn should have been created in simulate_quarter()")
        # Turns array already contains the SIP turn created in simulate_quarter() - no need to override
    
    # ✅ FIX: Return complete game document when game is final (Q4/OT ends with winner)
    # This eliminates race condition where complete_week() is called before Q4 save completes
    # Matches Tournament mode pattern where game document is already available
    if is_final and game_id:
        try:
            # Include the complete db_summary (without animations) in the response
            # This is the same document that was just saved to the database
            # ✅ FIX: Convert ObjectIds to strings for JSON serialization (recursively)
            from bson import ObjectId
            import json
            
            def convert_objectids(obj):
                # Recursively convert ObjectIds to strings for JSON serialization
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, dict):
                    return {k: convert_objectids(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_objectids(item) for item in obj]
                else:
                    return obj
            
            final_game_doc = convert_objectids(db_summary)
            frontend_summary["final_game_document"] = final_game_doc
            logging.info(f"✅ [SIMULATE_QUARTER] Game is final - returning complete game document: quarter={db_summary.get('quarter')}, is_final={db_summary.get('is_final')}, game_id={game_id}")
        except Exception as e:
            logging.error(f"❌ [SIMULATE_QUARTER] Error adding final_game_document to response: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Continue without it - frontend will fall back to fetch
    
    logger.debug(
        "simulate_quarter_endpoint turns len=%s first=%s",
        len(turns),
        turns[0] if turns else None,
    )
    
    # ⏱️ PERFORMANCE: Log total endpoint time
    total_time = (time.time() - start_time) * 1000
    response_size = len(str(frontend_summary).encode('utf-8'))
    logging.warning(
        f"⏱️ [PERF] /api/simulate-quarter - quarter={request.quarter}, "
        f"simulation: {sim_time:.2f}ms, summary: {summary_time:.2f}ms, "
        f"db_save: {db_save_time:.2f}ms, response_size: {response_size} bytes, "
        f"total: {total_time:.2f}ms, full_sim={request.full_sim}"
    )
    
    return frontend_summary


@app.post("/api/simulate-turn")
def simulate_turn_endpoint(request: TurnSimulationRequest):
    import time
    start_time = time.time()
    # Simulate a single turn for turn-by-turn gameplay.
    # This endpoint:
    # 1. Retrieves the GameManager from ongoing_games
    # 2. Applies user overrides (if any) for this turn
    # 3. Simulates ONE turn (one call to gm.simulate_macro_turn())
    # 4. Returns the turn data + game state metadata
    # 5. Saves game state periodically
    game_id = request.game_id
    
    # Get the GameManager from memory
    gm = ongoing_games.get(game_id)
    if gm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Game {game_id} not found. Start a quarter first with /api/simulate-quarter"
        )
    
    # Log lineup state when simulate-turn is called
    logging.info(f"🏀 simulate-turn: Retrieved game from ongoing_games, home_lineup_keys={list(gm.home_team.lineup.keys()) if gm.home_team.lineup else 'EMPTY'}, away_lineup_keys={list(gm.away_team.lineup.keys()) if gm.away_team.lineup else 'EMPTY'}")
    
    # Apply user overrides for THIS turn only
    if request.offense_override:
        gm.game_state["user_offense_override"] = request.offense_override
        logging.info(f"🎮 User offense override: {request.offense_override}")
    
    if request.defense_override:
        gm.game_state["user_defense_override"] = request.defense_override
        logging.info(f"🎮 User defense override: {request.defense_override}")
    
    # Check if quarter is already over
    if gm.game_state["time_remaining"] <= 0:
        early_return = {
            "quarter_complete": True,
            "game_id": game_id,
            "quarter": gm.quarter,
            "time_remaining": 0,
            "home_score": gm.score.get(gm.home_team.name, 0),
            "away_score": gm.score.get(gm.away_team.name, 0),
            "turn": None
        }
        # ⏱️ PERFORMANCE: Log early return path
        total_time = (time.time() - start_time) * 1000
        logging.warning(
            f"⏱️ [PERF] /api/simulate-turn - EARLY RETURN (quarter complete), "
            f"quarter={gm.quarter}, total: {total_time:.2f}ms"
        )
        return early_return
    
    # ✅ TIMEOUT: Check if last turn is a TIMEOUT turn (user-initiated or foul out)
    # If so, return it immediately without simulating a new turn
    if gm.turns and isinstance(gm.turns[-1], dict) and gm.turns[-1].get("result_type") == "TIMEOUT":
        timeout_turn = gm.turns[-1]
        logging.info(f"⏸️ TIMEOUT: Returning existing TIMEOUT turn (reason: {timeout_turn.get('timeout_reason')})")
        # Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
        gm.turns.pop()
        return {
            "turn": timeout_turn,
            "next_offensive_state": gm.game_state.get("offensive_state", "HCO"),
            "time_remaining": gm.game_state["time_remaining"],
            "clock": gm.game_state.get("clock", "8:00"),
            "quarter_complete": False,
            "quarter": gm.quarter,
            "is_final": False,
            "home_score": gm.score.get(gm.home_team.name, 0),
            "away_score": gm.score.get(gm.away_team.name, 0),
            "home_team_fouls": gm.home_team.team_fouls,
            "away_team_fouls": gm.away_team.team_fouls,
            "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
            "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
            "offense_team": gm.offense_team.name,
            "defense_team": gm.defense_team.name,
            "game_id": game_id,
            "ineligible_players": gm.game_state.get("ineligible_players", []),
            "box_score": gm.get_box_score(),
            "team_totals": {
                gm.home_team.name: gm.home_team.get_team_game_stats(),
                gm.away_team.name: gm.away_team.get_team_game_stats()
            }
        }
    
    # Simulate ONE turn
    try:
        # ✅ DEFERRED TIMEOUT: Check for pending computer timeout at start of API call
        # This creates the timeout turn after the previous turn has been animated
        if gm.game_state.get("pending_computer_timeout"):
            pending = gm.game_state["pending_computer_timeout"]
            calling_team = pending["calling_team"]
            turn_type = pending["turn_type"]
            
            logging.debug(f"⏸️ COMPUTER TIMEOUT: Creating deferred timeout turn for {calling_team.name} (turn_type: {turn_type})")
            
            # Create the timeout turn now (after previous turn was animated)
            timeout_turn = gm.call_timeout(
                calling_team=calling_team,
                timeout_reason="COMPUTER",
                rebuild_both_lineups=True,
                game_id=game_id  # Pass game_id for immediate save
            )
            
            # Clear pending timeout
            del gm.game_state["pending_computer_timeout"]
            
            if timeout_turn:
                # ✅ UNIFIED: Use shared helper function for timeout save and response
                # This ensures user and computer timeouts work identically
                try:
                    # 🔍 DEBUG: Log state BEFORE save
                    logging.warning(f"🔍 [COMPUTER TIMEOUT SAVE DEBUG] BEFORE save - game_id={game_id}, quarter={gm.quarter}")
                    logging.warning(f"🔍 [COMPUTER TIMEOUT SAVE DEBUG] gm.game_state timeout fields: timeout_next_play_type={gm.game_state.get('timeout_next_play_type')}, timeout_offense_team_id={gm.game_state.get('timeout_offense_team_id')}")
                    logging.warning(f"🔍 [COMPUTER TIMEOUT SAVE DEBUG] gm.score={gm.score}, clock={gm.game_state.get('clock')}, time_remaining={gm.game_state.get('time_remaining')}")
                    
                    # 🔍 DEBUG: Check DB state BEFORE save
                    before_save_doc = games_collection.find_one({"_id": game_id})
                    logging.warning(f"🔍 [COMPUTER TIMEOUT SAVE DEBUG] DB BEFORE save - timeout_next_play_type={before_save_doc.get('timeout_next_play_type') if before_save_doc else 'DOC_NOT_FOUND'}, timeout_offense_team_id={before_save_doc.get('timeout_offense_team_id') if before_save_doc else 'DOC_NOT_FOUND'}")
                    logging.warning(f"🔍 [COMPUTER TIMEOUT SAVE DEBUG] DB BEFORE save - score={before_save_doc.get('score') if before_save_doc else 'DOC_NOT_FOUND'}, clock={before_save_doc.get('clock') if before_save_doc else 'DOC_NOT_FOUND'}")
                    
                    # Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
                    timeout_turn = gm.turns.pop()
                    
                    # ✅ UNIFIED: Use shared helper function (same as user timeout)
                    timeout_response = handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="COMPUTER")
                    
                    # ⏱️ PERFORMANCE: Log timeout return path
                    total_time = (time.time() - start_time) * 1000
                    response_size = len(str(timeout_response).encode('utf-8'))
                    logging.warning(
                        f"⏱️ [PERF] /api/simulate-turn - TIMEOUT PATH, quarter={gm.quarter}, "
                        f"response_size: {response_size} bytes, total: {total_time:.2f}ms"
                    )
                    return timeout_response
                except Exception as e:
                    logging.error(f"🚨 COMPUTER TIMEOUT: Failed to save game state: {e}")
                    # Don't fail the timeout return if save fails - game is still in memory
                    # Return timeout turn without save (fallback)
                    timeout_turn = gm.turns.pop() if gm.turns else None
                    if timeout_turn:
                        return {
                            "turn": timeout_turn,
                            "time_remaining": gm.game_state.get("time_remaining", 480),
                            "clock": gm.game_state.get("clock", "8:00"),
                            "quarter_complete": False,
                            "quarter": gm.quarter
                        }
                # ⏱️ PERFORMANCE: Log timeout return path
                total_time = (time.time() - start_time) * 1000
                response_size = len(str(timeout_response).encode('utf-8'))
                logging.warning(
                    f"⏱️ [PERF] /api/simulate-turn - TIMEOUT PATH, quarter={gm.quarter}, "
                    f"response_size: {response_size} bytes, total: {total_time:.2f}ms"
                )
                return timeout_response
        
        # Track how many turns existed before this call (after deferred timeout check)
        turns_before = len(gm.turns)
        time_before_turn = gm.game_state["time_remaining"]
        
        # ⏱️ PERFORMANCE: Time the turn simulation
        turn_sim_start = time.time()
        # Simulate the next turn (unless we already returned a timeout above)
        gm.simulate_macro_turn()
        turn_sim_time = (time.time() - turn_sim_start) * 1000
        
        time_after_turn = gm.game_state["time_remaining"]
        
        # Update team fouls in game state
        gm.game_state["team_fouls"] = {
            gm.home_team.name: gm.home_team.team_fouls,
            gm.away_team.name: gm.away_team.team_fouls,
        }
        
        # Get all NEW turns created by this call
        # (simulate_macro_turn can create multiple turns for OREBs, side inbounds, etc.)
        new_turns = gm.turns[turns_before:] if len(gm.turns) > turns_before else []
        
        if not new_turns:
            # No turns were created (shouldn't happen, but handle gracefully)
            latest_turn = None
        elif len(new_turns) == 1:
            # Normal case: one turn created
            latest_turn = new_turns[0]
        else:
            # Multiple turns created (e.g., HCO miss → OREB turn)
            # Return them as a batch for the frontend to animate sequentially
            latest_turn = {
                "result_type": "BATCH",
                "batch_turns": new_turns,
                "text": " → ".join(t.get("text", "") for t in new_turns)
            }
        
        # Check if quarter is now complete
        quarter_complete = gm.game_state["time_remaining"] <= 0
        
        # Debug logging for quarter completion check
        if quarter_complete:
            turn_type = latest_turn.get("result_type", "UNKNOWN") if latest_turn else "NONE"
            turn_text = latest_turn.get("text", "")[:50] if latest_turn else ""
            time_elapsed = time_before_turn - time_after_turn
            logging.info(f"✅ [FINAL TURN DEBUG] Quarter complete! time_before_turn={time_before_turn}s, time_after_turn={time_after_turn}s, time_elapsed={time_elapsed}s, clock={gm.game_state.get('clock', 'N/A')}, turn_type={turn_type}, turn_text={turn_text}")
        
        # ✅ QUARTER BREAK RECHARGE: Recharge all players when quarter completes
        # This happens BEFORE game state is saved, so updated NG values are visible on lineup screen
        # Matches timeout recharge pattern (recharge happens before lineup screen)
        if quarter_complete:
            from BackEnd.utils.energy_system import recharge_all_players
            current_quarter = gm.quarter  # Quarter that just completed (before increment)
            # Determine recharge amounts based on which quarter just completed
            # Q2->Q3 (halftime): [0.15, 0.16, 0.17, 0.18, 0.19, 0.2]
            # Q1->Q2, Q3->Q4, or before OT: [0.07, 0.08, 0.09, 0.1, 0.11, 0.12]
            if current_quarter == 2:
                # Halftime break (between Q2 and Q3)
                recharge_amounts = [0.15, 0.16, 0.17, 0.18, 0.19, 0.2]
            else:
                # Regular quarter break (Q1->Q2, Q3->Q4, or before OT)
                recharge_amounts = [0.07, 0.08, 0.09, 0.1, 0.11, 0.12]
            
            recharge_all_players(gm, recharge_amounts)
        
        # If quarter is complete, increment quarter number
        if quarter_complete:
            gm.quarter += 1
            gm.game_state["quarter"] = gm.quarter  # ✅ FIX: Ensure game_state is updated
            logging.info(f"✅ Advanced to quarter {gm.quarter}")
        
        # Check if game is final (Q4+ complete and not tied)
        # Use the quarter BEFORE increment to avoid premature final at end of Q3
        quarter_before_increment = gm.quarter - 1 if quarter_complete else gm.quarter
        is_final = (
            quarter_complete
            and quarter_before_increment >= 4  # End-of-regulation or later
            and gm.score.get(gm.home_team.name, 0) != gm.score.get(gm.away_team.name, 0)
        )
        
        # ✅ PERFORMANCE: Save game state every 25 turns (reduced from 10 for better performance)
        # Still save on quarter complete to ensure quarter number is persisted
        # 25 turns is still sufficient for crash recovery (saves ~13 times per game vs 32)
        db_save_time = 0
        if len(gm.turns) % 25 == 0 or quarter_complete:
            db_save_start = time.time()
            try:
                db_summary = summarize_game_state(gm, exclude_animations=True)
                games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
                logging.info(f"💾 Saved game state at turn {len(gm.turns)}, quarter={gm.quarter}")
            except Exception as e:
                logging.error(f"Failed to save game state: {e}")
            finally:
                db_save_time = (time.time() - db_save_start) * 1000
        
        # Return turn data + metadata
        response_data = {
            "turn": latest_turn,
            "next_offensive_state": gm.game_state.get("offensive_state", "HCO"),
            "time_remaining": gm.game_state["time_remaining"],
            "clock": gm.game_state.get("clock", "8:00"),
            "quarter_complete": quarter_complete,
            "quarter": gm.quarter,
            "is_final": is_final,
            "home_score": gm.score.get(gm.home_team.name, 0),
            "away_score": gm.score.get(gm.away_team.name, 0),
            "home_team_fouls": gm.home_team.team_fouls,
            "away_team_fouls": gm.away_team.team_fouls,
            "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
            "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
            "offense_team": gm.offense_team.name,
            "defense_team": gm.defense_team.name,
            "game_id": game_id,
            "ineligible_players": gm.game_state.get("ineligible_players", []),  # Players with 5+ fouls
            # Box score for real-time updates
            "box_score": gm.get_box_score(),
            "team_totals": {
                gm.home_team.name: gm.home_team.get_team_game_stats(),
                gm.away_team.name: gm.away_team.get_team_game_stats()
            }
        }
        
        # Debug log for unexpected quarter complete
        if quarter_complete and gm.game_state["time_remaining"] != 0:
            logging.warning(f"⚠️ Quarter complete but time_remaining != 0: {gm.game_state['time_remaining']}")
        
        # ⏱️ PERFORMANCE: Log total endpoint time
        total_time = (time.time() - start_time) * 1000
        response_size = len(str(response_data).encode('utf-8'))
        turn_number = len(gm.turns)
        logging.warning(
            f"⏱️ [PERF] /api/simulate-turn - turn={turn_number}, quarter={gm.quarter}, "
            f"simulation: {turn_sim_time:.2f}ms, db_save: {db_save_time:.2f}ms, "
            f"response_size: {response_size} bytes, total: {total_time:.2f}ms, "
            f"quarter_complete={quarter_complete}"
        )
        
        return response_data
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.exception(f"Failed to simulate turn for game {game_id}")
        logging.error(f"Full traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nFull traceback:\n{error_trace}")


@app.post("/api/set-playcall-override")
async def set_playcall_override_endpoint(raw_request: Request):
    # SS&S: Set persistent playcall overrides for user team.
    # Overrides are stored in team.strategy_calls and persist until used.
    # This replaces the old single-turn override system.
    # Only processes fields that are explicitly provided in the request body.
    # This prevents accidentally clearing other overrides when setting one.
    # Parse request body to see which fields were explicitly provided
    body = await raw_request.json()
    provided_fields = set(body.keys())
    
    # Validate using Pydantic model
    request = PlaycallOverrideRequest(**body)
    
    game_id = request.game_id
    gm = ongoing_games.get(game_id)
    
    # ✅ DEBUG: Track ongoing_games state for playcall override issue
    logging.warning(f"🔍 [ONGOING_GAMES DEBUG] set_playcall_override called: game_id={game_id}")
    logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game in ongoing_games: {gm is not None}")
    if gm:
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] Game object found - object_id={id(gm)}, quarter={gm.quarter}")
    else:
        logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ❌ Game NOT in ongoing_games! Available games: {list(ongoing_games.keys())}")
    
    if gm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Game {game_id} not found. Start a quarter first with /api/simulate-quarter"
        )
    
    # Determine user team
    user_team = gm.home_team if request.user_team_side == "home" else gm.away_team
    
    # ✅ DEBUG: Log team info with object IDs for tracking
    user_team_id = id(user_team)  # Python object ID to verify same object
    logging.warning(f"🎮 [PLAYCALL SET] API: Setting override on team object")
    logging.warning(f"   - user_team_side={request.user_team_side}, user_team={user_team.name}")
    logging.warning(f"   - team_id={user_team.team_id}, object_id={user_team_id}")
    logging.warning(f"   - Current strategy_calls: {user_team.strategy_calls}")
    logging.warning(f"   - game_id={game_id}, game_object_id={id(gm)}")
    logging.warning(f"   - Provided fields in request: {provided_fields}")
    
    # ✅ SS&S: Only process fields that were explicitly provided in the request
    # The frontend now only sends the field being changed, so we can safely process all provided fields
    # - If a field is provided and non-None → set it
    # - If a field is provided and None → clear it (explicit clear via red X)
    
    if "offense_override" in provided_fields:
        if request.offense_override is not None:
            user_team.strategy_calls["offense_call"] = request.offense_override
            logging.warning(f"🎮 [PLAYCALL SET] ✅ Offense override SET: '{request.offense_override}'")
            logging.warning(f"   - Team: {user_team.name} (team_id: {user_team.team_id}, object_id: {id(user_team)})")
            logging.warning(f"   - After setting, strategy_calls['offense_call'] = {user_team.strategy_calls.get('offense_call')}")
        else:
            # Explicitly clearing (None was passed and this is the only field or all fields are None)
            old_override = user_team.strategy_calls.get("offense_call")
            user_team.strategy_calls["offense_call"] = None
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
            logging.warning(f"🔴 [OVERRIDE CLEARED] API: Offense override CLEARED by user (red X button)")
            logging.warning(f"🔴   Team: {user_team.name} (team_id: {user_team.team_id})")
            logging.warning(f"🔴   Override that was cleared: '{old_override}'")
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
    
    if "defense_override" in provided_fields:
        if request.defense_override is not None:
            user_team.strategy_calls["defense_call"] = request.defense_override
            logging.warning(f"🎮 [PLAYCALL SET] ✅ Defense override SET: '{request.defense_override}'")
            logging.warning(f"   - Team: {user_team.name} (team_id: {user_team.team_id}, object_id: {id(user_team)})")
            logging.warning(f"   - After setting, strategy_calls['defense_call'] = {user_team.strategy_calls.get('defense_call')}")
        else:
            # Explicitly clearing (None was passed and this is the only field or all fields are None)
            old_override = user_team.strategy_calls.get("defense_call")
            user_team.strategy_calls["defense_call"] = None
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
            logging.warning(f"🔴 [OVERRIDE CLEARED] API: Defense override CLEARED by user (red X button)")
            logging.warning(f"🔴   Team: {user_team.name} (team_id: {user_team.team_id})")
            logging.warning(f"🔴   Override that was cleared: '{old_override}'")
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
    
    if "aggression_override" in provided_fields:
        if request.aggression_override is not None:
            user_team.strategy_calls["aggression_override"] = request.aggression_override
            logging.warning(f"🎮 [PLAYCALL SET] ✅ Aggression override SET: '{request.aggression_override}'")
            logging.warning(f"   - Team: {user_team.name} (team_id: {user_team.team_id}, object_id: {id(user_team)})")
        else:
            # Explicitly clearing (None was passed and this is the only field or all fields are None)
            old_override = user_team.strategy_calls.get("aggression_override")
            user_team.strategy_calls["aggression_override"] = None
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
            logging.warning(f"🔴 [OVERRIDE CLEARED] API: Aggression override CLEARED by user (red X button)")
            logging.warning(f"🔴   Team: {user_team.name} (team_id: {user_team.team_id})")
            logging.warning(f"🔴   Override that was cleared: '{old_override}'")
            logging.warning(f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴")
    
    if "tempo_override" in provided_fields and request.tempo_override is not None:
        user_team.strategy_calls["tempo_override"] = request.tempo_override
        logging.info(f"🎮 [PLAYCALL OVERRIDE] Set tempo override for {user_team.name}: {request.tempo_override}")
    
    return {
        "status": "success",
        "overrides": {
            "offense": user_team.strategy_calls.get("offense_call"),
            "defense": user_team.strategy_calls.get("defense_call"),
            "aggression": user_team.strategy_calls.get("aggression_override"),
            "tempo": user_team.strategy_calls.get("tempo_override")
        }
    }


@app.post("/api/call-timeout")
async def call_timeout_endpoint(request: CallTimeoutRequest):
    # User-initiated timeout endpoint.
    # Creates a TIMEOUT turn and saves game state before navigating to lineup screen.
    game_id = request.game_id
    calling_team_side = request.calling_team  # 'home' or 'away'
    
    gm = ongoing_games.get(game_id)
    if gm is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found.")
    
    calling_team = gm.home_team if calling_team_side == 'home' else gm.away_team
    
    # Use unified timeout creation method (same as computer timeouts)
    timeout_turn = gm.call_timeout(
        calling_team=calling_team,
        timeout_reason="USER",
        rebuild_both_lineups=False,  # User timeout only rebuilds computer team
        game_id=None  # Don't save here - we'll save below
    )
    
    if not timeout_turn:
        raise HTTPException(
            status_code=400,
            detail=f"{calling_team.name} has no timeouts remaining."
        )
    
    # ✅ UNIFIED: Use shared helper function for timeout save and response
    # This ensures user and computer timeouts work identically
    try:
        # 🔍 DEBUG: Log state BEFORE save
        logging.warning(f"🔍 [USER TIMEOUT SAVE DEBUG] BEFORE save - game_id={game_id}, quarter={gm.quarter}")
        logging.warning(f"🔍 [USER TIMEOUT SAVE DEBUG] gm.game_state timeout fields: timeout_next_play_type={gm.game_state.get('timeout_next_play_type')}, timeout_offense_team_id={gm.game_state.get('timeout_offense_team_id')}")
        logging.warning(f"🔍 [USER TIMEOUT SAVE DEBUG] gm.score={gm.score}, clock={gm.game_state.get('clock')}, time_remaining={gm.game_state.get('time_remaining')}")
        
        # Use unified helper function (same as computer timeout)
        timeout_response = handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="USER")
        
        # Return response with additional fields for user timeout endpoint compatibility
        return {
            "message": f"Timeout called by {calling_team.name}",
            "calling_team": calling_team.name,
            "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
            "home_team_timeouts": timeout_response["home_team_timeouts"],
            "away_team_timeouts": timeout_response["away_team_timeouts"],
            "clock": timeout_response["clock"],  # ✅ Use saved data from DB (not cache)
            "time_remaining": timeout_response["time_remaining"],  # ✅ Use saved data from DB (not cache)
            "turn": timeout_response["turn"],  # Include turn for frontend consistency
            "quarter": timeout_response["quarter"],
            "quarter_complete": timeout_response["quarter_complete"],
            "home_score": timeout_response["home_score"],
            "away_score": timeout_response["away_score"],
            "game_id": timeout_response["game_id"]
        }
    except Exception as e:
        logging.error(f"🚨 TIMEOUT: Failed to save game state: {e}")
        # Don't fail the timeout call if save fails - game is still in memory
        # Return fallback response
        return {
            "message": f"Timeout called by {calling_team.name}",
            "calling_team": calling_team.name,
            "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
            "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
            "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
            "clock": gm.game_state.get("clock", "8:00"),
            "time_remaining": gm.game_state.get("time_remaining", 480),
        }


@app.get("/roster/{team_name}")
def get_team_roster(team_name: str, tournament_id: str | None = None, franchise_id: str | None = None, response: Response = None):
    endpoint_start = time.time()
    # ✅ FIX: Add cache-busting headers to ensure browser fetches fresh player data
    # This ensures updated player attributes (year, jersey, height, etc.) show up immediately
    if response:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    # ✅ UNIFIED: Support both tournament_id and franchise_id for mode-specific attributes
    # Tournament ID is currently ignored (future enhancement), franchise_id merges attributes

    # ✅ PERFORMANCE: Use MongoDB query for case-insensitive team lookup instead of loading all teams
    # This reduces data transfer from loading 8-16 teams to just 1 query
    normalized_name = unidecode(team_name.strip().replace("-", " ")).lower()
    
    # Use MongoDB aggregation for case-insensitive matching
    pipeline = [
        {
            "$addFields": {
                "normalized_name": {
                    "$toLower": {"$replaceAll": {"input": "$name", "find": "-", "replacement": " "}}
                }
            }
        },
        {
            "$match": {
                "normalized_name": normalized_name
            }
        },
        {
            "$limit": 1
        }
    ]
    
    query_start = time.time()
    team_result = list(teams_collection.aggregate(pipeline))
    query_time = (time.time() - query_start) * 1000
    match = team_result[0]["name"] if team_result else None

    if not match:
        print(f"❌ No team found matching: {normalized_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    load_start = time.time()
    team_doc, player_objects = load_roster(match)
    load_time = (time.time() - load_start) * 1000

    if not player_objects:
        print(f"❌ No players found for {team_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    team = team_doc or {"name": team_name}

    # ✅ UNIFIED: Load franchise-specific attributes if franchise_id is provided
    franchise_players = {}
    if franchise_id:
        try:
            fid = ObjectId(franchise_id)
            franchise_doc = franchises_collection.find_one({"_id": fid}, {"players": 1, "_id": 1})
            if franchise_doc:
                franchise_players = franchise_doc.get("players", {})
        except Exception as e:
            logging.warning(f"⚠️ Error loading franchise document {franchise_id}: {e}")

    display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]

    process_start = time.time()
    players = []
    for p in player_objects:
        player_id_str = str(p.get("_id"))
        
        # ✅ SS&S: For franchise mode, use franchise.players as single source of truth (no merging)
        if franchise_id and player_id_str in franchise_players:
            franchise_player_data = franchise_players[player_id_str]
            merged_attributes = franchise_player_data.get("attributes", {}).copy()
            # Ensure anchor_ versions exist (they should after initialization, but be safe)
            for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
                if attr_key in merged_attributes and f"anchor_{attr_key}" not in merged_attributes:
                    merged_attributes[f"anchor_{attr_key}"] = merged_attributes[attr_key]
        else:
            # Base mode or tournament mode - use universal collection attributes
            core_attributes = p.get("attributes", {})
            merged_attributes = core_attributes.copy()
            # Create anchor_ prefixed attributes (like Player class does)
            for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
                if attr_key in merged_attributes:
                    merged_attributes[f"anchor_{attr_key}"] = merged_attributes[attr_key]
        
        # ✅ SS&S: For franchise mode, use franchise.players as single source of truth for position_ratings
        if franchise_id and player_id_str in franchise_players:
            franchise_player_data = franchise_players[player_id_str]
            position_ratings = franchise_player_data.get("position_ratings", {})
        else:
            # Base mode or tournament mode - use universal collection position_ratings
            position_ratings = p.get("position_ratings", {})
        
        players.append({
            "_id": player_id_str,
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "year": p.get("year"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "jersey": p.get("jersey", 0),
            "position_ratings": position_ratings,
            "attributes": merged_attributes,  # Return merged attributes (franchise overrides core)
        })
    process_time = (time.time() - process_start) * 1000

    response_data = {
        "team": team.get("name", team_name),
        "team_name": team.get("name", team_name),
        "players": players
    }
    
    # Measure response size
    response_size = len(json.dumps(response_data))
    total_time = (time.time() - endpoint_start) * 1000
    logging.warning(f"⏱️ [PERF] /roster/{team_name} - DB query: {query_time:.2f}ms, load_roster: {load_time:.2f}ms, processing: {process_time:.2f}ms, response_size: {response_size} bytes, total: {total_time:.2f}ms")
    
    return response_data


@app.post("/api/init-game")
def init_game(request: dict):
    endpoint_start = time.time()
    # Initialize a game document with players (Emotion, Momentum) before first quarter starts
    from BackEnd.models.game_manager import GameManager
    from BackEnd.utils.game_id_utils import generate_game_id
    from BackEnd.utils.shared import summarize_game_state
    from BackEnd.main import _initialize_game_stats
    
    home_team = request.get("home_team")
    away_team = request.get("away_team")
    mode = request.get("mode", "single")
    tournament_id = request.get("tournament_id")
    franchise_id = request.get("franchise_id")
    
    if not home_team or not away_team:
        raise HTTPException(status_code=400, detail="home_team and away_team required")
    
    # ✅ FIX: Load playbook_settings from tournament/franchise document before creating GameManager
    # This ensures playbook_settings are stored in the initial game document
    settings_start = time.time()
    home_playbook_settings = {}
    away_playbook_settings = {}
    
    if mode == "tournament" and tournament_id:
        home_settings = load_team_settings_from_doc(
            mode,
            tournament_id,
            None,
            home_team
        )
        away_settings = load_team_settings_from_doc(
            mode,
            tournament_id,
            None,
            away_team
        )
        if home_settings:
            home_playbook_settings = home_settings.get("playbook_settings", {})
        if away_settings:
            away_playbook_settings = away_settings.get("playbook_settings", {})
    elif mode == "franchise" and franchise_id:
        home_settings = load_team_settings_from_doc(
            mode,
            franchise_id,
            None,
            home_team
        )
        away_settings = load_team_settings_from_doc(
            mode,
            franchise_id,
            None,
            away_team
        )
        if home_settings:
            home_playbook_settings = home_settings.get("playbook_settings", {})
        if away_settings:
            away_playbook_settings = away_settings.get("playbook_settings", {})
    settings_time = (time.time() - settings_start) * 1000
    
    # Generate game_id
    game_id = generate_game_id()
    
    # Create GameManager (this initializes teams and players)
    gm_start = time.time()
    logging.warning(f"⏱️ [PERF] /api/init-game - Starting GameManager creation")
    gm = GameManager(home_team, away_team, mode=mode)
    gm_create_time = (time.time() - gm_start) * 1000
    logging.warning(f"⏱️ [PERF] /api/init-game - GameManager created: {gm_create_time:.2f}ms")
    
    # Initialize game stats (this randomizes EM, CH, MO for all players)
    stats_start = time.time()
    _initialize_game_stats(gm, game_id=None)  # None = new game, will randomize
    stats_time = (time.time() - stats_start) * 1000
    logging.warning(f"⏱️ [PERF] /api/init-game - Game stats initialized: {stats_time:.2f}ms")
    gm_time = (time.time() - gm_start) * 1000
    
    # Create minimal game document with players
    # CRITICAL: Ensure scores are zeroed before summarizing
    summary_start = time.time()
    gm.score = {home_team: 0, away_team: 0}
    summary = summarize_game_state(gm, exclude_animations=True)
    summary["_id"] = game_id
    summary["game_stats_initialized"] = True
    summary["quarter"] = 1  # Pre-game, but set to 1 so simulate-quarter works correctly
    # Ensure score is explicitly zeroed in summary (summarize_game_state should already include this, but be explicit)
    summary["score"] = {home_team: 0, away_team: 0}
    if "home_team" in summary and isinstance(summary["home_team"], dict):
        summary["home_team"]["score"] = 0
    if "away_team" in summary and isinstance(summary["away_team"], dict):
        summary["away_team"]["score"] = 0
    
    # ✅ Set mode and mode-specific IDs on game document for playbook settings persistence
    # This ensures _load_playbook_settings() can find the correct tournament/franchise document during gameplay
    summary["mode"] = mode
    if mode == "tournament" and tournament_id:
        summary["tournament_id"] = str(tournament_id)
    elif mode == "franchise" and franchise_id:
        summary["franchise_id"] = str(franchise_id)
    
    # ✅ FIX: Store playbook_settings in game document's teams object
    # This ensures playbook_settings are available from the start and persist through saves
    if "teams" not in summary:
        summary["teams"] = {}
    
    home_team_id = gm.home_team.team_id
    away_team_id = gm.away_team.team_id
    
    if home_team_id not in summary["teams"]:
        summary["teams"][home_team_id] = {}
    if away_team_id not in summary["teams"]:
        summary["teams"][away_team_id] = {}
    
    summary["teams"][home_team_id]["playbook_settings"] = home_playbook_settings
    summary["teams"][away_team_id]["playbook_settings"] = away_playbook_settings
    summary_time = (time.time() - summary_start) * 1000
    
    # Set GameManager quarter to 1 to match
    gm.quarter = 1
    
    # Save to database
    db_start = time.time()
    games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
    db_time = (time.time() - db_start) * 1000
    
    # Store in ongoing_games so /api/game/{game_id} can access it
    ongoing_games[game_id] = gm
    logging.warning(f"🔍 [ONGOING_GAMES DEBUG] ✅ Added game to ongoing_games (init-game path): game_id={game_id}, object_id={id(gm)}, quarter={gm.quarter}")
    
    response_data = {"game_id": game_id}
    response_size = len(json.dumps(response_data))
    total_time = (time.time() - endpoint_start) * 1000
    logging.warning(f"⏱️ [PERF] /api/init-game - settings: {settings_time:.2f}ms, GameManager: {gm_time:.2f}ms, summary: {summary_time:.2f}ms, DB save: {db_time:.2f}ms, response_size: {response_size} bytes, total: {total_time:.2f}ms")
    
    return response_data


@app.get("/games")
def get_games():
    # Fetch the 10 most recent games (you can adjust this)
    games = list(games_collection.find().sort("_id", -1).limit(10))

    # Convert ObjectId to string for JSON serialization
    for game in games:
        game["_id"] = str(game["_id"])

    return JSONResponse(content=games)

@app.get("/player/{player_id}")
def get_player(player_id: str):
    try:
        print(f"🔍 Looking up player with ID: {player_id}")
        player = players_collection.find_one({"_id": player_id})
        if not player:
            print(f"❌ Player not found with _id: {player_id}")
            # Try a broader search to help debug
            sample = players_collection.find_one({})
            if sample:
                # Debug logging removed - was cluttering logs
                # logging.debug(f"📋 Sample player _id format: {sample.get('_id')} (type: {type(sample.get('_id'))})")
                pass
            raise HTTPException(status_code=404, detail="Player not found")
        # Debug logging removed - was cluttering logs
        # logging.debug(f"✅ Player found: {player.get('first_name')} {player.get('last_name')}")
        player["_id"] = str(player["_id"])  # ensure JSON serializable
        return player
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_player: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# for route in app.routes:
#     print(f"🚀 Registered route: {route.path}")


@app.get("/teams/{team_id}/players")
def get_team_players(team_id: str):
    # Return roster data for a given team.
    team_doc, players = load_roster(team_id)
    if not players:
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_id}'")

    display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]
    players_data = []
    for p in players:
        attributes = p.get("attributes", {})
        players_data.append({
            "_id": str(p.get("_id")),
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "year": p.get("year"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "position_ratings": p.get("position_ratings", {}),
            "attributes": {attr: attributes.get(attr, "--") for attr in display_attributes},
            "stats": p.get("stats", {}).get("season", {}),
        })

    return {
        "team": team_doc.get("name", team_id) if team_doc else team_id,
        "players": players_data,
    }


@app.get("/team-roster/{team}", response_class=HTMLResponse)
def team_roster_page(request: Request, team: str):
    # Render an HTML roster page for a given team.
    players_cursor = players_collection.find({"team": team})
    players = []
    order = ["PG", "SG", "SF", "PF", "C"]
    year_map = {
        "senior": "SR",
        "junior": "JR",
        "sophomore": "SO",
        "freshman": "FR",
    }
    for p in players_cursor:
        attrs = p.get("attributes", {})
        raw_height = p.get("height")
        try:
            height_raw = int(float(raw_height))
        except (TypeError, ValueError):
            height_raw = None
        display_attributes = [
            "SC",
            "SH",
            "ID",
            "OD",
            "PS",
            "BH",
            "RB",
            "AG",
            "ST",
            "ND",
            "IQ",
            "FT",
        ]

        pos_ratings = p.get("position_ratings") or {}
        pos = "-"
        rt_val: int | None = None
        for o in order:
            rating = pos_ratings.get(o)
            if rating is None:
                continue
            if rt_val is None or rating > rt_val:
                pos, rt_val = o, rating
        rt = int(rt_val) if rt_val is not None else "-"

        year_raw = p.get("year", "--")
        year_abbr = year_map.get(str(year_raw).lower(), year_raw or "--")

        # Convert attributes to 0-12 display scale
        display_attrs = {}
        for attr in display_attributes:
            raw_val = attrs.get(attr)
            if raw_val == "--" or raw_val is None:
                display_attrs[attr] = "--"
            else:
                display_attrs[attr] = int(raw_val // 10)  # Convert to 0-12 scale

        players.append(
            {
                "_id": str(p.get("_id")),  # Add player ID for linking
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "pos": pos,
                "year": year_abbr,
                "height": format_height(raw_height),
                "height_raw": height_raw,
                "weight": p.get("weight", "--"),
                "attributes": display_attrs,
                "position_ratings": p.get("position_ratings", {}),
                "rt": rt,
                "rt_value": rt_val if rt_val is not None else -1,
            }
        )

    players.sort(key=lambda x: x.get("rt_value", -1), reverse=True)

    template_name = f"team-roster/team-roster-{team.replace(' ', '-')}.html"
    return templates.TemplateResponse(
        template_name, {"request": request, "team": team, "players": players}
    )


@app.get("/tournament/active")
def get_active_tournament(user_team_id: Optional[str] = "BENTLEY-TRUMAN"):
    # Fetch the most recently created active tournament or create one.
    doc = tournaments_collection.find_one({"completed": False}, sort=[("created_at", -1)])
    if not doc:
        manager = TournamentManager(user_team_id=user_team_id, tournaments_collection=tournaments_collection)
        doc = manager.create_tournament()
    else:
        doc["_id"] = str(doc["_id"])
    # ✅ SS&S: Serialize all ObjectIds in nested structures (consistent with /tournament/state)
    from bson import ObjectId
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(doc, custom_encoder={ObjectId: str})


class SimQuarterDiagnosticRequest(BaseModel):
    gameId: str
    quarter: int
    homeTeam: str
    awayTeam: str
    timestamp: str
    scoreIncrements: list
    printedEvents: list
    mismatches: list
    totalScoreIncrements: int
    totalPrintedEvents: int
    mismatchCount: int


@app.post("/api/diagnostics/sim-quarter")
def save_sim_quarter_diagnostics(request: SimQuarterDiagnosticRequest):
    """
    Save Sim Quarter diagnostic data to a markdown file.
    Tracks score increments and printed events to identify missing prints.
    """
    try:
        # Create diagnostics directory if it doesn't exist
        diagnostics_dir = Path("docs/0_Text_Scroll_Debug")
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
        filename = f"sim_quarter_diagnostics_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.md"
        filepath = diagnostics_dir / filename
        
        # Build markdown content
        md_content = f"""# Sim Quarter Text Scroll Diagnostics

**Generated:** {request.timestamp}  
**Game ID:** {request.gameId}  
**Quarter:** {request.quarter}  
**Teams:** {request.homeTeam} vs {request.awayTeam}

## Summary

- **Total Score Increments:** {request.totalScoreIncrements}
- **Total Printed Events:** {request.totalPrintedEvents}
- **Mismatches (Missing Prints):** {request.mismatchCount}

---

## Score Increments

"""
        
        # Add score increments
        for i, inc in enumerate(request.scoreIncrements, 1):
            time_display = inc.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            
            md_content += f"""### Score Increment #{i}

- **Time:** {time_display}
- **Home Score Change:** +{inc.get('homeScoreChange', 0)}
- **Away Score Change:** +{inc.get('awayScoreChange', 0)}
- **Total Points:** {inc.get('homeScoreChange', 0) + inc.get('awayScoreChange', 0)}
- **Result Type:** {inc.get('resultType', 'N/A')}
- **Points (from turn):** {inc.get('points', 0)}
- **Shooter ID:** {inc.get('shooterId', 'N/A')}
- **New Scores:** {inc.get('newHomeScore', 0)} - {inc.get('newAwayScore', 0)}

"""
        
        md_content += "\n---\n\n## Printed Events\n\n"
        
        # Add printed events
        for i, event in enumerate(request.printedEvents, 1):
            time_display = event.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            
            md_content += f"""### Printed Event #{i}

- **Time:** {time_display}
- **Event Type:** {event.get('eventType', 'N/A')}
- **Result Type:** {event.get('resultType', 'N/A')}
- **Points Scored:** {event.get('pointsScored', 0)}
- **Player:** {event.get('playerName', 'N/A')} {event.get('playerJersey', '')}
- **Shot Type:** {event.get('shotType', 'N/A')}
- **Fast Break:** {event.get('isFastBreak', False)}
- **Scores:** {event.get('homeScore', 0)} - {event.get('awayScore', 0)}

"""
        
        # Add mismatches section
        if request.mismatches:
            md_content += "\n---\n\n## ⚠️ Mismatches (Score Increments Without Prints)\n\n"
            
            for i, mismatch in enumerate(request.mismatches, 1):
                if mismatch.get('type') == 'MISSING_PRINT':
                    score_inc = mismatch.get('scoreIncrement', {})
                    time_display = score_inc.get('timeRemaining', 'N/A')
                    if isinstance(time_display, (int, float)):
                        minutes = int(time_display // 60)
                        seconds = int(time_display % 60)
                        time_display = f"{minutes}:{seconds:02d}"
                    
                    md_content += f"""### Missing Print #{i}

- **Time:** {time_display}
- **Turn Index:** {score_inc.get('turnIndex', 'N/A')}
- **Score Change:** +{score_inc.get('homeScoreChange', 0)} (home), +{score_inc.get('awayScoreChange', 0)} (away)
- **Total Points:** {score_inc.get('totalPoints', 0)}
- **Result Type:** {score_inc.get('resultType', 'N/A')}
- **Points (from turn):** {score_inc.get('points', 0)}
- **Shooter ID:** {score_inc.get('shooterId', 'N/A')}

**⚠️ WARNING:** This score increment was NOT printed in the text scroll!

"""
        
        # Try to write file (for local development)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"✅ [DIAGNOSTIC] Saved Sim Quarter diagnostic file: {filepath}")
        except Exception as e:
            logger.warning(f"⚠️ [DIAGNOSTIC] Could not write file to filesystem (Railway ephemeral): {e}")
        
        # Return markdown content in response so frontend can download it
        return {
            "status": "success",
            "filename": filename,
            "mismatchCount": request.mismatchCount,
            "markdownContent": md_content  # Include content for frontend download
        }
    
    except Exception as e:
        logger.error(f"❌ [DIAGNOSTIC] Failed to save diagnostic file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save diagnostic file: {str(e)}")


class FTFGDiagnosticRequest(BaseModel):
    gameId: str
    quarter: int
    homeTeam: str
    awayTeam: str
    timestamp: str
    freeThrowEvents: list
    madeFGEvents: list
    printedFTEvents: list
    printedMadeFGEvents: list
    allPrintedEvents: list = []  # ✅ NEW: All printed events (not just FT/FG)
    playerLookupFailures: list = []  # ✅ NEW: Track when playerMap lookups fail
    playerMapStats: dict = {}  # ✅ NEW: PlayerMap statistics
    scoreboardUpdates: list = []  # ✅ NEW: Track every scoreboard update
    madeShotVerifications: list = []  # ✅ NEW: Track every made shot with print + scoreboard verification
    unmatchedPrints: list = []  # ✅ NEW: Track prints that don't link to made shots
    ftMismatches: list
    fgMismatches: list
    totalFreeThrows: int
    totalMadeFGs: int
    totalPrintedFTs: int
    totalPrintedMadeFGs: int
    totalAllPrintedEvents: int = 0  # ✅ NEW: Total printed events
    totalLookupFailures: int = 0  # ✅ NEW: Total lookup failures
    totalScoreboardUpdates: int = 0  # ✅ NEW: Total scoreboard updates
    totalMadeShotVerifications: int = 0  # ✅ NEW: Total made shot verifications
    totalUnmatchedPrints: int = 0  # ✅ NEW: Total unmatched prints
    ftMismatchCount: int
    fgMismatchCount: int


@app.post("/api/diagnostics/ft-fg-analysis")
def save_ft_fg_diagnostics(request: FTFGDiagnosticRequest):
    """
    Save Free Throw and Made Field Goal diagnostic data to a markdown file.
    Tracks free throws and made FGs to identify edge cases where result types don't match.
    """
    try:
        # Create diagnostics directory if it doesn't exist
        diagnostics_dir = Path("docs/0_Text_Scroll_Debug")
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
        filename = f"ft_fg_analysis_{timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.md"
        filepath = diagnostics_dir / filename
        
        # Build markdown content
        md_content = f"""# Free Throw & Made Field Goal Analysis

**Generated:** {request.timestamp}  
**Game ID:** {request.gameId}  
**Quarter:** {request.quarter}  
**Teams:** {request.homeTeam} vs {request.awayTeam}

## Summary

- **Total Free Throws (from turns):** {request.totalFreeThrows}
- **Total Printed Free Throws:** {request.totalPrintedFTs}
- **Free Throw Mismatches:** {request.ftMismatchCount}
- **Total Made Field Goals (from turns):** {request.totalMadeFGs}
- **Total Printed Made FGs:** {request.totalPrintedMadeFGs}
- **Made FG Mismatches:** {request.fgMismatchCount}
- **Total All Printed Events:** {request.totalAllPrintedEvents}
- **Total Player Lookup Failures:** {request.totalLookupFailures}
- **Total Scoreboard Updates:** {request.totalScoreboardUpdates}
- **PlayerMap Stats:** {request.playerMapStats.get('totalPlayers', 0) if request.playerMapStats else 0} players, {request.playerMapStats.get('playerMapSize', 0) if request.playerMapStats else 0} in map

---

## Free Throw Events

"""
        
        # Add free throw events
        for i, ft in enumerate(request.freeThrowEvents, 1):
            time_display = ft.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            elif time_display == 'N/A' or time_display is None:
                time_display = 'N/A'
            
            score = ft.get('score', {})
            home_score = score.get(request.homeTeam, score.get('home', 0))
            away_score = score.get(request.awayTeam, score.get('away', 0))
            
            md_content += f"""### Free Throw #{i}

- **Time:** {time_display}
- **Turn Index:** {ft.get('turnIndex', 'N/A')}
- **Shooter ID:** {ft.get('shooterId', 'N/A')}
- **Shooter Name (from turn):** {ft.get('shooterName', 'N/A')}
- **Turn Points:** {ft.get('turnPoints', 0)}
- **Expected Result:** {ft.get('expectedResultType', 'N/A')} (based on turn.points > 0)
- **Scores:** {home_score} - {away_score}

"""
        
        md_content += "\n---\n\n## Made Field Goal Events\n\n"
        
        # Add made FG events
        for i, fg in enumerate(request.madeFGEvents, 1):
            time_display = fg.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            elif time_display == 'N/A' or time_display is None:
                time_display = 'N/A'
            
            score = fg.get('score', {})
            home_score = score.get(request.homeTeam, score.get('home', 0))
            away_score = score.get(request.awayTeam, score.get('away', 0))
            
            md_content += f"""### Made Field Goal #{i}

- **Time:** {time_display}
- **Turn Index:** {fg.get('turnIndex', 'N/A')}
- **Shooter ID:** {fg.get('shooterId', 'N/A')}
- **Shooter Name (from turn):** {fg.get('shooterName', 'N/A')}
- **Turn Points:** {fg.get('turnPoints', 0)}
- **Scores:** {home_score} - {away_score}

"""
        
        md_content += "\n---\n\n## Printed Free Throw Events\n\n"
        
        # Add printed free throw events
        for i, pft in enumerate(request.printedFTEvents, 1):
            time_display = pft.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            elif time_display == 'N/A' or time_display is None:
                time_display = 'N/A'
            
            md_content += f"""### Printed Free Throw #{i}

- **Time:** {time_display}
- **Turn Index:** {pft.get('turnIndex', 'N/A')}
- **Player:** {pft.get('playerName', 'N/A')} {pft.get('playerJersey', '')}
- **Result Type (printed):** {pft.get('resultType', 'N/A')}
- **Scores:** {pft.get('homeScore', 0)} - {pft.get('awayScore', 0)}

"""
        
        md_content += "\n---\n\n## Printed Made Field Goal Events\n\n"
        
        # Add printed made FG events
        for i, pfg in enumerate(request.printedMadeFGEvents, 1):
            time_display = pfg.get('timeRemaining', 'N/A')
            if isinstance(time_display, (int, float)):
                minutes = int(time_display // 60)
                seconds = int(time_display % 60)
                time_display = f"{minutes}:{seconds:02d}"
            elif time_display == 'N/A' or time_display is None:
                time_display = 'N/A'
            
            md_content += f"""### Printed Made FG #{i}

- **Time:** {time_display}
- **Turn Index:** {pfg.get('turnIndex', 'N/A')}
- **Player:** {pfg.get('playerName', 'N/A')} {pfg.get('playerJersey', '')}
- **Shot Type:** {pfg.get('shotType', 'N/A')}
- **Points Scored:** {pfg.get('pointsScored', 0)}
- **Scores:** {pfg.get('homeScore', 0)} - {pfg.get('awayScore', 0)}

"""
        
        # Add scoreboard updates section
        if request.scoreboardUpdates:
            md_content += "\n---\n\n## Scoreboard Updates\n\n"
            
            for i, update in enumerate(request.scoreboardUpdates, 1):
                time_display = update.get('timeRemaining', 'N/A')
                if isinstance(time_display, (int, float)):
                    minutes = int(time_display // 60)
                    seconds = int(time_display % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                elif time_display == 'N/A' or time_display is None:
                    time_display = 'N/A'
                
                update_type = update.get('type', 'UNKNOWN')
                source = update.get('source', 'unknown')
                event_type = update.get('eventType', 'N/A')
                event_result = update.get('eventResultType', 'N/A')
                player_name = update.get('playerName', 'N/A')
                points_scored = update.get('pointsScored', 0)
                
                md_content += f"""### Scoreboard Update #{i}

- **Type:** {update_type}
- **Time:** {time_display}
- **Turn Index:** {update.get('turnIndex', 'N/A')}
- **Home Score:** {update.get('homeScore', 0)} (Change: {update.get('homeScoreChange', 0):+d})
- **Away Score:** {update.get('awayScore', 0)} (Change: {update.get('awayScoreChange', 0):+d})
- **Source:** {source}
"""
                
                if update_type == 'UPDATE':
                    md_content += f"- **Event Type:** {event_type}\n- **Event Result:** {event_result}\n- **Player:** {player_name}\n- **Points Scored:** {points_scored}\n"
                
                if update_type == 'FINAL' and 'previousHomeScore' in update:
                    md_content += f"- **Previous Home Score:** {update.get('previousHomeScore', 0)}\n- **Previous Away Score:** {update.get('previousAwayScore', 0)}\n"
                
                md_content += "\n"
        
        # Add made shot verifications section
        if request.madeShotVerifications:
            md_content += "\n---\n\n## Made Shot Verifications (Print + Scoreboard)\n\n"
            
            for i, verification in enumerate(request.madeShotVerifications, 1):
                time_display = verification.get('timeRemaining', 'N/A')
                if isinstance(time_display, (int, float)):
                    minutes = int(time_display // 60)
                    seconds = int(time_display % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                elif time_display == 'N/A' or time_display is None:
                    time_display = 'N/A'
                
                shot_type = verification.get('type', 'UNKNOWN')
                has_print = verification.get('hasPrint', False)
                has_scoreboard = verification.get('hasScoreboardUpdate', False)
                scoreboard_matches = verification.get('scoreboardMatches', False)
                
                status_icon = '✅' if (has_print and has_scoreboard and scoreboard_matches) else '⚠️'
                
                md_content += f"""### {status_icon} Made Shot Verification #{i}

- **Type:** {shot_type}
- **Time:** {time_display}
- **Turn Index:** {verification.get('turnIndex', 'N/A')}
- **Shooter:** {verification.get('shooterName', 'N/A')} (ID: {verification.get('shooterId', 'N/A')})
- **Turn Points:** {verification.get('turnPoints', 0)}
- **Has Print:** {'✅ Yes' if has_print else '❌ No'}
"""
                
                if has_print:
                    md_content += f"- **Print Result Type:** {verification.get('printResultType', 'N/A')}\n"
                    if shot_type == 'MADE_FG':
                        md_content += f"- **Print Points Scored:** {verification.get('printPointsScored', 0)}\n"
                
                md_content += f"- **Has Scoreboard Update:** {'✅ Yes' if has_scoreboard else '❌ No'}\n- **Expected Score Change:** {verification.get('expectedScoreChange', 0)}\n- **Actual Score Change:** {verification.get('actualScoreChange', 0)}\n- **Scoreboard Matches:** {'✅ Yes' if scoreboard_matches else '❌ No'}\n"
                
                if not has_print:
                    md_content += "\n**⚠️ WARNING:** Made shot was NOT printed in text scroll!\n"
                if not has_scoreboard:
                    md_content += "\n**⚠️ WARNING:** Made shot did NOT update scoreboard!\n"
                if has_scoreboard and not scoreboard_matches:
                    md_content += f"\n**⚠️ WARNING:** Scoreboard update ({verification.get('actualScoreChange', 0)}) doesn't match expected ({verification.get('expectedScoreChange', 0)})!\n"
                
                md_content += "\n"
        
        # Add unmatched prints section
        if request.unmatchedPrints:
            md_content += "\n---\n\n## ⚠️ Unmatched Prints (Prints Without Made Shots)\n\n"
            
            for i, print_event in enumerate(request.unmatchedPrints, 1):
                time_display = print_event.get('timeRemaining', 'N/A')
                if isinstance(time_display, (int, float)):
                    minutes = int(time_display // 60)
                    seconds = int(time_display % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                elif time_display == 'N/A' or time_display is None:
                    time_display = 'N/A'
                
                md_content += f"""### Unmatched Print #{i}

- **Type:** {print_event.get('type', 'UNKNOWN')}
- **Time:** {time_display}
- **Turn Index:** {print_event.get('turnIndex', 'N/A')}
- **Player:** {print_event.get('playerName', 'N/A')} (ID: {print_event.get('playerId', 'N/A')})
- **Result Type:** {print_event.get('resultType', 'N/A')}
- **Points Scored:** {print_event.get('pointsScored', 0)}
- **Shot Type:** {print_event.get('shotType', 'N/A')}
- **Scores:** {print_event.get('homeScore', 0)} - {print_event.get('awayScore', 0)}

**⚠️ WARNING:** This print does NOT have a corresponding made shot in the turn data!

"""
        
        # Add mismatches section
        if request.ftMismatches:
            md_content += "\n---\n\n## ⚠️ Free Throw Mismatches\n\n"
            
            for i, mismatch in enumerate(request.ftMismatches, 1):
                time_display = mismatch.get('timeRemaining', 'N/A')
                if isinstance(time_display, (int, float)):
                    minutes = int(time_display // 60)
                    seconds = int(time_display % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                elif time_display == 'N/A' or time_display is None:
                    time_display = 'N/A'
                
                mismatch_type = mismatch.get('type', 'UNKNOWN')
                if mismatch_type == 'RESULT_TYPE_MISMATCH':
                    md_content += f"""### Free Throw Mismatch #{i} - Result Type Mismatch

- **Time:** {time_display}
- **Turn Index:** {mismatch.get('turnIndex', 'N/A')}
- **Shooter:** {mismatch.get('shooterName', 'N/A')}
- **Expected Result (from turn.points):** {mismatch.get('expectedResultType', 'N/A')}
- **Printed Result:** {mismatch.get('printedResultType', 'N/A')}
- **Turn Points:** {mismatch.get('turnPoints', 0)}
- **Made (turn.points > 0):** {mismatch.get('made', False)}

**⚠️ WARNING:** Free throw result type mismatch! Expected {mismatch.get('expectedResultType', 'N/A')} but printed {mismatch.get('printedResultType', 'N/A')}

"""
                elif mismatch_type == 'NOT_PRINTED':
                    md_content += f"""### Free Throw Mismatch #{i} - Not Printed

- **Time:** {time_display}
- **Turn Index:** {mismatch.get('turnIndex', 'N/A')}
- **Shooter:** {mismatch.get('shooterName', 'N/A')}
- **Expected Result:** {mismatch.get('expectedResultType', 'N/A')}
- **Turn Points:** {mismatch.get('turnPoints', 0)}

**⚠️ WARNING:** Free throw was NOT printed in the text scroll!

"""
        
        if request.fgMismatches:
            md_content += "\n---\n\n## ⚠️ Made Field Goal Mismatches\n\n"
            
            for i, mismatch in enumerate(request.fgMismatches, 1):
                time_display = mismatch.get('timeRemaining', 'N/A')
                if isinstance(time_display, (int, float)):
                    minutes = int(time_display // 60)
                    seconds = int(time_display % 60)
                    time_display = f"{minutes}:{seconds:02d}"
                elif time_display == 'N/A' or time_display is None:
                    time_display = 'N/A'
                
                md_content += f"""### Made FG Mismatch #{i} - Not Printed

- **Time:** {time_display}
- **Turn Index:** {mismatch.get('turnIndex', 'N/A')}
- **Shooter:** {mismatch.get('shooterName', 'N/A')}
- **Turn Points:** {mismatch.get('turnPoints', 0)}

**⚠️ WARNING:** Made field goal was NOT printed in the text scroll!

"""
        
        # Try to write file (for local development)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"✅ [FT/FG DIAGNOSTIC] Saved analysis file: {filepath}")
        except Exception as e:
            logger.warning(f"⚠️ [FT/FG DIAGNOSTIC] Could not write file to filesystem (Railway ephemeral): {e}")
        
        # Return markdown content in response so frontend can download it
        return {
            "status": "success",
            "filename": filename,
            "markdownContent": md_content,
            "ftMismatchCount": request.ftMismatchCount,
            "fgMismatchCount": request.fgMismatchCount
        }
    
    except Exception as e:
        logger.error(f"❌ [FT/FG DIAGNOSTIC] Failed to save diagnostic file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save diagnostic file: {str(e)}")
