import pytest
from unittest.mock import MagicMock
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import teams_collection


def _seed_teams_ah():
    names = ["A", "B", "C", "D", "E", "F", "G", "H"]
    teams_collection.delete_many({"name": {"$in": names}})
    for n in names:
        teams_collection.insert_one({"name": n})


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.insert_one.return_value.inserted_id = ObjectId()
    return collection


def test_create_tournament_generates_seeded_bracket(mock_collection):
    _seed_teams_ah()
    user_team = "A"
    all_teams = ["A", "B", "C", "D", "E", "F", "G", "H"]

    manager = TournamentManager(
        user_team_id=user_team,
        tournaments_collection=mock_collection,
        team_ids=all_teams,
    )
    tournament = manager.create_tournament()

    assert tournament["user_team_id"] == user_team
    assert tournament["current_round"] == 1
    assert len(tournament["bracket"]["round1"]) == 4
    all_teams_used = set(
        [m["home_team"] for m in tournament["bracket"]["round1"]] +
        [m["away_team"] for m in tournament["bracket"]["round1"]]
    )
    assert len(all_teams_used) == 8
    mock_collection.insert_one.assert_called_once()


def test_save_game_result_and_advance_round(mock_collection):
    _seed_teams_ah()
    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=mock_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    manager.create_tournament()

    for i in range(4):
        match = manager.tournament["bracket"]["round1"][i]
        home = str(match["home_team"])
        away = str(match["away_team"])
        winner = home
        score = {home: i + 1, away: i}
        manager.save_game_result(1, i, f"game{i}", winner, score)
        assert manager.tournament["bracket"]["round1"][i]["game_id"] == f"game{i}"
        assert manager.tournament["bracket"]["round1"][i]["winner"] == winner
        assert manager.tournament["bracket"]["round1"][i]["score"] == score

    manager.advance_round()
    assert manager.tournament["current_round"] == 2
    assert len(manager.tournament["bracket"]["round2"]) == 2

    for i in range(2):
        manager.tournament["bracket"]["round2"][i]["winner"] = str(
            manager.tournament["bracket"]["round2"][i]["home_team"]
        )
    manager.advance_round()
    assert manager.tournament["current_round"] == 3
    assert len(manager.tournament["bracket"]["final"]) == 1

    manager.tournament["bracket"]["final"][0]["winner"] = str(
        manager.tournament["bracket"]["final"][0]["home_team"]
    )
    manager.advance_round()
    assert manager.tournament["completed"] is True
