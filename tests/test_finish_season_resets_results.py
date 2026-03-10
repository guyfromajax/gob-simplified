from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.models import franchise_manager


def test_finish_season_resets_franchise_results(monkeypatch):
    franchise_id = ObjectId()
    captured_update = {}

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id,
        "current_season": 1,
        "results": {"1": [{"team1_score": 80, "team2_score": 70}]},
    }

    def capture_update(_query, update_doc):
        captured_update.update(update_doc.get("$set", {}))

    mock_franchises.update_one.side_effect = capture_update

    mock_games = MagicMock()
    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(franchises=mock_franchises, games=mock_games),
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", MagicMock(find=MagicMock(return_value=[])))
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", MagicMock(find=MagicMock(return_value=[]), delete_many=MagicMock()))
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", MagicMock(delete_many=MagicMock()))

    dummy_manager = SimpleNamespace(
        schedule_manager=SimpleNamespace(generate_schedule=lambda: []),
        recruit_manager=SimpleNamespace(generate_recruits_list=lambda count=200: []),
        _build_region_team_map=lambda: {"A": []},
    )
    monkeypatch.setattr(franchise_manager, "FranchiseManager", lambda _db: dummy_manager)

    result = franchise_routes.finish_season(
        franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id))
    )

    assert result["status"] == "success"
    assert captured_update["results"] == {}
