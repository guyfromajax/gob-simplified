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


