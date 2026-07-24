from fastapi.testclient import TestClient

from BackEnd.api.api import app
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


def test_start_tournament_is_gone_and_does_not_mutate_player_stats():
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
    assert resp.status_code in {404, 405}

    player = players_collection.find_one({"_id": "p1"})
    assert player["stats"]["game"] == {"PTS": 5}
    assert player["stats"]["season"] == {"PTS": 5}
    assert player["stats"]["career"] == {"PTS": 10}
    assert player["stats"]["applied_games"] == ["old"]
    assert tournaments_collection.count_documents({}) == 0
