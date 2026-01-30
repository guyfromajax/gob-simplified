from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import players_collection, teams_collection, tournaments_collection


client = TestClient(app)


def setup_function(fn):
    players_collection.delete_many({})
    teams_collection.delete_many({})
    tournaments_collection.delete_many({})


def _make_team_docs():
    return [
        {"name": "Bentley-Truman"},
        {"name": "Four Corners"},
        {"name": "Lancaster"},
        {"name": "Little York"},
        {"name": "Morristown"},
        {"name": "Ocean City"},
        {"name": "South Lancaster"},
        {"name": "Xavien"},
    ]


def test_start_tournament_resets_player_stats():
    teams_collection.insert_many(_make_team_docs())
    players_collection.insert_one(
        {
            "_id": "p1",
            "team": "Lancaster",
            "first_name": "A",
            "last_name": "One",
            "stats": {
                "game": {"PTS": 5},
                "season": {"PTS": 5},
                "career": {"PTS": 10},
                "applied_games": ["old"],
            },
        }
    )

    resp = client.post("/tournament/start", json={"user_team_id": "Lancaster"})
    assert resp.status_code == 200

    player = players_collection.find_one({"_id": "p1"})
    zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
    assert player["stats"]["game"] == zero_stats
    assert player["stats"]["season"] == zero_stats
    assert player["stats"]["career"] == zero_stats
    assert player["stats"]["applied_games"] == []

