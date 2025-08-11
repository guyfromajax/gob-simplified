from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path
from bson import ObjectId
import logging
import random

from BackEnd.db import db, franchise_state_collection
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


def _apply_team_result(team1_id, team2_id, team1_score, team2_score, sign=1):
    db.teams.update_one({"_id": team1_id}, {"$inc": {"PF": sign * team1_score, "PA": sign * team2_score, "record.W": 0, "record.L": 0}})
    db.teams.update_one({"_id": team2_id}, {"$inc": {"PF": sign * team2_score, "PA": sign * team1_score, "record.W": 0, "record.L": 0}})
    if team1_score > team2_score:
        db.teams.update_one({"_id": team1_id}, {"$inc": {"record.W": sign}})
        db.teams.update_one({"_id": team2_id}, {"$inc": {"record.L": sign}})
    elif team2_score > team1_score:
        db.teams.update_one({"_id": team2_id}, {"$inc": {"record.W": sign}})
        db.teams.update_one({"_id": team1_id}, {"$inc": {"record.L": sign}})


def _save_game_result(team1_id, team2_id, team1_score, team2_score, week):
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

    db.games.update_one(
        filter_doc,
        {
            "$set": {
                "team1_id": team1_id,
                "team2_id": team2_id,
                "team1_score": team1_score,
                "team2_score": team2_score,
                "week": week,
            }
        },
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
                "team1_id": away_id,
                "team2_id": home_id,
                "team1_score": away_score,
                "team2_score": home_score,
                "week": week,
            }
        },
        upsert=True,
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
    results.append(_save_game_result(user.team1_id, user.team2_id, user.team1_score, user.team2_score, req.week))

    for away_id, home_id in week_games:
        if {str(away_id), str(home_id)} == {user.team1_id, user.team2_id}:
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
                "team1_id": str(existing["team1_id"]),
                "team2_id": str(existing["team2_id"]),
                "team1_score": existing["team1_score"],
                "team2_score": existing["team2_score"],
            })
            continue
        team1_score = random.randint(50, 90)
        team2_score = random.randint(50, 90)
        results.append(_save_game_result(away_id, home_id, team1_score, team2_score, req.week))

    existing_results = franchise_doc.get("results", {})
    existing_results[str(req.week)] = results
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {"results": existing_results, "week": req.week + 1}},
    )

    id_to_name = {str(t["_id"]): t.get("name", "") for t in db.teams.find({}, {"name": 1})}
    scoreboard = []
    for r in results:
        scoreboard.append({
            "team1": id_to_name.get(r["team1_id"], r["team1_id"]),
            "team2": id_to_name.get(r["team2_id"], r["team2_id"]),
            "team1_score": r["team1_score"],
            "team2_score": r["team2_score"],
        })

    return {"week": req.week, "results": scoreboard}


@router.get("/franchise/command-center/data")
def command_center_data():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    team_name = state.get("team", "")
    team_doc = db.teams.find_one({"name": team_name}) or {}
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
        "rank": team_doc.get("rank", "-")
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
    for idx, games in enumerate(schedule, start=1):
        week_games = []
        for away_id, home_id in games:
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


@router.get("/franchise/leaders")
def leaders():
    players = list(db.players.find())
    categories = ["PTS", "AST", "TPM", "REB", "BLK", "STL"]
    result = {}
    for cat in categories:
        sorted_players = sorted(
            players,
            key=lambda p: p.get("season_stats", {}).get(cat, 0),
            reverse=True
        )[:10]
        result[cat] = [
            {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "team": p.get("team"),
                "value": p.get("season_stats", {}).get(cat, 0)
            }
            for p in sorted_players
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
            for stat, val in p.get("season_stats", {}).items():
                totals[stat] = totals.get(stat, 0) + val
        output.append({"team": t["name"], "stats": totals})
    return {"teams": output}


@router.get("/franchise/recruits")
def recruits():
    recs = list(db.recruits.find({}, {"_id": 0}).limit(40))
    return {"recruits": recs}
