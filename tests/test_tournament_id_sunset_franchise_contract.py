"""Guards for retiring legacy standalone ``tournament_id``.

These tests protect the active Franchise end-of-season tournament contract.
Franchise tournament weeks are keyed by ``franchise_id`` plus EOS week/bracket
metadata; they must not acquire a dependency on the standalone Tournament Mode
identifier while that legacy mode is removed.
"""

from pathlib import Path

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.franchise_routes import (
    CompleteWeekRequest,
    PlayGameRequest,
    _build_eos_schedule_payload,
    router as franchise_router,
)
from BackEnd.api.api import app
from BackEnd.db import tournaments_collection
from BackEnd.tournament import franchise_tournament as ft

client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _model_field_names(model) -> set[str]:
    """Support both Pydantic v1 and v2 while the project straddles versions."""
    fields = getattr(model, "model_fields", None)
    if fields is None:
        fields = getattr(model, "__fields__", {})
    return set(fields)


def _conference_matchup(away_id: str, home_id: str) -> dict:
    return {
        "away_team": away_id,
        "home_team": home_id,
        "winner": None,
        "score": {},
        "game_id": None,
    }


def test_franchise_requests_are_keyed_by_franchise_id_not_tournament_id():
    assert _model_field_names(PlayGameRequest) == {"franchise_id"}
    assert "franchise_id" in _model_field_names(CompleteWeekRequest)
    assert "tournament_id" not in _model_field_names(CompleteWeekRequest)


def test_active_franchise_tournament_routes_remain_on_franchise_router():
    methods_by_path = {
        route.path: set(route.methods or ())
        for route in franchise_router.routes
        if hasattr(route, "path")
    }

    assert "POST" in methods_by_path["/franchise/play-next-game"]
    assert "POST" in methods_by_path["/franchise/complete-week"]
    assert "POST" in methods_by_path["/franchise/complete-week/phase-a"]
    assert "POST" in methods_by_path["/franchise/complete-week/phase-b"]
    assert "GET" in methods_by_path["/franchise/schedule"]


def test_franchise_eos_schedule_uses_week_and_bracket_metadata_without_legacy_id():
    away_id = str(ObjectId())
    home_id = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(),
        "week": ft.EOS_CONFERENCE_WEEKS[0],
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [_conference_matchup(away_id, home_id)],
                    "round2": [],
                    "final": [],
                },
            }
        },
        "region_tournaments": {},
        "national_tournament": {},
    }

    schedule, included_team_ids = _build_eos_schedule_payload(
        franchise_doc,
        {away_id: 1, home_id: 1},
    )

    assert set(schedule) == set(ft.EOS_WEEKS)
    assert included_team_ids == {away_id, home_id}

    game = schedule[ft.EOS_CONFERENCE_WEEKS[0]][0]
    assert game["phase"] == "conference"
    assert game["round"] == 1
    assert game["matchup_index"] == 0
    assert game["tournament_context"] == "Conference 1"
    assert game["away_team_id"] == away_id
    assert game["home_team_id"] == home_id
    assert "tournament_id" not in game


def test_standalone_tournament_creation_endpoints_are_gone():
    tournaments_collection.delete_many({})

    for path in ("/tournament/start", "/start-tournament"):
        response = client.post(path, json={"user_team_id": "Lancaster"})
        assert response.status_code == 410
        assert "retired" in response.json()["detail"].lower()

    assert tournaments_collection.count_documents({}) == 0


def test_standalone_tournament_pages_are_redirect_only_fallbacks():
    for relative_path in (
        "FrontEnd/static/tournament-select.html",
        "FrontEnd/static/tournament.html",
    ):
        html = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "window.location.replace('/mode-select.html')" in html
        assert '<meta http-equiv="refresh" content="0;url=/mode-select.html">' in html
        assert "tournament.js" not in html
        assert "tournament-select.js" not in html
