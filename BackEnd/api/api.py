# 1. Imports
from fastapi import FastAPI, HTTPException
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
import traceback
from unidecode import unidecode
from typing import Optional
import logging
from BackEnd.models.player import Player

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(tournament_router)
app.include_router(training_router)
app.include_router(franchise_router)
app.include_router(gameplan_router)
app.include_router(play_router)

templates = Jinja2Templates(directory="FrontEnd/static")

# app.mount("/", StaticFiles(directory="FrontEnd", html=True), name="static")
# app.mount("/static", StaticFiles(directory="FrontEnd", html=True), name="static")
app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")

print("🚀 Loaded FastAPI app from api.py")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # allows all origins including null
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]  # ← add this line
)

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


ongoing_games: dict[str, GameManager] = {}


class TurnSimulationRequest(BaseModel):
    game_id: str
    # Optional user overrides for this specific turn
    offense_override: str | None = None  # e.g., "Inside", "Attack", "Outside"
    defense_override: str | None = None  # e.g., "Zone", "Man"
    # Mode context
    mode: str | None = None  # "single", "tournament", or "franchise"


# Helper functions for tournament/franchise mode
def load_player_attributes_from_doc(mode: str, doc_id: str, player_id: str):
    """Load player attributes (EM, CH, MO) from tournament/franchise doc."""
    from BackEnd.db import franchises_collection
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                player_stats = doc.get("player_stats", {}).get(player_id, {})
                attrs = player_stats.get("attributes", {})
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
                    print(f"📋 Loaded {len(plays)} plays for team {team_id} from tournament doc")
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
                    print(f"📋 Loaded {len(plays)} plays for team {team_id} from franchise doc")
                    return plays
        except Exception as e:
            print(f"⚠️ Error loading plays from franchise doc: {e}")
    
    return None

def load_team_attributes_from_doc(mode: str, doc_id: str, team_id: str, team_name: str):
    """Load team_attributes from tournament/franchise doc, fallback to core teams doc."""
    from BackEnd.db import franchises_collection
    
    attrs = None
    
    if mode == "tournament":
        try:
            doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                team_obj = doc.get("teams", {}).get(team_id, {})
                # Extract team_attributes from team_obj (may include other fields)
                attrs = {}
                for key in ["shot_threshold", "ft_shot_threshold", "turnover_threshold", "foul_threshold",
                           "rebound_modifier", "momentum_score", "momentum_delta", "offensive_efficiency",
                           "offensive_adjust", "o_tendency_reads", "d_tendency_reads", "team_chemistry"]:
                    if key in team_obj:
                        attrs[key] = team_obj[key]
        except Exception as e:
            print(f"⚠️ Error loading team_attributes from tournament doc: {e}")
    elif mode == "franchise":
        try:
            doc = franchises_collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                team_obj = doc.get("franchise_teams", {}).get(team_id, {})
                # Extract team_attributes from team_obj
                attrs = {}
                for key in ["shot_threshold", "ft_shot_threshold", "turnover_threshold", "foul_threshold",
                           "rebound_modifier", "momentum_score", "momentum_delta", "offensive_efficiency",
                           "offensive_adjust", "o_tendency_reads", "d_tendency_reads", "team_chemistry"]:
                    if key in team_obj:
                        attrs[key] = team_obj[key]
        except Exception as e:
            print(f"⚠️ Error loading team_attributes from franchise doc: {e}")
    
    # If no attributes found, try core teams doc as fallback
    if not attrs:
        team_doc = teams_collection.find_one({"name": team_name})
        if team_doc:
            attrs = {}
            for key in ["shot_threshold", "ft_shot_threshold", "turnover_threshold", "foul_threshold",
                       "rebound_modifier", "momentum_score", "momentum_delta", "offensive_efficiency",
                       "offensive_adjust", "o_tendency_reads", "d_tendency_reads", "team_chemistry"]:
                if key in team_doc:
                    attrs[key] = team_doc[key]
    
    return attrs if attrs else None

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
def get_game_state(game_id: str):
    """Fetch current game state for displaying accumulated stats and player energy"""
    try:
        # Check ongoing games first
        gm = ongoing_games.get(game_id)
        if gm:
            # Get players with current energy levels
            players = []
            for team in [gm.home_team, gm.away_team]:
                for pos, player in team.lineup.items():
                    players.append({
                        "_id": player.player_id,
                        "name": player.name,
                        "NG": player.attributes.get("NG", 1.0),
                        "team": team.name
                    })
            
            return {
                "game_id": game_id,
                "score": gm.score,
                "box_score": gm.get_box_score(),
                "quarter": gm.quarter,
                "clock": gm.game_state.get("clock", "8:00"),
                "players": players
            }
        
        # Check database
        if games_collection is not None:
            saved = games_collection.find_one({"_id": game_id})
            if saved:
                # Extract player energy from saved game doc
                players = saved.get("players", [])
                # Map to include NG if available
                players_with_energy = []
                for p in players:
                    player_data = {
                        "_id": p.get("playerId") or p.get("player_id"),
                        "name": p.get("name"),
                        "NG": p.get("NG", 1.0),  # May be saved in game doc
                        "team": p.get("team")
                    }
                    players_with_energy.append(player_data)
                
                return {
                    "game_id": game_id,
                    "score": saved.get("score", {}),
                    "box_score": saved.get("box_score", {}),
                    "quarter": saved.get("quarter", 1),
                    "clock": saved.get("clock", "8:00"),
                    "players": players_with_energy
                }
        
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    except Exception as e:
        logging.exception(f"Error fetching game state for {game_id}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate-quarter")
def simulate_quarter_endpoint(request: QuarterSimulationRequest, debug: bool = False):
    game_id = request.game_id
    logging.info(
        "simulate_quarter_endpoint payload: game_id=%s, home_team=%s, away_team=%s, quarter=%s, home_lineup_keys=%s, away_lineup_keys=%s",
        game_id,
        request.home_team,
        request.away_team,
        request.quarter,
        list((request.home_lineup or {}).keys()),
        list((request.away_lineup or {}).keys()),
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
        if gm is None:
            logging.warning(
                "simulate_quarter_endpoint unknown game_id=%s; active=%s",
                game_id,
                list(ongoing_games.keys()),
            )
            if games_collection is not None:
                logging.info(
                    "simulate_quarter_endpoint querying DB for game_id=%s", game_id
                )
            else:
                logging.info(
                    "simulate_quarter_endpoint skipping DB lookup for game_id=%s; no collection",
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
                        away_strategy = away_team_data.get("strategy_settings")
                        
                        # Fallback to old flat structure if teams object doesn't exist (backwards compatibility)
                        if not home_plays and not teams_obj:
                            home_plays = saved.get("team_plays", {}).get(home)
                            away_plays = saved.get("team_plays", {}).get(away)
                            home_attrs = saved.get("team_attributes", {}).get(home)
                            away_attrs = saved.get("team_attributes", {}).get(away)
                            home_scouting = saved.get("scouting", {}).get(home)
                            away_scouting = saved.get("scouting", {}).get(away)
                        
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
                            mode="single"  # Loaded games are always single mode from games_collection
                        )
                        gm.game_state = gm._init_game_state()
                        saved_game_state = saved.get("game_state", {})
                        gm.game_state.update(saved_game_state)
                        gm.quarter = saved.get("quarter", 1)
                        
                        # Restore player stats and NG (energy) from saved game state
                        saved_players = saved_game_state.get("players", {})
                        for team_name, team_players in saved_players.items():
                            team = gm.home_team if team_name == "home" else gm.away_team
                            for player_id, saved_player_data in team_players.items():
                                if player_id in team.lineup:
                                    player = team.lineup[player_id]
                                    # Restore NG (energy)
                                    if "attributes" in saved_player_data and "NG" in saved_player_data["attributes"]:
                                        player.attributes["NG"] = saved_player_data["attributes"]["NG"]
                                        player._rescale_attributes()  # Update scaled attributes based on NG
                                    # Restore game stats
                                    if "stats" in saved_player_data:
                                        player.stats["game"] = saved_player_data["stats"]
                        
                        # Restore opening_tip_winner for Q2-Q4 possession logic
                        if "opening_tip_winner" in saved:
                            gm.game_state["opening_tip_winner"] = saved["opening_tip_winner"]
                            if debug:
                                logging.debug(
                                    "Restored opening_tip_winner: %s",
                                    saved["opening_tip_winner"]
                                )
                        
                        ongoing_games[game_id] = gm
                        if debug:
                            logging.debug(
                                "simulate_quarter_endpoint loaded from DB: %s vs %s",
                                home,
                                away,
                            )
                except Exception:
                    logging.exception("Failed to load game state for %s", game_id)
            if gm is None:
                if request.quarter == 1:
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
                    
                    #temp comment
                    gm = GameManager(
                        request.home_team, 
                        request.away_team,
                        home_strategy_settings=home_strategy,
                        away_strategy_settings=away_strategy,
                        mode=mode  # Pass mode so teams can initialize plays with correct stats structure
                    )
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
                        
                        # print(f"🔍 DEBUG: Populated {len(populated_plays)} plays for teams in simulate_quarter_endpoint (Q1, mode={mode})")
                        # print(f"🔍 DEBUG: Play keys: {list(populated_plays.keys())}")
                        
                        # Create team objects with plays for skeleton lookup
                        teams_obj = {
                            gm.home_team.team_id: {
                                "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                                "plays": populated_plays.copy()
                            },
                            gm.away_team.team_id: {
                                "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                                "plays": populated_plays.copy()
                            }
                        }
                        
                        # print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
                        # print(f"🔍 DEBUG: Home team plays: {len(teams_obj[gm.home_team.team_id]['plays'])}")
                        # print(f"🔍 DEBUG: Away team plays: {len(teams_obj[gm.away_team.team_id]['plays'])}")
                        
                        # Create a summary with new nested team structure
                        summary = summarize_game_state(gm)
                        
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
        
        gm = GameManager(
            request.home_team, 
            request.away_team,
            home_strategy_settings=home_strategy,
            away_strategy_settings=away_strategy,
            mode=mode  # Pass mode so teams can initialize plays with correct stats structure
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
            
            # print(f"🔍 DEBUG: Populated {len(populated_plays)} plays for teams in simulate_quarter_endpoint (no game_id, mode={mode})")
            # print(f"🔍 DEBUG: Play keys: {list(populated_plays.keys())}")
            
            # Create team objects with plays for skeleton lookup
            teams_obj = {
                gm.home_team.team_id: {
                    "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                    "plays": populated_plays.copy()
                },
                gm.away_team.team_id: {
                    "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                    "plays": populated_plays.copy()
                }
            }
            
            # print(f"🔍 DEBUG: Created teams object with keys: {list(teams_obj.keys())}")
            # print(f"🔍 DEBUG: Home team plays: {len(teams_obj[gm.home_team.team_id]['plays'])}")
            # print(f"🔍 DEBUG: Away team plays: {len(teams_obj[gm.away_team.team_id]['plays'])}")
            
            # Create a summary with new nested team structure
            summary = summarize_game_state(gm)
            
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
        simulate_quarter(
            gm,
            request.home_lineup,
            request.away_lineup,
            game_id,
            request.start_with_inbound,
            request.starting_possession,
            turn_by_turn_mode=True,  # NEW: Enable turn-by-turn mode
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
        logging.exception(
            "simulate_quarter failed for game_id=%s, home_team=%s, away_team=%s, quarter=%s, home_lineup_keys=%s, away_lineup_keys=%s",
            game_id,
            request.home_team,
            request.away_team,
            request.quarter,
            list((request.home_lineup or {}).keys()),
            list((request.away_lineup or {}).keys()),
        )
        raise HTTPException(status_code=500, detail=str(e))

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
        # print(f"🔍 DEBUG: Saving game with nested team structure")
        # print(f"🔍 DEBUG: Home team plays: {len(db_summary.get('home_team', {}).get('plays', []))}")
        # print(f"🔍 DEBUG: Away team plays: {len(db_summary.get('away_team', {}).get('plays', []))}")
        
        games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
        # print(f"🔍 DEBUG: Game document saved successfully")
    except Exception as e:
        print("🚨 Mongo upsert failed:", e)
        traceback.print_exc()

    if is_final and game_id:
        # Scrimmage simulations should not generate aggregate stats.
        # Finalizing with ``mode="scrimmage"`` is a no-op but documents intent.
        stat_updater.finalize_game(game_id, mode="scrimmage")
    
    # Return frontend summary WITH animations for real-time play
    turns = frontend_summary.get("turns", [])
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
    
    # Simulate ONE turn
    try:
        # Track how many turns existed before this call
        turns_before = len(gm.turns)
        
        gm.simulate_macro_turn()
        
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
            logging.info(f"✅ Quarter complete! time_remaining={gm.game_state['time_remaining']}, clock={gm.game_state.get('clock', 'N/A')}")
        
        # If quarter is complete, increment quarter number
        if quarter_complete:
            gm.quarter += 1
            logging.info(f"✅ Advanced to quarter {gm.quarter}")
        
        # Save game state to database every 10 turns (for crash recovery)
        if len(gm.turns) % 10 == 0 or quarter_complete:
            try:
                db_summary = summarize_game_state(gm, exclude_animations=True)
                games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
                logging.info(f"💾 Saved game state at turn {len(gm.turns)}")
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
            "home_score": gm.score.get(gm.home_team.name, 0),
            "away_score": gm.score.get(gm.away_team.name, 0),
            "home_team_fouls": gm.home_team.team_fouls,
            "away_team_fouls": gm.away_team.team_fouls,
            "offense_team": gm.offense_team.name,
            "defense_team": gm.defense_team.name,
            "game_id": game_id,
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
        logging.exception(f"Failed to simulate turn for game {game_id}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/roster/{team_name}")
def get_team_roster(team_name: str, tournament_id: str | None = None):
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
            "position_ratings": p.get("position_ratings", {}),
            "attributes": attributes,  # Return full attributes object (not filtered)
        })

    return {
        "team": team.get("name", team_name),
        "team_name": team.get("name", team_name),
        "players": players
    }


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
                print(f"📋 Sample player _id format: {sample.get('_id')} (type: {type(sample.get('_id'))})")
            raise HTTPException(status_code=404, detail="Player not found")
        print(f"✅ Player found: {player.get('first_name')} {player.get('last_name')}")
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
    return doc
