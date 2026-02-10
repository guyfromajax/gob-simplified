from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api import franchise_routes


def test_schedule_scopes_game_lookup_to_franchise(monkeypatch):
    franchise_id = ObjectId()
    other_franchise_id = ObjectId()
    away_id = ObjectId()
    home_id = ObjectId()

    leaked_game_doc = {
        "_id": ObjectId(),
        "week": 1,
        "team1_id": away_id,
        "team2_id": home_id,
        "team1_score": 90,
        "team2_score": 80,
        "franchise_id": str(other_franchise_id),
    }

    games = MagicMock()

    def games_find_one(query, projection=None):
        has_matchup = (
            query.get("week") == 1
            and query.get("team1_id") in (away_id, home_id)
            and query.get("team2_id") in (away_id, home_id)
        )
        if has_matchup and "franchise_id" not in query:
            return leaked_game_doc
        return None

    games.find_one.side_effect = games_find_one

    franchises = MagicMock()
    franchises.find_one.return_value = {
        "_id": franchise_id,
        "schedule": [[(away_id, home_id)]],
        "results": {},
        "user_team_id": "Away Team",
        "user_team_object_id": str(away_id),
    }

    fake_db = SimpleNamespace(franchises=franchises, games=games, teams=MagicMock())
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        SimpleNamespace(find_one=lambda *args, **kwargs: None),
    )

    payload = franchise_routes.season_schedule(str(franchise_id))
    game = payload["schedule"][0][0]

    assert game["status"] == "scheduled"
    assert game["away_score"] is None
    assert game["home_score"] is None
    assert game["game_id"] is None

    scoped_queries = [c.args[0] for c in games.find_one.call_args_list if c.args]
    assert any(q.get("franchise_id") == str(franchise_id) for q in scoped_queries)


def test_save_game_result_legacy_lookup_uses_franchise_scope(monkeypatch):
    team1_id = ObjectId()
    team2_id = ObjectId()
    week = 2
    franchise_id = str(ObjectId())

    existing_other_franchise_doc = {"_id": ObjectId(), "franchise_id": str(ObjectId())}

    games = MagicMock()

    def games_find_one(query, projection=None):
        if (
            query.get("week") == week
            and query.get("$or")
            and "franchise_id" not in query
        ):
            return existing_other_franchise_doc
        return None

    games.find_one.side_effect = games_find_one
    games.update_one = MagicMock()

    fake_db = SimpleNamespace(games=games)
    monkeypatch.setattr(franchise_routes, "db", fake_db)

    franchise_routes._save_game_result(
        team1_id=team1_id,
        team2_id=team2_id,
        team1_score=81,
        team2_score=79,
        week=week,
        franchise_id=franchise_id,
        game_id=None,
    )

    scoped_queries = [c.args[0] for c in games.find_one.call_args_list if c.args]
    assert any(
        q.get("week") == week and q.get("franchise_id") == franchise_id
        for q in scoped_queries
    )

    update_filter = games.update_one.call_args.args[0]
    assert update_filter == {"week": week, "team1_id": team1_id, "team2_id": team2_id}


def test_schedule_endpoint_does_not_leak_cross_franchise_game_docs(monkeypatch):
    client = TestClient(app)
    franchise_id = ObjectId()
    other_franchise_id = ObjectId()
    away_id = ObjectId()
    home_id = ObjectId()

    leaked_game_doc = {
        "_id": ObjectId(),
        "week": 1,
        "team1_id": away_id,
        "team2_id": home_id,
        "team1_score": 88,
        "team2_score": 77,
        "franchise_id": str(other_franchise_id),
    }

    games = MagicMock()

    def games_find_one(query, projection=None):
        has_matchup = (
            query.get("week") == 1
            and query.get("team1_id") in (away_id, home_id)
            and query.get("team2_id") in (away_id, home_id)
        )
        if has_matchup and "franchise_id" not in query:
            return leaked_game_doc
        return None

    games.find_one.side_effect = games_find_one

    franchises = MagicMock()
    franchises.find_one.return_value = {
        "_id": franchise_id,
        "schedule": [[(away_id, home_id)]],
        "results": {},
        "user_team_id": "Away Team",
        "user_team_object_id": str(away_id),
    }

    fake_db = SimpleNamespace(franchises=franchises, games=games, teams=MagicMock())
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        SimpleNamespace(find_one=lambda *args, **kwargs: None),
    )

    res = client.get(f"/franchise/schedule?franchise_id={franchise_id}")
    assert res.status_code == 200
    game = res.json()["schedule"][0][0]
    assert game["status"] == "scheduled"
    assert game["game_id"] is None
