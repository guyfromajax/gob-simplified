from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.db import db
from bson import ObjectId

client = TestClient(app)

def setup_franchise():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    ids = [ObjectId() for _ in range(4)]
    teams = [
        {"_id": ids[0], "name": "A", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[1], "name": "B", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[2], "name": "C", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[3], "name": "D", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ]
    db.teams.insert_many(teams)
    schedule = [[(ids[0], ids[1]), (ids[2], ids[3])]]
    fid = db.franchises.insert_one({"schedule": schedule, "week": 1}).inserted_id
    return str(fid), ids

def test_complete_week_saves_and_simulates():
    franchise_id, ids = setup_franchise()
    payload = {
        "franchise_id": franchise_id,
        "week": 1,
        "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 2

    team_a = db.teams.find_one({"_id": ids[0]})
    team_b = db.teams.find_one({"_id": ids[1]})
    assert team_a["record"]["W"] == 1
    assert team_b["record"]["L"] == 1
    assert team_a["PF"] == 70
    assert team_b["PF"] == 60

    # Idempotent second call
    res2 = client.post("/franchise/complete-week", json=payload)
    assert res2.status_code == 200
    team_a2 = db.teams.find_one({"_id": ids[0]})
    assert team_a2["record"]["W"] == 1
    games = list(db.games.find({"week": 1, "$or": [{"team1_id": ids[0], "team2_id": ids[1]}, {"team1_id": ids[1], "team2_id": ids[0]}]}))
    assert len(games) == 1

    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert franchise_doc["week"] == 2
    assert "1" in franchise_doc.get("results", {})
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})

