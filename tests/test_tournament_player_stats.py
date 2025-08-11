from BackEnd.utils.stat_updater import apply_stats_from_summary
from BackEnd.db import players_collection


def setup_function(fn):
    players_collection.delete_many({})
    players_collection.insert_many([
        {
            "_id": "p1",
            "team": "Lancaster",
            "first_name": "A",
            "last_name": "One",
            "stats": {
                "game": {"PTS": 0, "AST": 0},
                "season": {"PTS": 0, "AST": 0},
                "career": {"PTS": 0, "AST": 0},
                "applied_games": [],
            },
        },
        {
            "_id": "p2",
            "team": "Bentley-Truman",
            "first_name": "B",
            "last_name": "Two",
            "stats": {
                "game": {"PTS": 0, "AST": 0},
                "season": {"PTS": 0, "AST": 0},
                "career": {"PTS": 0, "AST": 0},
                "applied_games": [],
            },
        },
    ])


def test_apply_stats_idempotent():
    summary = {
        "home_team": "Lancaster",
        "away_team": "Bentley-Truman",
        "box_score": {
            "Lancaster": {"PG": {"name": "A One", "PTS": 10, "AST": 2}},
            "Bentley-Truman": {"PG": {"name": "B Two", "PTS": 5, "AST": 1}},
        },
        "players": [
            {"playerId": "p1", "team": "home", "pos": "PG"},
            {"playerId": "p2", "team": "away", "pos": "PG"},
        ],
    }
    apply_stats_from_summary(summary, "g1", "t1")
    p1 = players_collection.find_one({"_id": "p1"})
    assert p1["stats"]["season"]["PTS"] == 10
    assert p1["stats"]["season"]["AST"] == 2
    assert p1["stats"]["game"]["PTS"] == 0
    assert "t1:g1" in p1["stats"]["applied_games"]

    # Apply again; should be idempotent
    apply_stats_from_summary(summary, "g1", "t1")
    p1 = players_collection.find_one({"_id": "p1"})
    assert p1["stats"]["season"]["PTS"] == 10
    assert p1["stats"]["season"]["AST"] == 2
