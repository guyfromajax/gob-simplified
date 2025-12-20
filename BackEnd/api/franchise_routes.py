from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path
from bson import ObjectId
import logging
import random
from typing import Any
from datetime import datetime
from BackEnd.main import run_simulation

from BackEnd.db import db, franchise_state_collection
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.models.franchise_manager import FranchiseManager

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

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
    franchise_state_collection.delete_many({})
    franchise_state_collection.insert_one({"_id": "state", "team": selection.team_name})
    manager = FranchiseManager(db)
    manager.initialize_season()
    return {"status": "ok", "franchise_id": str(manager.franchise_id)}

@router.get("/franchise/command-center")
def command_center():
    return FileResponse(STATIC_DIR / "franchise-command-center.html")


@router.get("/animation")
def get_animation_page():
    return FileResponse(STATIC_DIR / "court.html")


@router.post("/franchise/play-next-game")
def play_next_game(req: PlayGameRequest):
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    franchise_doc = db.franchises.find_one({"_id": ObjectId(req.franchise_id)})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    manager = FranchiseManager(db)
    manager.schedule = franchise_doc.get("schedule", [])
    manager.week = franchise_doc.get("week", 1)
    manager.franchise_id = franchise_doc.get("_id")

    user_team_name = state.get("team")
    user_team_doc = db.teams.find_one({"name": user_team_name})
    user_team_id = user_team_doc.get("_id") if user_team_doc else None

    matchup = None
    if manager.week - 1 < len(manager.schedule):
        for away_id, home_id in manager.schedule[manager.week - 1]:
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
    user_res = _save_game_result(team1_id, team2_id, user.team1_score, user.team2_score, req.week)
    results.append({
        "away_id": user_res["team1_id"],
        "home_id": user_res["team2_id"],
        "away_score": user_res["team1_score"],
        "home_score": user_res["team2_score"],
    })

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
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    team_name = state.get("team", "")
    team_doc = db.teams.find_one({"name": team_name}) or {}
    
    # Get training status from franchise if franchise_id provided
    training_completed = False
    session_type = "in-season"
    if franchise_id:
        try:
            fid = ObjectId(franchise_id)
            franchise_doc = db.franchises.find_one({"_id": fid})
            if franchise_doc:
                training_status = franchise_doc.get("training_status", {})
                training_completed = training_status.get("training_completed", False)
                session_type = training_status.get("session_type", "in-season")
                
                # Get franchise-specific team stats if available
                team_id = str(team_doc.get("_id"))
                franchise_teams = franchise_doc.get("franchise_teams", {})
                franchise_team_stats = franchise_teams.get(team_id, {})
                if franchise_team_stats:
                    team_doc = franchise_team_stats  # Use franchise-specific stats
        except Exception:
            pass
    
    return {
        "team": team_name,
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
            if res:
                away_score, home_score = res
                status = "complete"
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
            week_games.append({
                "week": idx,
                "away_team_id": str(away_id),
                "home_team_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
                "status": status
            })
        weeks.append(week_games)

    logger.info("season_schedule returning franchise_id=%s found=%s", franchise_id, found)
    return {"schedule": weeks}


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
            block = pdata.get(scope, {}) or {}
            totals = block.get("totals", block)
            value = totals.get(stat, 0)
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

    pipeline = [
        {"$match": {"_id": fid}},
        {"$project": {"players": {"$objectToArray": "$players"}}},
        {"$unwind": "$players"},
        {
            "$project": {
                "player_id": "$players.k",
                "meta": "$players.v.meta",
                "value": f"$players.v.{scope}.totals.{stat}",
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
def team_stats():
    teams = list(db.teams.find({}, {"name": 1}))
    output = []
    for t in teams:
        players = list(db.players.find({"team": t["name"]}))
        totals = {}
        for p in players:
            for stat, val in p.get("stats", {}).get("season", {}).items():
                # Handle case where val might be a list or other non-numeric type
                if isinstance(val, (int, float)):
                    totals[stat] = totals.get(stat, 0) + val
                elif isinstance(val, list) and len(val) > 0:
                    # If it's a list, try to sum the numeric values
                    numeric_vals = [v for v in val if isinstance(v, (int, float))]
                    if numeric_vals:
                        totals[stat] = totals.get(stat, 0) + sum(numeric_vals)
        output.append({"team": t["name"], "stats": totals})
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
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    team_name = state.get("team")
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


@router.get("/franchise/roster")
def get_franchise_roster(franchise_id: str, team_name: str = None):
    """
    Get roster with franchise-specific player attributes.
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # Get team name from state if not provided
    if not team_name:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
    
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
    team_id: str = None
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
        return {
            "status": "already_completed",
            "week": current_week,
            "redirect": f"/static/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={req.team_id}&week={current_week}"
        }

    # Get user's team (use team_id from request if provided, otherwise from state)
    team_id = req.team_id
    if not team_id:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if not team_name:
            raise HTTPException(status_code=404, detail="User team not found")
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        team_id = str(team_doc["_id"])
    else:
        # team_id might be a name, try to resolve it
        team_doc = db.teams.find_one({"name": team_id})
        if team_doc:
            team_id = str(team_doc["_id"])
        else:
            # Assume it's already an ID
            pass

    # Get franchise-specific player data for the user's team
    franchise_players = franchise_doc.get("players", {})
    team_player_ids = team_doc.get("player_ids", [])
    
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
            "team": team_name,
            "attributes": franchise_player_data.get("attributes", {})
        }
        players_for_training.append(player)

    if not players_for_training:
        raise HTTPException(status_code=404, detail="No players found for training")

    # Get franchise-specific team stats
    franchise_teams = franchise_doc.get("franchise_teams", {})
    team_stats = franchise_teams.get(team_id, {}).copy()

    # Extract training data
    training_data = req.training_data
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    coaching_focus = training_data.get("coaching_focus")

    # Execute new training system
    # This applies pre-training conditions, then training points, and returns training report
    from BackEnd.models.training_execution_v2 import execute_training
    
    # Execute training (applies pre-training conditions, then training points)
    updated_players, updated_team, training_report = execute_training(
        players_for_training,
        team_stats,
        allocations,
        coaching_focus
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
    player_logs = training_report.get("player_changes", {})
    team_log = training_report.get("team_changes", {})

    # Update franchise document with new attribute values and position ratings
    franchise_update = {}
    for player in players_for_training:
        pid = player["_id"]
        attrs = player.get("attributes", {})
        
        # Update all anchor attributes and base attributes
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO", "NG"]:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                franchise_update[f"players.{pid}.attributes.{anchor_key}"] = attrs[anchor_key]
                franchise_update[f"players.{pid}.attributes.{attr}"] = attrs[attr]
        
        # Update position ratings for this player
        if pid in position_ratings_updates:
            franchise_update[f"players.{pid}.position_ratings"] = position_ratings_updates[pid]

    # Update franchise team stats
    for field, value in team_stats.items():
        # Skip non-numeric fields
        if isinstance(value, dict):
            continue
        franchise_update[f"franchise_teams.{team_id}.{field}"] = value

    # Mark training as completed and update status
    session_type = training_status.get("session_type", "in-season")
    franchise_update["training_status.training_completed"] = True
    franchise_update["training_status.week"] = current_week
    franchise_update["training_status.last_training_date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Store training report data
    training_report_data = {
        "week": current_week,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
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
def get_training_report(franchise_id: str = None, tournament_id: str = None, team_id: str = None, week: int = None):
    """
    Get training report data for display on training-report.html page.
    Supports both franchise and tournament modes.
    """
    try:
        mode = "franchise" if franchise_id else "tournament"
        doc_id = franchise_id if franchise_id else tournament_id
        
        if not doc_id or not team_id or week is None:
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        if mode == "franchise":
            doc_id_obj = ObjectId(doc_id)
            doc = db.franchises.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Franchise not found")
            
            # Get team data from franchise_teams
            franchise_teams = doc.get("franchise_teams", {})
            team_data = franchise_teams.get(team_id, {})
            
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
                    if str(away_id) == team_id or str(home_id) == team_id:
                        opponent_id = str(home_id) if str(away_id) == team_id else str(away_id)
                        opponent_team = db.teams.find_one({"_id": ObjectId(opponent_id)}, {"name": 1})
                        if opponent_team:
                            upcoming_opponent = opponent_team.get("name", "")
                        break
            
            # Get current player attributes (after training)
            players = []
            roster = team_data.get("roster", [])
            for player_id in roster:
                player_data = team_data.get("players", {}).get(player_id, {})
                if player_data:
                    attrs = player_data.get("attributes", {})
                    players.append({
                        "id": player_id,
                        "name": f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".strip(),
                        "attributes": {k.replace("anchor_", ""): v for k, v in attrs.items() if k.startswith("anchor_")}
                    })
            
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
            # TODO: Implement tournament mode training report
            raise HTTPException(status_code=501, detail="Tournament mode training reports not yet implemented")
        
        if not report_data:
            raise HTTPException(status_code=404, detail="Training report not found for this week")
        
        return {
            "status": "success",
            "week": week,
            "upcoming_opponent": upcoming_opponent,
            "coaching_focus": report_data.get("coaching_focus", {}),
            "player_changes": report_data.get("player_changes", {}),
            "team_changes": report_data.get("team_changes", {}),
            "players": players,
            "team_attributes": team_attrs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching training report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
