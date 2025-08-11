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
            "year": "senior",
            "height": "82",
            "weight": 200,
            "position_ratings": {"PG": 50},
            "attributes": _attrs(),
        }
    )
    teams_collection.insert_one({"name": "Lancaster", "player_ids": ["p1"]})

    resp = client.get("/team-roster/Lancaster")
    assert resp.status_code == 200
    assert "6'10\"" in unescape(resp.text)


def test_position_and_year_and_sorting():
    players_collection.delete_many({})
    teams_collection.delete_many({})
    players_collection.insert_many(
        [
            {
                "_id": "p1",
                "first_name": "Alpha",
                "last_name": "One",
                "team": "Lancaster",
                "year": "senior",
                "height": "70",
                "weight": 180,
                "position_ratings": {"PG": 80, "SG": 75},
                "attributes": _attrs(),
            },
            {
                "_id": "p2",
                "first_name": "Beta",
                "last_name": "Two",
                "team": "Lancaster",
                "year": "junior",
                "height": "71",
                "weight": 185,
                "position_ratings": {"PG": 85, "SG": 80},
                "attributes": _attrs(),
            },
        ]
    )
    teams_collection.insert_one({"name": "Lancaster", "player_ids": ["p1", "p2"]})

    resp = client.get("/team-roster/Lancaster")
    assert resp.status_code == 200
    text = unescape(resp.text)
    assert "<th>POS</th>" in text and "<th>RT</th>" in text
    assert "SR" in text and "JR" in text
    assert text.index("Beta Two") < text.index("Alpha One")
