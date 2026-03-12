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
        "week": 36,
        "current_season": 1,
        "results": {"1": [{"team1_score": 80, "team2_score": 70}]},
    }

    def capture_update(query, update_doc):
        if "$unset" in update_doc:
            return SimpleNamespace(modified_count=1)
        captured_update.update(update_doc.get("$set", {}))
        return SimpleNamespace(modified_count=1)

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


def test_finish_season_normalizes_signed_freshman_attributes(monkeypatch):
    franchise_id = ObjectId()
    team_id = ObjectId()
    inserted_docs = []

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id,
        "week": 36,
        "current_season": 1,
        "results": {},
        "week_35_recruiting_results": {
            "signed_players": [
                {
                    "player_id": "freshman-1",
                    "team_id": str(team_id),
                    "team_name": "Morristown",
                    "name": "Jayceon Rivers",
                    "height": 77,
                    "weight": 201,
                    "jersey": 11,
                    "archetype": "Outside C",
                    "attributes": {
                        "SC": 3, "SH": 2, "ID": 3, "OD": 1, "PS": 0, "BH": 3,
                        "RB": 2, "ST": 6, "AG": 3, "ND": 0, "IQ": 1, "FT": 2,
                    },
                    "position_ratings": {"C": 40, "PF": 30},
                }
            ]
        },
    }

    mock_franchises.update_one = MagicMock(return_value=SimpleNamespace(modified_count=1))
    mock_games = MagicMock()

    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(franchises=mock_franchises, games=mock_games),
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        MagicMock(
            find=MagicMock(return_value=[{"franchise_id": franchise_id, "team_id": team_id, "players": []}]),
            update_one=MagicMock(),
        ),
    )

    mock_fpd_collection = MagicMock(find=MagicMock(return_value=[]), delete_many=MagicMock())

    def capture_insert_many(docs):
        inserted_docs.extend(docs)

    mock_fpd_collection.insert_many.side_effect = capture_insert_many
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", mock_fpd_collection)
    monkeypatch.setattr(
        franchise_routes,
        "franchise_recruits_data_collection",
        MagicMock(delete_many=MagicMock(), insert_many=MagicMock()),
    )

    dummy_manager = SimpleNamespace(
        schedule_manager=SimpleNamespace(generate_schedule=lambda: []),
        recruit_manager=SimpleNamespace(generate_recruits_list=lambda count=300: []),
        _build_region_team_map=lambda: {"A": []},
    )
    monkeypatch.setattr(franchise_manager, "FranchiseManager", lambda _db: dummy_manager)

    def fake_randomize_game_attributes(attrs):
        attrs["NG"] = 1.0
        attrs["anchor_NG"] = 1.0
        attrs["CH"] = 55
        attrs["anchor_CH"] = 55
        attrs["MO"] = 0
        attrs["anchor_MO"] = 0
        attrs["EM"] = 44
        attrs["anchor_EM"] = 44
        return attrs

    monkeypatch.setattr(franchise_routes.Player, "randomize_game_attributes", staticmethod(fake_randomize_game_attributes))

    result = franchise_routes.finish_season(
        franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id))
    )

    assert result["status"] == "success"
    freshman_doc = next(doc for doc in inserted_docs if doc["player_id"] == "freshman-1")
    attrs = freshman_doc["attributes"]
    assert attrs["SC"] == 3
    assert attrs["anchor_SC"] == 3
    assert attrs["FT"] == 2
    assert attrs["anchor_FT"] == 2
    assert attrs["CH"] == 55
    assert attrs["anchor_CH"] == 55
    assert attrs["EM"] == 44
    assert attrs["anchor_EM"] == 44
    assert attrs["MO"] == 0
    assert attrs["anchor_MO"] == 0
    assert attrs["NG"] == 1.0
    assert attrs["anchor_NG"] == 1.0


def test_finish_season_rejects_duplicate_transition(monkeypatch):
    franchise_id = ObjectId()

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id,
        "week": 36,
        "current_season": 1,
        "results": {},
        "season_transition_token": "token-123",
        "week_35_recruiting_results": {},
    }

    def update_one(query, update_doc):
        if "$unset" in update_doc:
            return SimpleNamespace(modified_count=0)
        return SimpleNamespace(modified_count=1)

    mock_franchises.update_one.side_effect = update_one
    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(franchises=mock_franchises, games=MagicMock()),
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", MagicMock(find=MagicMock(return_value=[])))
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", MagicMock(find=MagicMock(return_value=[]), delete_many=MagicMock()))
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", MagicMock(delete_many=MagicMock()))

    try:
        franchise_routes.finish_season(
            franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id))
        )
        assert False, "Expected duplicate season transition to be rejected"
    except franchise_routes.HTTPException as exc:
        assert exc.status_code == 409
        assert "already been processed" in exc.detail
