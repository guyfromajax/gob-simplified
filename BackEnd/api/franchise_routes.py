from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path

from BackEnd.db import db, franchise_state_collection
from BackEnd.models.franchise_manager import FranchiseManager

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

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

@router.post("/franchise/select-team")
def select_team(selection: TeamSelection):
    franchise_state_collection.delete_many({})
    franchise_state_collection.insert_one({"_id": "state", "team": selection.team_name})
    manager = FranchiseManager(db)
    manager.initialize_season()
    return {"status": "ok"}

@router.get("/franchise/command-center")
def command_center():
    return FileResponse(STATIC_DIR / "franchise-command-center.html")


@router.get("/animation")
def get_animation_page():
    return FileResponse(STATIC_DIR / "court.html")


@router.post("/franchise/play-next-game")
def play_next_game():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    manager = FranchiseManager(db)
    manager.schedule = state.get("schedule", [])
    manager.week = state.get("week", 1)

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
                    "away": away_doc.get("name", "")
                }
                break

    manager.run_week()

    if not matchup:
        raise HTTPException(status_code=404, detail="User matchup not found")
    return matchup


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
def standings():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    schedule = state.get("schedule", [])
    week = state.get("week", 1)

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
    return {"standings": output}


@router.get("/franchise/schedule")
def season_schedule():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    schedule = state.get("schedule", [])

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
