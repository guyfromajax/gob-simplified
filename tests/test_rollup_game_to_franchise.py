from BackEnd.utils.stat_updater import rollup_game_to_franchise
from BackEnd.db import db, games_collection, players_collection
from pytest import approx


def setup_function(_fn):
    games_collection.delete_many({})
    players_collection.delete_many({})
    db.franchises.delete_many({})


def test_rollup_game_to_franchise_idempotent():
    players_collection.insert_many(
        [
            {"_id": "p1", "first_name": "A", "last_name": "One", "team": "Team1"},
            {"_id": "p2", "first_name": "B", "last_name": "Two", "team": "Team2"},
        ]
    )

    fid = db.franchises.insert_one({"player_stats": {}, "processed_games": []}).inserted_id

    game = {
        "home_team": "Team1",
        "away_team": "Team2",
        "box_score": {
            "Team1": {"PG": {"name": "A One", "PTS": 10, "FGA": 5, "FGM": 4, "FTA": 2, "FTM": 1}},
            "Team2": {"PG": {"name": "B Two", "PTS": 8, "FGA": 6, "FGM": 3, "FTA": 1, "FTM": 1}},
        },
        "players": [
            {"playerId": "p1", "team": "home", "pos": "PG"},
            {"playerId": "p2", "team": "away", "pos": "PG"},
        ],
    }
    gid = games_collection.insert_one(game).inserted_id

    rollup_game_to_franchise(str(fid), str(gid))
    doc1 = db.franchises.find_one({"_id": fid})

    p1 = doc1["player_stats"]["p1"]
    p2 = doc1["player_stats"]["p2"]
    assert p1["season"]["PTS"] == 10
    assert p1["season"]["FGA"] == 5
    assert p1["season"]["FGM"] == 4
    assert p1["season"]["GP"] == 1
    assert p1["season"]["per_game"]["PTS"] == 10
    assert p1["season"]["percentages"]["FG%"] == 80.0
    assert p1["season"]["percentages"]["FT%"] == 50.0
    assert p1["season"]["percentages"]["TS%"] == approx(85.0340136, rel=1e-3)
    assert p1["season"]["percentages"]["eFG%"] == 80.0

    assert p1["career"]["per_game"]["PTS"] == 10
    assert p1["career"]["percentages"]["FG%"] == 80.0

    assert p2["season"]["PTS"] == 8
    assert p2["season"]["percentages"]["FG%"] == 50.0
    assert p2["season"]["percentages"]["FT%"] == 100.0
    assert p2["career"]["percentages"]["FG%"] == 50.0

    assert doc1["processed_games"] == [str(gid)]

    rollup_game_to_franchise(str(fid), str(gid))
    doc2 = db.franchises.find_one({"_id": fid})

    assert doc2 == doc1


def test_rollup_game_to_franchise_validates_stats():
    players_collection.insert_one(
        {"_id": "p1", "first_name": "A", "last_name": "One", "team": "Team1"}
    )

    fid = db.franchises.insert_one({"player_stats": {}, "processed_games": []}).inserted_id

    game = {
        "home_team": "Team1",
        "away_team": "Team2",
        "box_score": {
            "Team1": {
                "PG": {"name": "A One", "PTS": -5, "FGA": "5", "FGM": 4}
            },
            "Team2": {},
        },
        "players": [
            {"playerId": "p1", "team": "home", "pos": "PG"},
        ],
    }
    gid = games_collection.insert_one(game).inserted_id

    rollup_game_to_franchise(str(fid), str(gid))
    doc = db.franchises.find_one({"_id": fid})
    p1 = doc["player_stats"]["p1"]

    assert "PTS" not in p1["season"]
    assert "FGA" not in p1["season"]
    assert p1["season"]["FGM"] == 4
    assert p1["season"]["percentages"]["FG%"] == 0
    assert doc["processed_games"] == [str(gid)]

