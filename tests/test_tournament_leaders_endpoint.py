from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import get_tournament_leaders
from BackEnd.db import players_collection, tournaments_collection


def setup_function(fn):
    players_collection.delete_many({})
    tournaments_collection.delete_many({})


def test_leaders_return_top_players_and_exclude_others():
    players_collection.insert_many(
        [
            {
                "_id": "p1",
                "team": "A",
                "first_name": "Ann",
                "last_name": "Alpha",
                "stats": {
                    "season": {
                        "PTS": 20,
                        "TPM": 5,
                        "TPA": 10,
                        "REB": 8,
                        "AST": 4,
                        "STL": 2,
                        "BLK": 1,
                        "MIN": 30,
                    }
                },
            },
            {
                "_id": "p2",
                "team": "B",
                "first_name": "Bob",
                "last_name": "Beta",
                "stats": {
                    "season": {
                        "PTS": 15,
                        "TPM": 5,
                        "TPA": 8,
                        "REB": 7,
                        "AST": 5,
                        "STL": 1,
                        "BLK": 0,
                        "MIN": 28,
                    }
                },
            },
            {
                "_id": "p3",
                "team": "X",
                "first_name": "X",  # should be excluded
                "last_name": "Excluded",
                "stats": {
                    "season": {
                        "PTS": 100,
                        "TPM": 20,
                        "TPA": 30,
                        "REB": 10,
                        "AST": 10,
                        "STL": 10,
                        "BLK": 10,
                        "MIN": 40,
                    }
                },
            },
        ]
    )

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tourney = manager.create_tournament()

    leaders = get_tournament_leaders(tourney["_id"])

    assert leaders["PTS"][0]["player_id"] == "p1"
    assert leaders["PTS"][1]["player_id"] == "p2"
    assert all(entry["player_id"] != "p3" for entry in leaders["PTS"])
    assert leaders["TPM"][0]["player_id"] == "p1"
    assert leaders["TPM"][1]["player_id"] == "p2"
