import pytest
from unittest.mock import MagicMock
from BackEnd.tournament.tournament_manager import TournamentManager

@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.insert_one.return_value.inserted_id = "mock_id"
    return collection

def test_create_tournament_generates_seeded_bracket(mock_collection):
    user_team = "Xavien"
    all_teams = ["Xavien", "Morristown", "Lancaster", "Little York", "Ocean City", "South Lancaster", "Bentley-Truman", "Four Corners"]

    manager = TournamentManager(
        user_team_id=user_team,
        tournaments_collection=mock_collection,
        team_ids=all_teams,
    )
    tournament = manager.create_tournament()

    assert tournament["user_team_id"] == user_team
    assert tournament["current_round"] == 1
    assert len(tournament["bracket"]["round1"]) == 4
    all_teams_used = set([m["home_team"] for m in tournament["bracket"]["round1"]] +
                         [m["away_team"] for m in tournament["bracket"]["round1"]])
    assert set(all_teams) == all_teams_used
    assert tournament["_id"] == "mock_id"
    mock_collection.insert_one.assert_called_once()

    # ensure players mapping was created for all teams
    assert isinstance(tournament.get("players"), dict)
    assert set(tournament["players"].keys()) == set(all_teams)

def test_save_game_result_and_advance_round(mock_collection):
    manager = TournamentManager(
        user_team_id="Xavien",
        tournaments_collection=mock_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    manager.create_tournament()

    # simulate round 1 results
    for i in range(4):
        manager.save_game_result("round1", i, f"game{i}", f"Winner{i}")
        assert manager.tournament["bracket"]["round1"][i]["game_id"] == f"game{i}"
        assert manager.tournament["bracket"]["round1"][i]["winner"] == f"Winner{i}"

    manager.advance_round()
    assert manager.tournament["current_round"] == 2
    assert len(manager.tournament["bracket"]["round2"]) == 2

    # simulate round 2 results
    for i in range(2):
        manager.tournament["bracket"]["round2"][i]["winner"] = f"R2Winner{i}"

    manager.advance_round()
    assert manager.tournament["current_round"] == 3
    assert len(manager.tournament["bracket"]["final"]) == 1

    # simulate final result
    manager.tournament["bracket"]["final"][0]["winner"] = "Champion"
    manager.advance_round()
    assert manager.tournament["completed"] is True
