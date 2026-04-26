import os
import sys

import pytest

# Ensure the project root is on sys.path so 'import BackEnd' succeeds
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.models.game_manager import GameManager
from BackEnd.constants import POSITION_LIST


async def _test_user():
    """Fake user for tests that hit auth-protected endpoints."""
    return {"user_id": "test-user-123", "email": "test@test.com", "role": "user"}


@pytest.fixture(autouse=True)
def override_auth_for_tests():
    """Provide a fake authenticated user so tests can call protected endpoints."""
    from BackEnd.api.api import app
    from BackEnd.utils.auth import get_current_user

    app.dependency_overrides[get_current_user] = _test_user
    yield
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]


@pytest.fixture(autouse=True)
def seed_canonical_teams_for_mongomock():
    """Mongomock starts empty; API tests need teams.name → team_id for summarize_game_state keys."""
    from BackEnd.db import teams_collection

    for name, team_id in (
        ("Morristown", "MORRISTOWN"),
        ("Lancaster", "LANCASTER"),
        ("Bentley-Truman", "BENTLEY_TRUMAN"),
    ):
        teams_collection.update_one(
            {"name": name},
            {"$set": {"name": name, "team_id": team_id}},
            upsert=True,
        )
    yield


@pytest.fixture
def mock_game_manager():
    # Uses team names that must exist in your database
    gm = GameManager("Lancaster", "Bentley-Truman")
    return gm

@pytest.fixture
def simulated_game():
    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.simulate_macro_turn()
    return gm


