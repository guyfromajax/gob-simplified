from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.db import players_collection, teams_collection
from html import unescape

client = TestClient(app)


def _attrs():
    return {k: 1 for k in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]}


def test_height_formatted():
    players_collection.delete_many({})
    teams_collection.delete_many({})
    players_collection.insert_one(
        {
            "_id": "p1",
            "first_name": "Tall",
            "last_name": "Player",
            "team": "Lancaster",
            "height": "82",
            "weight": 200,
            "attributes": _attrs(),
        }
    )
    teams_collection.insert_one({"name": "Lancaster", "player_ids": ["p1"]})

    resp = client.get("/team-roster/Lancaster")
    assert resp.status_code == 200
    assert "6'10\"" in unescape(resp.text)
