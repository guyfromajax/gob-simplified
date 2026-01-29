from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import get_tournament_leaders
from BackEnd.db import tournaments_collection
from tests.tournament_test_helpers import seed_teams_ah


def setup_function(fn):
    seed_teams_ah()
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
                            "3PTM": 5,
                            "3PTA": 10,
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
                            "3PTM": 5,
                            "3PTA": 8,
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
                            "3PTM": 20,
                            "3PTA": 30,
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
    assert leaders["3PTM"][0]["player_id"] == "p1"
    assert leaders["3PTM"][1]["player_id"] == "p2"

    # ensure leaderboards persisted to tournament document
    stored = tournaments_collection.find_one({"_id": tid})
    assert "leaderboards" in stored
    assert stored["leaderboards"]["PTS"][0]["player_id"] == "p1"
