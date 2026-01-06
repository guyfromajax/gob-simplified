# 1. Imports
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from BackEnd.constants import POSITION_LIST
import uuid
from BackEnd.main import run_simulation, simulate_quarter
from BackEnd.models.game_manager import GameManager
from BackEnd.db import (
    players_collection,
    teams_collection,
    games_collection,
    tournaments_collection,
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
from BackEnd.models.player import Player

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(tournament_router)
app.include_router(training_router)
app.include_router(franchise_router)
app.include_router(gameplan_router)
app.include_router(play_router)
app.include_router(skeleton_router)

templates = Jinja2Templates(directory="FrontEnd/static")

# app.mount("/", StaticFiles(directory="FrontEnd", html=True), name="static")
# app.mount("/static", StaticFiles(directory="FrontEnd", html=True), name="static")
# Conditionally mount static files (only in development)
# In production, Netlify serves static files
environment = os.getenv("ENVIRONMENT", "development")
if environment == "development":
    app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")
    print("✅ Static files mounted (development mode)")

print("🚀 Loaded FastAPI app from api.py")

# CORS Configuration - Must match actual testing domains, not just final ideal
# CRITICAL: Include default Railway/Netlify domains initially, tighten later
def get_cors_origins():
    """
    Get CORS allowed origins based on environment.
    Includes default Railway/Netlify domains for initial deployment,
    custom domains when configured, and localhost for development.
    """
    origins = [
        "http://localhost:8000",  # Local development
        "http://localhost:3000",  # Alternative local port
    ]
    
    # Get custom origins from environment variable (comma-separated)
    custom_origins = os.getenv("CORS_ORIGINS", "")
    if custom_origins:
        origins.extend([origin.strip() for origin in custom_origins.split(",") if origin.strip()])
    
    return origins

# Get CORS origins
cors_origins = get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.(railway|netlify)\.app",  # Allow default Railway/Netlify domains (fixed regex)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

logger.info(f"🔒 CORS configured with origins: {cors_origins}")

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
    playcall_settings: dict[str, int] | None = None
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
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
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
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
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
                                logging.info(f"✅ TIMEOUT RESUME: Found game in tournament nested structure (round: {round_key})")
                                break
            except Exception as e:
                logging.warning(f"⚠️ TIMEOUT RESUME: Error loading from tournament nested structure: {e}")
            
            # Fallback to games_collection if not found in nested structure
            if not saved and games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                if saved:
                    logging.info(f"✅ TIMEOUT RESUME: Found game in games_collection (tournament fallback)")
        
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
                                logging.info(f"✅ TIMEOUT RESUME: Found game in franchise nested structure (week: {week_key})")
                                break
            except Exception as e:
                logging.warning(f"⚠️ TIMEOUT RESUME: Error loading from franchise nested structure: {e}")
            
            # Fallback to games_collection if not found in nested structure
            if not saved and games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                if saved:
                    logging.info(f"✅ TIMEOUT RESUME: Found game in games_collection (franchise fallback)")
        
        else:
            # Single game mode: Check games_collection
            if games_collection is not None:
                saved = games_collection.find_one({"_id": game_id})
                if saved:
                    logging.info(f"✅ TIMEOUT RESUME: Found game in games_collection (single mode)")
        
        if not saved:
            logging.warning(f"⚠️ TIMEOUT RESUME: Game {game_id} not found in any document location (mode: {request.mode})")
            return None
        
        # Validate that timeout_next_play_type exists
        if "timeout_next_play_type" not in saved:
            logging.error(f"❌ TIMEOUT RESUME: timeout_next_play_type missing from saved game {game_id}")
            return None
        
        logging.info(
            f"✅ TIMEOUT RESUME: Loaded state from DB - "
            f"timeout_next_play_type={saved.get('timeout_next_play_type')}, "
            f"quarter={saved.get('quarter')}, clock={saved.get('clock')}, mode={request.mode}"
        )
        return saved
    except Exception as e:
        logging.error(f"❌ TIMEOUT RESUME: Error loading from DB: {e}", exc_info=True)
        return None

def apply_timeout_resume_state_to_gm(gm: "GameManager", saved: dict):
    """
    Apply restored timeout state to GameManager.
    Called after gm is loaded/created.
    Works for all modes (single, tournament, franchise).
    """
    if not saved or not gm:
        return
    
    # Restore critical timeout state
    if "timeout_next_play_type" in saved:
        gm.game_state["timeout_next_play_type"] = saved["timeout_next_play_type"]
        logging.info(f"🔄 TIMEOUT RESUME: Applied timeout_next_play_type={saved['timeout_next_play_type']}")
    
    if "clock" in saved:
        gm.game_state["clock"] = saved["clock"]
        logging.info(f"🔄 TIMEOUT RESUME: Applied clock={saved['clock']}")
    
    if "time_remaining" in saved:
        gm.game_state["time_remaining"] = saved["time_remaining"]
        logging.info(f"🔄 TIMEOUT RESUME: Applied time_remaining={saved['time_remaining']}")

# 4. Routes
@app.get("/")
def root():
    return {"message": "GOB Simulation API is live"}

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
def get_game_state(game_id: str, quarter: int | None = None):
    """Fetch current game state for displaying accumulated stats and player energy
    
    Args:
        game_id: Game ID
        quarter: Optional quarter query parameter. If quarter=1 and saved game is Q2+,
                 returns empty stats (new game scenario)
    """
    try:
        logging.info(f"🔍 [BOX_SCORE] Loading game: game_id={game_id}, quarter={quarter}")
        # Check ongoing games first
        gm = ongoing_games.get(game_id)
        logging.info(f"📊 /api/game/{game_id} - GameManager in memory: {gm is not None}, quarter param: {quarter}")
        logging.info(f"📊 Active games in memory: {list(ongoing_games.keys())}")
        if gm:
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
            
            return {
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
        
        # Check database
        if games_collection is not None:
            logging.info(f"🔍 [BOX_SCORE] Checking database for game_id={game_id}")
            # Try both string and ObjectId lookups
            saved = games_collection.find_one({"_id": game_id})
            if not saved and isinstance(game_id, str):
                try:
                    saved = games_collection.find_one({"_id": ObjectId(game_id)})
                    logging.info(f"✅ [BOX_SCORE] Found game using ObjectId conversion")
                except Exception as e:
                    logging.warning(f"⚠️ [BOX_SCORE] Could not convert game_id to ObjectId: {e}")
            
            if saved:
                logging.info(f"✅ [BOX_SCORE] Found game in database: quarter={saved.get('quarter')}, is_final={saved.get('is_final')}, has_box_score={bool(saved.get('box_score'))}, has_players={bool(saved.get('players'))}")
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
                    return {
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
                
                # Extract team data
                home_team_data = saved.get("home_team", {})
                away_team_data = saved.get("away_team", {})
                
                # Extract scouting data from teams object (contains playcall stats for S2 tab)
                teams_obj = saved.get("teams", {})
                home_team_id = saved.get("home_team_id")
                away_team_id = saved.get("away_team_id")
                
                home_scouting = {}
                away_scouting = {}
                if home_team_id and home_team_id in teams_obj:
                    home_scouting = teams_obj[home_team_id].get("scouting", {})
                if away_team_id and away_team_id in teams_obj:
                    away_scouting = teams_obj[away_team_id].get("scouting", {})
                
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
                
                # Build box_score from nested structure (summarize_game_state stores it under home_team/away_team)
                box_score = saved.get("box_score", {})
                if not box_score:
                    # Build from nested structure
                    home_team_name = home_team_data.get("name")
                    away_team_name = away_team_data.get("name")
                    if home_team_name and "box_score" in home_team_data:
                        box_score[home_team_name] = home_team_data.get("box_score", {})
                    if away_team_name and "box_score" in away_team_data:
                        box_score[away_team_name] = away_team_data.get("box_score", {})
                
                return {
                    "game_id": game_id,
                    "score": saved.get("score", {}),
                    "box_score": box_score,
                    "quarter": saved.get("quarter", 1),
                    "clock": saved.get("clock", "8:00"),
                    "players": players_with_energy,
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
                    "home_team": {
                        "name": home_team_data.get("name"),
                        "team_fouls": home_team_data.get("team_fouls", 0),
                        "attributes": home_team_data.get("attributes", {})  # Team attributes for S3 tab
                    },
                    "away_team": {
                        "name": away_team_data.get("name"),
                        "team_fouls": away_team_data.get("team_fouls", 0),
                        "attributes": away_team_data.get("attributes", {})  # Team attributes for S3 tab
                    }
                }
        
            logging.error(f"❌ [BOX_SCORE] Game not found in database: game_id={game_id}")
            # Try to find any games with similar IDs for debugging
            if isinstance(game_id, str) and len(game_id) > 10:
                similar = list(games_collection.find({"_id": {"$regex": game_id[:10]}}).limit(5))
                logging.info(f"🔍 [BOX_SCORE] Found {len(similar)} similar game IDs (first 10 chars): {[str(g.get('_id')) for g in similar]}")
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logging.exception(f"Error fetching game state for {game_id}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate-quarter")
def simulate_quarter_endpoint(request: QuarterSimulationRequest, debug: bool = False):
    game_id = request.game_id
    logging.info(
        "simulate_quarter_endpoint payload: game_id=%s, home_team=%s, away_team=%s, quarter=%s, home_lineup_keys=%s, away_lineup_keys=%s, resume_from_timeout=%s, mode=%s",
        game_id,
        request.home_team,
        request.away_team,
        request.quarter,
        list((request.home_lineup or {}).keys()),
        list((request.away_lineup or {}).keys()),
        request.resume_from_timeout,
        request.mode,
    )
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
    if game_id:
        gm = ongoing_games.get(game_id)
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
            del ongoing_games[game_id]
            gm = None  # Force reload from DB where new game detection will run
        
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
        logging.info(f"🔍 TIMEOUT RESUME CHECK: Checking if we should look for timeout state (game_id={game_id}, quarter={request.quarter}, mode={request.mode}, URL resume_from_timeout={request.resume_from_timeout})")
        
        # Check for timeout state if we have a game_id (existing game)
        # Don't skip Q1 - we could be resuming from a timeout in Q1!
        # The restore_timeout_resume_state function will validate quarter match to prevent stale data
        if game_id:
            logging.info(f"🔍 TIMEOUT RESUME: Checking DB for timeout state (game_id exists)")
            timeout_saved_state = restore_timeout_resume_state(game_id, request, games_collection)
        else:
            logging.info(f"🔍 TIMEOUT RESUME: Skipping timeout check (no game_id - brand new game)")
        
        if timeout_saved_state:
            # Validate quarter match to prevent stale data from affecting new games
            saved_quarter = timeout_saved_state.get("quarter", 0)
            timeout_next_play_type = timeout_saved_state.get("timeout_next_play_type")
            
            if timeout_next_play_type and saved_quarter == request.quarter:
                logging.info(f"✅ TIMEOUT RESUME: Found valid timeout state in DB, timeout_next_play_type={timeout_next_play_type}, quarter={saved_quarter}")
                # Override request.resume_from_timeout to ensure simulate_quarter() handles timeout resume
                request.resume_from_timeout = True
                logging.info(f"✅ TIMEOUT RESUME: Detected valid timeout state in DB, setting resume_from_timeout=True for simulate_quarter()")
                if gm is not None:
                    # Game is in memory - apply timeout state now (before simulate_quarter)
                    logging.info(f"🔍 TIMEOUT RESUME: Applying state to in-memory game")
                    apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
                else:
                    logging.info(f"🔍 TIMEOUT RESUME: Game not in memory, will apply after DB load")
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
                logging.info(f"🔍 TIMEOUT RESUME: No timeout state in DB (normal game start/resume)")
        
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
                    # Handle both old (flat) and new (teams object) structure
                    home_team_field = saved.get("home_team")
                    away_team_field = saved.get("away_team")
                    
                    # New structure: home_team is a dict with name and team_id
                    if isinstance(home_team_field, dict):
                        home = home_team_field.get("name")
                        away = away_team_field.get("name") if isinstance(away_team_field, dict) else None
                        home_team_id = home_team_field.get("team_id")
                        away_team_id = away_team_field.get("team_id") if isinstance(away_team_field, dict) else None
                    # Old structure: home_team is a string
                    else:
                        home = home_team_field or saved.get("homeTeam", {}).get("name")
                        away = away_team_field or saved.get("awayTeam", {}).get("name")
                        home_team_id = None
                        away_team_id = None
                    
                    if home and away:
                        # Try to load from new 'teams' object structure (by team_id)
                        teams_obj = saved.get("teams", {})
                        home_team_data = teams_obj.get(home_team_id, {}) if home_team_id else {}
                        away_team_data = teams_obj.get(away_team_id, {}) if away_team_id else {}
                        
                        # Extract team data from teams object
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
                        # ✅ FIX: Log loaded quarter to debug save/load issues
                        logging.info(f"📂 Loaded game from DB: game_id={game_id}, saved_quarter={saved_quarter}, requested_quarter={request.quarter}")
                        
                        # ✅ SS&S: Restore user_team_side to game_state (persists override checking across game loads)
                        # If saved game has it, use that; otherwise use request.user_team_side
                        if "user_team_side" in saved:
                            gm.game_state["user_team_side"] = saved["user_team_side"]
                            logging.warning(f"✅ Restored user_team_side from DB: {saved['user_team_side']}")
                        elif request.user_team_side:
                            gm.game_state["user_team_side"] = request.user_team_side
                            logging.warning(f"✅ Set user_team_side from request: {request.user_team_side}")
                        else:
                            logging.warning(f"⚠️ No user_team_side found in DB or request - override checking will not work!")
                        
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
                                logging.info(f"✅ TIMEOUT RESUME: Detected timeout state in saved document, setting resume_from_timeout=True (quarter {request.quarter})")
                        
                        # ✅ TIMEOUT RESUME: Check for timeout state in saved document BEFORE calculating should_restore_stats
                        # This ensures scores/fouls are restored when resuming from timeout
                        # Check if timeout state exists in saved document (regardless of URL parameter or timeout_saved_state)
                        has_timeout_state = "timeout_next_play_type" in saved and saved.get("timeout_next_play_type") is not None
                        if has_timeout_state and saved_quarter == request.quarter:
                            # Timeout state found in saved document - ensure resume_from_timeout is set
                            if not request.resume_from_timeout:
                                request.resume_from_timeout = True
                                logging.info(f"✅ TIMEOUT RESUME: Detected timeout state in saved document, setting resume_from_timeout=True (quarter {request.quarter})")
                        
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
                            logging.info(f"✅ Loaded from DB: Set home lineup from request: {list(gm.home_team.lineup.keys())}")
                        elif not gm.home_team.lineup:
                            from BackEnd.utils.db_utils import build_lineup_from_mongo
                            gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
                            logging.info(f"✅ Loaded from DB: Built home lineup from MongoDB: {list(gm.home_team.lineup.keys())}")
                        
                        if request.away_lineup:
                            from BackEnd.utils.db_utils import assign_lineup_from_ids
                            gm.away_team.lineup = assign_lineup_from_ids(gm.away_team, request.away_lineup)
                            logging.info(f"✅ Loaded from DB: Set away lineup from request: {list(gm.away_team.lineup.keys())}")
                        elif not gm.away_team.lineup:
                            from BackEnd.utils.db_utils import build_lineup_from_mongo
                            gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)
                            logging.info(f"✅ Loaded from DB: Built away lineup from MongoDB: {list(gm.away_team.lineup.keys())}")
                        
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
                            logging.info(f"🔄 Restoring stats for {len(saved_players_list)} players")
                        else:
                            saved_players_list = []
                            logging.info(f"🆕 New Q1 game (requested Q1 but saved game is Q{saved_quarter}) - skipping stat restoration")
                        
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
                                old_pts = player.stats.get("game", {}).get("PTS", 0)
                                player.stats["game"] = saved_player_data["stats"]
                                new_pts = player.stats["game"].get("PTS", 0)
                                logging.info(f"🔄 Player {player_id}: PTS restored {old_pts} → {new_pts}")
                        
                        # Restore team-level stats (score, fouls, totals, points by quarter)
                        # Only restore if this is NOT a new Q1 game (fresh start)
                        if should_restore_stats:
                            home_team_data = saved.get("home_team", {})
                            away_team_data = saved.get("away_team", {})
                            
                            # Restore team scores
                            if "score" in home_team_data:
                                gm.score[gm.home_team.name] = home_team_data["score"]
                                logging.info(f"🔄 Home team score restored: {home_team_data['score']}")
                            if "score" in away_team_data:
                                gm.score[gm.away_team.name] = away_team_data["score"]
                                logging.info(f"🔄 Away team score restored: {away_team_data['score']}")
                            
                            # Restore team fouls
                            if "team_fouls" in home_team_data:
                                gm.home_team.team_fouls = home_team_data["team_fouls"]
                                logging.info(f"🔄 Home team fouls restored: {home_team_data['team_fouls']}")
                            if "team_fouls" in away_team_data:
                                gm.away_team.team_fouls = away_team_data["team_fouls"]
                                logging.info(f"🔄 Away team fouls restored: {away_team_data['team_fouls']}")
                            
                            # Restore team timeouts
                            if "timeouts" in home_team_data:
                                gm.home_team.timeouts = home_team_data["timeouts"]
                                logging.info(f"🔄 Home team timeouts restored: {home_team_data['timeouts']}")
                            else:
                                # Default to 5 if not in saved data (backward compatibility)
                                gm.home_team.timeouts = 4
                                logging.info(f"🔄 Home team timeouts set to default: 4")
                            if "timeouts" in away_team_data:
                                gm.away_team.timeouts = away_team_data["timeouts"]
                                logging.info(f"🔄 Away team timeouts restored: {away_team_data['timeouts']}")
                            else:
                                # Default to 5 if not in saved data (backward compatibility)
                                gm.away_team.timeouts = 4
                                logging.info(f"🔄 Away team timeouts set to default: 4")
                            
                            # Restore team totals (aggregated stats)
                            if "totals" in home_team_data:
                                gm.team_totals[gm.home_team.name] = home_team_data["totals"]
                                logging.info(f"🔄 Home team totals restored: {home_team_data['totals']}")
                            if "totals" in away_team_data:
                                gm.team_totals[gm.away_team.name] = away_team_data["totals"]
                                logging.info(f"🔄 Away team totals restored: {away_team_data['totals']}")
                            
                            # Restore points by quarter
                            if "points_by_quarter" in home_team_data:
                                gm.game_state["points_by_quarter"][gm.home_team.name] = home_team_data["points_by_quarter"]
                                logging.info(f"🔄 Home team points_by_quarter restored: {home_team_data['points_by_quarter']}")
                            if "points_by_quarter" in away_team_data:
                                gm.game_state["points_by_quarter"][gm.away_team.name] = away_team_data["points_by_quarter"]
                                logging.info(f"🔄 Away team points_by_quarter restored: {away_team_data['points_by_quarter']}")
                            
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
                                apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
                                # Override request.resume_from_timeout to ensure simulate_quarter() handles timeout resume
                                request.resume_from_timeout = True
                                logging.info(f"✅ TIMEOUT RESUME: Detected valid timeout state in DB (quarter matches), setting resume_from_timeout=True for simulate_quarter()")
                            else:
                                logging.warning(f"⚠️ TIMEOUT RESUME: Found timeout state but quarter mismatch or missing next_play_type - treating as normal game (saved_quarter={saved_quarter}, requested_quarter={request.quarter})")
                                timeout_saved_state = None  # Clear invalid timeout state
                        else:
                            # Not resuming from timeout - restore clock/time_remaining normally
                            if "clock" in saved:
                                gm.game_state["clock"] = saved["clock"]
                                logging.info(f"🔄 Clock restored: {saved['clock']}")
                            if "time_remaining" in saved:
                                gm.game_state["time_remaining"] = saved["time_remaining"]
                                logging.info(f"🔄 Time remaining restored: {saved['time_remaining']} seconds")
                        
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
                        
                        ongoing_games[game_id] = gm
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
        logging.info(f"🎮 simulate_quarter_endpoint: full_sim={request.full_sim}, turn_by_turn_mode={turn_by_turn_mode}, quarter={request.quarter}, resume_from_timeout={request.resume_from_timeout}")
        
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
    frontend_summary = summarize_game_state(gm, exclude_animations=False)
    
    # Add start_box_score (only needed for Q2-Q4 frontend, not critical for saves)
    frontend_summary["start_box_score"] = gm.game_state.get("start_box_score")
    
    # Get is_final status
    is_final = frontend_summary.get("is_final", False)

    # Save to database (WITHOUT animations to reduce document size)
    try:
        db_summary = summarize_game_state(gm, exclude_animations=True)
        # ✅ FIX: Log quarter before save to debug save/load issues
        logging.info(f"💾 Saving game state: game_id={game_id}, quarter={db_summary.get('quarter')}, gm.quarter={gm.quarter}")
        
        # ✅ TOURNAMENT MODE: Add mode and tournament_id to game document for consistency with Franchise mode
        # Infer mode from tournament_id/franchise_id if mode not provided in request
        mode = request.mode
        if not mode:
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
    except Exception as e:
        print("🚨 Mongo upsert failed:", e)
        traceback.print_exc()

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
                """Recursively convert ObjectIds to strings for JSON serialization"""
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
    return frontend_summary


@app.post("/api/simulate-turn")
def simulate_turn_endpoint(request: TurnSimulationRequest):
    """
    Simulate a single turn for turn-by-turn gameplay.
    
    This endpoint:
    1. Retrieves the GameManager from ongoing_games
    2. Applies user overrides (if any) for this turn
    3. Simulates ONE turn (one call to gm.simulate_macro_turn())
    4. Returns the turn data + game state metadata
    5. Saves game state periodically
    """
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
        return {
            "quarter_complete": True,
            "game_id": game_id,
            "quarter": gm.quarter,
            "time_remaining": 0,
            "home_score": gm.score.get(gm.home_team.name, 0),
            "away_score": gm.score.get(gm.away_team.name, 0),
            "turn": None
        }
    
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
                # ✅ COMPUTER TIMEOUT: Save game state immediately (same as user timeouts)
                # This ensures clock, scores, fouls, etc. are preserved when user returns from lineup screen
                try:
                    db_summary = summarize_game_state(gm, exclude_animations=True)
                    games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
                    logging.info(
                        f"💾 COMPUTER TIMEOUT: Saved game state before returning timeout turn: "
                        f"game_id={game_id}, quarter={db_summary.get('quarter')}, "
                        f"clock={db_summary.get('clock')}, time_remaining={gm.game_state.get('time_remaining')}, "
                        f"next_play_type={gm.game_state.get('timeout_next_play_type')}"
                    )
                except Exception as e:
                    logging.error(f"🚨 COMPUTER TIMEOUT: Failed to save game state: {e}")
                    # Don't fail the timeout return if save fails - game is still in memory
                
                # Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
                timeout_turn = gm.turns.pop()
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
        
        # Track how many turns existed before this call (after deferred timeout check)
        turns_before = len(gm.turns)
        time_before_turn = gm.game_state["time_remaining"]
        
        # Simulate the next turn (unless we already returned a timeout above)
        gm.simulate_macro_turn()
        
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
        
        # Save game state to database every 10 turns (for crash recovery)
        # ✅ FIX: Always save when quarter completes to ensure quarter number is persisted
        if len(gm.turns) % 10 == 0 or quarter_complete:
            try:
                db_summary = summarize_game_state(gm, exclude_animations=True)
                games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
                logging.info(f"💾 Saved game state at turn {len(gm.turns)}, quarter={gm.quarter}")
            except Exception as e:
                logging.error(f"Failed to save game state: {e}")
        
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
        
        return response_data
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.exception(f"Failed to simulate turn for game {game_id}")
        logging.error(f"Full traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nFull traceback:\n{error_trace}")


@app.post("/api/set-playcall-override")
async def set_playcall_override_endpoint(raw_request: Request):
    """
    ✅ SS&S: Set persistent playcall overrides for user's team.
    
    Overrides are stored in team.strategy_calls and persist until used.
    This replaces the old single-turn override system.
    
    Only processes fields that are explicitly provided in the request body.
    This prevents accidentally clearing other overrides when setting one.
    """
    # Parse request body to see which fields were explicitly provided
    body = await raw_request.json()
    provided_fields = set(body.keys())
    
    # Validate using Pydantic model
    request = PlaycallOverrideRequest(**body)
    
    game_id = request.game_id
    gm = ongoing_games.get(game_id)
    
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
    """
    User-initiated timeout endpoint.
    Creates a TIMEOUT turn and saves game state before navigating to lineup screen.
    """
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
    
    # ✅ TIMEOUT: Save game state to database (reuse existing persistence pattern)
    # This ensures scores, clock, fouls, etc. are preserved when user returns from lineup screen
    try:
        db_summary = summarize_game_state(gm, exclude_animations=True)
        games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
        logging.info(
            f"💾 TIMEOUT: Saved game state before navigating to lineup screen: "
            f"game_id={game_id}, quarter={db_summary.get('quarter')}, "
            f"clock={db_summary.get('clock')}, next_play_type={timeout_turn.get('next_play_type')}"
        )
    except Exception as e:
        logging.error(f"🚨 TIMEOUT: Failed to save game state: {e}")
        # Don't fail the timeout call if save fails - game is still in memory
    
    # Return current timeout counts and clock for frontend display
    return {
        "message": f"Timeout called by {calling_team.name}",
        "calling_team": calling_team.name,
        "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
        "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
        "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
        "clock": gm.game_state.get("clock", "8:00"),  # ✅ TIMEOUT: Include current clock (backend source of truth)
        "time_remaining": gm.game_state.get("time_remaining", 480),  # Also include time_remaining for consistency
    }


@app.get("/roster/{team_name}")
def get_team_roster(team_name: str, tournament_id: str | None = None, response: Response = None):
    # ✅ FIX: Add cache-busting headers to ensure browser fetches fresh player data
    # This ensures updated player attributes (year, jersey, height, etc.) show up immediately
    if response:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    # print(f"🔍 Endpoint hit: GET /roster/{team_name}")
    if tournament_id:
        print(f"🔍 Tournament ID provided but ignored: {tournament_id}")

    # Normalize team name to match DB
    normalized_name = unidecode(team_name.strip().replace("-", " ")).lower()

    all_teams = [t["name"] for t in teams_collection.find({}, {"name": 1})]
    match = next((t for t in all_teams if unidecode(t.lower().replace("-", " ")) == normalized_name), None)

    if not match:
        print(f"❌ No team found matching: {normalized_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    team_doc, player_objects = load_roster(match)
    ...


    if not player_objects:
        print(f"❌ No players found for {team_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    team = team_doc or {"name": team_name}


    display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]

    players = []
    for p in player_objects:
        attributes = p.get("attributes", {})  # safely get nested attributes dict
        
        # Create anchor_ prefixed attributes (like Player class does)
        for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
            if attr_key in attributes:
                attributes[f"anchor_{attr_key}"] = attributes[attr_key]
        
        players.append({
            "_id": str(p.get("_id")),
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "year": p.get("year"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "jersey": p.get("jersey", 0),
            "position_ratings": p.get("position_ratings", {}),
            "attributes": attributes,  # Return full attributes object (not filtered)
        })

    return {
        "team": team.get("name", team_name),
        "team_name": team.get("name", team_name),
        "players": players
    }


@app.post("/api/init-game")
def init_game(request: dict):
    """Initialize a game document with players (Emotion, Momentum) before first quarter starts"""
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
    
    # Generate game_id
    game_id = generate_game_id()
    
    # Create GameManager (this initializes teams and players)
    gm = GameManager(home_team, away_team, mode=mode)
    
    # Initialize game stats (this randomizes EM, CH, MO for all players)
    _initialize_game_stats(gm, game_id=None)  # None = new game, will randomize
    
    # Create minimal game document with players
    # CRITICAL: Ensure scores are zeroed before summarizing
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
    
    # Set GameManager quarter to 1 to match
    gm.quarter = 1
    
    # Save to database
    games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
    
    # Store in ongoing_games so /api/game/{game_id} can access it
    ongoing_games[game_id] = gm
    
    return {"game_id": game_id}


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
    """Return roster data for a given team."""
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
    """Render an HTML roster page for a given team."""
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
    """Fetch the most recently created active tournament or create one."""
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
