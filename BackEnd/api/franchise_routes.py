from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
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
from BackEnd.models.franchise_manager import FranchiseManager

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
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    team_name = state.get("team")
    if team_name:
        team_doc = db.teams.find_one({"name": team_name})
        if team_doc:
            return (team_name, str(team_doc["_id"]))
    
    return (None, None)

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


def _save_game_result(team1_id, team2_id, team1_score, team2_score, week, franchise_id=None):
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

@router.post("/franchise/select-team")
def select_team(selection: TeamSelection):
    # Resolve team name to ObjectId
    team_doc = db.teams.find_one({"name": selection.team_name})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user_team_id = selection.team_name  # Team name (human-readable)
    user_team_object_id = str(team_doc["_id"])  # ObjectId string (database identifier)
    
    # Keep state collection for backward compatibility (will be phased out)
    franchise_state_collection.delete_many({})
    franchise_state_collection.insert_one({"_id": "state", "team": selection.team_name})
    
    manager = FranchiseManager(db)
    manager.initialize_season(user_team_id=user_team_id, user_team_object_id=user_team_object_id)
    return {"status": "ok", "franchise_id": str(manager.franchise_id)}

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

    matchup = None
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
    user_res = _save_game_result(team1_id, team2_id, user.team1_score, user.team2_score, req.week, franchise_id=req.franchise_id)
    results.append({
        "away_id": user_res["team1_id"],
        "home_id": user_res["team2_id"],
        "away_score": user_res["team1_score"],
        "home_score": user_res["team2_score"],
    })
    
    # ✅ SS&S: Find user's game and call finalize_game() to rollup stats to franchise document
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
        if user_game_id:
            stat_updater.finalize_game(
                user_game_id, mode="franchise", franchise_id=req.franchise_id
            )

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
            token = f"{req.week}-{away_id}-{home_id}"
            summary["_id"] = token
            summary["franchise_id"] = str(req.franchise_id)
            summary["week"] = req.week
            db.games.update_one({"_id": token}, {"$set": summary}, upsert=True)
            stat_updater.finalize_game(
                token, mode="franchise", franchise_id=req.franchise_id
            )
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
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {
            "results": existing_results, 
            "week": next_week,
            "training_status.current_week": next_week,
            "training_status.training_completed": False,
            "training_status.session_type": "in-season"
        }},
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
    # Get user team info from franchise document (with backward compatibility)
    team_name = None
    team_id = None
    training_completed = False
    session_type = "in-season"
    
    if franchise_id:
        try:
            fid = ObjectId(franchise_id)
            franchise_doc = db.franchises.find_one({"_id": fid})
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
                    franchise_team_stats = franchise_teams.get(team_id, {})
                    if franchise_team_stats:
                        team_doc = franchise_team_stats  # Use franchise-specific stats
                    else:
                        # Fallback to universal team doc
                        team_doc = db.teams.find_one({"_id": ObjectId(team_id)}) or {}
                else:
                    team_doc = {}
        except Exception:
            team_doc = {}
    else:
        # Fallback to state collection if no franchise_id (backward compatibility)
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team", "")
        team_doc = db.teams.find_one({"name": team_name}) or {}
        team_id = str(team_doc.get("_id", "")) if team_doc.get("_id") else None
    
    # Get username and seed from state (backward compatibility)
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    
    return {
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
        "session_type": session_type
    }


@router.get("/franchise/standings")
def standings(franchise_id: str):
    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    found = franchise_doc is not None
    logger.info("standings franchise_id=%s found=%s", franchise_id, found)
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    schedule = franchise_doc.get("schedule", [])
    week = franchise_doc.get("week", 1)
    next_games = schedule[week - 1] if week - 1 < len(schedule) else []
    id_to_name = {t["_id"]: t["name"] for t in db.teams.find({}, {"name": 1})}

    matchup_map = {}
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
            "next": matchup_map.get(t["_id"], "")
        })

    output.sort(key=lambda x: (x["W"], x["differential"]), reverse=True)
    logger.info("standings returning franchise_id=%s found=%s", franchise_id, found)
    return {"standings": output}


@router.get("/franchise/schedule")
def season_schedule(franchise_id: str):
    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
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

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    doc = db.franchises.find_one({"_id": fid}, {"players": 1}) or {}
    players = doc.get("players", {}) or {}

    if len(players) <= 500:
        rows: list[dict[str, Any]] = []
        for pid, pdata in players.items():
            meta = pdata.get("meta", {})
            # ✅ SS&S: Read stats directly from players.{pid}.season.{stat} (no totals wrapper)
            block = pdata.get(scope, {}) or {}
            value = block.get(stat, 0)
            rows.append(
                {
                    "player_id": pid,
                    "first_name": meta.get("first_name", ""),
                    "last_name": meta.get("last_name", ""),
                    "team": meta.get("team", meta.get("team_id", "")),
                    "value": value,
                }
            )

        rows.sort(key=lambda r: r["value"], reverse=True)
        return rows[:limit]

    # ✅ SS&S: Read stats directly from players.{pid}.season.{stat} (no totals wrapper)
    pipeline = [
        {"$match": {"_id": fid}},
        {"$project": {"players": {"$objectToArray": "$players"}}},
        {"$unwind": "$players"},
        {
            "$project": {
                "player_id": "$players.k",
                "meta": "$players.v.meta",
                "value": f"$players.v.{scope}.{stat}",  # Direct stat access, no totals wrapper
            }
        },
        {"$sort": {"value": -1}},
        {"$limit": limit},
    ]

    agg = list(db.franchises.aggregate(pipeline))
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

    return results


@router.get("/franchise/leaders")
def leaders(
    franchise_id: str,
    scope: str = "season",
    limit: int = 10,
):
    categories = ["PTS", "AST", "TPM", "REB", "BLK", "STL"]
    result: dict[str, list[dict[str, Any]]] = {}
    for cat in categories:
        top = get_leaders(franchise_id, scope=scope, stat=cat, limit=limit)
        result[cat] = [
            {
                "player_id": p.get("player_id"),
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "team": p.get("team"),
                "value": p.get("value", 0),
            }
            for p in top
        ]
    return result


@router.get("/franchise/team-stats")
def team_stats(franchise_id: str):
    """Get team stats by aggregating player stats from franchise document.
    
    ✅ SS&S: Aggregates from franchise.players object (franchise-specific stats),
    not from universal players_collection.
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id")
    
    franchise_doc = db.franchises.find_one({"_id": fid}, {"players": 1, "franchise_teams": 1})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    players = franchise_doc.get("players", {})
    franchise_teams = franchise_doc.get("franchise_teams", {})
    
    # Get all team IDs from franchise_teams
    team_stats_map: Dict[str, Dict[str, int]] = {}
    
    # Initialize team stats for all teams in franchise
    # ✅ SS&S: Normalize team_id keys to strings for consistent comparison
    for team_id in franchise_teams.keys():
        team_id_str = str(team_id)
        team_stats_map[team_id_str] = {
            "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
            "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
            "TO": 0, "F": 0
        }
    
    # Aggregate stats from players object
    for pid, pdata in players.items():
        meta = pdata.get("meta", {})
        team_id = meta.get("team_id")
        if not team_id:
            continue
        
        # ✅ SS&S: Normalize team_id to string for consistent comparison
        team_id_str = str(team_id)
        
        season_stats = pdata.get("season", {})
        if team_id_str not in team_stats_map:
            team_stats_map[team_id_str] = {
                "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
                "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
                "TO": 0, "F": 0
            }
        
        # Sum all stats for this team
        for stat, val in season_stats.items():
            if isinstance(val, (int, float)) and stat in team_stats_map[team_id_str]:
                team_stats_map[team_id_str][stat] += val
    
    # Convert to output format with team names
    output = []
    for team_id_str, stats in team_stats_map.items():
        # Get team name from teams collection
        try:
            team_doc = db.teams.find_one({"_id": ObjectId(team_id_str)}, {"name": 1})
            team_name = team_doc.get("name", team_id_str) if team_doc else team_id_str
        except Exception:
            # Fallback if team_id_str is not a valid ObjectId
            team_name = team_id_str
        output.append({"team": team_name, "stats": stats})
    
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
    from bson import ObjectId
    
    # Get recruits from franchise document
    franchise = db.franchises.find_one(
        {"_id": ObjectId(franchise_id)}, 
        {"recruits": 1}
    )
    
    if not franchise:
        return {"recruits": []}
    
    recs = franchise.get("recruits", [])
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
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    franchise_doc = db.franchises.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Convert ObjectId to string for JSON serialization
    franchise_doc["_id"] = str(franchise_doc["_id"])
    
    return jsonable_encoder(franchise_doc, custom_encoder={ObjectId: str})


@router.get("/franchise/team-data")
def get_franchise_team_data(franchise_id: str, team_id: str = None, team_name: str = None):
    """
    Get team data (attributes, plays, scouting_data) from franchise_teams.
    
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
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
        franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
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
    
    # Get franchise document
    franchise_doc = db.franchises.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get team object from franchise_teams
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_obj = franchise_teams.get(actual_team_id, {})
    
    if not team_obj:
        raise HTTPException(status_code=404, detail=f"Team data not found in franchise for team_id: {actual_team_id}")
    
    # Extract team attributes
    team_attributes = {}
    attr_keys = ['shot_threshold', 'turnover_modifier', 'foul_modifier', 'rebound_modifier', 
                 'momentum_score', 'offensive_efficiency', 'team_chemistry', 'defensive_efficiency',
                 'fb_efficiency', 'pt_efficiency', 'fb_opp_modifier', 'pt_opp_modifier']
    for key in attr_keys:
        if key in team_obj:
            team_attributes[key] = team_obj[key]
        else:
            team_attributes[key] = 0  # Default to 0 if not present
    
    # Get plays data
    plays_data = team_obj.get("plays", {})
    
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
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # Get team name from franchise document if not provided (with backward compatibility)
    if not team_name:
        franchise_doc = db.franchises.find_one({"_id": fid})
        if franchise_doc:
            user_team_id, _ = get_user_team_from_franchise(franchise_doc)
            team_name = user_team_id
    
    if not team_name:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team document
    team_doc = db.teams.find_one({"name": team_name})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get franchise document
    franchise_doc = db.franchises.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    franchise_players = franchise_doc.get("players", {})
    team_player_ids = team_doc.get("player_ids", [])
    
    # Build player list with franchise-specific attributes
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
    
    return {"players": players}


class FranchiseTrainingRequest(BaseModel):
    franchise_id: str
    team_id: Optional[str] = None
    training_data: dict  # Contains player_drills, team_drills, general, coaching_focus


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
    if training_status.get("training_completed", False) and training_status.get("week") == current_week:
        # Training already completed for this week, redirect to report
        # ✅ SS&S: Use user_team_object_id from franchise document for redirect (authoritative)
        user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        redirect_team_id = user_team_object_id if user_team_object_id else req.team_id
        return {
            "status": "already_completed",
            "week": current_week,
            "redirect": f"/static/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={redirect_team_id}&week={current_week}"
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
    playcall_settings = team_data.get("playcall_settings", {})
    strategy_settings = team_data.get("strategy_settings", {})
    playbook_settings = team_data.get("playbook_settings", {})
    scouting_data = team_data.get("scouting_data", {})
    
    # Initialize plays_data if empty (first time training for this team)
    if not plays_data:
        logger.warning(f"📚 [API] plays_data is empty, populating from universal plays collection")
        from BackEnd.api.gameplan_routes import populate_team_plays
        plays_data = populate_team_plays(mode="franchise")
        # Save to database
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {f"franchise_teams.{team_id}.plays": plays_data}}
        )
    
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
        playcall_settings=playcall_settings,
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
    
    # Update plays data
    if updated_plays:
        franchise_update[f"franchise_teams.{team_id}.plays"] = updated_plays
    
    # Update scouting_data (defenses)
    if updated_scouting_data:
        franchise_update[f"franchise_teams.{team_id}.scouting_data"] = updated_scouting_data

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

    # Save to franchise document
    db.franchises.update_one({"_id": franchise_id}, {"$set": franchise_update})
    
    return {
        "status": "success",
        "week": current_week,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "session_type": session_type,
        "redirect": f"/static/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={team_id}&week={current_week}"
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
            if round is not None:
                week = round  # Use round parameter if provided (for historical reports)
            elif week is not None:
                week = week  # Use week parameter if provided (backward compatibility)
            else:
                # SS&S: Determine round from backend state (training_status or latest_training)
                from BackEnd.db import tournaments_collection
                doc_id_obj = ObjectId(doc_id)
                doc = tournaments_collection.find_one({"_id": doc_id_obj})
                if not doc:
                    raise HTTPException(status_code=404, detail="Tournament not found")
                
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
                "rebound_modifier": team_data.get("rebound_modifier", 1.0),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "foul_modifier": team_data.get("foul_modifier", 0),
                "turnover_modifier": team_data.get("turnover_modifier", 0),
                "momentum_score": team_data.get("momentum_score", 0),
                "team_chemistry": team_data.get("team_chemistry", 7),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0)
            }
            
        else:  # tournament mode
            from BackEnd.db import tournaments_collection, teams_collection
            doc_id_obj = ObjectId(doc_id)
            doc = tournaments_collection.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            # Resolve team_id to ObjectId string (matches Franchise pattern)
            team_id_resolved = team_id
            team_doc = teams_collection.find_one({"name": team_id})
            if team_doc:
                team_id_resolved = str(team_doc["_id"])
            else:
                try:
                    team_id_obj = ObjectId(team_id)
                    team_id_resolved = str(team_id_obj)
                except:
                    pass
            
            team_id_str = str(team_id_resolved)
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
            tournament_players = doc.get("player_stats", {})
            
            # Resolve team_id - might be a name or an ID
            team_id_resolved = team_id
            team_doc = teams_collection.find_one({"name": team_id})
            if team_doc:
                team_id_resolved = str(team_doc["_id"])
            else:
                try:
                    team_id_obj = ObjectId(team_id)
                    team_id_resolved = str(team_id_obj)
                except:
                    pass
            
            team_id_str = str(team_id_resolved)
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
                "rebound_modifier": team_data.get("rebound_modifier", 1.0),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "foul_modifier": team_data.get("foul_modifier", 0),
                "turnover_modifier": team_data.get("turnover_modifier", 0),
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
