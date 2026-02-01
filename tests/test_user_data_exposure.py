"""
Tests for 5.2 User Data Exposure Prevention.

- Unauthenticated requests to user-data endpoints must return 401.
- Authenticated users must not access another user's franchise/tournament/game (403/404).
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
