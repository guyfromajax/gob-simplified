"""Tournament browse route: read-only brackets payload."""

from __future__ import annotations

import copy

import pytest
from bson import ObjectId

from BackEnd.persistence import create_store
from BackEnd.tournament.browse import (
    TOURNAMENT_FIRST_WEEK,
    build_tournament_brackets_response,
    shape_eos_tournament,
)
from tests.test_persistence_adapter import _mongomock_env


def _user_id():
    return str(ObjectId())


def _minimal_franchise(week: int, user_team: str, conf: int = 1, region: str = "A"):
    away = str(ObjectId())
    home = str(ObjectId())
    return {
        "_id": ObjectId(),
        "user_id": "coach-1",
        "user_team_object_id": user_team,
        "week": week,
        "browse_rev": 1,
        "conference_tournaments": {
            str(conf): {
                "current_round": 1,
                "bracket": {
                    "round1": [{
                        "home_team": home,
                        "away_team": away,
                        "winner": home,
                        "game_id": "g-conf-1",
                        "score": {"home": 70, "away": 60},
                    }],
                    "round2": [],
                    "final": [],
                },
                "seeds": {home: 1, away: 8},
            }
        },
        "region_tournaments": {},
        "national_tournament": {},
        "results": {},
    }


def test_shape_eos_tournament_conference_week():
    uid = str(ObjectId())
    doc = _minimal_franchise(27, uid)
    shaped = shape_eos_tournament(doc, 27, 1, "A", {})
    assert shaped is not None
    assert shaped["bracket"]["round1"]


def test_locked_before_week_27():
    uid = str(ObjectId())
    doc = _minimal_franchise(26, uid)
    from BackEnd.api import franchise_routes as routes

    class _EmptyFtd:
        def find(self, *args, **kwargs):
            return []

    payload = build_tournament_brackets_response(
        doc,
        user_team_id=uid,
        user_team_doc={"conference": 1, "region": "A"},
        teams_collection=type("T", (), {"find_one": lambda *a, **k: None})(),
        franchise_team_data_collection=_EmptyFtd(),
        get_user_eos_phase_status=routes._get_user_eos_phase_status,
        calculate_franchise_standings=lambda *a, **k: {},
    )
    assert payload["locked"] is True
    assert payload["first_week"] == TOURNAMENT_FIRST_WEEK


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_route_does_not_mutate_franchise_at_week_30(kind, tmp_path, monkeypatch):
    if kind == "mongo":
        env = _mongomock_env(tmp_path)
    else:
        env = _mongomock_env(
            tmp_path,
            GOB_PERSISTENCE="sqlite",
            GOB_SQLITE_PATH=str(tmp_path / "tournament.sqlite"),
        )
    store = create_store(env)
    franchise_id = ObjectId()
    team_oid = ObjectId()
    user_team = str(team_oid)
    opp = str(ObjectId())
    store.teams_collection.insert_one({
        "_id": team_oid,
        "name": "Lancaster",
        "conference": 1,
        "region": "A",
    })
    store.franchise_team_data_collection.insert_one({
        "franchise_id": franchise_id,
        "team_id": user_team,
        "natl_rank": 4,
    })
    before = {
        "_id": franchise_id,
        "user_id": "coach-1",
        "user_team_id": str(team_oid),
        "user_team_object_id": str(team_oid),
        "week": 30,
        "browse_rev": 3,
        "region_tournaments": {
            "A": {
                "round1": [{
                    "home_team": user_team,
                    "away_team": opp,
                    "winner": None,
                    "score": {},
                }],
                "final": [],
                "current_round": 1,
            }
        },
        "conference_tournaments": {},
        "national_tournament": {},
    }
    store.franchises_collection.insert_one(copy.deepcopy(before))

    import BackEnd.api.franchise_routes as routes
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(routes, "db", store.db)
    monkeypatch.setattr(routes, "franchise_team_data_collection", store.franchise_team_data_collection)
    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)

    routes.get_tournament_brackets(str(franchise_id), user={"user_id": "coach-1"})
    after = store.franchises_collection.find_one({"_id": franchise_id})
    assert after["browse_rev"] == before["browse_rev"]
    assert after["region_tournaments"] == before["region_tournaments"]
    assert after["week"] == 30


def test_stale_region_served_in_response_not_persisted(monkeypatch):
    from BackEnd.tournament import franchise_tournament as ft
    from BackEnd.tournament import browse as tb

    uid = str(ObjectId())
    opp = str(ObjectId())
    stored = {
        "A": {
            "round1": [],
            "final": [{"home_team": "R1_0", "away_team": None, "winner": None}],
            "current_round": 1,
        }
    }
    reconciled = {
        "A": {
            "round1": [{"home_team": uid, "away_team": opp, "winner": None, "score": {}}],
            "final": [],
            "current_round": 1,
        }
    }
    franchise_doc = {
        "_id": ObjectId(),
        "week": 30,
        "region_tournaments": stored,
        "conference_tournaments": {},
        "national_tournament": {},
        "results": {},
    }

    class _Ftd:
        def find(self, *args, **kwargs):
            return [{"team_id": uid}]

    monkeypatch.setattr(tb, "region_tournaments_stale", lambda *a, **k: True)
    monkeypatch.setattr(
        ft,
        "reconcile_region_tournaments_with_canonical",
        lambda *a, **k: reconciled,
    )
    monkeypatch.setattr(tb, "build_teams_map", lambda *a, **k: {})

    from BackEnd.api import franchise_routes as routes

    out = tb.build_tournament_brackets_response(
        franchise_doc,
        user_team_id=uid,
        user_team_doc={"conference": 1, "region": "A"},
        teams_collection=object(),
        franchise_team_data_collection=_Ftd(),
        get_user_eos_phase_status=routes._get_user_eos_phase_status,
        calculate_franchise_standings=lambda *a, **k: {},
    )
    assert out["region_tournaments_stale"] is True
    assert out["region_tournaments"] == reconciled
    assert franchise_doc["region_tournaments"] == stored


def _real_shape_franchise(owner_id: str, teams: dict[str, ObjectId]) -> dict:
    """Week 30 as a real season stores it (read off a staging franchise and a full
    offline season): conference brackets played, with string ids and ``{"home", "away"}``
    scores; a region with a round-1 game, an ``R1_0`` placeholder in its final and no
    ``seeds``; a region that is one final and nothing else; no national bracket yet."""
    ids = {name: str(oid) for name, oid in teams.items()}

    def played(home, away, winner, hs, as_, gid):
        return {"home_team": ids[home], "away_team": ids[away], "game_id": gid,
                "winner": ids[winner], "score": {"home": hs, "away": as_}}

    def open_game(away, home):
        return {"away_team": ids.get(away, away), "home_team": ids.get(home, home),
                "game_id": None, "winner": None, "score": {}}

    return {
        "_id": ObjectId(),
        "user_id": owner_id,
        "user_team_id": "MORRISTOWN",
        "user_team_object_id": ids["morristown"],
        "week": 30,
        "current_season": 1,
        "browse_rev": 7,
        "eos_tournament_active": True,
        "results": {},
        "conference_tournaments": {
            "1": {
                "bracket": {
                    "round1": [played("xavien", "little_york", "xavien", 87, 49, "g-r1")],
                    "round2": [played("xavien", "morristown", "xavien", 85, 58, "g-r2")],
                    "final": [played("xavien", "lancaster", "lancaster", 78, 82, "g-f")],
                },
                "current_round": 3,
                "seeds": {ids["xavien"]: 1, ids["lancaster"]: 2, ids["morristown"]: 4, ids["little_york"]: 8},
                "champion": ids["lancaster"],
            },
        },
        "region_tournaments": {
            "A": {
                "round1": [open_game("lancaster", "xavien")],
                "final": [open_game("R1_0", "durham")],
                "current_round": 1,
            },
            "B": {"round1": [], "final": [open_game("concord", "providence")], "current_round": 1},
        },
    }


def test_route_needs_the_session_and_serves_a_real_season_shape():
    """The real auth dependency. Every other test runs behind the conftest override,
    which is how a client that sent no Authorization header went unnoticed: the route
    is 401 without the bearer token, and 200 with it."""
    from fastapi.testclient import TestClient

    from BackEnd.api.api import app
    from BackEnd.db import db, franchise_team_data_collection, users_collection
    from BackEnd.utils import auth
    from BackEnd.utils.auth import get_current_user

    override = app.dependency_overrides.pop(get_current_user, None)
    try:
        owner = users_collection.insert_one({"email": "coach@example.com", "token_version": 0}).inserted_id
        auth.invalidate_user_auth_cache()
        layout = {
            "morristown": (1, "A"), "xavien": (1, "A"), "lancaster": (1, "A"), "little_york": (1, "A"),
            "durham": (2, "A"), "concord": (3, "B"), "providence": (4, "B"),
        }
        teams = {name: ObjectId() for name in layout}
        for name, oid in teams.items():
            db.teams.insert_one({"_id": oid, "name": name.replace("_", " ").title(),
                                 "conference": layout[name][0], "region": layout[name][1]})
        doc = _real_shape_franchise(str(owner), teams)
        db.franchises.insert_one(copy.deepcopy(doc))
        for rank, oid in enumerate(teams.values(), start=1):
            franchise_team_data_collection.insert_one(
                {"franchise_id": doc["_id"], "team_id": oid, "natl_rank": rank})

        client = TestClient(app)
        params = {"franchise_id": str(doc["_id"])}

        bare = client.get("/franchise/tournament/brackets", params=params)
        assert bare.status_code == 401
        assert bare.json() == {"detail": "Not authenticated"}

        token = auth.create_access_token({"sub": str(owner), "email": "coach@example.com", "tv": 0})
        ok = client.get("/franchise/tournament/brackets", params=params,
                        headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["locked"] is False
        assert body["week"] == 30
        assert body["current_phase"] == "region"
        # What the tab reads to pick each phase's bracket.
        assert body["user_conference"] == 1
        assert body["user_region"] == "A"
        assert body["conference_tournaments"]["1"]["bracket"]["final"][0]["winner"] == str(teams["lancaster"])
        assert "A" in body["region_tournaments"]
        assert body["national_tournament"] == {}
        # Every team in the user's conference bracket has a name; a placeholder is not a team.
        for name in ("morristown", "xavien", "lancaster", "little_york"):
            assert str(teams[name]) in body["teams"]
        assert "R1_0" not in body["teams"]
        assert body["teams"][str(teams["little_york"])]["name"] == "Little York"

        # A token for someone else's franchise is still refused.
        other = users_collection.insert_one({"email": "other@example.com", "token_version": 0}).inserted_id
        stranger = auth.create_access_token({"sub": str(other), "email": "other@example.com", "tv": 0})
        denied = client.get("/franchise/tournament/brackets", params=params,
                            headers={"Authorization": f"Bearer {stranger}"})
        assert denied.status_code == 403
    finally:
        if override is not None:
            app.dependency_overrides[get_current_user] = override
