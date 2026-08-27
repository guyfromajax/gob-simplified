from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.utils.senior_tribute import build_senior_tribute_payload


def test_senior_tribute_active_seniors_rt_desc(monkeypatch):
    from BackEnd.utils import senior_tribute as st

    fid = ObjectId()
    team_id = ObjectId()
    ftd = MagicMock()
    ftd.find_one.return_value = {
        "players": ["star", "role", "junior", "missing"],
        "training_squad_players": ["ts-senior"],
    }
    fpd = MagicMock()
    fpd.find.return_value = [
        {
            "player_id": "star",
            "meta": {"first_name": "Ace", "last_name": "Walker", "year": "Senior"},
            "career": {"GP": 30, "PTS": 540, "REB": 210, "AST": 120, "DEF_S": 80, "DEF_A": 100},
            "position_ratings": {"SG": 88, "PG": 70},
            "titles": {"conf_rs": 1, "conf_t": 0, "region": 0, "national": 0},
        },
        {
            "player_id": "role",
            "meta": {"first_name": "Ben", "last_name": "Cole", "year": "senior"},
            "career": {"GP": 10, "PTS": 50, "OREB": 10, "DREB": 15, "AST": 8, "DEF_S": 0, "DEF_A": 0},
            "position_ratings": {"PF": 61},
            "titles": {},
        },
        {
            "player_id": "junior",
            "meta": {"first_name": "Cal", "last_name": "Young", "year": "Junior"},
            "career": {"GP": 30, "PTS": 400},
            "position_ratings": {"PG": 90},
            "titles": {"national": 1},
        },
        {
            "player_id": "ts-senior",
            "meta": {"first_name": "Dee", "last_name": "Bench", "year": "Senior"},
            "career": {"GP": 0},
            "position_ratings": {"C": 99},
            "titles": {},
        },
    ]
    monkeypatch.setattr(st, "franchise_team_data_collection", ftd)
    monkeypatch.setattr(st, "franchise_players_data_collection", fpd)

    payload = build_senior_tribute_payload(
        franchise_id=fid,
        user_team_object_id=str(team_id),
        current_season=3,
    )
    assert payload["season"] == 3
    ids = [row["player_id"] for row in payload["players"]]
    assert ids == ["star", "role"]
    star = payload["players"][0]
    assert star["name"] == "Ace Walker"
    assert star["rt"] == 88
    assert star["ppg"] == 18.0
    assert star["rpg"] == 7.0
    assert star["apg"] == 4.0
    assert star["def_pct"] == 80
    assert star["titles"]["conf_rs"] == 1
    assert star["titles"]["national"] == 0
    role = payload["players"][1]
    assert role["ppg"] == 5.0
    assert role["rpg"] == 2.5
    assert role["def_pct"] == 0
    assert role["titles"] == {"conf_rs": 0, "conf_t": 0, "region": 0, "national": 0}


def test_senior_tribute_empty_without_team():
    payload = build_senior_tribute_payload(
        franchise_id=ObjectId(),
        user_team_object_id=None,
        current_season=1,
    )
    assert payload == {"season": 1, "players": []}


def test_finish_season_carries_returning_titles(monkeypatch):
    from BackEnd.api import franchise_routes
    from BackEnd.models import franchise_manager

    franchise_id = ObjectId()
    team_id = ObjectId()
    inserted_docs = []

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id,
        "week": 36,
        "current_season": 2,
        "results": {},
        "week_35_recruiting_results": {},
    }
    mock_franchises.update_one = MagicMock(return_value=SimpleNamespace(modified_count=1))
    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(franchises=mock_franchises, games=MagicMock()),
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        MagicMock(
            find=MagicMock(
                return_value=[
                    {
                        "franchise_id": franchise_id,
                        "team_id": team_id,
                        "players": ["keep", "grad"],
                        "scholarship_players": ["keep"],
                    }
                ]
            ),
            update_one=MagicMock(),
        ),
    )
    mock_fpd = MagicMock()
    mock_fpd.find.return_value = [
        {
            "player_id": "keep",
            "meta": {"first_name": "Pat", "last_name": "Stay", "year": "Junior"},
            "career": {"GP": 20, "PTS": 100},
            "attributes": {},
            "position_ratings": {"PG": 70},
            "titles": {"conf_rs": 1, "national": 2},
        },
        {
            "player_id": "grad",
            "meta": {"first_name": "Sam", "last_name": "Done", "year": "Senior"},
            "career": {"GP": 30, "PTS": 200},
            "attributes": {},
            "position_ratings": {"SF": 80},
            "titles": {"conf_t": 1},
        },
    ]

    def capture_insert_many(docs):
        inserted_docs.extend(docs)

    mock_fpd.insert_many.side_effect = capture_insert_many
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", mock_fpd)
    monkeypatch.setattr(
        franchise_routes,
        "franchise_recruits_data_collection",
        MagicMock(delete_many=MagicMock(), insert_many=MagicMock()),
    )
    monkeypatch.setattr(
        franchise_manager,
        "FranchiseManager",
        lambda _db: SimpleNamespace(
            schedule_manager=SimpleNamespace(generate_schedule=lambda: []),
            recruit_manager=SimpleNamespace(generate_recruits_list=lambda count=300: []),
            _build_region_team_map=lambda: {"A": []},
        ),
    )

    result = franchise_routes.finish_season(
        franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id))
    )
    assert result["status"] == "success"
    ids = [doc["player_id"] for doc in inserted_docs]
    assert "keep" in ids
    assert "grad" not in ids
    keep = next(doc for doc in inserted_docs if doc["player_id"] == "keep")
    assert keep["titles"] == {"conf_rs": 1, "conf_t": 0, "region": 0, "national": 2}
    assert keep["meta"]["year"] == "Senior"
