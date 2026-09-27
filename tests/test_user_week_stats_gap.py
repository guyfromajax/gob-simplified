"""A user result is stored only when that game's box was applied once.

Reusing a previous week's game id, or posting a score with no box, must not
write ``franchises.results``. A retry of the same week and the same game is a
success and does not add a second GP.
"""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_players_data_collection
from BackEnd.utils import stat_updater

client = TestClient(app)


def _reset():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})


def _teams():
    team_a, team_b, team_c = ObjectId(), ObjectId(), ObjectId()
    db.teams.insert_many([
        {"_id": team_a, "name": "Lancaster", "team_id": "LANCASTER"},
        {"_id": team_b, "name": "Casino Row", "team_id": "CASINO_ROW"},
        {"_id": team_c, "name": "Appalachia", "team_id": "APPALACHIA"},
    ])
    return team_a, team_b, team_c


def _franchise(team_a, week, schedule):
    return db.franchises.insert_one({
        "schedule": schedule,
        "week": week,
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_a),
        "results": {},
        "applied_games": [],
        "applied_matchups": [],
    }).inserted_id


def _player(fid, pid, team_id):
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": pid,
        "meta": {"first_name": "Roger", "last_name": "Henrich", "team_id": str(team_id)},
        "season": {"GP": 0, "FGA": 0, "PTS": 0},
        "career": {"GP": 0, "FGA": 0, "PTS": 0},
    })


def _gp(fid, pid):
    doc = franchise_players_data_collection.find_one(
        {"franchise_id": str(fid), "player_id": pid}
    )
    return int(((doc or {}).get("season") or {}).get("GP") or 0)


def _box(pid, fga=8):
    return {"PG": {"playerId": pid, "name": "Roger Henrich", "FGA": fga, "PTS": 11}}


def test_reused_game_id_returns_409_and_leaves_week_one_untouched():
    _reset()
    team_a, team_b, team_c = _teams()
    fid = _franchise(team_a, 1, [[(team_a, team_b)], [(team_c, team_a)]])
    _player(fid, "p-user-1", team_a)
    game_id = str(ObjectId())
    db.games.insert_one({
        "_id": game_id,
        "week": 1,
        "quarter": 4,
        "is_final": True,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"name": "Lancaster", "box_score": _box("p-user-1")},
            "CASINO_ROW": {"name": "Casino Row", "box_score": {}},
        },
    })
    stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(fid))
    assert _gp(fid, "p-user-1") == 1

    db.franchises.update_one({"_id": fid}, {"$set": {"week": 2}})
    res = client.post("/franchise/complete-week/phase-a", json={
        "franchise_id": str(fid),
        "week": 2,
        "game_id": game_id,
        "result": {
            "team1_id": "APPALACHIA",
            "team2_id": "LANCASTER",
            "team1_score": 63,
            "team2_score": 51,
        },
    })
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["reason"] == "stale_game_id"

    franchise = db.franchises.find_one({"_id": fid})
    assert not (franchise.get("results") or {}).get("2")
    stored = db.games.find_one({"_id": game_id})
    assert stored["week"] == 1
    assert stored["home_team_id"] == "CASINO_ROW"
    assert stored["away_team_id"] == "LANCASTER"
    assert stored.get("team1_id") in (None, "CASINO_ROW", str(team_b))
    assert _gp(fid, "p-user-1") == 1


def test_missing_box_returns_409_without_claim_or_result():
    _reset()
    team_a, team_b, _team_c = _teams()
    fid = _franchise(team_a, 1, [[(team_a, team_b)]])
    _player(fid, "p-user-1", team_a)
    game_id = str(ObjectId())
    db.games.insert_one({
        "_id": game_id,
        "week": 1,
        "quarter": 1,
        "is_final": False,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "team1_score": 0,
        "team2_score": 0,
    })
    res = client.post("/franchise/complete-week/phase-a", json={
        "franchise_id": str(fid),
        "week": 1,
        "game_id": game_id,
        "result": {
            "team1_id": "CASINO_ROW",
            "team2_id": "LANCASTER",
            "team1_score": 70,
            "team2_score": 60,
        },
    })
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["reason"] == "missing_box_score"
    franchise = db.franchises.find_one({"_id": fid})
    assert not (franchise.get("results") or {}).get("1")
    assert franchise.get("applied_games") in (None, [])
    assert franchise.get("applied_matchups") in (None, [])
    assert _gp(fid, "p-user-1") == 0


def test_same_week_retry_does_not_double_count():
    _reset()
    team_a, team_b, _team_c = _teams()
    fid = _franchise(team_a, 1, [[(team_a, team_b)]])
    _player(fid, "p-user-1", team_a)
    game_id = str(ObjectId())
    db.games.insert_one({
        "_id": game_id,
        "week": 1,
        "quarter": 4,
        "is_final": True,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"name": "Lancaster", "box_score": _box("p-user-1")},
            "CASINO_ROW": {"name": "Casino Row", "box_score": {}},
        },
    })
    payload = {
        "franchise_id": str(fid),
        "week": 1,
        "game_id": game_id,
        "result": {
            "team1_id": "CASINO_ROW",
            "team2_id": "LANCASTER",
            "team1_score": 51,
            "team2_score": 63,
        },
    }
    first = client.post("/franchise/complete-week/phase-a", json=payload)
    assert first.status_code == 200, first.text
    assert _gp(fid, "p-user-1") == 1
    second = client.post("/franchise/complete-week/phase-a", json=payload)
    assert second.status_code == 200, second.text
    assert second.json().get("idempotent") is True
    franchise = db.franchises.find_one({"_id": fid})
    assert len((franchise.get("results") or {}).get("1") or []) == 1
    assert _gp(fid, "p-user-1") == 1


def test_fresh_game_increments_gp_once_for_both_teams():
    _reset()
    team_a, team_b, _team_c = _teams()
    fid = _franchise(team_a, 1, [[(team_a, team_b)]])
    _player(fid, "p-user-1", team_a)
    _player(fid, "p-cpu-1", team_b)
    game_id = str(ObjectId())
    db.games.insert_one({
        "_id": game_id,
        "week": 1,
        "quarter": 4,
        "is_final": True,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"name": "Lancaster", "box_score": _box("p-user-1", 8)},
            "CASINO_ROW": {"name": "Casino Row", "box_score": _box("p-cpu-1", 5)},
        },
    })
    res = client.post("/franchise/complete-week/phase-a", json={
        "franchise_id": str(fid),
        "week": 1,
        "game_id": game_id,
        "result": {
            "team1_id": "CASINO_ROW",
            "team2_id": "LANCASTER",
            "team1_score": 51,
            "team2_score": 63,
        },
    })
    assert res.status_code == 200, res.text
    assert _gp(fid, "p-user-1") == 1
    assert _gp(fid, "p-cpu-1") == 1
    franchise = db.franchises.find_one({"_id": fid})
    assert len((franchise.get("results") or {}).get("1") or []) == 1
    assert game_id in [str(item) for item in (franchise.get("applied_games") or [])]
