from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api.franchise_routes import get_leaders
from BackEnd.db import db, franchise_players_data_collection

client = TestClient(app)


def setup_function(_fn):
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})


def seed_franchise():
    fid = db.franchises.insert_one({}).inserted_id
    franchise_players_data_collection.insert_many(
        [
            {
                "franchise_id": str(fid),
                "player_id": "p1",
                "meta": {"first_name": "Ann", "last_name": "Alpha", "team": "A"},
                "season": {"PTS": 20},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p2",
                "meta": {"first_name": "Bob", "last_name": "Beta", "team": "B"},
                "season": {"PTS": 15},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p3",
                "meta": {"first_name": "Cara", "last_name": "Gamma", "team": "C"},
                "season": {"PTS": 5},
            },
        ]
    )
    return str(fid)


def test_get_leaders_and_endpoint():
    fid = seed_franchise()

    top = get_leaders(fid, stat="PTS", limit=2)
    assert [p["player_id"] for p in top] == ["p1", "p2"]

    resp = client.get(f"/franchise/leaders?franchise_id={fid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["PTS"][0]["name"] == "Ann Alpha"
    assert data["PTS"][0]["value"] == 20
    assert data["PTS"][1]["name"] == "Bob Beta"
