"""
Tests for 5.2 User Data Exposure Prevention and 5.4 Input Validation.

- Unauthenticated requests to user-data endpoints must return 401.
- Authenticated users must not access another user's franchise/tournament/game (403/404).
- Invalid input (malformed IDs, bad JSON) must return 400/422.
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.utils.auth import get_current_user


client = TestClient(app)


async def _test_user():
    return {"user_id": "test-user-123", "email": "test@test.com", "role": "user"}


async def _other_user():
    return {"user_id": "other-user-456", "email": "other@test.com", "role": "user"}


def test_unauthenticated_franchise_select_team_blocked():
    """Without auth, POST /franchise/select-team must return 401."""
    # Clear auth override so we test real unauthenticated behavior
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]
    try:
        resp = client.post("/franchise/select-team", json={"team_name": "Lancaster"})
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_unauthenticated_tournament_start_blocked():
    """Without auth, POST /tournament/start must return 401."""
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]
    try:
        resp = client.post("/tournament/start", json={"user_team_id": "Lancaster"})
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_unauthenticated_game_state_blocked():
    """Without auth, GET /api/game/{game_id} must return 401."""
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]
    try:
        resp = client.get("/api/game/507f1f77bcf86cd799439011")
        assert resp.status_code == 401, resp.text
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_cross_user_franchise_access_blocked(monkeypatch):
    """Authenticated user B must not access franchise owned by user A."""
    fid = ObjectId()
    team_oid = ObjectId()
    mock_franchise_doc = {
        "_id": fid,
        "user_id": "user-a-owner",
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_oid),
        "week": 1,
        "schedule": [],
        "training_status": {},
    }

    def mock_find_one(query):
        if query.get("_id") == fid:
            return mock_franchise_doc
        return None

    monkeypatch.setattr(
        "BackEnd.utils.ownership.franchises_collection",
        type("MockCollection", (), {"find_one": lambda self, q: mock_find_one(q)})(),
    )
    try:
        app.dependency_overrides[get_current_user] = _other_user
        resp = client.get(f"/franchise/command-center/data?franchise_id={fid}")
        assert resp.status_code in (403, 404), resp.text
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_invalid_franchise_id_returns_400(monkeypatch):
    """Invalid franchise_id format must return 400, not 500."""
    app.dependency_overrides[get_current_user] = _test_user
    try:
        resp = client.get("/franchise/command-center/data?franchise_id=not-a-valid-objectid")
        assert resp.status_code == 400
        assert "Invalid" in resp.json().get("detail", "")
    finally:
        app.dependency_overrides[get_current_user] = _test_user


def test_invalid_json_returns_422():
    """Malformed JSON body must return 422."""
    app.dependency_overrides[get_current_user] = _test_user
    try:
        resp = client.post(
            "/franchise/select-team",
            content="{ invalid json }",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides[get_current_user] = _test_user
