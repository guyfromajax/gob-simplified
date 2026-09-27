"""A later user week must not keep a result when season stats do not move.

The desktop save did this: week 2 posted phase-a with the week-1 game id and a
new score. ``results`` gained a row, ``finalize_game`` returned because that id
was already claimed, and franchise_players_data season GP stayed at 1.
"""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_players_data_collection
from BackEnd.utils import stat_updater

client = TestClient(app)


def test_phase_a_reused_game_id_does_not_leave_a_result_without_stats():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})

    team_a, team_b, team_c = ObjectId(), ObjectId(), ObjectId()
    db.teams.insert_many([
        {"_id": team_a, "name": "Lancaster", "team_id": "LANCASTER"},
        {"_id": team_b, "name": "Casino Row", "team_id": "CASINO_ROW"},
        {"_id": team_c, "name": "Appalachia", "team_id": "APPALACHIA"},
    ])
    pid = "p-user-1"
    fid = db.franchises.insert_one({
        "schedule": [[(team_a, team_b)], [(team_c, team_a)]],
        "week": 1,
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_a),
        "results": {},
        "applied_games": [],
        "applied_matchups": [],
    }).inserted_id
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": pid,
        "meta": {"first_name": "Roger", "last_name": "Henrich", "team_id": str(team_a)},
        "season": {"GP": 0, "FGA": 0, "PTS": 0},
        "career": {"GP": 0, "FGA": 0, "PTS": 0},
    })

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
            "LANCASTER": {
                "name": "Lancaster",
                "box_score": {
                    "PG": {"playerId": pid, "name": "Roger Henrich", "FGA": 8, "PTS": 11},
                },
            },
            "CASINO_ROW": {"name": "Casino Row", "box_score": {}},
        },
    })
    stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(fid))
    after_first = franchise_players_data_collection.find_one(
        {"franchise_id": str(fid), "player_id": pid}
    )
    assert int((after_first.get("season") or {}).get("GP") or 0) == 1
    assert int((after_first.get("season") or {}).get("FGA") or 0) == 8

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
    assert res.status_code == 200, res.text
    franchise = db.franchises.find_one({"_id": fid})
    week2 = (franchise.get("results") or {}).get("2") or []
    assert week2, "phase-a wrote no week-2 result"
    after_second = franchise_players_data_collection.find_one(
        {"franchise_id": str(fid), "player_id": pid}
    )
    season = after_second.get("season") or {}
    assert int(season.get("GP") or 0) == 2
    assert int(season.get("FGA") or 0) > 8
