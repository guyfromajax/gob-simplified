from BackEnd.tournament.tournament_manager import TournamentManager
from bson import ObjectId

from BackEnd.api.tournament_routes import get_tournament_leaders
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import tournaments_collection


def setup_function(fn):
    tournaments_collection.delete_many({})


def test_leaders_return_top_players_and_exclude_others():
    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tourney = manager.create_tournament()
    tid = ObjectId(tourney["_id"])

    tournaments_collection.update_one(
        {"_id": tid},
        {
            "$set": {
                "player_stats": {
                    "p1": {
                        "team": "A",
                        "first_name": "Ann",
                        "last_name": "Alpha",
                        "season": {
                            "PTS": 20,
                            "TPM": 5,
                            "TPA": 10,
                            "REB": 8,
                            "AST": 4,
                            "STL": 2,
                            "BLK": 1,
                            "MIN": 30,
                        },
                    },
                    "p2": {
                        "team": "B",
                        "first_name": "Bob",
                        "last_name": "Beta",
                        "season": {
                            "PTS": 15,
                            "TPM": 5,
                            "TPA": 8,
                            "REB": 7,
                            "AST": 5,
                            "STL": 1,
                            "BLK": 0,
                            "MIN": 28,
                        },
                    },
                    "p3": {
                        "team": "X",  # should be excluded
                        "first_name": "X",
                        "last_name": "Excluded",
                        "season": {
                            "PTS": 100,
                            "TPM": 20,
                            "TPA": 30,
                            "REB": 10,
                            "AST": 10,
                            "STL": 10,
                            "BLK": 10,
                            "MIN": 40,
                        },
                    },
                }
            }
        },
    )

    leaders = get_tournament_leaders(tourney["_id"])

    assert leaders["PTS"][0]["player_id"] == "p1"
    assert leaders["PTS"][1]["player_id"] == "p2"
    assert all(entry["player_id"] != "p3" for entry in leaders["PTS"])
    assert leaders["TPM"][0]["player_id"] == "p1"
    assert leaders["TPM"][1]["player_id"] == "p2"
