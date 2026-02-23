# 1. Imports
import re
import sys
import os
# ✅ PERFORMANCE: Removed debug print statements - use logger instead

# Sentry - init before FastAPI (captures unhandled exceptions)
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment=os.getenv("RAILWAY_ENVIRONMENT", os.getenv("ENV", "development")),
    )
    print("🔶 [SENTRY] Backend error tracking enabled", file=sys.stderr, flush=True)


# Bootstrap: get app with /health so server starts even if rest fails
from BackEnd.api._bootstrap import app
import traceback
_startup_error = None
try:
    from fastapi import Depends, FastAPI, HTTPException, Response
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
        franchise_players_data_collection,
    )
    from BackEnd.utils.roster_loader import load_roster
    from BackEnd.utils.game_summary_builder import build_game_summary
    from BackEnd.utils.shared import clean_mongo_ids, summarize_game_state, format_height, deserialize_computer_timeouts
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
    from .pointer_validation_routes import router as pointer_validation_router
    from .auth_routes import router as auth_router
    from .admin_routes import router as admin_router
    from .feedback_routes import router as feedback_router
    from BackEnd.utils.auth import get_current_user
    from BackEnd.utils.ownership import verify_game_owned_by_user
    import traceback
    from unidecode import unidecode
    from typing import Optional
    import logging
    import json
    import time
    from datetime import datetime
    from pathlib import Path
    from BackEnd.models.player import Player
    
    logger = logging.getLogger(__name__)
    
    
    # ============================================================================
    # ALPHA CONFIGURATION
    # ============================================================================
    # IS_ALPHA controls alpha-specific behavior:
    # - When True: OTP required for signup, alpha badge shown, data disclaimers displayed
    # - When False: Normal public access, no alpha restrictions
    # Set IS_ALPHA=true in production for alpha launch, false for public launch
    IS_ALPHA = os.getenv("IS_ALPHA", "false").lower() == "true"
    print(f"🔶 [ALPHA] IS_ALPHA={IS_ALPHA}", file=sys.stderr, flush=True)

    # ============================================================================
    # MAINTENANCE MODE (Optional - Part C)
    # ============================================================================
    # When enabled, block mutation endpoints (POST/PUT/PATCH/DELETE) with a fast 503.
    # This protects users with already-open tabs during deploys/maintenance.
    def _maintenance_mode_enabled() -> bool:
        return os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

    @app.middleware("http")
    async def maintenance_mode_middleware(request: Request, call_next):
        # Always allow Railway health checks.
        if request.url.path.startswith("/health"):
            return await call_next(request)

        if _maintenance_mode_enabled():
            method = (request.method or "").upper()
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                resp = JSONResponse(
                    status_code=503,
                    content={
                        "error": "maintenance_mode",
                        "message": "Service temporarily unavailable due to maintenance.",
                    },
                )
                resp.headers["Retry-After"] = "60"
                return resp

        return await call_next(request)
    
    @app.get("/sentry-debug")
    def sentry_debug():
        """Test endpoint - raises error to verify backend Sentry capture. Remove before public launch."""
        raise RuntimeError("Test Sentry backend capture")
    
    
    @app.get("/app-config")
    def get_app_config():
        """
        Returns frontend configuration including alpha status.
        Frontend uses this to conditionally show alpha badge, disclaimers, and OTP field.
        """
        return {
            "isAlpha": IS_ALPHA,
            "alphaDisclaimer": "This is an alpha release. Data may be wiped without notice. Gameplay balance and features may change." if IS_ALPHA else None,
            "version": "alpha-1.0" if IS_ALPHA else "1.0",
            "sentryDsn": os.getenv("SENTRY_DSN_FRONTEND") or None,
        }
    
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
            "https://gob-test.netlify.app",  # ✅ Staging Netlify domain
            "https://gob-production.netlify.app",  # ✅ Production Netlify default domain
            "https://www.geekedoutbasketball.com",  # ✅ Production custom domain
            "https://geekedoutbasketball.com",  # ✅ Production custom domain (non-www)
        ]
        
        # Get custom origins from environment variable (comma-separated)
        custom_origins = os.getenv("CORS_ORIGINS", "")
        if custom_origins:
            origins.extend([origin.strip() for origin in custom_origins.split(",") if origin.strip()])
        
        return origins
    
    # Get CORS origins and configure middleware BEFORE including routers
    cors_origins = get_cors_origins()
    
    # CORS: Explicit allowlist only (no wildcards). Custom domains in allowlist.
    # Regex commented out per 5.1 - explicit list covers prod/staging; regex allowed any *.netlify.app
    # To re-enable deploy previews: allow_origin_regex=r"https://.*\.(railway|netlify)\.app"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # allow_origin_regex=r"https://.*\.(railway|netlify)\.app",  # Disabled for security
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # Explicit methods
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600  # Cache preflight requests for 1 hour
    )
    
    print(f"🌐 [CORS] Configured with origins: {cors_origins}")
    logging.info(f"🌐 CORS configured with origins: {cors_origins}")
    
    # ============================================================================
    # RATE LIMITING (Step 6)
    # ============================================================================
    # Protects against brute force, DoS, and resource exhaustion
    # Limits: auth=10/min, simulation=30/min, general=100/min (per IP)
    # Optional: if slowapi/rate_limiter fails to import, app still starts (deploy resilience)
    limiter = None
    SIM_RATE_LIMIT = "30/minute"
    SIM_TURN_RATE_LIMIT = "300/minute"
    try:
        from slowapi.errors import RateLimitExceeded
        from BackEnd.utils.rate_limiter import (
            limiter as _limiter,
            rate_limit_exceeded_handler,
            SIM_RATE_LIMIT as _SIM_RATE_LIMIT,
            SIM_TURN_RATE_LIMIT as _SIM_TURN_RATE_LIMIT,
        )
        limiter = _limiter
        SIM_RATE_LIMIT = _SIM_RATE_LIMIT
        SIM_TURN_RATE_LIMIT = _SIM_TURN_RATE_LIMIT
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        print("🛡️ [RATE LIMIT] Rate limiting enabled", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"⚠️ [RATE LIMIT] Failed to enable rate limiting: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
    
    def _no_limit(f):
        """No-op when rate limiter is disabled."""
        return f
    _rate_limit_sim = limiter.limit(SIM_RATE_LIMIT) if limiter else _no_limit
    _rate_limit_turn = limiter.limit(SIM_TURN_RATE_LIMIT) if limiter else _no_limit
    
    # Include routers AFTER CORS middleware is configured
    app.include_router(tournament_router)
    app.include_router(training_router)
    app.include_router(franchise_router)
    app.include_router(gameplan_router)
    app.include_router(play_router)
    app.include_router(skeleton_router)
    app.include_router(pointer_validation_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(feedback_router)

    @app.get("/debug/server-state")
    def debug_server_state():
        """
        Return in-memory and disk state for performance debugging (e.g. on Railway).
        No auth; restrict in production if desired (e.g. by IP or remove).
        """
        return {
            "ongoing_games_count": len(ongoing_games),
        }
    
    templates = Jinja2Templates(directory="FrontEnd/static")
    
    # Conditionally mount static files (only in development)
    # In production, Netlify serves static files
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "development":
        app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")
        print("✅ Static files mounted (development mode)")
    
    # ✅ PERFORMANCE: Removed debug print statements
    
    # ✅ ERROR HANDLING + Step 5.6 Security headers
    @app.middleware("http")
    async def cors_debug_middleware(request: Request, call_next):
        """Catch exceptions early; add security headers to all responses."""
        try:
            response = await call_next(request)
            # Step 5.6: Security headers on all responses
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
            return response
        except Exception as e:
            logging.error(f"🔴 [ERROR] EXCEPTION on {request.method} {request.url.path}: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    # ✅ PERFORMANCE: Removed debug print statements
    
    # ✅ Add global exception handler to catch all unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print(f"🔴 [ERROR] Global exception handler: {type(exc).__name__}: {str(exc)}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # ✅ CORS FIX: Ensure CORS headers are included even on error responses
        response = JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "type": type(exc).__name__, "message": str(exc)}
        )
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # CORS headers will be added by middleware, but explicitly set origin header for safety
        origin = request.headers.get("origin")
        if origin and (origin in cors_origins or any(origin.startswith(p) for p in ["https://", "http://localhost"])):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    
    # ✅ Add startup event to verify app is ready
    @app.on_event("startup")
    async def startup_event():
        # Ensure indexes exist (idempotent; safe on every deploy)
        try:
            from BackEnd.db import (
                ensure_users_username_index,
                ensure_ftd_index,
                ensure_fpd_index,
                ensure_frd_index,
                ensure_games_franchise_index,
                ensure_franchises_user_id_index,
            )
            ensure_users_username_index()
            ensure_ftd_index()
            ensure_fpd_index()
            ensure_frd_index()
            ensure_games_franchise_index()
            ensure_franchises_user_id_index()
        except Exception as e:
            print(f"⚠️ [WARNING] startup: ensure indexes: {e}", file=sys.stderr, flush=True)

        # Check MongoDB connection status (non-blocking, don't crash if it fails)
        # MongoDB connections are lazy - this just verifies the client exists
        try:
            from BackEnd.db import client, DB_NAME
            # ✅ PERFORMANCE: Removed verbose startup debug prints
            
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
        playbook_settings: dict | None = None  # Playbook settings (motion, set plays, slot_assignments, etc.)
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
    
    
    class SaveManDefenseMatchupsRequest(BaseModel):
        game_id: str
        matchups: dict[str, str]  # {"PG": "PG", "SG": "SG", ...} - defensive position → offensive position
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
                # ✅ FTD: Load team_attributes from franchise_team_data collection instead of franchise doc
                from BackEnd.db import franchise_team_data_collection
                from bson import ObjectId
                
                # Convert team_id to ObjectId if it's a string
                try:
                    team_object_id = ObjectId(team_id) if team_id else None
                except:
                    # If team_id is not a valid ObjectId, try to resolve from team_name
                    if team_name:
                        team_doc = teams_collection.find_one({"name": team_name})
                        if team_doc:
                            team_object_id = team_doc.get("_id")
                        else:
                            team_object_id = None
                    else:
                        team_object_id = None
                
                if team_object_id:
                    ftd_doc = franchise_team_data_collection.find_one(
                        {"franchise_id": ObjectId(doc_id), "team_id": team_object_id},
                        {"team_attributes": 1}
                    )
                    if ftd_doc:
                        attrs = ftd_doc.get("team_attributes", {})
                        # Ensure all expected keys exist (with defaults if missing)
                        expected_keys = {
                            "shot_threshold": 90,
                            "discipline": 0,
                            "fight": 0,
                            "rebound_modifier": 1.0,
                            "momentum_score": 0,
                            "offensive_efficiency": 0,
                            "team_chemistry": 8,
                            "defensive_efficiency": 0,
                            "fb_efficiency": 0,
                            "pt_efficiency": 0,
                            "fb_opp_modifier": 0,
                            "pt_opp_modifier": 0
                        }
                        # Fill in missing keys with defaults
                        for key, default_value in expected_keys.items():
                            if key not in attrs:
                                attrs[key] = default_value
            except Exception as e:
                print(f"⚠️ Error loading team_attributes from FTD: {e}")
                import traceback
                traceback.print_exc()
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
    
    def load_ftd_data_for_team(franchise_id: str, team_id: str, team_name: str = None):
        """
        Load franchise team data (FTD) for a team.
        
        Returns:
            dict with keys: team_attributes, strategy_settings, playbook_settings, plays, scouting_data
            or None if not found
        """
        from BackEnd.db import franchise_team_data_collection, teams_collection
        from bson import ObjectId
        
        try:
            # Convert team_id to ObjectId if needed
            try:
                team_object_id = ObjectId(team_id) if team_id else None
            except:
                # If team_id is not a valid ObjectId, resolve from team_name
                if team_name:
                    team_doc = teams_collection.find_one({"name": team_name})
                    if team_doc:
                        team_object_id = team_doc.get("_id")
                    else:
                        return None
                else:
                    return None
            
            if not team_object_id:
                return None
            
            # Load FTD document
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(franchise_id), "team_id": team_object_id}
            )
            
            if not ftd_doc:
                return None
            
            # Extract and return data
            return {
                "team_attributes": ftd_doc.get("team_attributes", {}),
                "strategy_settings": ftd_doc.get("strategy_settings", {}),
                "playbook_settings": ftd_doc.get("playbook_settings", {}),
                "plays": ftd_doc.get("plays", {}),
                "scouting_data": ftd_doc.get("scouting_data", {})
            }
        except Exception as e:
            logging.warning(f"⚠️ Error loading FTD data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def load_team_settings_from_doc(mode: str, doc_id: str, team_id: str, team_name: str, game_id: str = None):
        """
        Load strategy_settings and playbook_settings from tournament/franchise doc.
        
        ✅ PHASE 5.7: For franchise/tournament mode, tries game doc first, then falls back to master doc.
        """
        from BackEnd.db import franchises_collection
        from BackEnd.api.franchise_routes import get_user_team_from_franchise
        from BackEnd.api.tournament_routes import get_user_team_from_tournament
        
        # Resolve team_id from team_name if not provided
        if not team_id and team_name:
            team_doc = teams_collection.find_one({"name": team_name})
            if team_doc:
                team_id = str(team_doc.get("_id"))
        
        strategy_settings = None
        playbook_settings = None
        
        # ✅ PHASE 5.7: For franchise/tournament mode, try game doc first, fallback to master doc
        if mode in ["franchise", "tournament"] and game_id:
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
                    
                    if (mode == "franchise" and game_mode == "franchise" and str(game_franchise_id) == str(doc_id)) or \
                       (mode == "tournament" and game_mode == "tournament" and str(game_tournament_id) == str(doc_id)):
                        # Game belongs to this franchise/tournament - try to load settings from game doc using unified function
                        from BackEnd.utils.team_settings_manager import extract_team_settings
                        
                        # Use team_name or team_id as identifier (unified function handles resolution)
                        team_identifier = team_name or team_id
                        if team_identifier:
                            strategy_settings = extract_team_settings(
                                saved_doc=game_doc,
                                team_identifier=team_identifier,
                                settings_type="strategy_settings",
                                mode="single",  # Game doc uses single mode structure
                                game_doc=game_doc
                            )
                            playbook_settings = extract_team_settings(
                                saved_doc=game_doc,
                                team_identifier=team_identifier,
                                settings_type="playbook_settings",
                                mode="single",  # Game doc uses single mode structure
                                game_doc=game_doc
                            )
                            if strategy_settings or playbook_settings:
                                logging.warning(f"✅ [PHASE 5.7] Loaded settings from game doc using unified function (game_id={game_id}, team_identifier={team_identifier})")
            except Exception as e:
                logging.warning(f"⚠️ [PHASE 5.7] Error loading from game doc, falling back to master: {e}")
        
        # If settings not loaded from game doc, load from master doc (FTD for franchise, extract for tournament)
        if strategy_settings is None and playbook_settings is None:
            from BackEnd.utils.team_settings_manager import extract_team_settings
            from BackEnd.db import franchise_team_data_collection
            
            if mode == "franchise":
                # ✅ FTD: Load strategy_settings and playbook_settings from FTD
                logging.warning(f"🔍 [LOAD-TEAM-SETTINGS] franchise master load: doc_id={doc_id!r}, team_id={team_id!r}, team_name={team_name!r}, game_id={game_id!r}")
                try:
                    franchise_doc = franchises_collection.find_one(
                        {"_id": ObjectId(doc_id)},
                        {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                    )
                    if not franchise_doc:
                        logging.warning(f"🔍 [LOAD-TEAM-SETTINGS] franchise doc not found for _id={doc_id!r}")
                    else:
                        _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
                        logging.warning(f"🔍 [LOAD-TEAM-SETTINGS] get_user_team_from_franchise -> user_team_object_id={user_team_object_id!r}")
                        if not user_team_object_id:
                            logging.warning(f"🔍 [LOAD-TEAM-SETTINGS] user_team_object_id missing in franchise doc")
                        else:
                            ftd_filter = {"franchise_id": ObjectId(doc_id), "team_id": ObjectId(user_team_object_id)}
                            ftd_doc = franchise_team_data_collection.find_one(ftd_filter, {"strategy_settings": 1, "playbook_settings": 1})
                            if not ftd_doc:
                                logging.warning(f"🔍 [LOAD-TEAM-SETTINGS] FTD doc not found for franchise_id={doc_id!r}, team_id={user_team_object_id!r}")
                            else:
                                strategy_settings = ftd_doc.get("strategy_settings")
                                playbook_settings = ftd_doc.get("playbook_settings")
                                logging.warning(
                                    f"🔍 [LOAD-TEAM-SETTINGS] FTD found: strategy_settings={bool(strategy_settings)} keys={list(strategy_settings.keys()) if strategy_settings else []}, "
                                    f"playbook_settings={bool(playbook_settings)} keys={list(playbook_settings.keys())[:10] if playbook_settings else []}"
                                )
                                if strategy_settings or playbook_settings:
                                    logging.warning(f"✅ [LOAD-TEAM-SETTINGS] Loaded from FTD for franchise {doc_id}, team {user_team_object_id}")
                except Exception as e:
                    logging.warning(f"⚠️ Error loading franchise master settings from FTD: {e}", exc_info=True)
            else:
                # Tournament: load master doc and extract from teams
                master_doc = None
                if mode == "tournament":
                    try:
                        master_doc = tournaments_collection.find_one({"_id": ObjectId(doc_id)})
                    except Exception as e:
                        logging.warning(f"⚠️ Error loading tournament doc: {e}")
                
                if master_doc:
                    team_identifier = team_name or team_id
                    if team_identifier:
                        strategy_settings = extract_team_settings(
                            saved_doc=master_doc,
                            team_identifier=team_identifier,
                            settings_type="strategy_settings",
                            mode=mode,
                            game_doc=None
                        )
                        playbook_settings = extract_team_settings(
                            saved_doc=master_doc,
                            team_identifier=team_identifier,
                            settings_type="playbook_settings",
                            mode=mode,
                            game_doc=None
                        )
        elif mode == "single":
            try:
                # For single game mode, try both UUID string and ObjectId formats
                doc = games_collection.find_one(
                    {"_id": doc_id},
                    {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                )
                if not doc:
                    try:
                        doc = games_collection.find_one(
                            {"_id": ObjectId(doc_id)},
                            {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}
                        )
                    except:
                        pass
                if doc:
                    teams_obj = doc.get("teams", {})
                    home_team_id = doc.get("home_team_id")
                    away_team_id = doc.get("away_team_id")
                    
                    # ✅ PHASE 1.1: Use same team ID resolution as save_playbooks()/update_gameplan()
                    # Resolve team_id from team_name if needed (using game document's teams object)
                    resolved_team_id = None
                    
                    # If team_id was provided, try to use it directly (if it's a team_id key)
                    if team_id:
                        # Step 1: Try direct key match (if team_id looks like a team_id key)
                        if team_id in teams_obj and (team_id.isupper() and "_" in team_id):
                            resolved_team_id = team_id
                        # Step 2: If not found, iterate through teams to find by name match
                        if not resolved_team_id:
                            for tid in teams_obj.keys():
                                team_obj = teams_obj.get(tid, {})
                                if team_obj.get("name") == team_id:
                                    resolved_team_id = tid
                                    break
                    
                    # If team_name was provided but team_id wasn't resolved, try name matching
                    # ✅ PHASE 5.2: Simplified - removed home/away fallback (not needed for new games)
                    if not resolved_team_id and team_name:
                        for tid in teams_obj.keys():
                            team_obj = teams_obj.get(tid, {})
                            if team_obj.get("name") == team_name:
                                resolved_team_id = tid
                                break
                    
                    # Load settings from resolved team_id key
                    if resolved_team_id:
                        team_obj = teams_obj.get(resolved_team_id, {})
                        strategy_settings = team_obj.get("strategy_settings")
                        playbook_settings = team_obj.get("playbook_settings")
                        
                        # ✅ TRACE: Log what we found in DB
                        trace_id_load = f"load_{doc_id}_{resolved_team_id}"
                        logging.warning(f"🟢 [TRACE-LOAD] {trace_id_load} | LOAD-TEAM-SETTINGS | resolved_team_id={resolved_team_id}, team_name={team_name}")
                        logging.warning(f"🟢 [TRACE-LOAD] {trace_id_load} | FOUND IN DB | strategy={bool(strategy_settings)}, playbook={bool(playbook_settings)}")
                        
                        if strategy_settings:
                            strategy_inside = strategy_settings.get('inside', 'MISSING')
                            logging.warning(f"🟢 [TRACE-LOAD] {trace_id_load} | STRATEGY LOADED | inside={strategy_inside}")
                        
                        if playbook_settings:
                            slot_count = len(playbook_settings.get("slot_assignments", {}))
                            logging.warning(f"🟢 [TRACE-LOAD] {trace_id_load} | PLAYBOOK LOADED | slot_assignments={slot_count}")
                        else:
                            logging.warning(f"🟢 [TRACE-LOAD] {trace_id_load} | PLAYBOOK MISSING | No playbook_settings found in DB")
                    else:
                        logging.warning(f"⚠️ [LOAD-SETTINGS] Could not resolve team_id for team_name={team_name}, team_id={team_id}")
            except Exception as e:
                logging.warning(f"⚠️ Error loading team settings from game doc: {e}", exc_info=True)
        
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
    
    def find_game_doc(games_collection, game_id: str):
        """
        Single load path: find game doc by _id, trying string then ObjectId.
        Returns (doc, effective_id) so callers can use effective_id for updates.
        """
        if games_collection is None or not game_id:
            return None, None
        saved = games_collection.find_one({"_id": game_id})
        if saved:
            return saved, game_id
        if len(game_id) == 24:
            try:
                oid = ObjectId(game_id)
                saved = games_collection.find_one({"_id": oid})
                if saved:
                    logging.info(
                        "🔍 [PERSISTENCE] find_game_doc: string _id missed; found with ObjectId for game_id=%s",
                        game_id,
                    )
                    return saved, oid
            except (ValueError, TypeError):
                pass
        return None, None

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
        query_id = None  # _id that matched (string or ObjectId) for updates
        
        try:
            # ✅ CRITICAL FIX: Games are saved as standalone documents in games_collection (not nested)
            # Use single load path (string then ObjectId) so we find doc regardless of _id type
            if games_collection is not None:
                saved, query_id = find_game_doc(games_collection, game_id)
                if saved:
                    logging.info(f"✅ TIMEOUT RESUME: Found game in games_collection (where we save)")
            else:
                logging.warning(f"⚠️ TIMEOUT RESUME: Game {game_id} not found in games_collection")
            
            if not saved:
                logging.warning(f"⚠️ TIMEOUT RESUME: Game {game_id} not found in any document location (mode: {request.mode})")
                return None
            
            # 🔍 FOUL_OUT DATA-LOSS DEBUG: Log what we loaded (Hypothesis 2 - confirm doc has timeout state and game_stats_initialized)
            logging.warning(
                "🔍 [FOUL_OUT DEBUG] restore_timeout_resume_state loaded doc: game_id=%s, timeout_next_play_type=%s, "
                "game_stats_initialized=%s, has_teams=%s, top_level_score=%s",
                game_id,
                saved.get("timeout_next_play_type"),
                saved.get("game_stats_initialized"),
                "teams" in saved and bool(saved.get("teams")),
                saved.get("score"),
            )
            
            # Validate/repair timeout_next_play_type.
            # Older or partially-saved timeout docs can miss this field; infer SIDE_INBOUND
            # when timeout_offense_team_id is present so resume flow remains deterministic.
            if not saved.get("timeout_next_play_type"):
                if saved.get("timeout_offense_team_id"):
                    inferred_next_play_type = "SIDE_INBOUND"
                    saved["timeout_next_play_type"] = inferred_next_play_type
                    try:
                        # Use same _id that matched find (string or ObjectId)
                        games_collection.update_one(
                            {"_id": query_id or game_id},
                            {"$set": {"timeout_next_play_type": inferred_next_play_type}},
                        )
                    except Exception as update_err:
                        logging.warning(
                            "⚠️ TIMEOUT RESUME: Failed to persist inferred timeout_next_play_type "
                            "for game %s: %s",
                            game_id,
                            update_err,
                        )
                    logging.warning(
                        "⚠️ TIMEOUT RESUME: timeout_next_play_type missing for game %s; "
                        "inferred SIDE_INBOUND from timeout_offense_team_id",
                        game_id,
                    )
                else:
                    logging.warning(
                        "⚠️ TIMEOUT RESUME: timeout_next_play_type missing from saved game %s "
                        "and no timeout_offense_team_id present; treating as no timeout resume",
                        game_id,
                    )
                    return None
            
            # ✅ DIAGNOSTIC: Log what settings are loaded from DB during timeout resume
            saved_teams = saved.get("teams", {})
            home_team_id = saved.get("home_team_id")
            away_team_id = saved.get("away_team_id")
            
            if home_team_id:
                saved_home_strategy = saved_teams.get(home_team_id, {}).get("strategy_settings", {})
                saved_home_pb = saved_teams.get(home_team_id, {}).get("playbook_settings", {})
            if away_team_id:
                saved_away_strategy = saved_teams.get(away_team_id, {}).get("strategy_settings", {})
                saved_away_pb = saved_teams.get(away_team_id, {}).get("playbook_settings", {})
            
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
        
        # ✅ DIAGNOSTIC: Log GameManager state before saving during timeout
        debug_prefix = "USER" if timeout_reason == "USER" else "COMPUTER"
        home_before = gm.home_team.strategy_settings.get("inside", "MISSING") if hasattr(gm.home_team, 'strategy_settings') and gm.home_team.strategy_settings else "NO_SETTINGS"
        away_before = gm.away_team.strategy_settings.get("inside", "MISSING") if hasattr(gm.away_team, 'strategy_settings') and gm.away_team.strategy_settings else "NO_SETTINGS"
        logging.warning(f"💾 [TIMEOUT-SAVE] BEFORE save: Home inside={home_before}, Away inside={away_before}")
        
        # Get playbook_settings from GameManager if available
        home_pb = getattr(gm.home_team, 'playbook_settings', {})
        away_pb = getattr(gm.away_team, 'playbook_settings', {})
        home_slots = len(home_pb.get("slot_assignments", {})) if home_pb else 0
        away_slots = len(away_pb.get("slot_assignments", {})) if away_pb else 0
        logging.warning(f"💾 [TIMEOUT-SAVE] BEFORE save: Home slot_assignments={home_slots}, Away slot_assignments={away_slots}")
        
        # Save to DB (same for both user and computer timeouts)
        from bson import ObjectId
        db_summary = summarize_game_state(gm, exclude_animations=True)
        game_id_type = type(game_id).__name__
        logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] Saving with _id: '{game_id}' (type: {game_id_type})")
        result = games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
        if result.matched_count == 0 and isinstance(game_id, str) and len(game_id) == 24:
            try:
                result = games_collection.update_one({"_id": ObjectId(game_id)}, {"$set": db_summary}, upsert=True)
                if result.matched_count > 0:
                    logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] Retried with ObjectId - matched: {result.matched_count}")
            except (ValueError, TypeError):
                pass
        logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] Update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}")
        
        # ✅ DIAGNOSTIC: Log what was saved in db_summary
        logging.warning(f"💾 [TIMEOUT-SAVE] Saved db_summary:")
        home_summary_strategy = db_summary.get("teams", {}).get(db_summary.get("home_team_id", ""), {}).get("strategy_settings", {})
        away_summary_strategy = db_summary.get("teams", {}).get(db_summary.get("away_team_id", ""), {}).get("strategy_settings", {})
        home_summary_pb = db_summary.get("teams", {}).get(db_summary.get("home_team_id", ""), {}).get("playbook_settings", {})
        away_summary_pb = db_summary.get("teams", {}).get(db_summary.get("away_team_id", ""), {}).get("playbook_settings", {})
        
        logging.warning(f"💾 [TIMEOUT-SAVE] db_summary home strategy inside: {home_summary_strategy.get('inside', 'MISSING') if home_summary_strategy else 'NO_SETTINGS'}")
        logging.warning(f"💾 [TIMEOUT-SAVE] db_summary away strategy inside: {away_summary_strategy.get('inside', 'MISSING') if away_summary_strategy else 'NO_SETTINGS'}")
        logging.warning(f"💾 [TIMEOUT-SAVE] db_summary home playbook slot_assignments: {len(home_summary_pb.get('slot_assignments', {})) if home_summary_pb else 0}")
        logging.warning(f"💾 [TIMEOUT-SAVE] db_summary away playbook slot_assignments: {len(away_summary_pb.get('slot_assignments', {})) if away_summary_pb else 0}")
        logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] db_summary timeout fields: timeout_next_play_type={db_summary.get('timeout_next_play_type')}, timeout_offense_team_id={db_summary.get('timeout_offense_team_id')}")
        logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] db_summary score={db_summary.get('score')}, clock={db_summary.get('clock')}, time_remaining={db_summary.get('time_remaining')}")
        
        # ✅ DIAGNOSTIC: Verify what was actually saved to DB
        from bson import ObjectId
        logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] Verifying save - querying with _id: '{game_id}' (type: {type(game_id).__name__})")
        saved_doc = games_collection.find_one({"_id": game_id})
        if not saved_doc and isinstance(game_id, str):
            logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] String query failed during verification, trying ObjectId...")
            try:
                saved_doc = games_collection.find_one({"_id": ObjectId(game_id)})
            except Exception as e:
                logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] ObjectId verification query failed: {e}")
        if saved_doc:
            saved_id_type = type(saved_doc.get("_id")).__name__
            saved_id_value = str(saved_doc.get("_id"))
            logger.warning(f"🔍 [TIMEOUT-SAVE DEBUG] ✅ Verification found document with _id: '{saved_id_value}' (type: {saved_id_type})")
            saved_teams = saved_doc.get("teams", {})
            home_team_id = saved_doc.get("home_team_id")
            away_team_id = saved_doc.get("away_team_id")
            saved_home_strategy = saved_teams.get(home_team_id, {}).get("strategy_settings", {}) if home_team_id else {}
            saved_away_strategy = saved_teams.get(away_team_id, {}).get("strategy_settings", {}) if away_team_id else {}
            saved_home_pb = saved_teams.get(home_team_id, {}).get("playbook_settings", {}) if home_team_id else {}
            saved_away_pb = saved_teams.get(away_team_id, {}).get("playbook_settings", {}) if away_team_id else {}
            
            logging.warning(f"✅ [TIMEOUT-SAVE] VERIFIED: Saved to DB - home strategy inside: {saved_home_strategy.get('inside', 'MISSING') if saved_home_strategy else 'NO_SETTINGS'}")
            logging.warning(f"✅ [TIMEOUT-SAVE] VERIFIED: Saved to DB - away strategy inside: {saved_away_strategy.get('inside', 'MISSING') if saved_away_strategy else 'NO_SETTINGS'}")
            logging.warning(f"✅ [TIMEOUT-SAVE] VERIFIED: Saved to DB - home playbook slot_assignments: {len(saved_home_pb.get('slot_assignments', {})) if saved_home_pb else 0}")
            logging.warning(f"✅ [TIMEOUT-SAVE] VERIFIED: Saved to DB - away playbook slot_assignments: {len(saved_away_pb.get('slot_assignments', {})) if saved_away_pb else 0}")
        else:
            logging.error(f"❌ [TIMEOUT-SAVE] VERIFICATION FAILED: Could not read saved document from DB")
        
        logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] DB AFTER save - timeout_next_play_type={saved_doc.get('timeout_next_play_type') if saved_doc else 'DOC_NOT_FOUND'}, timeout_offense_team_id={saved_doc.get('timeout_offense_team_id') if saved_doc else 'DOC_NOT_FOUND'}")
        logging.warning(f"🔍 [{debug_prefix} TIMEOUT SAVE DEBUG] DB AFTER save - score={saved_doc.get('score') if saved_doc else 'DOC_NOT_FOUND'}, clock={saved_doc.get('clock') if saved_doc else 'DOC_NOT_FOUND'}, time_remaining={saved_doc.get('time_remaining') if saved_doc else 'DOC_NOT_FOUND'}")
        
        # ✅ PHASE 3.3: Refresh cache after DB write to ensure cache matches DB
        if saved_doc and game_id in ongoing_games:
            refresh_game_cache_from_db(ongoing_games[game_id], saved_doc)
        
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
        if "shot_clock_remaining" in saved:
            gm.game_state["shot_clock_remaining"] = saved["shot_clock_remaining"]
        
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
        
        # ✅ CRITICAL FIX: Restore ALL critical game state from saved document
        # This ensures saved state (from timeout save) overwrites any stale in-memory state
        
        # Restore timeout-specific state
        if "timeout_next_play_type" in saved:
            gm.game_state["timeout_next_play_type"] = saved["timeout_next_play_type"]
            logging.info(f"🔄 TIMEOUT RESUME: Applied timeout_next_play_type={saved['timeout_next_play_type']}")
        
        # ✅ FREE_THROW timeout resume: restore offensive_state, shooter, free_throws so first simulate_turn creates the FT turn
        if saved.get("timeout_next_play_type") == "FREE_THROW":
            gm.game_state["offensive_state"] = "FREE_THROW"
            if "timeout_free_throws_remaining" in saved and saved["timeout_free_throws_remaining"] is not None:
                gm.game_state["free_throws_remaining"] = saved["timeout_free_throws_remaining"]
            if "timeout_free_throws" in saved and saved["timeout_free_throws"] is not None:
                gm.game_state["free_throws"] = saved["timeout_free_throws"]
            if "timeout_one_and_one" in saved:
                gm.game_state["one_and_one"] = saved["timeout_one_and_one"]
            shooter_id = saved.get("timeout_shooter_id")
            if shooter_id:
                shooter = None
                shooter_id_str = str(shooter_id)
                for team in (gm.home_team, gm.away_team):
                    for p in team.get_all_players():
                        if str(getattr(p, "player_id", None) or "") == shooter_id_str:
                            shooter = p
                            break
                    if shooter is not None:
                        break
                if shooter is not None:
                    gm.game_state["shooter"] = shooter
                    logging.info(f"🔄 TIMEOUT RESUME: Restored FREE_THROW state (shooter_id={shooter_id}, free_throws_remaining={gm.game_state.get('free_throws_remaining')})")
                else:
                    logging.warning(f"⚠️ TIMEOUT RESUME: FREE_THROW resume could not find shooter_id={shooter_id} in rosters")
        
        # ✅ CRITICAL FIX: Restore offense team from timeout_offense_team_id
        # This ensures the correct team has possession after timeout (e.g., if user called timeout during BIP)
        if "timeout_offense_team_id" in saved:
            gm.game_state["timeout_offense_team_id"] = saved["timeout_offense_team_id"]
            
            # ✅ SS&S FIX: Set offense_team and defense_team based on timeout_offense_team_id
            # This is critical for maintaining proper possession (e.g., user calls timeout during BIP)
            saved_offense_team_id = saved["timeout_offense_team_id"]
            if saved_offense_team_id == gm.home_team.team_id:
                gm.offense_team = gm.home_team
                gm.defense_team = gm.away_team
                logging.info(f"🔄 TIMEOUT RESUME: Set offense_team to HOME ({gm.home_team.name}) based on timeout_offense_team_id")
            elif saved_offense_team_id == gm.away_team.team_id:
                gm.offense_team = gm.away_team
                gm.defense_team = gm.home_team
                logging.info(f"🔄 TIMEOUT RESUME: Set offense_team to AWAY ({gm.away_team.name}) based on timeout_offense_team_id")
            else:
                logging.warning(f"⚠️ TIMEOUT RESUME: timeout_offense_team_id ({saved_offense_team_id}) does not match home_team_id ({gm.home_team.team_id}) or away_team_id ({gm.away_team.team_id}) - possession may be incorrect")
        
        # Restore clock and time (critical for timeout resume)
        if "clock" in saved:
            gm.game_state["clock"] = saved["clock"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored clock={saved['clock']} from saved document")
        
        if "time_remaining" in saved:
            gm.game_state["time_remaining"] = saved["time_remaining"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored time_remaining={saved['time_remaining']} from saved document")
        if "shot_clock_remaining" in saved:
            gm.game_state["shot_clock_remaining"] = saved["shot_clock_remaining"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored shot_clock_remaining={saved['shot_clock_remaining']} from saved document")
        
        # ✅ COMPUTER TIMEOUT: Restore per-quarter count and checked_conditions (enforces max 1 per quarter Q1–Q3 after DB load)
        if "computer_timeouts" in saved and saved["computer_timeouts"]:
            gm.game_state["computer_timeouts"] = deserialize_computer_timeouts(saved["computer_timeouts"])
            logging.info(f"🔄 TIMEOUT RESUME: Restored computer_timeouts from saved document")
        # ✅ MAN DEFENSE MATCHUPS: Restore user and computer matchups (computer defaults if missing)
        from BackEnd.utils.man_defense_matchups import get_default_matchups, USER_MATCHUPS_KEY, COMPUTER_MATCHUPS_KEY
        if USER_MATCHUPS_KEY in saved:
            gm.game_state[USER_MATCHUPS_KEY] = saved.get(USER_MATCHUPS_KEY) or get_default_matchups()
        if COMPUTER_MATCHUPS_KEY in saved:
            gm.game_state[COMPUTER_MATCHUPS_KEY] = saved.get(COMPUTER_MATCHUPS_KEY) or get_default_matchups()
        elif not gm.game_state.get(COMPUTER_MATCHUPS_KEY):
            gm.game_state[COMPUTER_MATCHUPS_KEY] = get_default_matchups()
        
        # ✅ CRITICAL FIX: Restore scores from saved document (overwrites stale in-memory scores)
        if "score" in saved and isinstance(saved["score"], dict):
            # Restore scores for both teams
            for team_name, score_value in saved["score"].items():
                if team_name in gm.score:
                    gm.score[team_name] = score_value
                    logging.info(f"🔄 TIMEOUT RESUME: Restored score {team_name}={score_value} from saved document")
        
        # ✅ CRITICAL FIX: Restore team fouls and timeouts from saved document
        # Check unified teams structure first, then fall back to old structure
        teams_obj = saved.get("teams", {})
        home_team_id = saved.get("home_team_id")
        away_team_id = saved.get("away_team_id")
        
        # Get team data from unified structure (preferred)
        home_team_data = teams_obj.get(home_team_id, {}) if home_team_id else {}
        away_team_data = teams_obj.get(away_team_id, {}) if away_team_id else {}
        
        # Fallback to old structure for backward compatibility
        if not home_team_data:
            home_team_data = saved.get("home_team", {})
        if not away_team_data:
            away_team_data = saved.get("away_team", {})
        
        if "team_fouls" in home_team_data:
            gm.home_team.team_fouls = home_team_data["team_fouls"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored home team_fouls={home_team_data['team_fouls']} from saved document")
        
        if "team_fouls" in away_team_data:
            gm.away_team.team_fouls = away_team_data["team_fouls"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored away team_fouls={away_team_data['team_fouls']} from saved document")
        
        # ✅ CRITICAL FIX: Restore team timeouts from saved document (unified structure support)
        if "timeouts" in home_team_data:
            gm.home_team.timeouts = home_team_data["timeouts"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored home timeouts={home_team_data['timeouts']} from saved document")
        
        if "timeouts" in away_team_data:
            gm.away_team.timeouts = away_team_data["timeouts"]
            logging.info(f"🔄 TIMEOUT RESUME: Restored away timeouts={away_team_data['timeouts']} from saved document")
    
    # 4. Routes
    @app.get("/")
    def root():
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
    @_rate_limit_sim
    def simulate_game(request: Request, body: SimulationRequest):
        """Rate limited: 30/minute per IP."""
        home_team = body.home_team
        away_team = body.away_team
    
        known_teams = [team["name"] for team in teams_collection.find({}, {"name": 1})]
    
        if home_team not in known_teams:
            raise HTTPException(status_code=400, detail=f"Unknown home_team: '{home_team}'")
        if away_team not in known_teams:
            raise HTTPException(status_code=400, detail=f"Unknown away_team: '{away_team}'")
        
        print("🔥 Simulate endpoint hit - BOOM!!")
        print(f"Home: {body.home_team}, Away: {body.away_team}")
    
        # ✅ Add this line to print the full request body
        # print("🔍 Full request body:", body)
    
    
        game = run_simulation(home_team, away_team, body.home_lineup, body.away_lineup)
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
    
        # ✅ PERFORMANCE: Removed verbose debug print
    
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
    
        return JSONResponse(content=summary, status_code=200)
    
    
    @app.get("/api/game/{game_id}")
    def get_game_state(
        game_id: str,
        quarter: int | None = None,
        source: str | None = None,
        user: dict = Depends(get_current_user),
    ):
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
        
        # ✅ PHASE 1.1: Normalize game_id at entry point (standardize to ObjectId format)
        from BackEnd.utils.game_id_utils import normalize_game_id
        from bson import ObjectId
        original_game_id = game_id
        original_game_id_type = type(original_game_id).__name__
        game_id = normalize_game_id(game_id)
        game_id_type = type(game_id).__name__
    
        # ✅ 5.2 User Data Exposure: verify game belongs to user (raises 403/404 if not)
        verify_game_owned_by_user(game_id, user["user_id"])
    
        try:
            # ---------- CACHE PATH (commented out): always use DB for SS&S team_attribute_changes, home_team_id, away_team_id ----------
            # force_db_read = source == "db"
            # gm = None
            # cache_hit = False
            # if not force_db_read:
            #     gm = ongoing_games.get(game_id)
            #     if gm:
            #         cache_hit = True
            # if gm:
            #     process_start = time.time()
            #     players = []
            #     for team in [gm.home_team, gm.away_team]:
            #         for player in team.get_all_players():
            #             players.append({
            #                 "_id": player.player_id,
            #                 "name": player.name,
            #                 "NG": player.attributes.get("NG", 1.0),
            #                 "team": team.name,
            #                 "stats": player.stats.get("game", {}),
            #                 "attributes": {
            #                     "EM": player.attributes.get("EM", 50),
            #                     "MO": player.attributes.get("MO", 0),
            #                     "CH": player.attributes.get("CH", 50),
            #                     "NG": player.attributes.get("NG", 1.0)
            #                 }
            #             })
            #     team_stats = {
            #         gm.home_team.name: {"offense": gm.home_team.scouting_data.get("offense", {}), "defense": gm.home_team.scouting_data.get("defense", {})},
            #         gm.away_team.name: {"offense": gm.away_team.scouting_data.get("offense", {}), "defense": gm.away_team.scouting_data.get("defense", {})}
            #     }
            #     response_data = {
            #         "game_id": game_id,
            #         "score": gm.score,
            #         "box_score": gm.get_box_score(),
            #         "quarter": gm.quarter,
            #         "clock": gm.game_state.get("clock", "8:00"),
            #         "players": players,
            #         "ineligible_players": gm.game_state.get("ineligible_players", []),
            #         "team_totals": gm.team_totals,
            #         "team_stats": team_stats,
            #         "points_by_quarter": gm.game_state.get("points_by_quarter", {}),
            #         "home_team": {"name": gm.home_team.name, "team_fouls": gm.home_team.team_fouls, "timeouts": getattr(gm.home_team, 'timeouts', 4), "attributes": gm.home_team.team_attributes},
            #         "away_team": {"name": gm.away_team.name, "team_fouls": gm.away_team.team_fouls, "timeouts": getattr(gm.away_team, 'timeouts', 4), "attributes": gm.away_team.team_attributes}
            #     }
            #     return response_data
            # --------------------------------------------------------------------------------------------------------------------------
    
            # Check database
            if games_collection is not None:
                # ✅ REMOVED: Verbose debug logs - only log on errors
                # ✅ PERFORMANCE: Use projection to only load needed fields (80-95% reduction in data transfer)
                # Fields needed: players (energy/stats), score, box_score, quarter, clock,
                # teams (name, team_id, box_score, totals, scouting, attributes, colors, score, timeouts, team_fouls, points_by_quarter),
                # home_team_id, away_team_id, team_totals, team_stats, points_by_quarter
                # NOT needed: turns (already empty), text_log, teams[].plays, teams[].strategy_settings, teams[].playbook_settings
                projection = {
                    "players": 1,              # Player energy, stats, attributes (F for foul count)
                    "score": 1,                # Current score
                    "box_score": 1,            # Box score (may be in teams object, but include for backward compatibility)
                    "quarter": 1,              # Current quarter
                    "clock": 1,                # Game clock
                    "home_team_id": 1,         # For unified teams structure
                    "away_team_id": 1,         # For unified teams structure
                    "teams": 1,                # Teams object (will project nested fields if needed)
                    "points_by_quarter": 1,    # Points by quarter (may be in teams object, but include for backward compatibility)
                    "team_attribute_changes": 1,  # Franchise post-game attribute deltas (box score)
                    "_id": 1
                }
                
                # ✅ PERFORMANCE DIAGNOSTIC: Measure database query time
                import time
                query_start = time.time()
                
                # Try both string and ObjectId lookups with projection
                saved = games_collection.find_one({"_id": game_id}, projection)
                if not saved and isinstance(game_id, str):
                    try:
                        oid_game_id = ObjectId(game_id)
                        saved = games_collection.find_one({"_id": oid_game_id}, projection)
                    except Exception:
                        pass
                
                query_time = (time.time() - query_start) * 1000  # Convert to ms
                # ✅ REMOVED: Verbose PERF and DEBUG logs - only log on errors or slow queries (>100ms)
                if query_time > 100:
                    doc_size = len(str(saved)) if saved else 0
                    # logging.warning(f"⚠️ [PERF] Slow DB query: /api/game/{game_id} - {query_time:.2f}ms, doc_size: {doc_size} bytes")
                    pass
                if saved:
                    # ✅ REMOVED: Verbose debug logs
                    
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
                            # ✅ SS&S FIX: Extract NG from attributes.NG (where it's saved) with fallback to top-level NG
                            attrs = p.get("attributes", {})
                            ng_value = attrs.get("NG", p.get("NG", 1.0))  # Check attributes first, then top-level, then default
                            
                            player_data = {
                                "_id": p.get("playerId") or p.get("player_id"),
                                "name": p.get("name"),
                                "NG": ng_value,  # ✅ Real-time NG from attributes.NG
                                "team": p.get("team"),
                                "stats": {},  # Empty stats for new game
                                "attributes": attrs  # ✅ Add attributes (EM, MO, CH, NG) from saved doc
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
                        # logging.warning(f"⏱️ [PERF] /api/game/{game_id} - New game path: response_size: {response_size} bytes, total: {total_time:.2f}ms")
                        return response_data
                    
                    # Extract player energy, stats, and attributes from saved game doc
                    players = saved.get("players", [])
                    # Map to include NG, stats, and attributes if available
                    players_with_energy = []
                    for p in players:
                        # ✅ SS&S FIX: Extract NG from attributes.NG (where it's saved) with fallback to top-level NG
                        # This ensures real-time energy values saved during timeout are correctly loaded
                        attrs = p.get("attributes", {})
                        ng_value = attrs.get("NG", p.get("NG", 1.0))  # Check attributes first, then top-level, then default
                        
                        # ✅ SS&S FIX: Ensure stats are properly extracted - saved as flat dict from player.stats.get("game", {})
                        # Frontend expects either gp.stats.game (nested) or gp.stats (flat), then falls back to {}
                        saved_stats = p.get("stats", {})
                        # Stats are saved as flat dict, so ensure we return them as flat dict
                        # Frontend will check gp.stats?.game first, but since it's flat, will use gp.stats
                        # ✅ DIAGNOSTIC: Log if stats are empty (for debugging)
                        if not saved_stats or not any(saved_stats.values()):
                            player_name = p.get("name", "Unknown")
                            # ✅ REMOVED: Stats debug log (cluttering Railway logs)
                            # logging.warning(f"⚠️ [STATS DEBUG] Player {player_name} has empty stats in saved doc - this may be expected for players with no game activity")
                        
                        player_data = {
                            "_id": p.get("playerId") or p.get("player_id"),
                            "name": p.get("name"),
                            "NG": ng_value,  # ✅ Real-time NG from attributes.NG (saved during timeout)
                            "team": p.get("team"),
                            "stats": saved_stats,  # ✅ Flat game stats dict (PTS, REB, AST, etc.)
                            "attributes": attrs  # ✅ Add attributes (EM, MO, CH, NG) from saved doc
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
                    
                    # ✅ FIX: Extract team names with fallbacks to ensure we always have strings (never None)
                    # This prevents TypeError when using None as dictionary keys
                    home_team_name = (
                        home_team_data.get("name") or 
                        saved.get("home_team", {}).get("name") or 
                        (home_team_id if home_team_id else "") or
                        ""
                    )
                    away_team_name = (
                        away_team_data.get("name") or 
                        saved.get("away_team", {}).get("name") or 
                        (away_team_id if away_team_id else "") or
                        ""
                    )
                    
                    # Extract scouting data from teams object (contains playcall stats for S2 tab)
                    home_scouting = home_team_data.get("scouting", {})
                    away_scouting = away_team_data.get("scouting", {})
                    
                    # Build team_stats structure (for S2 tab - playcall stats)
                    team_stats = {
                        home_team_name: {
                            "offense": home_scouting.get("offense", {}),
                            "defense": home_scouting.get("defense", {})
                        },
                        away_team_name: {
                            "offense": away_scouting.get("offense", {}),
                            "defense": away_scouting.get("defense", {})
                        }
                    }
                    
                    # ✅ SS&S: Build box_score from nested structure using team_id keys (not team names)
                    box_score = saved.get("box_score", {})
                    if not box_score:
                        # Build from unified teams structure (use team_id keys)
                        home_team_id = saved.get("home_team_id")
                        away_team_id = saved.get("away_team_id")
                        if home_team_id and "box_score" in home_team_data:
                            home_box = home_team_data.get("box_score", {})
                            box_score[home_team_id] = home_box
                        if away_team_id and "box_score" in away_team_data:
                            away_box = away_team_data.get("box_score", {})
                            box_score[away_team_id] = away_box
                    if not box_score:
                        logging.error(f"❌ [BOX-SCORE] /api/game/{game_id} - box_score is EMPTY after building!")
                    
                    # ✅ UNIFIED STRUCTURE: Return unified teams object structure
                    # Frontend should read from teams[home_team_id]/teams[away_team_id]
                    # Keeping backward compatibility home_team/away_team for now (built from teams object)
                    
                    # ✅ SS&S FIX: Extract score from saved document
                    # Score is saved as {"teamName1": score1, "teamName2": score2} at top level
                    saved_score = saved.get("score", {})
                    # If score is empty but teams object has scores, build from teams object (fallback)
                    if not saved_score and home_team_data and away_team_data:
                        home_score = home_team_data.get("score", 0)
                        away_score = away_team_data.get("score", 0)
                        saved_score = {
                            home_team_name: home_score,
                            away_team_name: away_score
                        }
                        logging.warning(f"🔍 [SCORE DEBUG] Built score from teams object: {saved_score}")
                    # ✅ REMOVED: Score debug log (cluttering Railway logs)
                    # if not saved_score or not any(saved_score.values()):
                    #     logging.warning(f"⚠️ [SCORE DEBUG] Saved score is empty or all zeroes: {saved_score}")
                    # else:
                    #     logging.info(f"✅ [SCORE DEBUG] Score loaded from DB: {saved_score}")
                    
                    response_data = {
                        "game_id": game_id,
                        "score": saved_score,  # ✅ Team scores: {"teamName1": score1, "teamName2": score2}
                        "box_score": box_score,
                        "quarter": saved.get("quarter", 1),
                        "clock": saved.get("clock", "8:00"),
                        "players": players_with_energy,  # ✅ Includes stats (flat dict, F=fouls) and attributes (EM, MO, NG)
                        # Team IDs for unified structure access
                        "home_team_id": home_team_id,
                        "away_team_id": away_team_id,
                        # Unified teams object (single source of truth)
                        "teams": teams_obj,
                        # Team-level stats (for S1/S2/S3 tabs and scoreboard)
                        "team_totals": {
                            home_team_name: home_team_data.get("totals", {}),
                            away_team_name: away_team_data.get("totals", {})
                        },
                        "team_stats": team_stats,  # Playcall stats for S2 tab
                        "points_by_quarter": {
                            home_team_name: home_team_data.get("points_by_quarter", [0, 0, 0, 0]),
                            away_team_name: away_team_data.get("points_by_quarter", [0, 0, 0, 0])
                        },
                        # ✅ BACKWARD COMPATIBILITY: Keep home_team/away_team in response (built from teams object)
                        # TODO: Remove these after frontend is updated to use teams[home_team_id]/teams[away_team_id]
                        "home_team": {
                            "name": home_team_name,
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
                            "name": away_team_name,
                            "team_fouls": away_team_data.get("team_fouls", 0),
                            "attributes": away_team_data.get("attributes", {}),  # Team attributes for S3 tab
                            "colors": away_team_data.get("colors", {}),
                            "score": away_team_data.get("score", 0),
                            "timeouts": away_team_data.get("timeouts", 4),
                            "points_by_quarter": away_team_data.get("points_by_quarter", [0, 0, 0, 0]),
                            "box_score": away_team_data.get("box_score", {}),
                            "totals": away_team_data.get("totals", {})
                        },
                        "team_attribute_changes": saved.get("team_attribute_changes") or {}
                    }
                    tac = response_data.get("team_attribute_changes") or {}
                    logging.warning(
                        "🔍 [ATTR-CHANGES] /api/game DB path: team_attribute_changes keys=%s, home_team_id=%s, away_team_id=%s",
                        list(tac.keys()), home_team_id, away_team_id
                    )
                    response_size = len(json.dumps(response_data))
                    total_time = (time.time() - endpoint_start) * 1000
                    # ✅ REMOVED: Verbose PERF log - only log if slow (>100ms)
                    if total_time > 100:
                        # logging.warning(f"⚠️ [PERF] Slow DB path: /api/game/{game_id} - {total_time:.2f}ms")
                        pass
                    return response_data
            
                logging.error(f"❌ [BOX_SCORE] Game not found in database: game_id={game_id} (type: {type(game_id).__name__})")
                # Try to find any games with similar IDs for debugging
                if isinstance(game_id, str) and len(game_id) > 10:
                    # Try to find documents with similar string _id
                    similar_str = list(games_collection.find({"_id": {"$regex": re.escape(game_id[:10])}}).limit(5))
                    logger.warning(f"🔍 [DB LOOKUP DEBUG] Found {len(similar_str)} similar string IDs: {[str(g.get('_id')) + ' (type: ' + type(g.get('_id')).__name__ + ')' for g in similar_str]}")
                    # Also try ObjectId search
                    try:
                        similar_oid = list(games_collection.find({"_id": {"$gte": ObjectId(game_id[:8] + "0" * 16), "$lt": ObjectId(game_id[:8] + "f" * 16)}}).limit(5))
                        logger.warning(f"🔍 [DB LOOKUP DEBUG] Found {len(similar_oid)} similar ObjectId IDs: {[str(g.get('_id')) + ' (type: ' + type(g.get('_id')).__name__ + ')' for g in similar_oid]}")
                    except Exception as e:
                        logger.warning(f"🔍 [DB LOOKUP DEBUG] Could not search ObjectId range: {e}")
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        except Exception as e:
            logging.exception(f"Error fetching game state for {game_id}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            # ✅ PERFORMANCE DIAGNOSTIC: Log total endpoint time (if not already logged)
            if 'endpoint_start' in locals() and 'response_size' not in locals():
                total_time = (time.time() - endpoint_start) * 1000  # Convert to ms
                # ✅ REMOVED: Verbose PERF log - only log if slow (>100ms)
                if total_time > 100:
                    # logging.warning(f"⚠️ [PERF] Slow endpoint: /api/game/{game_id} - {total_time:.2f}ms")
                    pass
    
    @app.get("/api/game/{game_id}/playbook-settings")
    def get_game_playbook_settings(game_id: str, team_id: str):
        """
        Get current playbook settings from GameManager (single source of truth during gameplay).
        Falls back to DB if game is not in memory.
        Returns format compatible with /api/playbooks for frontend consistency.
        """
        from BackEnd.db import games_collection
        from bson import ObjectId
        
        # ✅ SS&S: GameManager is single source of truth during gameplay
        gm = ongoing_games.get(game_id)
        
        if gm:
            # Game is in memory - return settings from GameManager
            # Determine which team
            target_team = None
            if gm.home_team.team_id == team_id or gm.home_team.name == team_id:
                target_team = gm.home_team
            elif gm.away_team.team_id == team_id or gm.away_team.name == team_id:
                target_team = gm.away_team
            
            if target_team and hasattr(target_team, 'playbook_settings') and target_team.playbook_settings:
                playbook_settings = target_team.playbook_settings
                slot_count = len(playbook_settings.get("slot_assignments", {}))
                logging.warning(f"✅ [GAME-PLAYBOOK] Returning playbook_settings from GameManager: team={target_team.name}, slot_assignments={slot_count}")
                
                # Return format compatible with /api/playbooks response
                return {
                    "slot_assignments": playbook_settings.get("slot_assignments", {}),
                    "motion_dropdowns": playbook_settings.get("motion_dropdowns", {}),
                    "source": "gamemanager"  # Indicate source for debugging
                }
        
        # Fallback to DB if game not in memory
        try:
            doc = games_collection.find_one({"_id": game_id})
            if not doc:
                try:
                    doc = games_collection.find_one({"_id": ObjectId(game_id)})
                except:
                    pass
            
            if doc:
                teams = doc.get("teams", {})
                # Find team by team_id or name
                team_obj = None
                for tid, tdata in teams.items():
                    if tid == team_id or tdata.get("name") == team_id:
                        team_obj = tdata
                        break
                
                if team_obj:
                    playbook_settings = team_obj.get("playbook_settings", {})
                    if playbook_settings:
                        slot_count = len(playbook_settings.get("slot_assignments", {}))
                        logging.warning(f"✅ [GAME-PLAYBOOK] Returning playbook_settings from DB (fallback): slot_assignments={slot_count}")
                        return {
                            "slot_assignments": playbook_settings.get("slot_assignments", {}),
                            "motion_dropdowns": playbook_settings.get("motion_dropdowns", {}),
                            "source": "database"  # Indicate source for debugging
                        }
        except Exception as e:
            logging.warning(f"⚠️ [GAME-PLAYBOOK] Error loading from DB: {e}")
        
        # Return empty if not found
        logging.warning(f"⚠️ [GAME-PLAYBOOK] No playbook_settings found for game_id={game_id}, team_id={team_id}")
        return {
            "slot_assignments": {},
            "motion_dropdowns": {},
            "source": "none"
        }
    
    @app.options("/api/simulate-quarter")
    async def simulate_quarter_options():
        """
        Explicit OPTIONS handler for CORS preflight.
        This ensures CORS works even if middleware has issues.
        """
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "https://gob-test.netlify.app",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "3600",
            }
        )
    
    @app.post("/api/simulate-quarter")
    @_rate_limit_sim
    def simulate_quarter_endpoint(
        request: Request,
        body: QuarterSimulationRequest,
        debug: bool = False,
        quiet_sim: bool = False,
        profile: bool = False,
    ):
        """Rate limited: 30/minute per IP. quiet_sim=True sets log level to ERROR during sim (sanity check for logging cost)."""
        import time
        start_time = time.time()
        raw_game_id = body.game_id
        game_id = raw_game_id
        # Keep non-ObjectId ids stable. Normalizing non-ObjectId values can generate
        # a new id and break timeout resume hydration.
        if game_id:
            from BackEnd.utils.game_id_utils import normalize_game_id, validate_game_id
            if validate_game_id(game_id):
                game_id = normalize_game_id(game_id) or game_id
            else:
                logging.info(
                    "🔍 simulate_quarter_endpoint: preserving non-ObjectId game_id for lookup (%s)",
                    game_id,
                )

        def _candidate_game_ids():
            ids = []
            if game_id:
                ids.append(game_id)
            if raw_game_id and raw_game_id not in ids:
                ids.append(raw_game_id)
            return ids

        def _get_cached_game():
            for gid in _candidate_game_ids():
                cached = ongoing_games.get(gid)
                if cached is not None:
                    return cached, gid
            return None, None

        def _drop_cached_game():
            for gid in _candidate_game_ids():
                if gid in ongoing_games:
                    del ongoing_games[gid]

        def _store_cached_game(gm_obj):
            for gid in _candidate_game_ids():
                ongoing_games[gid] = gm_obj

        def _find_saved_game_doc():
            if games_collection is None:
                return None, None
            for gid in _candidate_game_ids():
                saved_doc, effective = find_game_doc(games_collection, gid)
                if saved_doc:
                    return saved_doc, (effective or gid)
            return None, None
        # ✅ PERFORMANCE: Removed debug logging - only log errors and critical events
        if debug:
            logging.debug(
                "simulate_quarter_endpoint request detail: %s",
                {
                    "game_id": game_id,
                    "home_team": body.home_team,
                    "away_team": body.away_team,
                    "quarter": body.quarter,
                },
            )
        source = "resume"
        sim_quarter_load_source = None  # "cache" | "db" | "new" for PERF logging
        # ✅ SS&S: Preserve user_team_side from in-memory game BEFORE any DB operations
        # This ensures user_team_side persists even if it's not in the saved document or request
        preserved_user_team_side = None
        if game_id:
            gm, _ = _get_cached_game()
            if gm is not None:
                sim_quarter_load_source = "cache"
            # ✅ DEBUG: Track ongoing_games state at start of simulate_quarter_endpoint
            # ✅ REMOVED: Verbose ONGOING_GAMES DEBUG logs - only log errors
            # Preserve user_team_side from in-memory game
            if gm and gm.game_state.get("user_team_side"):
                preserved_user_team_side = gm.game_state.get("user_team_side")
            if gm is not None and (
                body.home_team != gm.home_team.name
                or body.away_team != gm.away_team.name
            ):
                if debug:
                    logging.debug(
                        "simulate_quarter_endpoint team mismatch: game_id=%s expected=%s vs %s got=%s vs %s",
                        game_id,
                        gm.home_team.name,
                        gm.away_team.name,
                        body.home_team,
                        body.away_team,
                    )
                raise HTTPException(
                    status_code=400,
                    detail="game_id belongs to a different matchup",
                )
            # Check if this is a "new game" scenario: user wants Q1 but saved game is Q2+
            # In this case, remove from memory and reload from DB (which will run new game detection)
            if gm is not None and body.quarter == 1 and gm.quarter > 1:
                logging.warning(
                    f"🆕 [ONGOING_GAMES] Removing game from cache: game_id={game_id}, reason='New game scenario (Q1 requested but game in memory at Q{gm.quarter})'"
                )
                _drop_cached_game()
                gm = None  # Force reload from DB where new game detection will run
                sim_quarter_load_source = None
            
            # ✅ SS&S: Ensure user_team_side is set in in-memory game if missing
            # This fixes the case where user_team_side was never set or was lost
            if gm is not None and not gm.game_state.get("user_team_side"):
                if body.user_team_side:
                    gm.game_state["user_team_side"] = body.user_team_side
                elif preserved_user_team_side:
                    gm.game_state["user_team_side"] = preserved_user_team_side
            
            # ✅ CRITICAL FIX: If game is already in memory, update strategy_settings if request has them
            # This ensures user's updated Game Plan settings are applied even if game is already loaded
            if gm is not None and body.strategy_settings and body.user_team_side:
                try:
                    # Ensure strategy_settings is a dict before copying
                    if not isinstance(body.strategy_settings, dict):
                        logging.error(f"⚠️ [STRATEGY SETTINGS] body.strategy_settings is not a dict: {type(body.strategy_settings)}")
                    else:
                        if body.user_team_side == "home":
                            old_hct = gm.home_team.strategy_settings.get('hc_trap', 'MISSING') if hasattr(gm.home_team, 'strategy_settings') and gm.home_team.strategy_settings else 'MISSING'
                            old_fcp = gm.home_team.strategy_settings.get('fc_press', 'MISSING') if hasattr(gm.home_team, 'strategy_settings') and gm.home_team.strategy_settings else 'MISSING'
                            gm.home_team.strategy_settings = dict(body.strategy_settings)  # Use dict() constructor for safety
                            new_hct = body.strategy_settings.get('hc_trap', 'MISSING')
                            new_fcp = body.strategy_settings.get('fc_press', 'MISSING')
                            # ✅ COMMENTED OUT: Strategy settings logs (cluttering transition debugging)
                            # logging.warning(f"🔧 [STRATEGY SETTINGS] Updated home team (IN MEMORY) - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                            # logging.warning(f"   - Full strategy_settings: {gm.home_team.strategy_settings}")
                        elif body.user_team_side == "away":
                            old_hct = gm.away_team.strategy_settings.get('hc_trap', 'MISSING') if hasattr(gm.away_team, 'strategy_settings') and gm.away_team.strategy_settings else 'MISSING'
                            old_fcp = gm.away_team.strategy_settings.get('fc_press', 'MISSING') if hasattr(gm.away_team, 'strategy_settings') and gm.away_team.strategy_settings else 'MISSING'
                            gm.away_team.strategy_settings = dict(body.strategy_settings)  # Use dict() constructor for safety
                            new_hct = body.strategy_settings.get('hc_trap', 'MISSING')
                            new_fcp = body.strategy_settings.get('fc_press', 'MISSING')
                            # ✅ COMMENTED OUT: Strategy settings logs (cluttering transition debugging)
                            # logging.warning(f"🔧 [STRATEGY SETTINGS] Updated away team (IN MEMORY) - HCT: {old_hct} → {new_hct}, FCP: {old_fcp} → {new_fcp}")
                            # logging.warning(f"   - Full strategy_settings: {gm.away_team.strategy_settings}")
                except Exception as e:
                    logging.error(f"❌ [STRATEGY SETTINGS] Error updating strategy_settings: {e}", exc_info=True)
            
            # ✅ CRITICAL FIX: Always load playbook_settings from DB when game is cached
            # Strategy_settings are handled later with validity checks, but playbook_settings must be loaded here
            # This ensures settings saved pre-game are applied to cached games (e.g., init-game → save settings → simulate-quarter)
            mode = body.mode or "single"
            
            # ✅ CRITICAL FIX: Always load playbook_settings when game is cached (all modes: single, franchise, tournament)
            # Previously only single mode set playbook_settings here; franchise/tournament never did, causing 40+ DB fallbacks per quarter.
            logging.warning(f"🔴🔴🔴 [DIAG] simulate-quarter CACHED PATH: gm={gm is not None}, mode={mode}, game_id={body.game_id}, quarter={body.quarter}")
            if gm is not None and body.game_id:
                doc_id = None
                game_id_arg = None
                if mode == "single":
                    doc_id = body.game_id
                elif mode == "franchise" and body.franchise_id:
                    doc_id = body.franchise_id
                    game_id_arg = body.game_id
                elif mode == "tournament" and body.tournament_id:
                    doc_id = body.tournament_id
                    game_id_arg = body.game_id
                if doc_id:
                    home_settings = load_team_settings_from_doc(
                        mode,
                        doc_id,
                        None,
                        body.home_team,
                        game_id=game_id_arg
                    )
                    away_settings = load_team_settings_from_doc(
                        mode,
                        doc_id,
                        None,
                        body.away_team,
                        game_id=game_id_arg
                    )
                    # ✅ Apply playbook_settings to GameManager so _load_playbook_settings uses cache (no DB per turn)
                    trace_id_cached = f"sim_q{body.quarter}_{body.game_id}_cached"
                    logging.warning(f"🔴🔴🔴 [DIAG] CACHED PATH: Setting playbook_settings on GameManager. gm_id={id(gm)}, home_team_id={id(gm.home_team)}, away_team_id={id(gm.away_team)}")
                    if home_settings and "playbook_settings" in home_settings:
                        gm.home_team.playbook_settings = home_settings.get("playbook_settings") or {}
                        after_slots = len(gm.home_team.playbook_settings.get("slot_assignments", {})) if gm.home_team.playbook_settings else 0
                        logging.warning(f"🔴🔴🔴 [DIAG] CACHED PATH: Set home playbook_settings: slots={after_slots}, team_obj_id={id(gm.home_team)}")
                    elif not hasattr(gm.home_team, 'playbook_settings'):
                        gm.home_team.playbook_settings = {}
                        logging.warning(f"🔴🔴🔴 [DIAG] CACHED PATH: Set empty home playbook_settings (no DB settings), team_obj_id={id(gm.home_team)}")
                    if away_settings and "playbook_settings" in away_settings:
                        gm.away_team.playbook_settings = away_settings.get("playbook_settings") or {}
                        after_slots = len(gm.away_team.playbook_settings.get("slot_assignments", {})) if gm.away_team.playbook_settings else 0
                        logging.warning(f"🔴🔴🔴 [DIAG] CACHED PATH: Set away playbook_settings: slots={after_slots}, team_obj_id={id(gm.away_team)}")
                    elif not hasattr(gm.away_team, 'playbook_settings'):
                        gm.away_team.playbook_settings = {}
                        logging.warning(f"🔴🔴🔴 [DIAG] CACHED PATH: Set empty away playbook_settings (no DB settings), team_obj_id={id(gm.away_team)}")
            
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
                timeout_saved_state = restore_timeout_resume_state(game_id, body, games_collection)
            
            if timeout_saved_state:
                # Only activate timeout resume when the client explicitly requested it.
                # Non-resume requests should ignore timeout state (without mutating/clearing DB state).
                saved_quarter = timeout_saved_state.get("quarter", 0)
                timeout_next_play_type = timeout_saved_state.get("timeout_next_play_type")
                
                if body.resume_from_timeout and timeout_next_play_type and saved_quarter == body.quarter:
                    logging.info(f"✅ TIMEOUT RESUME: Found valid timeout state in DB, timeout_next_play_type={timeout_next_play_type}, quarter={saved_quarter}")
                    # body.resume_from_timeout already True from client
                    # ✅ CRITICAL FIX: Always force reload from DB when resuming from timeout
                    # This ensures we use the latest saved state, not stale in-memory state
                    # This fixes the bug where computer timeout → user timeout shows stale data
                    if gm is not None:
                        logging.warning(f"🔍 TIMEOUT RESUME: Game in memory, but forcing DB reload to ensure latest state (game_id={game_id})")
                        logging.warning(f"🔄 [ONGOING_GAMES] Removing game from cache: game_id={game_id}, reason='Timeout resume - forcing DB reload'")
                        _drop_cached_game()
                        gm = None  # Force reload from DB
                    logging.info(f"🔍 TIMEOUT RESUME: Will load fresh game from DB and apply timeout state")
                elif body.resume_from_timeout and timeout_next_play_type and saved_quarter != body.quarter:
                    # Timeout resume requested with quarter mismatch: use saved quarter as source of truth.
                    logging.warning(
                        "⚠️ TIMEOUT RESUME: Quarter mismatch (requested=%s, saved=%s) - using saved quarter and treating as timeout resume (game_id=%s)",
                        body.quarter, saved_quarter, game_id,
                    )
                    body.quarter = saved_quarter
                    if gm is not None:
                        logging.warning(f"🔍 TIMEOUT RESUME: Game in memory, forcing DB reload (game_id={game_id})")
                        _drop_cached_game()
                        gm = None
                    logging.info(f"✅ TIMEOUT RESUME: Corrected body.quarter to %s, resume_from_timeout=True", saved_quarter)
                else:
                    # Non-resume requests (or missing next_play_type): ignore timeout state for this request.
                    # Do not mutate DB timeout fields here; timeout state is cleared after a successful resume.
                    timeout_saved_state = None
                    if body.resume_from_timeout:
                        logging.warning(
                            "⚠️ QUARTER BREAK: resume_from_timeout=true but timeout state is incomplete/invalid "
                            "(saved_quarter=%s, requested_quarter=%s, next_play_type=%s). Treating as normal quarter start.",
                            saved_quarter,
                            body.quarter,
                            timeout_next_play_type,
                        )
                        body.resume_from_timeout = False
            else:
                if body.resume_from_timeout:
                    logging.warning(f"⚠️ TIMEOUT RESUME: URL has resume_from_timeout=true but no timeout state found in DB for game_id={game_id} - treating as normal quarter start")
                    # ✅ QUARTER BREAK: Clear resume_from_timeout flag if no timeout state in DB
                    # This handles cases where resume_from_timeout was incorrectly preserved across quarter boundaries
                    body.resume_from_timeout = False
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
                db_lookup_start = time.time()
                saved, _ = _find_saved_game_doc()
                db_lookup_time = (time.time() - db_lookup_start) * 1000
                # logging.warning(f"⏱️ [DB TIMING] simulate_quarter: games_collection.find_one(game_id={game_id}): {db_lookup_time:.2f}ms, found={saved is not None}")
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
                            # ✅ SS&S: Restore strategy_calls (playcall overrides) from database
                            home_strategy_calls = home_team_data.get("strategy_calls")
                            away_strategy_calls = away_team_data.get("strategy_calls")
                            
                            # Fallback to old flat structure if teams object doesn't exist (backwards compatibility)
                            if not home_plays and not teams_obj:
                                home_plays = saved.get("team_plays", {}).get(home)
                                away_plays = saved.get("team_plays", {}).get(away)
                                home_attrs = saved.get("team_attributes", {}).get(home)
                                away_attrs = saved.get("team_attributes", {}).get(away)
                                home_scouting = saved.get("scouting", {}).get(home)
                                away_scouting = saved.get("scouting", {}).get(away)
                            
                            # ✅ UNIFIED: Load both strategy_settings and playbook_settings using unified function
                            # This ensures consistent logic for both settings types (extract from DB, override with request if valid)
                            from BackEnd.utils.team_settings_manager import load_and_apply_team_settings_to_gamemanager
                            
                            # ✅ SS&S: Use body.mode (supports single, franchise, tournament)
                            mode = body.mode or "single"
                            
                            home_strategy, away_strategy, home_playbook_settings, away_playbook_settings = load_and_apply_team_settings_to_gamemanager(
                                saved_doc=saved,
                                home_team_name=home,
                                away_team_name=away,
                                mode=mode,
                                request_strategy_settings=body.strategy_settings,
                                request_playbook_settings=body.playbook_settings,
                                user_team_side=body.user_team_side,
                                gm=None  # Will apply after GameManager creation
                            )
                            
                            # Debug logging removed - was cluttering logs
                            # logging.debug(f"🔧 LOADING FROM DB - home_strategy={home_strategy}, away_strategy={away_strategy}")
                            
                            # ✅ CRITICAL: Pass DB strategy_settings to GameManager constructor
                            # If request was invalid/missing, home_strategy/away_strategy already contain DB settings
                            # If request was valid, home_strategy/away_strategy contain request settings
                            # GameManager constructor will apply these settings correctly
                            # ✅ FRANCHISE MODE: Extract franchise_id from saved game document if present
                            saved_franchise_id = saved.get("franchise_id")
                            saved_mode = saved.get("mode", "single")
                            franchise_id_for_roster = saved_franchise_id if saved_mode == "franchise" else None
                            
                            gm_create_start = time.time()
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
                                mode=saved_mode,  # Use saved mode (could be franchise/tournament)
                                user_team_side=body.user_team_side,  # ✅ SS&S: Set is_user_team flags
                                franchise_id=franchise_id_for_roster  # ✅ FRANCHISE MODE: Pass franchise_id for loading trained attributes
                            )
                            gm_create_time = (time.time() - gm_create_start) * 1000
                            # logging.warning(f"⏱️ [DB TIMING] simulate_quarter: GameManager created from DB: {gm_create_time:.2f}ms")
                            
                            # ✅ UNIFIED: Apply both strategy_settings and playbook_settings to GameManager
                            # This ensures both settings are loaded into GameManager when game starts (not just after timeout resume)
                            # The unified function already extracted from DB and handled request overrides
                            if home_strategy:
                                gm.home_team.strategy_settings = dict(home_strategy)
                            if away_strategy:
                                gm.away_team.strategy_settings = dict(away_strategy)
                            # ✅ FIX: Always set playbook_settings (even if empty dict or None) to prevent DB fallbacks during gameplay
                            # This ensures the attribute exists so _load_playbook_settings can check it without hitting DB 37 times per quarter
                            # Empty dict means "no settings configured" which is valid - cache it so we don't hit DB
                            logging.warning(f"🔴🔴🔴 [DIAG] DB LOAD PATH: Setting playbook_settings on GameManager. gm_id={id(gm)}, home_team_id={id(gm.home_team)}, away_team_id={id(gm.away_team)}")
                            gm.home_team.playbook_settings = dict(home_playbook_settings) if home_playbook_settings else {}
                            slot_count = len(home_playbook_settings.get("slot_assignments", {})) if home_playbook_settings else 0
                            logging.warning(f"🔴🔴🔴 [DIAG] DB LOAD PATH: Set home playbook_settings: slots={slot_count}, team_obj_id={id(gm.home_team)}")
                            gm.away_team.playbook_settings = dict(away_playbook_settings) if away_playbook_settings else {}
                            slot_count = len(away_playbook_settings.get("slot_assignments", {})) if away_playbook_settings else 0
                            logging.warning(f"🔴🔴🔴 [DIAG] DB LOAD PATH: Set away playbook_settings: slots={slot_count}, team_obj_id={id(gm.away_team)}")
                            
                            # ✅ VERIFY: Log settings after GameManager creation to confirm they were applied
                            if home_strategy or away_strategy:
                                # logging.info(f"✅ [UNIFIED-SETTINGS] GameManager created with strategy_settings: home={bool(home_strategy)} (tempo={gm.home_team.strategy_settings.get('tempo', 'MISSING') if home_strategy else 'N/A'}), away={bool(away_strategy)} (tempo={gm.away_team.strategy_settings.get('tempo', 'MISSING') if away_strategy else 'N/A'})")
                                pass
                            if home_playbook_settings or away_playbook_settings:
                                home_slots = len(home_playbook_settings.get("slot_assignments", {})) if home_playbook_settings else 0
                                away_slots = len(away_playbook_settings.get("slot_assignments", {})) if away_playbook_settings else 0
                                # logging.info(f"✅ [UNIFIED-SETTINGS] GameManager created with playbook_settings: home={bool(home_playbook_settings)} (slot_assignments={home_slots}), away={bool(away_playbook_settings)} (slot_assignments={away_slots})")
                            
                            # ✅ UNIFIED: Restore playbook_settings to game document after GameManager creation
                            # This ensures playbook_settings persist when navigating to Playbooks page
                            # Use canonical team_id keys (same as summarize_game_state uses)
                            if home_playbook_settings or away_playbook_settings:
                                try:
                                    from BackEnd.utils.team_id_resolver import resolve_team_id_to_canonical
                                    
                                    # Resolve to canonical team_id (same logic as summarize_game_state)
                                    home_canonical_key = resolve_team_id_to_canonical(
                                        team_identifier=home,
                                        mode="single",
                                        doc=saved
                                    ) if saved else gm.home_team.team_id
                                    
                                    away_canonical_key = resolve_team_id_to_canonical(
                                        team_identifier=away,
                                        mode="single",
                                        doc=saved
                                    ) if saved else gm.away_team.team_id
                                    
                                    update_data = {}
                                    if home_playbook_settings:
                                        update_data[f"teams.{home_canonical_key}.playbook_settings"] = home_playbook_settings
                                    if away_playbook_settings:
                                        update_data[f"teams.{away_canonical_key}.playbook_settings"] = away_playbook_settings
                                    
                                    if update_data:
                                        games_collection.update_one({"_id": game_id}, {"$set": update_data})
                                        # logging.info(f"✅ [UNIFIED-SETTINGS] Restored playbook_settings to game document: home={bool(home_playbook_settings)} (key={home_canonical_key}), away={bool(away_playbook_settings)} (key={away_canonical_key})")
                                except Exception as e:
                                    # logging.warning(f"⚠️ [UNIFIED-SETTINGS] Could not restore playbook_settings to game document: {e}", exc_info=True)
                                    pass
                            
                            # Debug logging removed - was cluttering logs
                            # logging.debug(f"🔧 AFTER GAMEMANAGER - home.strategy_settings={gm.home_team.strategy_settings.get('tempo', 'MISSING')}, away.strategy_settings={gm.away_team.strategy_settings.get('tempo', 'MISSING')}")
                            # CRITICAL: Don't reset game_state when loading from database
                            # The GameManager constructor already initialized game_state with defaults
                            # Resetting it here wipes out FREE_THROW state that might be set during active gameplay
                            # Only update quarter - game_state is already initialized by GameManager.__init__
                            saved_quarter = saved.get("quarter", 1)
                            gm.quarter = saved_quarter
                            # 🔍 DEBUG: Log quarter mismatch
                            # logging.warning(f"🔍 [QUARTER_DEBUG] Loaded from DB: saved_quarter={saved_quarter}, body.quarter={body.quarter}, gm.quarter set to={gm.quarter}")
                            if saved_quarter != body.quarter:
                                # logging.warning(f"🔍 [QUARTER_DEBUG] ⚠️ QUARTER MISMATCH: saved_quarter ({saved_quarter}) != body.quarter ({body.quarter})")
                                pass
                            
                            # ✅ SS&S: Restore user_team_side to game_state (persists override checking across game loads)
                            # Priority: 1) Saved document, 2) Preserved from in-memory, 3) Request, 4) Warn
                            if "user_team_side" in saved:
                                gm.game_state["user_team_side"] = saved["user_team_side"]
                                logging.warning(f"✅ Restored user_team_side from DB: {saved['user_team_side']}")
                            elif preserved_user_team_side:
                                gm.game_state["user_team_side"] = preserved_user_team_side
                                logging.warning(f"✅ Restored user_team_side from preserved in-memory value: {preserved_user_team_side}")
                            elif body.user_team_side:
                                gm.game_state["user_team_side"] = body.user_team_side
                                logging.warning(f"✅ Set user_team_side from request: {body.user_team_side}")
                            else:
                                logging.warning(f"⚠️ No user_team_side found in DB, preserved memory, or request - override checking will not work!")
                            
                            # 🔍 DEBUG: Log offense_play_type in saved state (if present)
                            if "offense_play_type" in saved:
                                gm.game_state["offense_play_type"] = saved["offense_play_type"]
                                logging.warning(f"🔍 [GAME LOAD DEBUG] Restored offense_play_type from DB: '{saved['offense_play_type']}'")
                            else:
                                logging.warning(f"🔍 [GAME LOAD DEBUG] offense_play_type NOT in saved state (will be set by set_playcalls())")
                            
                            # ✅ COMPUTER TIMEOUT: Restore per-quarter count and checked_conditions when loading from DB
                            if "computer_timeouts" in saved and saved["computer_timeouts"]:
                                gm.game_state["computer_timeouts"] = deserialize_computer_timeouts(saved["computer_timeouts"])
                                logging.warning(f"✅ Restored computer_timeouts from DB (enforces max 1 per quarter Q1–Q3)")
                            # ✅ MAN DEFENSE MATCHUPS: Restore user and computer matchups (computer defaults if missing for old saves)
                            from BackEnd.utils.man_defense_matchups import get_default_matchups, USER_MATCHUPS_KEY, COMPUTER_MATCHUPS_KEY
                            if USER_MATCHUPS_KEY in saved:
                                gm.game_state[USER_MATCHUPS_KEY] = saved.get(USER_MATCHUPS_KEY) or get_default_matchups()
                            if COMPUTER_MATCHUPS_KEY in saved:
                                gm.game_state[COMPUTER_MATCHUPS_KEY] = saved.get(COMPUTER_MATCHUPS_KEY) or get_default_matchups()
                            elif not gm.game_state.get(COMPUTER_MATCHUPS_KEY):
                                gm.game_state[COMPUTER_MATCHUPS_KEY] = get_default_matchups()
                            
                            # ✅ TIMEOUT RESUME: Do NOT set body.resume_from_timeout from doc here.
                            # We only treat as timeout resume when the client sent resume_from_timeout=true (see earlier block).
                            # Otherwise "Play Quarter" after "Sim quarter" would incorrectly restore FREE_THROW state and cause instant EOG.
                            
                            # Simple check: If requesting Q1 but saved game is at a later quarter, start fresh (new game)
                            # ✅ TIMEOUT: If resuming from timeout, always restore stats (we're continuing an existing game)
                            is_new_game = (body.quarter == 1 and saved_quarter > 1) and not body.resume_from_timeout
                            should_restore_stats = not is_new_game or body.resume_from_timeout
                            # 🔍 FOUL_OUT DATA-LOSS DEBUG: Log restore path so we can confirm Hypothesis 1
                            logging.warning(
                                "🔍 [FOUL_OUT DEBUG] Restore path: should_restore_stats=%s, resume_from_timeout=%s, "
                                "saved_quarter=%s, body.quarter=%s, game_id=%s",
                                should_restore_stats, body.resume_from_timeout, saved_quarter, body.quarter, game_id,
                            )
                            
                            # CRITICAL: Build lineups BEFORE restoring player stats
                            # Player stat restoration (below) looks up players in team.lineup, so lineups must exist
                            # If request has lineups, use them; otherwise build from MongoDB
                            if body.home_lineup:
                                from BackEnd.utils.db_utils import assign_lineup_from_ids
                                gm.home_team.lineup = assign_lineup_from_ids(gm.home_team, body.home_lineup)
                                # ✅ PERFORMANCE: Removed debug logging
                            elif not gm.home_team.lineup:
                                from BackEnd.utils.db_utils import build_lineup_from_mongo
                                gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
                            
                            if body.away_lineup:
                                from BackEnd.utils.db_utils import assign_lineup_from_ids
                                gm.away_team.lineup = assign_lineup_from_ids(gm.away_team, body.away_lineup)
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
                                # Prefer unified teams structure for restore (current save format),
                                # then fallback to legacy home_team/away_team documents.
                                restore_home_team_data = {}
                                restore_away_team_data = {}
                                if home_team_id and isinstance(teams_obj, dict):
                                    restore_home_team_data = teams_obj.get(home_team_id, {}) or {}
                                if away_team_id and isinstance(teams_obj, dict):
                                    restore_away_team_data = teams_obj.get(away_team_id, {}) or {}
                                if not restore_home_team_data and isinstance(saved.get("home_team"), dict):
                                    restore_home_team_data = saved.get("home_team", {})
                                if not restore_away_team_data and isinstance(saved.get("away_team"), dict):
                                    restore_away_team_data = saved.get("away_team", {})
                                
                                # Restore team scores
                                # 🔍 DEBUG: Log score restoration
                                logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Before restore: gm.score={gm.score}, gm.quarter={gm.quarter}")
                                if "score" in restore_home_team_data:
                                    gm.score[gm.home_team.name] = restore_home_team_data["score"]
                                    logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Restored home score: {gm.home_team.name}={restore_home_team_data['score']}")
                                if "score" in restore_away_team_data:
                                    gm.score[gm.away_team.name] = restore_away_team_data["score"]
                                    logging.warning(f"🔍 [SCORE_RESTORE DEBUG] Restored away score: {gm.away_team.name}={restore_away_team_data['score']}")
                                logging.warning(f"🔍 [SCORE_RESTORE DEBUG] After restore: gm.score={gm.score}, gm.quarter={gm.quarter}")
                                
                                # Restore team fouls
                                if "team_fouls" in restore_home_team_data:
                                    gm.home_team.team_fouls = restore_home_team_data["team_fouls"]
                                if "team_fouls" in restore_away_team_data:
                                    gm.away_team.team_fouls = restore_away_team_data["team_fouls"]
                                
                                # Restore team timeouts
                                if "timeouts" in restore_home_team_data:
                                    gm.home_team.timeouts = restore_home_team_data["timeouts"]
                                else:
                                    # Default to 4 if not in saved data (backward compatibility)
                                    gm.home_team.timeouts = 4
                                if "timeouts" in restore_away_team_data:
                                    gm.away_team.timeouts = restore_away_team_data["timeouts"]
                                else:
                                    # Default to 4 if not in saved data (backward compatibility)
                                    gm.away_team.timeouts = 4
                                
                                # Restore team totals (aggregated stats)
                                if "totals" in restore_home_team_data:
                                    gm.team_totals[gm.home_team.name] = restore_home_team_data["totals"]
                                if "totals" in restore_away_team_data:
                                    gm.team_totals[gm.away_team.name] = restore_away_team_data["totals"]
                                
                                # Restore points by quarter (sync team objects + game_state mirror)
                                if "points_by_quarter" in restore_home_team_data:
                                    home_quarters = list(restore_home_team_data["points_by_quarter"] or [0, 0, 0, 0])
                                    gm.home_team.points_by_quarter = home_quarters
                                    gm.game_state["points_by_quarter"][gm.home_team.name] = list(home_quarters)
                                if "points_by_quarter" in restore_away_team_data:
                                    away_quarters = list(restore_away_team_data["points_by_quarter"] or [0, 0, 0, 0])
                                    gm.away_team.points_by_quarter = away_quarters
                                    gm.game_state["points_by_quarter"][gm.away_team.name] = list(away_quarters)
                                # ✅ PERFORMANCE: Removed debug logging
                                
                                # Restore game_stats_initialized flag to prevent stats reset
                                if "game_stats_initialized" in saved:
                                    gm.game_state["game_stats_initialized"] = saved["game_stats_initialized"]
                                    logging.info(f"🔄 game_stats_initialized restored: {saved['game_stats_initialized']}")
                                else:
                                    # 🔍 FOUL_OUT DATA-LOSS DEBUG: Doc has no game_stats_initialized → simulate_quarter may call _initialize_game_stats and zero everyone
                                    logging.warning(
                                        "🔍 [FOUL_OUT DEBUG] should_restore_stats=True but saved doc has NO 'game_stats_initialized' "
                                        "(game_id=%s); gm.game_stats_initialized will stay False → risk of stats reset in simulate_quarter",
                                        game_id,
                                    )
                            else:
                                # New Q1 game - ensure stats are zeroed
                                gm.score = {gm.home_team.name: 0, gm.away_team.name: 0}
                                gm.home_team.team_fouls = 0
                                gm.away_team.team_fouls = 0
                                gm.home_team.timeouts = 4  # New game starts with 4 timeouts
                                gm.away_team.timeouts = 4  # New game starts with 4 timeouts
                            
                            # ✅ UNIFIED: Playbook_settings restore is now handled by unified function (lines 1943-1965)
                            # Removed duplicate code - unified function handles both extraction and restore
                            
                            # ✅ TIMEOUT RESUME: Apply unified timeout state restoration (if resuming from timeout)
                            # This uses the state we loaded earlier from DB (single source of truth)
                            # Only apply if we actually found timeout state and quarter matches (not stale data)
                            if timeout_saved_state and body.resume_from_timeout:
                                # Validate that this is actually a timeout resume (not stale data from previous game)
                                # Check that timeout_next_play_type exists and quarter matches
                                saved_quarter = saved.get("quarter", 0)
                                if timeout_saved_state.get("timeout_next_play_type") and saved_quarter == body.quarter:
                                    # ✅ CRITICAL FIX: Apply timeout state from the FULL saved document, not just timeout_saved_state
                                    # This ensures we restore ALL game state (scores, clock, etc.) from the latest DB save
                                    # Use 'saved' (the full document) instead of 'timeout_saved_state' (which might be partial)
                                    apply_timeout_resume_state_to_gm(gm, saved)  # Use full saved document
                                    # Override body.resume_from_timeout to ensure simulate_quarter() handles timeout resume
                                    body.resume_from_timeout = True
                                    logging.info(f"✅ TIMEOUT RESUME: Applied timeout state from full saved document (quarter matches), setting resume_from_timeout=True for simulate_quarter()")
                                else:
                                    logging.warning(f"⚠️ TIMEOUT RESUME: Found timeout state but quarter mismatch or missing next_play_type - treating as normal game (saved_quarter={saved_quarter}, requested_quarter={body.quarter})")
                                    timeout_saved_state = None  # Clear invalid timeout state
                            else:
                                # ✅ FIX: Don't restore time_remaining when starting a new quarter
                                # simulate_quarter() will reset it to 480 (for Q1-Q4) or 240 (for OT)
                                # Only restore clock/time_remaining when resuming mid-quarter (timeout resume)
                                # For new quarter starts, let simulate_quarter() reset them
                                saved_quarter = saved.get("quarter", 0)
                                if saved_quarter != body.quarter:
                                    # Quarter mismatch - this shouldn't happen, but if it does, don't restore time
                                    logging.warning(f"⚠️ Quarter mismatch: saved={saved_quarter}, requested={body.quarter} - not restoring time_remaining")
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
                            
                            _store_cached_game(gm)
                            sim_quarter_load_source = "db"
                            # ✅ DEBUG: Track when game is added to ongoing_games
                            # ✅ REMOVED: Verbose debug log
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
                    if body.quarter == 1:
                        # Determine which team gets the user's settings
                        home_strategy = None
                        away_strategy = None
                        
                        if body.user_team_side == "home" and body.strategy_settings:
                            try:
                                if isinstance(body.strategy_settings, dict):
                                    home_strategy = dict(body.strategy_settings)  # Use dict() constructor for safety
                                    # Only apply user's settings to their team, not the CPU team
                                    away_strategy = None  # CPU team will use random defaults
                                    logging.warning(f"🔧 [STRATEGY SETTINGS] CREATING NEW GAME - user_team_side=home")
                                    logging.warning(f"   - Applied to HOME team only: HCT={body.strategy_settings.get('hc_trap')}, FCP={body.strategy_settings.get('fc_press')}")
                                    logging.warning(f"   - AWAY team will use random defaults")
                                else:
                                    logging.error(f"⚠️ [STRATEGY SETTINGS] body.strategy_settings is not a dict: {type(body.strategy_settings)}")
                            except Exception as e:
                                logging.error(f"❌ [STRATEGY SETTINGS] Error processing strategy_settings for new game: {e}", exc_info=True)
                        elif body.user_team_side == "away" and body.strategy_settings:
                            try:
                                if isinstance(body.strategy_settings, dict):
                                    away_strategy = dict(body.strategy_settings)  # Use dict() constructor for safety
                                    # Only apply user's settings to their team, not the CPU team
                                    home_strategy = None  # CPU team will use random defaults
                                    logging.warning(f"🔧 [STRATEGY SETTINGS] CREATING NEW GAME - user_team_side=away")
                                    logging.warning(f"   - Applied to AWAY team only: HCT={body.strategy_settings.get('hc_trap')}, FCP={body.strategy_settings.get('fc_press')}")
                                    logging.warning(f"   - HOME team will use random defaults")
                                else:
                                    logging.error(f"⚠️ [STRATEGY SETTINGS] body.strategy_settings is not a dict: {type(body.strategy_settings)}")
                            except Exception as e:
                                logging.error(f"❌ [STRATEGY SETTINGS] Error processing strategy_settings for new game: {e}", exc_info=True)
                        else:
                            logging.warning(f"⚠️ [STRATEGY SETTINGS] CREATING NEW GAME - No strategy_settings provided!")
                            logging.warning(f"   - user_team_side={body.user_team_side}, has_strategy_settings={bool(body.strategy_settings)}")
                        
                        # Get mode from body (default to "single")
                        mode = body.mode or "single"
                        
                        # Load team attributes from tournament/franchise/single game documents if available
                        home_team_attributes = None
                        away_team_attributes = None
                        home_plays_data = None
                        away_plays_data = None
                        home_scouting_data = None
                        away_scouting_data = None
                        
                        if mode == "tournament" and body.tournament_id:
                            # Load team attributes from tournament document
                            home_attrs = load_team_attributes_from_doc(
                                mode, 
                                body.tournament_id, 
                                None,  # team_id will be resolved inside the function
                                body.home_team
                            )
                            away_attrs = load_team_attributes_from_doc(
                                mode,
                                body.tournament_id,
                                None,
                                body.away_team
                            )
                            if home_attrs:
                                home_team_attributes = home_attrs
                            if away_attrs:
                                away_team_attributes = away_attrs
                        elif mode == "single" and body.game_id:
                            # Load team attributes from game document
                            home_attrs = load_team_attributes_from_doc(
                                mode, 
                                body.game_id, 
                                None,  # team_id will be resolved inside the function
                                body.home_team
                            )
                            away_attrs = load_team_attributes_from_doc(
                                mode,
                                body.game_id,
                                None,
                                body.away_team
                            )
                            if home_attrs:
                                home_team_attributes = home_attrs
                            if away_attrs:
                                away_team_attributes = away_attrs
                        elif mode == "franchise" and body.franchise_id:
                            # ✅ FTD: Load team data from FTD collection instead of franchise doc
                            home_ftd = load_ftd_data_for_team(
                                body.franchise_id,
                                None,  # team_id will be resolved from team_name
                                body.home_team
                            )
                            away_ftd = load_ftd_data_for_team(
                                body.franchise_id,
                                None,  # team_id will be resolved from team_name
                                body.away_team
                            )
                            
                            # Extract team_attributes, plays, and scouting_data from FTD
                            if home_ftd:
                                home_team_attributes = home_ftd.get("team_attributes")
                                home_plays_data = home_ftd.get("plays", {})
                                home_scouting_data = home_ftd.get("scouting_data", {})
                                # Initialize game_stats for plays (copy effectiveness/cloaking/momentum, reset game_stats)
                                if home_plays_data:
                                    for play_name, play_data in home_plays_data.items():
                                        # Copy effectiveness/cloaking/momentum from FTD
                                        # Initialize game_stats = 0 (season_stats stays in FTD)
                                        home_plays_data[play_name] = {
                                            "play_id": play_data.get("play_id", ""),
                                            "name": play_data.get("name", play_name),
                                            "play_type": play_data.get("play_type", ""),
                                            "play_focus": play_data.get("play_focus", ""),
                                            "effectiveness": play_data.get("effectiveness", 0),
                                            "cloaking": play_data.get("cloaking", 0),
                                            "momentum": play_data.get("momentum", 0),
                                            "game_stats": {
                                                "times_run": 0,
                                                "successes": 0,
                                                "player_points": {},
                                                "effectiveness": 0.0
                                            }
                                            # NO season_stats - that stays in FTD
                                        }
                                # Initialize game_stats for scouting_data defense
                                if home_scouting_data and "defense" in home_scouting_data:
                                    for defense_name, defense_data in home_scouting_data["defense"].items():
                                        if isinstance(defense_data, dict):
                                            # Copy effectiveness/momentum/cloaking, reset game_stats
                                            home_scouting_data["defense"][defense_name] = {
                                                "effectiveness": defense_data.get("effectiveness", 0),
                                                "momentum": defense_data.get("momentum", 0),
                                                "cloaking": defense_data.get("cloaking", 0),
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
                                                }
                                                # NO season_stats - that stays in FTD
                                            }
                                # Initialize game_stats for scouting_data offense
                                if home_scouting_data and "offense" in home_scouting_data:
                                    # Offense tracking starts fresh each game
                                    pass  # Will be initialized by TeamManager if needed
                            
                            if away_ftd:
                                away_team_attributes = away_ftd.get("team_attributes")
                                away_plays_data = away_ftd.get("plays", {})
                                away_scouting_data = away_ftd.get("scouting_data", {})
                                # Initialize game_stats for plays (same as home)
                                if away_plays_data:
                                    for play_name, play_data in away_plays_data.items():
                                        away_plays_data[play_name] = {
                                            "play_id": play_data.get("play_id", ""),
                                            "name": play_data.get("name", play_name),
                                            "play_type": play_data.get("play_type", ""),
                                            "play_focus": play_data.get("play_focus", ""),
                                            "effectiveness": play_data.get("effectiveness", 0),
                                            "cloaking": play_data.get("cloaking", 0),
                                            "momentum": play_data.get("momentum", 0),
                                            "game_stats": {
                                                "times_run": 0,
                                                "successes": 0,
                                                "player_points": {},
                                                "effectiveness": 0.0
                                            }
                                        }
                                # Initialize game_stats for scouting_data defense (same as home)
                                if away_scouting_data and "defense" in away_scouting_data:
                                    for defense_name, defense_data in away_scouting_data["defense"].items():
                                        if isinstance(defense_data, dict):
                                            away_scouting_data["defense"][defense_name] = {
                                                "effectiveness": defense_data.get("effectiveness", 0),
                                                "momentum": defense_data.get("momentum", 0),
                                                "cloaking": defense_data.get("cloaking", 0),
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
                                                }
                                            }
                        
                        gm = GameManager(
                            body.home_team, 
                            body.away_team,
                            home_strategy_settings=home_strategy,
                            away_strategy_settings=away_strategy,
                            home_team_attributes=home_team_attributes,
                            away_team_attributes=away_team_attributes,
                            home_scouting_data=home_scouting_data if mode == "franchise" and body.franchise_id and home_ftd else None,
                            away_scouting_data=away_scouting_data if mode == "franchise" and body.franchise_id and away_ftd else None,
                            home_plays_data=home_plays_data if mode == "franchise" and body.franchise_id and home_ftd else None,
                            away_plays_data=away_plays_data if mode == "franchise" and body.franchise_id and away_ftd else None,
                            mode=mode,  # Pass mode so teams can initialize plays with correct stats structure
                            user_team_side=body.user_team_side,  # ✅ SS&S: Set is_user_team flags
                            franchise_id=body.franchise_id if mode == "franchise" else None  # ✅ FRANCHISE MODE: Pass franchise_id for loading trained attributes
                        )
                        
                        # ✅ SS&S: Ensure user_team_side is set in game_state (GameManager should set it, but double-check)
                        if body.user_team_side and not gm.game_state.get("user_team_side"):
                            gm.game_state["user_team_side"] = body.user_team_side
                            logging.warning(f"✅ [NEW GAME] Set user_team_side in game_state: {body.user_team_side}")
                        elif gm.game_state.get("user_team_side"):
                            logging.warning(f"✅ [NEW GAME] user_team_side already set in game_state: {gm.game_state.get('user_team_side')}")
                        else:
                            logging.warning(f"⚠️ [NEW GAME] No user_team_side set! body.user_team_side={body.user_team_side}")
                        
                        logging.warning(f"🔧 [STRATEGY SETTINGS] AFTER GAMEMANAGER (NEW)")
                        logging.warning(f"   - Home: HCT={gm.home_team.strategy_settings.get('hc_trap', 'MISSING')}, FCP={gm.home_team.strategy_settings.get('fc_press', 'MISSING')}")
                        logging.warning(f"   - Away: HCT={gm.away_team.strategy_settings.get('hc_trap', 'MISSING')}, FCP={gm.away_team.strategy_settings.get('fc_press', 'MISSING')}")
                        # ✅ SS&S: Require game_id - game document must be created via init-game endpoint
                        # Never create game document in simulate-quarter - this causes settings to be lost
                        if not body.game_id:
                            raise HTTPException(
                                status_code=400,
                                detail=f"game_id required for Q1. Game document must be created via /api/init-game before simulating Q1. This ensures playbook and game plan settings persist."
                            )
                        # Verify game document exists in database
                        saved = games_collection.find_one({"_id": body.game_id}) if games_collection is not None else None
                        if not saved:
                            try:
                                saved = games_collection.find_one({"_id": ObjectId(body.game_id)}) if games_collection is not None else None
                            except:
                                pass
                        if not saved:
                            raise HTTPException(
                                status_code=404,
                                detail=f"Game document {body.game_id} not found. Game document must be created via /api/init-game before simulating Q1. This ensures playbook and game plan settings persist."
                            )
                            game_id = body.game_id
                        gm.game_id = game_id  # Store game_id on the GameManager object
                        ongoing_games[game_id] = gm
                        # ✅ REMOVED: Verbose debug log
                        source = "new"
                        sim_quarter_load_source = "new"
                        
                        # Save teams object to database for skeleton lookup during simulation
                        try:
                            from BackEnd.api.gameplan_routes import populate_team_plays
                            
                            # Get mode from body (default to "single")
                            mode = body.mode or "single"
                            
                            # ✅ FTD: For franchise mode, use plays_data loaded from FTD (already initialized with game_stats)
                            # For other modes, use populate_team_plays
                            if mode == "franchise" and body.franchise_id and home_plays_data and away_plays_data:
                                # Use plays_data from FTD (already initialized with game_stats = 0)
                                home_plays_for_game = home_plays_data
                                away_plays_for_game = away_plays_data
                            else:
                                # Get populated plays for team objects (with game_stats and optionally season_stats)
                                populated_plays = populate_team_plays(mode=mode)
                                home_plays_for_game = populated_plays.copy()
                                away_plays_for_game = populated_plays.copy()
                            
                            # ✅ FIX: Load playbook_settings from tournament/franchise document for new Q1 games
                            # This ensures playbook_settings are stored in game document from the start
                            home_playbook_settings = {}
                            away_playbook_settings = {}
                            
                            if mode == "tournament" and body.tournament_id:
                                # ✅ PHASE 5.7: Try game doc first, fallback to master doc
                                home_settings = load_team_settings_from_doc(
                                    mode,
                                    body.tournament_id,
                                    None,
                                    body.home_team,
                                    game_id=body.game_id
                                )
                                away_settings = load_team_settings_from_doc(
                                    mode,
                                    body.tournament_id,
                                    None,
                                    body.away_team,
                                    game_id=body.game_id
                                )
                                if home_settings:
                                    home_playbook_settings = home_settings.get("playbook_settings", {})
                                    # ✅ FIX: Also load strategy_settings from master doc if not provided in request
                                    if not home_strategy and home_settings.get("strategy_settings"):
                                        home_strategy = home_settings.get("strategy_settings")
                                        gm.home_team.strategy_settings = dict(home_strategy) if home_strategy else {}
                                if away_settings:
                                    away_playbook_settings = away_settings.get("playbook_settings", {})
                                    # ✅ FIX: Also load strategy_settings from master doc if not provided in request
                                    if not away_strategy and away_settings.get("strategy_settings"):
                                        away_strategy = away_settings.get("strategy_settings")
                                        gm.away_team.strategy_settings = dict(away_strategy) if away_strategy else {}
                            elif mode == "franchise" and body.franchise_id:
                                # ✅ FTD: Load playbook_settings and strategy_settings from FTD
                                if home_ftd:
                                    home_playbook_settings = home_ftd.get("playbook_settings", {})
                                    # ✅ FIX: Also load strategy_settings from FTD if not provided in request
                                    if not home_strategy and home_ftd.get("strategy_settings"):
                                        home_strategy = home_ftd.get("strategy_settings")
                                        gm.home_team.strategy_settings = dict(home_strategy) if home_strategy else {}
                                if away_ftd:
                                    away_playbook_settings = away_ftd.get("playbook_settings", {})
                                    # ✅ FIX: Also load strategy_settings from FTD if not provided in request
                                    if not away_strategy and away_ftd.get("strategy_settings"):
                                        away_strategy = away_ftd.get("strategy_settings")
                                        gm.away_team.strategy_settings = dict(away_strategy) if away_strategy else {}
                            
                            # ✅ FIX: Apply playbook_settings to GameManager so they're available during gameplay (prevents 37 DB lookups per quarter)
                            # Always set (even if empty dict) to ensure attribute exists
                            logging.warning(f"🔴🔴🔴 [DIAG] NEW GAME PATH: Setting playbook_settings on GameManager. gm_id={id(gm)}, home_team_id={id(gm.home_team)}, away_team_id={id(gm.away_team)}")
                            gm.home_team.playbook_settings = dict(home_playbook_settings) if home_playbook_settings else {}
                            gm.away_team.playbook_settings = dict(away_playbook_settings) if away_playbook_settings else {}
                            home_slots = len(home_playbook_settings.get("slot_assignments", {})) if home_playbook_settings else 0
                            away_slots = len(away_playbook_settings.get("slot_assignments", {})) if away_playbook_settings else 0
                            logging.warning(f"🔴🔴🔴 [DIAG] NEW GAME PATH: Set playbook_settings: home_slots={home_slots}, away_slots={away_slots}, home_team_obj_id={id(gm.home_team)}, away_team_obj_id={id(gm.away_team)}")
                            
                            # Create team objects with plays and playbook_settings for skeleton lookup
                            teams_obj = {
                                gm.home_team.team_id: {
                                    "strategy_settings": getattr(gm.home_team, 'strategy_settings', {}),
                                    "plays": home_plays_for_game,
                                    "playbook_settings": home_playbook_settings
                                },
                                gm.away_team.team_id: {
                                    "strategy_settings": getattr(gm.away_team, 'strategy_settings', {}),
                                    "plays": away_plays_for_game,
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
            
            if body.user_team_side == "home" and body.strategy_settings:
                home_strategy = body.strategy_settings
                # In single game mode, apply defensive strategy to BOTH teams for consistent pressure
                away_strategy = body.strategy_settings
            elif body.user_team_side == "away" and body.strategy_settings:
                away_strategy = body.strategy_settings
                # In single game mode, apply defensive strategy to BOTH teams for consistent pressure
                home_strategy = body.strategy_settings
            
            # Get mode from body (default to "single")
            mode = body.mode or "single"
            # ✅ Ensure trace_id always defined (used in GAMEMANAGER INIT logs regardless of mode/path)
            trace_id = f"sim_q{body.quarter}_{body.game_id or 'no_id'}"
            
            # Load team attributes from tournament/franchise/single game documents if available
            home_team_attributes = None
            away_team_attributes = None
            
            # ✅ FIX: Load strategy_settings and playbook_settings from mode documents
            # This ensures settings persist from pre-game to gameplay
            home_settings = None
            away_settings = None
            
            if mode == "tournament" and body.tournament_id:
                # Load team attributes from tournament document
                home_attrs = load_team_attributes_from_doc(
                    mode, 
                    body.tournament_id, 
                    None,  # team_id will be resolved inside the function
                    body.home_team
                )
                away_attrs = load_team_attributes_from_doc(
                    mode,
                    body.tournament_id,
                    None,
                    body.away_team
                )
                if home_attrs:
                    home_team_attributes = home_attrs
                if away_attrs:
                    away_team_attributes = away_attrs
                
                # Load strategy_settings and playbook_settings from tournament document
                    home_settings = load_team_settings_from_doc(
                        mode,
                        body.tournament_id,
                        None,
                        body.home_team
                    )
                    away_settings = load_team_settings_from_doc(
                        mode,
                        body.tournament_id,
                        None,
                        body.away_team
                    )
                    # Override strategy_settings if loaded from tournament (unless request has them)
                    if home_settings.get("strategy_settings") and not home_strategy:
                        home_strategy = home_settings.get("strategy_settings")
                    if away_settings.get("strategy_settings") and not away_strategy:
                        away_strategy = away_settings.get("strategy_settings")
            elif mode == "single" and body.game_id:
                # Load team attributes from game document
                home_attrs = load_team_attributes_from_doc(
                    mode, 
                    body.game_id, 
                    None,  # team_id will be resolved inside the function
                    body.home_team
                )
                away_attrs = load_team_attributes_from_doc(
                    mode,
                    body.game_id,
                    None,
                    body.away_team
                )
                if home_attrs:
                    home_team_attributes = home_attrs
                if away_attrs:
                    away_team_attributes = away_attrs
                
                # Load strategy_settings and playbook_settings from game document
                trace_id = f"sim_q{body.quarter}_{body.game_id}"
                logging.warning(f"🟢 [TRACE-LOAD] {trace_id} | LOADING FROM DB | game_id={body.game_id}")
                home_settings = load_team_settings_from_doc(
                    mode,
                    body.game_id,
                    None,
                    body.home_team
                )
                away_settings = load_team_settings_from_doc(
                    mode,
                    body.game_id,
                    None,
                    body.away_team
                )
                # ✅ TRACE: Log what we loaded
                home_db_inside = home_settings.get("strategy_settings", {}).get("inside", "MISSING") if home_settings.get("strategy_settings") else "NO_DB_SETTINGS"
                away_db_inside = away_settings.get("strategy_settings", {}).get("inside", "MISSING") if away_settings.get("strategy_settings") else "NO_DB_SETTINGS"
                home_slots = len(home_settings.get("playbook_settings", {}).get("slot_assignments", {})) if home_settings.get("playbook_settings") else 0
                away_slots = len(away_settings.get("playbook_settings", {}).get("slot_assignments", {})) if away_settings.get("playbook_settings") else 0
                logging.warning(f"🟢 [TRACE-LOAD] {trace_id} | LOADED FROM DB | home_strategy_inside={home_db_inside}, away_strategy_inside={away_db_inside}, home_slots={home_slots}, away_slots={away_slots}")
                # ✅ SS&S: Server (DB) is source of truth - always load from DB first
                # Only use request settings if they're explicitly provided AND valid (representing user action)
                # If request settings are empty/invalid, ignore them and use DB
                
                # Helper to check if request settings are valid (not empty/stale)
                def is_valid_request_settings(settings: dict | None) -> bool:
                    if not settings or not isinstance(settings, dict):
                        return False
                    # Must have all required keys to be considered valid
                    required_keys = ['offense', 'inside', 'attack', 'outside', 'tempo', 'defense', 'aggression', 'hc_trap', 'fc_press', 'rebounding']
                    return all(key in settings for key in required_keys) and any(settings.get(k) is not None for k in required_keys)
                
                # Home team: DB is source of truth, request only if valid
                if home_settings.get("strategy_settings"):
                    if is_valid_request_settings(home_strategy):
                        if gm is not None:
                            before_inside = gm.home_team.strategy_settings.get("inside", "MISSING") if gm.home_team.strategy_settings else "MISSING"
                            default_settings = gm.home_team._init_strategy_settings()
                            gm.home_team.strategy_settings = {**default_settings, **home_strategy}
                            after_inside = gm.home_team.strategy_settings.get("inside", "MISSING")
                    else:
                        home_strategy = home_settings.get("strategy_settings")
                        if gm is not None:
                            before_inside = gm.home_team.strategy_settings.get("inside", "MISSING") if gm.home_team.strategy_settings else "MISSING"
                            default_settings = gm.home_team._init_strategy_settings()
                            gm.home_team.strategy_settings = {**default_settings, **home_strategy}
                            after_inside = gm.home_team.strategy_settings.get("inside", "MISSING")
                elif is_valid_request_settings(home_strategy):
                    # No DB settings but request is valid - use request
                    logging.warning(f"✅ [SIMULATE-QUARTER] Using request home strategy_settings (no DB settings found)")
                    if gm is not None:
                        default_settings = gm.home_team._init_strategy_settings()
                        gm.home_team.strategy_settings = {**default_settings, **home_strategy}
                
                # ✅ CRITICAL FIX: Apply playbook_settings from DB (always, regardless of strategy_settings)
                # ✅ FIX: Always set playbook_settings (even if empty dict) to prevent DB fallbacks
                if home_settings and "playbook_settings" in home_settings:
                    db_slots = len(home_settings.get("playbook_settings", {}).get("slot_assignments", {}))
                    if gm is not None:
                        before_slots = len(getattr(gm.home_team, 'playbook_settings', {}).get("slot_assignments", {})) if getattr(gm.home_team, 'playbook_settings', None) else 0
                        gm.home_team.playbook_settings = home_settings.get("playbook_settings") or {}
                        after_slots = len(gm.home_team.playbook_settings.get("slot_assignments", {})) if gm.home_team.playbook_settings else 0
                # ✅ DIAGNOSTIC: Log request vs DB settings comparison for away team
                db_away_inside = away_settings.get("strategy_settings", {}).get("inside", "MISSING") if away_settings.get("strategy_settings") else "NO_DB_SETTINGS"
                req_away_inside = away_strategy.get("inside", "MISSING") if away_strategy and isinstance(away_strategy, dict) else "NO_REQUEST"
                logging.warning(f"📊 [APPLY-SETTINGS] Away team: DB inside={db_away_inside}, Request inside={req_away_inside}, is_valid_request={is_valid_request_settings(away_strategy)}")
                
                # Away team: DB is source of truth, request only if valid
                if away_settings.get("strategy_settings"):
                    if is_valid_request_settings(away_strategy):
                        # Request has valid settings (user action) - use request but log DB for debugging
                        logging.warning(f"✅ [APPLY-SETTINGS] Using request away strategy_settings (user action detected): inside={req_away_inside}")
                        if gm is not None:
                            default_settings = gm.away_team._init_strategy_settings()
                            gm.away_team.strategy_settings = {**default_settings, **away_strategy}
                            after_inside = gm.away_team.strategy_settings.get("inside", "MISSING")
                            logging.warning(f"✅ [APPLY-SETTINGS] Applied request away strategy: GameManager inside now={after_inside}")
                    else:
                        # Request is empty/invalid - use DB (server is source of truth)
                        away_strategy = away_settings.get("strategy_settings")
                        logging.warning(f"✅ [APPLY-SETTINGS] Using DB away strategy_settings (request was empty/invalid): inside={db_away_inside}")
                        if gm is not None:
                            default_settings = gm.away_team._init_strategy_settings()
                            gm.away_team.strategy_settings = {**default_settings, **away_strategy}
                            after_inside = gm.away_team.strategy_settings.get("inside", "MISSING")
                            logging.warning(f"✅ [APPLY-SETTINGS] Applied DB away strategy: GameManager inside now={after_inside}")
                elif is_valid_request_settings(away_strategy):
                    # No DB settings but request is valid - use request
                    logging.warning(f"✅ [SIMULATE-QUARTER] Using request away strategy_settings (no DB settings found)")
                    if gm is not None:
                        default_settings = gm.away_team._init_strategy_settings()
                        gm.away_team.strategy_settings = {**default_settings, **away_strategy}
                
                # ✅ CRITICAL FIX: Apply playbook_settings from DB (always, regardless of strategy_settings)
                # ✅ FIX: Always set playbook_settings (even if empty dict) to prevent DB fallbacks
                if away_settings and "playbook_settings" in away_settings:
                    db_slots = len(away_settings.get("playbook_settings", {}).get("slot_assignments", {}))
                    if gm is not None:
                        gm.away_team.playbook_settings = away_settings.get("playbook_settings") or {}
                        logging.warning(f"✅ [APPLY-SETTINGS] Applied DB away playbook_settings: slot_assignments={db_slots}")
                    home_strategy = home_settings.get("strategy_settings")
                    logging.warning(f"✅ [SIMULATE-QUARTER] Applied home strategy_settings from DB")
                    # ✅ CRITICAL FIX: If game is in cache, apply settings directly to cached GameManager
                    # This fixes the bug where settings are loaded from DB but not applied to cached games
                    if gm is not None:
                        default_settings = gm.home_team._init_strategy_settings()
                        gm.home_team.strategy_settings = {**default_settings, **home_strategy}
                        logging.warning(f"✅ [SIMULATE-QUARTER] Applied DB home strategy_settings to cached GameManager")
                elif home_settings.get("strategy_settings") and home_strategy:
                    logging.warning(f"⚠️ [SIMULATE-QUARTER] Skipped DB home strategy_settings (body.strategy_settings takes precedence)")
                if away_settings.get("strategy_settings") and not away_strategy:
                    away_strategy = away_settings.get("strategy_settings")
                    logging.warning(f"✅ [SIMULATE-QUARTER] Applied away strategy_settings from DB")
                    # ✅ CRITICAL FIX: If game is in cache, apply settings directly to cached GameManager
                    if gm is not None:
                        default_settings = gm.away_team._init_strategy_settings()
                        gm.away_team.strategy_settings = {**default_settings, **away_strategy}
                        logging.warning(f"✅ [SIMULATE-QUARTER] Applied DB away strategy_settings to cached GameManager")
                elif away_settings.get("strategy_settings") and away_strategy:
                    logging.warning(f"⚠️ [SIMULATE-QUARTER] Skipped DB away strategy_settings (body.strategy_settings takes precedence)")
            elif mode == "franchise" and body.franchise_id:
                # Load team attributes from franchise document
                home_attrs = load_team_attributes_from_doc(
                    mode,
                    body.franchise_id,
                    None,
                    body.home_team
                )
                away_attrs = load_team_attributes_from_doc(
                    mode,
                    body.franchise_id,
                    None,
                    body.away_team
                )
                if home_attrs:
                    home_team_attributes = home_attrs
                if away_attrs:
                    away_team_attributes = away_attrs
                
                # ✅ PHASE 5.7: Load strategy_settings and playbook_settings from franchise document
                # Try game doc first, fallback to master doc
                home_settings = load_team_settings_from_doc(
                    mode,
                    body.franchise_id,
                    None,
                    body.home_team,
                    game_id=body.game_id
                )
                away_settings = load_team_settings_from_doc(
                    mode,
                    body.franchise_id,
                    None,
                    body.away_team,
                    game_id=body.game_id
                )
                # Override strategy_settings if loaded from franchise (unless request has them)
                if home_settings.get("strategy_settings") and not home_strategy:
                    home_strategy = home_settings.get("strategy_settings")
                if away_settings.get("strategy_settings") and not away_strategy:
                    away_strategy = away_settings.get("strategy_settings")
            
            gm = GameManager(
                body.home_team, 
                body.away_team,
                home_strategy_settings=home_strategy,
                away_strategy_settings=away_strategy,
                home_team_attributes=home_team_attributes,
                away_team_attributes=away_team_attributes,
                mode=mode,  # Pass mode so teams can initialize plays with correct stats structure
                user_team_side=body.user_team_side,  # ✅ SS&S: Pass user_team_side to set is_user_team flags
                franchise_id=body.franchise_id if mode == "franchise" else None  # ✅ FRANCHISE MODE: Pass franchise_id for loading trained attributes
            )
            
            # ✅ SS&S: Require game_id for Q2-Q4 - cannot start mid-game without existing game document
            # Game document must be created via init-game endpoint before Q1
            if not body.game_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"game_id required for Q{body.quarter}. Game document must be created via /api/init-game before Q1. Cannot start Q{body.quarter} without existing game document."
                )
            # ✅ PHASE 1.1: Normalize game_id at entry point (standardize to ObjectId format)
            from BackEnd.utils.game_id_utils import normalize_game_id
            original_game_id = body.game_id
            game_id = normalize_game_id(body.game_id)
            if original_game_id != game_id:
                logger.warning(f"🔍 [NORMALIZE] POST /api/simulate-quarter - Normalized game_id from '{original_game_id}' to '{game_id}'")
            saved = games_collection.find_one({"_id": game_id}) if games_collection is not None else None
            if not saved:
                try:
                    saved = games_collection.find_one({"_id": ObjectId(game_id)}) if games_collection is not None else None
                except:
                    pass
            if not saved:
                raise HTTPException(
                    status_code=404,
                    detail=f"Game document {game_id} not found for Q{body.quarter}. Game document must be created via /api/init-game before Q1. Cannot resume Q{body.quarter} without existing game document."
                )
            gm.game_id = game_id  # Store game_id on the GameManager object
            ongoing_games[game_id] = gm
            # ✅ REMOVED: Verbose debug log
            source = "new"
            
            # Save teams object to database for skeleton lookup during simulation
            try:
                from BackEnd.api.gameplan_routes import populate_team_plays
                
                # Get mode from body (default to "single")
                mode = body.mode or "single"
                
                # Get populated plays for team objects (with game_stats and optionally season_stats)
                populated_plays = populate_team_plays(mode=mode)
                
                # ✅ FIX: Load playbook_settings from tournament/franchise document for new Q1 games
                # This ensures playbook_settings are stored in game document from the start
                home_playbook_settings = {}
                away_playbook_settings = {}
                
                if mode == "tournament" and body.tournament_id:
                    # ✅ PHASE 5.7: Try game doc first, fallback to master doc
                    home_settings = load_team_settings_from_doc(
                        mode,
                        body.tournament_id,
                        None,
                        body.home_team,
                        game_id=body.game_id
                    )
                    away_settings = load_team_settings_from_doc(
                        mode,
                        body.tournament_id,
                        None,
                        body.away_team,
                        game_id=body.game_id
                    )
                    if home_settings:
                        home_playbook_settings = home_settings.get("playbook_settings", {})
                    if away_settings:
                        away_playbook_settings = away_settings.get("playbook_settings", {})
                elif mode == "franchise" and body.franchise_id:
                    home_settings = load_team_settings_from_doc(
                        mode,
                        body.franchise_id,
                        None,
                        body.home_team
                    )
                    away_settings = load_team_settings_from_doc(
                        mode,
                        body.franchise_id,
                        None,
                        body.away_team
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
                "home_team": body.home_team,
                "away_team": body.away_team,
                "quarter": body.quarter,
                "source": source,
            }
        )
    
        # If the requested quarter has already been simulated, return the existing state
        if body.quarter < gm.quarter:
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
            return JSONResponse(content=summary, status_code=200)
    
        # Allow quarter progression: only prevent going backwards or skipping too far ahead
        if body.quarter < gm.quarter:
            if debug:
                logging.debug(
                    "simulate_quarter_endpoint quarter regression: game_id=%s current=%s requested=%s",
                    game_id,
                    gm.quarter,
                    body.quarter,
                )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot simulate previous quarter. Current quarter is {gm.quarter}, requested {body.quarter}",
            )
        elif body.quarter > gm.quarter + 1:
            if debug:
                logging.debug(
                    "simulate_quarter_endpoint quarter skip: game_id=%s current=%s requested=%s",
                    game_id,
                    gm.quarter,
                    body.quarter,
                )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot skip quarters. Current quarter is {gm.quarter}, requested {body.quarter}",
            )
    
        try:
            profile_summary_sim = None
            # ✅ FIX: Use full_sim parameter to determine turn_by_turn_mode
            # When full_sim=True (simming), fully simulate the quarter instantly (no animation)
            # When full_sim=False (playing), use turn-by-turn mode (for animation)
            turn_by_turn_mode = not body.full_sim
            logging.info(f"🎮 simulate_quarter_endpoint: full_sim={body.full_sim}, turn_by_turn_mode={turn_by_turn_mode}, quarter={body.quarter}, resume_from_timeout={body.resume_from_timeout}")
            
            # Sanity check: quiet_sim=True suppresses INFO/WARNING during sim to measure logging cost
            saved_log_levels = None
            if quiet_sim:
                root = logging.getLogger()
                loggers_to_quiet = [
                    root,
                    logging.getLogger("BackEnd.main"),
                    logging.getLogger("BackEnd.models.turn_manager"),
                    logging.getLogger("BackEnd.models.game_manager"),
                ]
                saved_log_levels = {log: log.level for log in loggers_to_quiet}
                for log in loggers_to_quiet:
                    log.setLevel(logging.ERROR)
            try:
                # ⏱️ PERFORMANCE: Time the quarter simulation
                sim_start = time.time()
                if profile:
                    from BackEnd.utils.profiling import run_profiled
                    def _sim():
                        simulate_quarter(
                            gm,
                            body.home_lineup,
                            body.away_lineup,
                            game_id,
                            body.start_with_inbound,
                            body.starting_possession,
                            turn_by_turn_mode=turn_by_turn_mode,
                            resume_from_timeout=body.resume_from_timeout,
                        )
                    profile_summary_sim = run_profiled(_sim, top_n=80)
                    sim_time = (time.time() - sim_start) * 1000
                else:
                    simulate_quarter(
                        gm,
                        body.home_lineup,
                        body.away_lineup,
                        game_id,
                        body.start_with_inbound,
                        body.starting_possession,
                        turn_by_turn_mode=turn_by_turn_mode,
                        resume_from_timeout=body.resume_from_timeout,
                    )
                    sim_time = (time.time() - sim_start) * 1000
            finally:
                if saved_log_levels is not None:
                    for log, level in saved_log_levels.items():
                        log.setLevel(level)
            
        except ValueError as e:
            logging.error(
                "simulate_quarter lineup error for game_id=%s, home_team=%s, away_team=%s, quarter=%s: %s",
                game_id,
                body.home_team,
                body.away_team,
                body.quarter,
                e,
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logging.error(
                "simulate_quarter failed for game_id=%s, home_team=%s, away_team=%s, quarter=%s, home_lineup_keys=%s, away_lineup_keys=%s, full_sim=%s, turn_by_turn_mode=%s",
                game_id,
                body.home_team,
                body.away_team,
                body.quarter,
                list((body.home_lineup or {}).keys()),
                list((body.away_lineup or {}).keys()),
                body.full_sim,
                not body.full_sim,
            )
            logging.error(f"Full traceback:\n{error_trace}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
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
        # ✅ REMOVED: Verbose debug logs - only log if game is unexpectedly missing
        gm_after_sim = ongoing_games.get(game_id)
        if not gm_after_sim and not body.full_sim:
            logging.warning(f"⚠️ [ONGOING_GAMES] Game NOT in ongoing_games after simulate_quarter! Available games: {list(ongoing_games.keys())}")
        
        # Save to database (WITHOUT animations to reduce document size)
        db_save_start = time.time()
        try:
            db_summary = summarize_game_state(gm, exclude_animations=True)
            # ✅ FIX: Log quarter before save to debug save/load issues
            logging.info(f"💾 Saving game state: game_id={game_id}, quarter={db_summary.get('quarter')}, gm.quarter={gm.quarter}")
            
            # ✅ TOURNAMENT MODE: Add mode and tournament_id to game document for consistency with Franchise mode
            # ✅ FIX: Prefer explicit mode from body over inferring from IDs
            # This prevents Single Game mode from being incorrectly set to "franchise" when franchise_id leaks from localStorage
            mode = body.mode
            if not mode:
                # Only infer mode if it's truly not set
                # Default to "single" if mode is not explicitly provided (even if IDs are present)
                if body.tournament_id:
                    mode = "tournament"
                elif body.franchise_id:
                    mode = "franchise"
                else:
                    mode = "single"
            
            # Add mode to game document (for consistency with init_game() pattern)
            if mode:
                db_summary["mode"] = mode
            
            # Add tournament_id to game document when in tournament mode (matches Franchise mode pattern)
            if mode == "tournament" and body.tournament_id:
                db_summary["tournament_id"] = str(body.tournament_id)
            
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
            
            # ✅ PHASE 3.3: Refresh cache after DB write to ensure cache matches DB
            if game_id in ongoing_games:
                saved_doc_full = games_collection.find_one({"_id": game_id_oid})
                if saved_doc_full:
                    refresh_game_cache_from_db(ongoing_games[game_id], saved_doc_full)
            
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
            import traceback as _tb
            print("🚨 Mongo upsert failed:", e)
            _tb.print_exc()
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
        if body.resume_from_timeout:
            logging.info(f"✅ TIMEOUT RESUME: Returning turns from simulate_quarter() (turns count: {len(turns)})")
            if turns:
                first_turn = turns[0]
                logging.info(f"✅ TIMEOUT RESUME: First turn result_type={first_turn.get('result_type')}, current_turn={first_turn.get('current_turn')}, quarter={first_turn.get('quarter')}")
            else:
                timeout_resume_next_play_type = None
                if isinstance(timeout_saved_state, dict):
                    timeout_resume_next_play_type = timeout_saved_state.get("timeout_next_play_type")
                elif isinstance(locals().get("saved"), dict):
                    timeout_resume_next_play_type = locals()["saved"].get("timeout_next_play_type")

                if timeout_resume_next_play_type == "SIDE_INBOUND":
                    logging.error("🚨 TIMEOUT RESUME: No turns returned for SIDE_INBOUND resume; expected immediate SIP turn from simulate_quarter()")
                elif timeout_resume_next_play_type in {"FREE_THROW", "BASELINE_INBOUND"}:
                    logging.info(
                        "✅ TIMEOUT RESUME: No immediate turns returned for %s resume (expected; first turn is created on /api/simulate-turn)",
                        timeout_resume_next_play_type,
                    )
                else:
                    logging.warning(
                        "⚠️ TIMEOUT RESUME: No turns returned and timeout_next_play_type is unknown/missing (%s)",
                        timeout_resume_next_play_type,
                    )
            # Turns array already contains the SIP turn created in simulate_quarter() when applicable.
        
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
        
        # ⏱️ PERFORMANCE: Log total + breakdown (sim = turn loop, summary = build response, db_save = persist)
        total_time = (time.time() - start_time) * 1000
        _src = sim_quarter_load_source if sim_quarter_load_source else "?"
        logging.warning(
            f"⏱️ [PERF] simulate-quarter total={total_time/1000:.2f}s sim={sim_time/1000:.1f}s summary={summary_time:.0f}ms db_save={db_save_time:.0f}ms source={_src} q={body.quarter} full_sim={body.full_sim} quiet_sim={quiet_sim}"
        )
        if profile_summary_sim is not None:
            frontend_summary["profile_summary"] = profile_summary_sim
        return JSONResponse(content=frontend_summary, status_code=200)
    
    
    def _has_pending_terminal_free_throw(gm) -> bool:
        """
        True when a free throw sequence is still pending and must be resolved,
        even if time_remaining has reached 0.
        """
        try:
            if (gm.game_state.get("free_throws_remaining", 0) or 0) > 0:
                return True
            if gm.game_state.get("offensive_state") == "FREE_THROW":
                return True
            if gm.turns and isinstance(gm.turns[-1], dict):
                last_turn = gm.turns[-1]
                if last_turn.get("next_play_type") == "FREE_THROW":
                    return True
                if (
                    last_turn.get("current_turn") == "FREE_THROW"
                    and (last_turn.get("free_throws_remaining", 0) or 0) > 0
                ):
                    return True
        except Exception:
            # Defensive fallback: never block normal completion on helper failure.
            return False
        return False

    @app.post("/api/simulate-turn")
    @_rate_limit_turn
    def simulate_turn_endpoint(request: Request, body: TurnSimulationRequest):
        import time
        start_time = time.time()
        # Simulate a single turn for turn-by-turn gameplay.
        # This endpoint:
        # 1. Retrieves the GameManager from ongoing_games
        # 2. Applies user overrides (if any) for this turn
        # 3. Simulates ONE turn (one call to gm.simulate_macro_turn())
        # 4. Returns the turn data + game state metadata
        # 5. Saves game state periodically
        game_id = body.game_id
        
        # Get the GameManager from memory
        gm = ongoing_games.get(game_id)
        if gm is None:
            raise HTTPException(
                status_code=404,
                detail=f"Game {game_id} not found. Start a quarter first with /api/simulate-quarter"
            )
        
        # Log lineup state when simulate-turn is called
        home_lineup = getattr(gm.home_team, "lineup", None)
        away_lineup = getattr(gm.away_team, "lineup", None)
        logging.info(
            f"🏀 simulate-turn: Retrieved game from ongoing_games, "
            f"home_lineup_keys={list(home_lineup.keys()) if home_lineup else 'EMPTY'}, "
            f"away_lineup_keys={list(away_lineup.keys()) if away_lineup else 'EMPTY'}"
        )
        
        # Apply user overrides for THIS turn only
        if body.offense_override:
            gm.game_state["user_offense_override"] = body.offense_override
            logging.info(f"🎮 User offense override: {body.offense_override}")
        
        if body.defense_override:
            gm.game_state["user_defense_override"] = body.defense_override
            logging.info(f"🎮 User defense override: {body.defense_override}")
        
        pending_terminal_ft = _has_pending_terminal_free_throw(gm)

        # Check if quarter is already over.
        # Edge-case rule: at 0:00, only continue if a free throw sequence is pending.
        if gm.game_state["time_remaining"] <= 0 and not pending_terminal_ft:
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
            # logging.warning(
            #     f"⏱️ [PERF] /api/simulate-turn - EARLY RETURN (quarter complete), "
            #     f"quarter={gm.quarter}, total: {total_time:.2f}ms"
            # )
            return JSONResponse(content=early_return, status_code=200)
        elif gm.game_state["time_remaining"] <= 0 and pending_terminal_ft:
            logging.warning(
                "🧭 [EOG-EDGE] time_remaining=0 but pending FT sequence detected; continuing turn simulation"
            )
        
        # ✅ TIMEOUT: Check if last turn is a TIMEOUT turn (user-initiated or foul out)
        # If so, return it immediately without simulating a new turn
        if gm.turns and isinstance(gm.turns[-1], dict) and gm.turns[-1].get("result_type") == "TIMEOUT":
            # Edge-case rule: if clock is 0 and FT is pending, skip timeout UX and
            # resolve FT/endgame directly.
            if gm.game_state["time_remaining"] <= 0 and pending_terminal_ft:
                skipped_timeout = gm.turns.pop()
                logging.warning(
                    "🧭 [EOG-EDGE] Skipping TIMEOUT turn at 0:00 to resolve pending FT (reason=%s)",
                    skipped_timeout.get("timeout_reason"),
                )
            else:
                timeout_turn = gm.turns[-1]
                logging.info(f"⏸️ TIMEOUT: Returning existing TIMEOUT turn (reason: {timeout_turn.get('timeout_reason')})")
                # Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
                gm.turns.pop()
                return JSONResponse(
                    content={
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
                        "box_score": gm.get_box_score(),
                        "team_totals": {
                            gm.home_team.name: gm.home_team.get_team_game_stats(),
                            gm.away_team.name: gm.away_team.get_team_game_stats()
                        }
                    },
                    status_code=200,
                )
        
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
                        # Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
                        timeout_turn = gm.turns.pop()
                        
                        # ✅ UNIFIED: Use shared helper function (same as user timeout)
                        timeout_response = handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="COMPUTER")
                        
                        # ⏱️ PERFORMANCE: Log timeout return path
                        total_time = (time.time() - start_time) * 1000
                        response_size = len(str(timeout_response).encode('utf-8'))
                        # logging.warning(
                        #     f"⏱️ [PERF] /api/simulate-turn - TIMEOUT PATH, quarter={gm.quarter}, "
                        #     f"response_size: {response_size} bytes, total: {total_time:.2f}ms"
                        # )
                        return JSONResponse(content=timeout_response, status_code=200)
                    except Exception as e:
                        logging.error(f"🚨 COMPUTER TIMEOUT: Failed to save game state: {e}")
                        # Don't fail the timeout return if save fails - game is still in memory
                        # Return timeout turn without save (fallback)
                        timeout_turn = gm.turns.pop() if gm.turns else None
                        if timeout_turn:
                            fallback = {
                                "turn": timeout_turn,
                                "time_remaining": gm.game_state.get("time_remaining", 480),
                                "clock": gm.game_state.get("clock", "8:00"),
                                "quarter_complete": False,
                                "quarter": gm.quarter,
                            }
                            return JSONResponse(content=fallback, status_code=200)
                    # ⏱️ PERFORMANCE: Log timeout return path
                    total_time = (time.time() - start_time) * 1000
                    response_size = len(str(timeout_response).encode('utf-8'))
                    # logging.warning(
                    #     f"⏱️ [PERF] /api/simulate-turn - TIMEOUT PATH, quarter={gm.quarter}, "
                    #     f"response_size: {response_size} bytes, total: {total_time:.2f}ms"
                    # )
                    return JSONResponse(content=timeout_response, status_code=200)
            
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
            # ✅ CRITICAL: If pending_computer_timeout was just processed above, timeout_turn was already created and returned
            # In that case, simulate_macro_turn() wasn't called, so new_turns will be empty - that's expected and correct
            new_turns = gm.turns[turns_before:] if len(gm.turns) > turns_before else []
            
            if not new_turns:
                # No turns were created - this can happen legitimately if pending_computer_timeout was processed above
                # In that case, the timeout was already returned, so we shouldn't reach here
                # But handle gracefully: check if pending timeout was just processed (shouldn't happen, but defensive)
                if gm.game_state.get("pending_computer_timeout"):
                    logging.error(f"🚨 UNEXPECTED: No new turns but pending_computer_timeout still exists! This should have been handled above.")
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
            
            # ✅ FOUL_OUT RESUME: Persist timeout state via same path as user/computer timeout so return-to-court finds it
            for t in new_turns:
                if isinstance(t, dict) and t.get("result_type") == "TIMEOUT" and t.get("timeout_reason") == "FOUL_OUT":
                    try:
                        save_id = getattr(gm, "game_id", None) or game_id
                        if save_id:
                            handle_timeout_save_and_response(gm, t, save_id, timeout_reason="FOUL_OUT")
                            logging.info(f"💾 FOUL_OUT: Saved timeout state via handle_timeout_save_and_response (game_id={save_id})")
                    except Exception as e:
                        logging.error(f"🚨 FOUL_OUT: handle_timeout_save_and_response failed: {e}")
                    break
            
            # Check if quarter is now complete.
            # Edge-case rule: if FT is still pending at 0:00, quarter is NOT complete yet.
            # Phase 6: Final Turn shot and FINAL_HOLD use time_elapsed = time_remaining, so clock reaches 0
            # after the turn (or after FTs if shooting foul); this block then sets quarter_complete and
            # advances to Quarter Break / OT / game end via existing logic.
            pending_terminal_ft_after_turn = _has_pending_terminal_free_throw(gm)
            quarter_complete = (
                gm.game_state["time_remaining"] <= 0
                and not pending_terminal_ft_after_turn
            )
            
            # Debug logging for quarter completion check
            if quarter_complete:
                turn_type = latest_turn.get("result_type", "UNKNOWN") if latest_turn else "NONE"
                turn_text = latest_turn.get("text", "")[:50] if latest_turn else ""
                time_elapsed = time_before_turn - time_after_turn
                logging.info(f"✅ [FINAL TURN DEBUG] Quarter complete! time_before_turn={time_before_turn}s, time_after_turn={time_after_turn}s, time_elapsed={time_elapsed}s, clock={gm.game_state.get('clock', 'N/A')}, turn_type={turn_type}, turn_text={turn_text}")
            elif gm.game_state["time_remaining"] <= 0 and pending_terminal_ft_after_turn:
                logging.warning("🧭 [EOG-EDGE] Quarter not complete at 0:00 because FT sequence remains pending")
            
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
                
                # ✅ MAN DEFENSE MATCHUPS: Reset to defaults at start of quarter break
                from BackEnd.utils.man_defense_matchups import reset_matchups_to_defaults
                reset_matchups_to_defaults(gm.game_state)
                logging.info("✅ QUARTER BREAK: Reset man defense matchups to defaults")
                
                # ✅ QUARTER BREAK: Clear timeout state when quarter completes (not a timeout resume)
                # This ensures quarter breaks are treated as new quarter starts, not timeout resumes
                if "timeout_next_play_type" in gm.game_state:
                    del gm.game_state["timeout_next_play_type"]
                    logging.info(f"✅ QUARTER BREAK: Cleared timeout_next_play_type (quarter break, not timeout)")
                if "timeout_offense_team_id" in gm.game_state:
                    del gm.game_state["timeout_offense_team_id"]
                    logging.info(f"✅ QUARTER BREAK: Cleared timeout_offense_team_id (quarter break, not timeout)")
            
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
                "shot_clock_remaining": gm.game_state.get("shot_clock_remaining", min(30, gm.game_state.get("time_remaining", 0))),
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
                # Box score for real-time updates (fouled-out derived from player stats F >= 5)
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
            # logging.warning(
            #     f"⏱️ [PERF] /api/simulate-turn - turn={turn_number}, quarter={gm.quarter}, "
            #     f"simulation: {turn_sim_time:.2f}ms, db_save: {db_save_time:.2f}ms, "
            #     f"response_size: {response_size} bytes, total: {total_time:.2f}ms, "
            #     f"quarter_complete={quarter_complete}"
            # )
            
            return JSONResponse(content=response_data, status_code=200)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logging.exception(f"Failed to simulate turn for game {game_id}")
            logging.error(f"Full traceback:\n{error_trace}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    
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
        
        # Validate using Pydantic model (use req for all body fields; body is a dict)
        req = PlaycallOverrideRequest(**body)
        
        game_id = req.game_id
        gm = ongoing_games.get(game_id)
        
        # ✅ DEBUG: Track ongoing_games state for playcall override issue
        # ✅ REMOVED: Verbose debug logs - only log if game is missing
        if not gm:
            logging.warning(f"⚠️ [ONGOING_GAMES] Game NOT in ongoing_games! Available games: {list(ongoing_games.keys())}")
        
        if gm is None:
            raise HTTPException(
                status_code=404,
                detail=f"Game {game_id} not found. Start a quarter first with /api/simulate-quarter"
            )
        
        # Determine user team
        user_team = gm.home_team if req.user_team_side == "home" else gm.away_team
        
        # ✅ DEBUG: Log team info with object IDs for tracking
        user_team_id = id(user_team)  # Python object ID to verify same object
        logging.warning(f"🎮 [PLAYCALL SET] API: Setting override on team object")
        logging.warning(f"   - user_team_side={req.user_team_side}, user_team={user_team.name}")
        logging.warning(f"   - team_id={user_team.team_id}, object_id={user_team_id}")
        logging.warning(f"   - Current strategy_calls: {user_team.strategy_calls}")
        logging.warning(f"   - game_id={game_id}, game_object_id={id(gm)}")
        logging.warning(f"   - Provided fields in request: {provided_fields}")
        
        # ✅ SS&S: Only process fields that were explicitly provided in the request
        # The frontend now only sends the field being changed, so we can safely process all provided fields
        # - If a field is provided and non-None → set it
        # - If a field is provided and None → clear it (explicit clear via red X)
        
        if "offense_override" in provided_fields:
            if req.offense_override is not None:
                user_team.strategy_calls["offense_call"] = req.offense_override
                logging.warning(f"🎮 [PLAYCALL SET] ✅ Offense override SET: '{req.offense_override}'")
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
            if req.defense_override is not None:
                user_team.strategy_calls["defense_call"] = req.defense_override
                logging.warning(f"🎮 [PLAYCALL SET] ✅ Defense override SET: '{req.defense_override}'")
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
            if req.aggression_override is not None:
                user_team.strategy_calls["aggression_override"] = req.aggression_override
                logging.warning(f"🎮 [PLAYCALL SET] ✅ Aggression override SET: '{req.aggression_override}'")
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
        
        if "tempo_override" in provided_fields and req.tempo_override is not None:
            user_team.strategy_calls["tempo_override"] = req.tempo_override
            logging.info(f"🎮 [PLAYCALL OVERRIDE] Set tempo override for {user_team.name}: {req.tempo_override}")
        
        response_data = {
            "status": "success",
            "overrides": {
                "offense": user_team.strategy_calls.get("offense_call"),
                "defense": user_team.strategy_calls.get("defense_call"),
                "aggression": user_team.strategy_calls.get("aggression_override"),
                "tempo": user_team.strategy_calls.get("tempo_override")
            }
        }
        return JSONResponse(content=response_data, status_code=200)
    
    
    @app.post("/api/call-timeout")
    async def call_timeout_endpoint(request: CallTimeoutRequest):
        # User-initiated timeout endpoint.
        # Creates a TIMEOUT turn and saves game state before navigating to lineup screen.
        # ✅ PHASE 1.1: Normalize game_id at entry point (standardize to ObjectId format)
        from BackEnd.utils.game_id_utils import normalize_game_id
        original_game_id = request.game_id
        game_id = normalize_game_id(request.game_id) if request.game_id else None
        if original_game_id != game_id:
            logger.warning(f"🔍 [NORMALIZE] POST /api/call-timeout - Normalized game_id from '{original_game_id}' to '{game_id}'")
        
        calling_team_side = request.calling_team  # 'home' or 'away'
        
        gm = ongoing_games.get(game_id) if game_id else None
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
    
    
    @app.post("/api/save-man-defense-matchups")
    def save_man_defense_matchups(request: SaveManDefenseMatchupsRequest):
        """
        Save custom man defense matchups for a game.
        Matchups are stored in game_state and reset to defaults at each break.
        
        Args:
            request: SaveManDefenseMatchupsRequest with game_id and matchups dict
                    matchups format: {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"}
                    (defensive position → offensive position)
        
        Returns:
            Success message and updated matchups
        """
        from BackEnd.utils.game_id_utils import normalize_game_id
        from BackEnd.utils.man_defense_matchups import validate_man_defense_matchups
        
        game_id = normalize_game_id(request.game_id) if request.game_id else None
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id is required")
        
        # Validate matchups
        is_valid, error_message = validate_man_defense_matchups(request.matchups)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid matchups: {error_message}")
        
        # Get game from memory or database
        gm = ongoing_games.get(game_id)
        if gm is None:
            # Try to load from database
            game_doc = games_collection.find_one({"_id": ObjectId(game_id)})
            if not game_doc:
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
            # Game exists in DB but not in memory - this is OK, we'll save to DB
            # Matchups will be loaded when game is next accessed
            games_collection.update_one(
                {"_id": ObjectId(game_id)},
                {"$set": {"man_defense_matchups": request.matchups}}
            )
            logging.info(f"✅ Saved man defense matchups to DB for game {game_id}")
        else:
            # Game is in memory - update game_state
            gm.game_state["man_defense_matchups"] = request.matchups.copy()
            logging.info(f"✅ Saved man defense matchups to in-memory game {game_id}")
            
            # Also save to database for persistence
            try:
                from BackEnd.utils.shared import summarize_game_state
                db_summary = summarize_game_state(gm, exclude_animations=True)
                games_collection.update_one({"_id": ObjectId(game_id)}, {"$set": db_summary}, upsert=True)
            except Exception as e:
                logging.error(f"⚠️ Failed to save matchups to DB: {e}")
                # Don't fail the request if DB save fails - matchups are in memory
        
        return JSONResponse(
            content={
                "message": "Man defense matchups saved successfully",
                "matchups": request.matchups,
            },
            status_code=200,
        )
    
    
    @app.get("/api/game/{game_id}/lineup-for-matchups")
    def get_lineup_for_matchups(game_id: str):
        """
        Get lineup data for both teams with player stats and attributes for the matchups popup.
        
        Returns:
            Dict with user_team and computer_team lineups, each containing:
            - players: List of players with position, name, headshot, attributes, stats
            - team_name: Team name
        """
        from BackEnd.utils.game_id_utils import normalize_game_id
        
        game_id = normalize_game_id(game_id) if game_id else None
        if not game_id:
            raise HTTPException(status_code=400, detail="game_id is required")
        
        # Get game from memory or database
        gm = ongoing_games.get(game_id)
        if gm is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        # Determine user team side
        user_team_side = gm.game_state.get("user_team_side")
        if not user_team_side:
            raise HTTPException(status_code=400, detail="Cannot determine user team side")
        
        user_team = gm.home_team if user_team_side == "home" else gm.away_team
        computer_team = gm.away_team if user_team_side == "home" else gm.home_team
        
        # Get current matchups (defaults if not set)
        matchups = gm.game_state.get("man_defense_matchups", {
            "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C"
        })
        
        def build_player_data(team, position):
            """Build player data for a specific position"""
            player = team.lineup.get(position)
            if not player:
                return None
            
            # Get attributes
            attrs = player.attributes
            # Get game stats
            stats = player.stats.get("game", {})
            
            # Calculate DEF% (defensive win percentage)
            def_a = stats.get("DEF_A", 0)
            def_s = stats.get("DEF_S", 0)
            def_pct = round((def_s / def_a * 100)) if def_a > 0 else 0
            
            # Get NG as percentage (always use current NG, not anchor)
            ng = attrs.get("NG", 1.0)
            ng_percent = round(ng * 100)
            
            # ✅ ANCHOR VALUES: Use anchor_ prefixed attributes (base values, independent of NG effects)
            # Fallback to current values if anchor not available
            from BackEnd.utils.shared import format_height
            return {
                "player_id": player.player_id,
                "position": position,
                "name": player.name,
                "height": format_height(getattr(player, "height", None)),
                "weight": getattr(player, "weight", None) or "--",
                "headshot_url": f"/images/players/{player.player_id}.png",
                "attributes": {
                    "ID": attrs.get("anchor_ID", attrs.get("ID", 0)),
                    "OD": attrs.get("anchor_OD", attrs.get("OD", 0)),
                    "AG": attrs.get("anchor_AG", attrs.get("AG", 0)),
                    "ST": attrs.get("anchor_ST", attrs.get("ST", 0)),
                    "ND": attrs.get("anchor_ND", attrs.get("ND", 0)),
                    "IQ": attrs.get("anchor_IQ", attrs.get("IQ", 0)),
                    "NG": ng_percent,  # NG is always current (energy level)
                    "DEF%": def_pct  # User team only
                },
                "stats": {
                    "SC": attrs.get("anchor_SC", attrs.get("SC", 0)),  # Computer team only
                    "SH": attrs.get("anchor_SH", attrs.get("SH", 0)),  # Computer team only
                    "AG": attrs.get("anchor_AG", attrs.get("AG", 0)),
                    "ST": attrs.get("anchor_ST", attrs.get("ST", 0)),
                    "ND": attrs.get("anchor_ND", attrs.get("ND", 0)),
                    "IQ": attrs.get("anchor_IQ", attrs.get("IQ", 0)),
                    "NG": ng_percent,  # NG is always current (energy level)
                    "PTS": stats.get("PTS", 0)  # Computer team only
                }
            }
        
        # Build user team lineup
        user_players = []
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            player_data = build_player_data(user_team, pos)
            if player_data:
                user_players.append(player_data)
        
        # Build computer team lineup
        computer_players = []
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            player_data = build_player_data(computer_team, pos)
            if player_data:
                # Determine which user position is guarding this computer position
                # Reverse lookup: find user_pos where matchups[user_pos] == computer_pos
                guarding_user_pos = None
                for user_pos, guarded_pos in matchups.items():
                    if guarded_pos == pos:
                        guarding_user_pos = user_pos
                        break
                
                player_data["guarding_user_position"] = guarding_user_pos or pos  # Fallback to same position
                computer_players.append(player_data)
        
        return {
            "user_team": {
                "team_name": user_team.name,
                "players": user_players,
                "primary_color": getattr(user_team, "primary_color", "#000000"),
                "secondary_color": getattr(user_team, "secondary_color", "#ffffff")
            },
            "computer_team": {
                "team_name": computer_team.name,
                "players": computer_players,
                "primary_color": getattr(computer_team, "primary_color", "#000000"),
                "secondary_color": getattr(computer_team, "secondary_color", "#ffffff")
            },
            "current_matchups": matchups
        }
    
    
    @app.get("/roster/{team_identifier}")
    def get_team_roster(team_identifier: str, team_id: str | None = None, tournament_id: str | None = None, franchise_id: str | None = None, response: Response = None, profile: bool = False):
        if profile:
            from BackEnd.utils.profiling import run_profiled
            _out = [None]
            def _wrapped():
                _out[0] = get_team_roster(team_identifier, team_id, tournament_id, franchise_id, response, profile=False)
            profile_summary = run_profiled(_wrapped, top_n=60)
            result = _out[0]
            result["profile_summary"] = profile_summary
            return result
        endpoint_start = time.time()
        # ✅ FIX: Add cache-busting headers to ensure browser fetches fresh player data
        # This ensures updated player attributes (year, jersey, height, etc.) show up immediately
        if response:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        # ✅ SS&S: Prefer team_id query parameter, fallback to team_identifier path parameter
        # team_identifier can be either team_id string, ObjectId, or team_name (for backward compatibility)
        lookup_value = team_id if team_id else team_identifier
        
        # ✅ SS&S: Try multiple lookup strategies in order of preference
        team_doc = None
        query_start = time.time()
        
        # Strategy 1: Try team_id string lookup first (SS&S preferred)
        team_doc = teams_collection.find_one({"team_id": lookup_value})
        
        # Strategy 2: If not found and looks like ObjectId, try ObjectId lookup and get team_id string
        if not team_doc and len(lookup_value) == 24 and all(c in '0123456789abcdefABCDEF' for c in lookup_value):
            try:
                from bson import ObjectId
                obj_id = ObjectId(lookup_value)
                team_doc = teams_collection.find_one({"_id": obj_id})
                if team_doc:
                    # Get team_id string from the document for future lookups
                    lookup_value = team_doc.get("team_id", lookup_value)
            except Exception:
                pass
        
        # Strategy 3: If not found, try team_name lookup (backward compatibility)
        if not team_doc:
            normalized_name = unidecode(lookup_value.strip().replace("-", " ")).lower()
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
            team_result = list(teams_collection.aggregate(pipeline))
            team_doc = team_result[0] if team_result else None
        
        query_time = (time.time() - query_start) * 1000
        
        if not team_doc:
            print(f"❌ No team found matching: {lookup_value}")
            raise HTTPException(status_code=404, detail=f"No players found for team '{lookup_value}'")
        
        match = team_doc.get("name")
        
        if not match:
            print(f"❌ Team document found but has no 'name' field: {lookup_value}")
            raise HTTPException(status_code=404, detail=f"Team document missing name field for '{lookup_value}'")
    
        load_start = time.time()
        # ✅ DEBUG: Determine mode from query parameters
        actual_mode = "single"
        if franchise_id:
            actual_mode = "franchise"
        elif tournament_id:
            actual_mode = "tournament"
        # ✅ DEBUG: Log franchise_id being passed to load_roster()
        # logging.warning(f"🔍 [BOX-SCORE ROSTER DEBUG] /roster/{team_identifier} - franchise_id={franchise_id}, tournament_id={tournament_id}, team_name={match}, mode={actual_mode}")
        # ✅ FIX: Pass franchise_id to load_roster() so it loads trained attributes from franchise.players
        # This ensures Roster tab displays trained values (e.g., SH in 90s) instead of universal collection values (e.g., SH in 80s)
        team_doc, player_objects = load_roster(match, franchise_id=franchise_id)
        load_time = (time.time() - load_start) * 1000
        # ✅ DEBUG: Log what load_roster() returned
        if player_objects:
            sample_player = player_objects[0]
            sample_attrs = sample_player.get("attributes", {})
            sample_sh = sample_attrs.get("SH", "MISSING")
            sample_anchor_sh = sample_attrs.get("anchor_SH", "MISSING")
            sample_id = str(sample_player.get("_id", "NO_ID"))
            # logging.warning(f"🔍 [BOX-SCORE ROSTER DEBUG] load_roster() returned {len(player_objects)} players. Sample player: _id={sample_id}, SH={sample_sh}, anchor_SH={sample_anchor_sh}")
        else:
            # logging.error(f"❌ [BOX-SCORE ROSTER DEBUG] load_roster() returned NO players for team={match}, franchise_id={franchise_id}!")
            pass
    
        if not player_objects:
            print(f"❌ No players found for {match}")
            raise HTTPException(status_code=404, detail=f"No players found for team '{match}'")
    
        team = team_doc or {"name": match}
    
        display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]
    
        process_start = time.time()
        players = []
        for p in player_objects:
            player_id_str = str(p.get("_id"))
            player_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            
            # ✅ SS&S: Trust load_roster() - it already loaded franchise attributes if franchise_id was provided
            # No need to re-check or re-merge - load_roster() handles franchise mode correctly
            merged_attributes = p.get("attributes", {}).copy()
            
            # ✅ DEBUG: Log attributes for first player (or specific player if Kevin Nelson)
            if len(players) == 0 or "Nelson" in player_name:
                sh_val = merged_attributes.get("SH", "MISSING")
                anchor_sh_val = merged_attributes.get("anchor_SH", "MISSING")
                # logging.warning(f"🔍 [ROSTER DEBUG] Processing player {player_name} ({player_id_str}): SH={sh_val}, anchor_SH={anchor_sh_val}")
            
            # Ensure anchor_ versions exist (they should after initialization, but be safe)
            for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
                if attr_key in merged_attributes and f"anchor_{attr_key}" not in merged_attributes:
                    merged_attributes[f"anchor_{attr_key}"] = merged_attributes[attr_key]
            
            # Use position_ratings from player_objects (already loaded from franchise if franchise_id provided)
            position_ratings = p.get("position_ratings", {})
            
            final_attrs = merged_attributes.copy()
            players.append({
                "_id": player_id_str,
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "name": player_name,
                "year": p.get("year"),
                "height": p.get("height"),
                "weight": p.get("weight"),
                "jersey": p.get("jersey", 0),
                "position_ratings": position_ratings,
                "attributes": final_attrs,  # Return merged attributes (franchise overrides core)
            })
            
            # ✅ DEBUG: Log final attributes for first player (or Kevin Nelson)
            if len(players) == 1 or "Nelson" in player_name:
                final_sh = final_attrs.get("SH", "MISSING")
                final_anchor_sh = final_attrs.get("anchor_SH", "MISSING")
                # logging.warning(f"🔍 [ROSTER DEBUG] Final response for {player_name}: SH={final_sh}, anchor_SH={final_anchor_sh}")
        process_time = (time.time() - process_start) * 1000
    
        response_data = {
            "team": team.get("name", match if match else team_identifier),
            "team_name": team.get("name", match if match else team_identifier),
            "players": players
        }
        
        # ✅ DEBUG: Log response details for box score debugging
        if franchise_id:
            sample_player_ids = [str(p.get("_id", "NO_ID")) for p in players[:3]]
            # logging.warning(f"🔍 [BOX-SCORE ROSTER DEBUG] /roster/{team_identifier} response: {len(players)} players. Sample IDs: {sample_player_ids}")
        
        # Measure response size
        response_size = len(json.dumps(response_data))
        total_time = (time.time() - endpoint_start) * 1000
        # logging.warning(f"⏱️ [PERF] /roster/{team_identifier} - DB query: {query_time:.2f}ms, load_roster: {load_time:.2f}ms, processing: {process_time:.2f}ms, response_size: {response_size} bytes, total: {total_time:.2f}ms")
        
        return response_data
    
    
    @app.post("/api/init-game")
    def init_game(request: dict, profile: bool = False):
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
        user_team_side = request.get("user_team_side")  # "home" or "away"
        
        if not home_team or not away_team:
            raise HTTPException(status_code=400, detail="home_team and away_team required")
        
        # ✅ SS&S: Load playbook_settings for single mode only (franchise/tournament mode loads from their documents during gameplay)
        # For franchise/tournament mode, _load_playbook_settings() loads directly from franchise/tournament documents
        # For single mode, we need to store them in the game document since that's where they're accessed from
        settings_start = time.time()
        home_playbook_settings = {}
        away_playbook_settings = {}
        
        # Only load playbook_settings for single mode (they'll be stored in game document)
        # For franchise/tournament mode, settings are accessed directly from franchise/tournament documents
        if mode == "single":
            # For single mode, playbook_settings may be loaded from teams collection or game document
            # They'll be stored in the game document below for persistence
            pass
        settings_time = (time.time() - settings_start) * 1000
        
        # Generate game_id
        game_id = generate_game_id()
        
        # Create GameManager (this initializes teams and players)
        gm_start = time.time()
        profile_summary = None
        if profile:
            from BackEnd.utils.profiling import run_profiled
            _gm_ref = [None]
            def _create_gm():
                _gm_ref[0] = GameManager(
                    home_team, away_team, mode=mode, user_team_side=user_team_side,
                    franchise_id=franchise_id if mode == "franchise" else None,
                )
            profile_summary = run_profiled(_create_gm)
            gm = _gm_ref[0]
        else:
            gm = GameManager(home_team, away_team, mode=mode, user_team_side=user_team_side, franchise_id=franchise_id if mode == "franchise" else None)  # ✅ FRANCHISE MODE: Pass franchise_id for loading trained attributes
        # ✅ CRITICAL: Set game_id on GameManager immediately after creation
        gm.game_id = game_id
        gm_create_time = (time.time() - gm_start) * 1000
        
        # ✅ CRITICAL: Store user_team_side in game_state for persistence
        # This ensures is_user_team flags persist across game loads
        if user_team_side:
            gm.game_state["user_team_side"] = user_team_side
            logging.warning(f"✅ [INIT-GAME] Set user_team_side in game_state: {user_team_side}")
        else:
            logging.warning(f"⚠️ [INIT-GAME] No user_team_side provided - override checking will not work!")
        
        # Initialize game stats (this randomizes EM, CH, MO for all players)
        stats_start = time.time()
        _initialize_game_stats(gm, game_id=None)  # None = new game, will randomize
        stats_time = (time.time() - stats_start) * 1000
        # logging.warning(f"⏱️ [PERF] /api/init-game - Game stats initialized: {stats_time:.2f}ms")
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
        
        # ✅ CRITICAL: Store user_team_side in game document for persistence
        # This ensures is_user_team flags are correctly set when game is loaded from DB
        if user_team_side:
            summary["user_team_side"] = user_team_side
            logging.warning(f"✅ [INIT-GAME] Stored user_team_side in game document: {user_team_side}")
        
        # ✅ PHASE 5.7: Store settings in game document for all modes
        # For single mode: Settings may be loaded from teams collection or come from previous saves
        # For franchise/tournament mode: Copy master settings from franchise/tournament doc to game doc as baseline
        if "teams" not in summary:
            summary["teams"] = {}
        
        home_team_id = gm.home_team.team_id
        away_team_id = gm.away_team.team_id
        
        if home_team_id not in summary["teams"]:
            summary["teams"][home_team_id] = {}
        if away_team_id not in summary["teams"]:
            summary["teams"][away_team_id] = {}
        
        if mode == "single":
            # For single mode, playbook_settings are stored in game document for persistence
            # They may be loaded from teams collection or come from previous saves
            summary["teams"][home_team_id]["playbook_settings"] = home_playbook_settings
            summary["teams"][away_team_id]["playbook_settings"] = away_playbook_settings
            # ✅ FIX: Always set playbook_settings on GameManager (even if empty) to prevent DB fallbacks during gameplay
            gm.home_team.playbook_settings = dict(home_playbook_settings) if home_playbook_settings else {}
            gm.away_team.playbook_settings = dict(away_playbook_settings) if away_playbook_settings else {}
        elif mode == "franchise" and franchise_id:
            # ✅ FTD: Copy master settings from FTD to game doc as baseline
            from BackEnd.api.franchise_routes import get_user_team_from_franchise
            from BackEnd.db import franchises_collection, franchise_team_data_collection
            
            try:
                # Get user team info from franchise doc
                franchise_doc = franchises_collection.find_one(
                    {"_id": ObjectId(franchise_id)},
                    {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
                if franchise_doc:
                    user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
                    if user_team_object_id:
                        # Load FTD for user team
                        user_ftd = franchise_team_data_collection.find_one(
                            {"franchise_id": ObjectId(franchise_id), "team_id": user_team_object_id},
                            {"playbook_settings": 1, "strategy_settings": 1}
                        )
                        
                        if user_ftd:
                            # Copy master settings to game doc for user team
                            master_playbook = user_ftd.get("playbook_settings", {})
                            master_strategy = user_ftd.get("strategy_settings", {})
                            
                            # Determine which team is the user team
                            user_team_id_in_game = None
                            if user_team_side == "home" or (not user_team_side and home_team == user_team_name):
                                user_team_id_in_game = home_team_id
                            elif user_team_side == "away" or (not user_team_side and away_team == user_team_name):
                                user_team_id_in_game = away_team_id
                            
                            if user_team_id_in_game:
                                if master_playbook:
                                    summary["teams"][user_team_id_in_game]["playbook_settings"] = master_playbook.copy()
                                    logging.warning(f"✅ [FTD] Copied playbook_settings from FTD to game doc for team {user_team_id_in_game}")
                                    # ✅ FIX: Apply to GameManager so settings are available during gameplay (prevents 37 DB lookups per quarter)
                                    if user_team_id_in_game == home_team_id:
                                        gm.home_team.playbook_settings = dict(master_playbook) if master_playbook else {}
                                    elif user_team_id_in_game == away_team_id:
                                        gm.away_team.playbook_settings = dict(master_playbook) if master_playbook else {}
                                if master_strategy:
                                    summary["teams"][user_team_id_in_game]["strategy_settings"] = master_strategy.copy()
                                    logging.warning(f"✅ [FTD] Copied strategy_settings from FTD to game doc for team {user_team_id_in_game}")
                                    # ✅ FIX: Apply to GameManager so settings are available during gameplay
                                    if user_team_id_in_game == home_team_id:
                                        gm.home_team.strategy_settings = dict(master_strategy) if master_strategy else {}
                                    elif user_team_id_in_game == away_team_id:
                                        gm.away_team.strategy_settings = dict(master_strategy) if master_strategy else {}
            except Exception as e:
                logging.warning(f"⚠️ [FTD] Error copying settings from FTD: {e}")
                import traceback
                traceback.print_exc()
        elif mode == "tournament" and tournament_id:
            # ✅ PHASE 5.7: Copy master settings from tournament doc to game doc as baseline
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            from BackEnd.db import tournaments_collection
            
            try:
                tournament_doc = tournaments_collection.find_one(
                    {"_id": ObjectId(tournament_id)},
                    {"teams": 1, "user_team_id": 1, "user_team_object_id": 1, "_id": 1}
                )
                if tournament_doc:
                    user_team_name, user_team_object_id = get_user_team_from_tournament(tournament_doc)
                    if user_team_object_id:
                        tournament_teams = tournament_doc.get("teams", {})
                        user_team_obj = tournament_teams.get(str(user_team_object_id), {})
                        
                        # Copy master settings to game doc for user team
                        master_playbook = user_team_obj.get("playbook_settings", {})
                        master_strategy = user_team_obj.get("strategy_settings", {})
                        
                        # Determine which team is the user team
                        user_team_id_in_game = None
                        if user_team_side == "home" or (not user_team_side and home_team == user_team_name):
                            user_team_id_in_game = home_team_id
                        elif user_team_side == "away" or (not user_team_side and away_team == user_team_name):
                            user_team_id_in_game = away_team_id
                        
                        if user_team_id_in_game:
                            if master_playbook:
                                summary["teams"][user_team_id_in_game]["playbook_settings"] = master_playbook.copy()
                                logging.warning(f"✅ [PHASE 5.7] Copied playbook_settings from tournament master to game doc for team {user_team_id_in_game}")
                                # ✅ FIX: Apply to GameManager so settings are available during gameplay (prevents 37 DB lookups per quarter)
                                if user_team_id_in_game == home_team_id:
                                    gm.home_team.playbook_settings = dict(master_playbook) if master_playbook else {}
                                elif user_team_id_in_game == away_team_id:
                                    gm.away_team.playbook_settings = dict(master_playbook) if master_playbook else {}
                            if master_strategy:
                                summary["teams"][user_team_id_in_game]["strategy_settings"] = master_strategy.copy()
                                logging.warning(f"✅ [PHASE 5.7] Copied strategy_settings from tournament master to game doc for team {user_team_id_in_game}")
                                # ✅ FIX: Apply to GameManager so settings are available during gameplay
                                if user_team_id_in_game == home_team_id:
                                    gm.home_team.strategy_settings = dict(master_strategy) if master_strategy else {}
                                elif user_team_id_in_game == away_team_id:
                                    gm.away_team.strategy_settings = dict(master_strategy) if master_strategy else {}
            except Exception as e:
                logging.warning(f"⚠️ [PHASE 5.7] Error copying settings from tournament master: {e}")
        summary_time = (time.time() - summary_start) * 1000
        
        # Set GameManager quarter to 1 to match
        gm.quarter = 1
        
        # Save to database
        db_start = time.time()
        games_collection.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
        db_time = (time.time() - db_start) * 1000
        
        # Store in ongoing_games so /api/game/{game_id} can access it
        ongoing_games[game_id] = gm
        # ✅ REMOVED: Verbose debug log
        
        response_data = {"game_id": game_id}
        if profile_summary is not None:
            response_data["profile_summary"] = profile_summary
        total_time = (time.time() - endpoint_start) * 1000
        logging.warning(
            f"⏱️ [PERF] init-game total={total_time/1000:.2f}s gm_create={gm_create_time:.0f}ms summary={summary_time:.0f}ms db_save={db_time:.0f}ms"
        )
        return response_data
    
    
    @app.get("/games")
    def get_games():
        # Fetch the 10 most recent games (you can adjust this)
        games = list(games_collection.find().sort("_id", -1).limit(10))
    
        # Convert ObjectId to string for JSON serialization
        for game in games:
            game["_id"] = str(game["_id"])
    
        return JSONResponse(content=games)

    class DeleteCompletedSingleGameRequest(BaseModel):
        game_id: str

    @app.post("/api/games/delete-completed-single")
    def delete_completed_single_game(body: DeleteCompletedSingleGameRequest):
        """
        Delete a completed Single Game mode game from the database.
        Safe to call when the user has left the game (e.g. returned to mode-select).
        Only deletes if the game is single mode (no franchise_id, no tournament_id) and is_final.
        Idempotent: returns 200 if game already missing or after delete.
        """
        game_id = (body.game_id or "").strip()
        if not game_id:
            return {"ok": True, "deleted": False, "reason": "no_game_id"}
        try:
            doc_id = ObjectId(game_id)
        except Exception:
            doc_id = game_id
        game = games_collection.find_one({"_id": doc_id})
        if not game:
            return {"ok": True, "deleted": False, "reason": "not_found"}
        if game.get("franchise_id") or game.get("tournament_id"):
            raise HTTPException(
                status_code=400,
                detail="Game is not a single game (has franchise_id or tournament_id)",
            )
        if not game.get("is_final"):
            raise HTTPException(
                status_code=400,
                detail="Game is not completed (is_final is not true)",
            )
        games_collection.delete_one({"_id": doc_id})
        return {"ok": True, "deleted": True}

    @app.get("/player/{player_id}")
    def get_player(
        player_id: str,
        mode: Optional[str] = None,
        franchise_id: Optional[str] = None,
        tournament_id: Optional[str] = None,  # reserved for future mode-aware overlays
        game_id: Optional[str] = None,        # reserved for future mode-aware overlays
    ):
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
            # Franchise mode: overlay per-franchise player progression if available.
            # Keep default behavior unchanged for all other modes/contexts.
            if mode == "franchise" and franchise_id:
                fpd_doc = franchise_players_data_collection.find_one(
                    {"franchise_id": str(franchise_id), "player_id": str(player_id)},
                    {"attributes": 1, "position_ratings": 1, "meta": 1},
                )
                if fpd_doc:
                    if isinstance(fpd_doc.get("attributes"), dict):
                        player["attributes"] = fpd_doc["attributes"]
                    if isinstance(fpd_doc.get("position_ratings"), dict):
                        player["position_ratings"] = fpd_doc["position_ratings"]
                    if isinstance(fpd_doc.get("meta"), dict):
                        for key in ("year", "height", "weight", "jersey", "team"):
                            if key in fpd_doc["meta"]:
                                player[key] = fpd_doc["meta"][key]

            # Debug logging removed - was cluttering logs
            # logging.debug(f"✅ Player found: {player.get('first_name')} {player.get('last_name')}")
            player["_id"] = str(player["_id"])  # ensure JSON serializable
            return player
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error in get_player: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    
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
            raise HTTPException(status_code=500, detail="Internal server error")
    
    
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
    **Quarter:** {getattr(request, 'quarter', 'N/A')}  
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
            raise HTTPException(status_code=500, detail="Internal server error")
except Exception as e:
    _startup_error = e
    traceback.print_exc(file=sys.stderr)
    @app.get("/startup-error")
    def _startup_error_route():
        return {"status": "error", "error": str(e), "type": type(e).__name__}
