import os
import sys

import pytest

# Tests select in-memory Mongo explicitly. This must happen before pytest_configure
# imports BackEnd.db; missing/failed real Mongo configuration no longer falls back.
os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")

# GOB_STRICT_EXCEPTIONS — ON for the whole suite (2026-09-24).
#
# The animation path carries 86 `except Exception` handlers. They keep the sim alive when an
# emitter fails on a rare turn, which is legitimate, but they also caught a Stage 2 NameError
# 70-101 times per game and let the turn continue with no animation_steps
# (reports/rebaseline-and-handler-audit.md). Every one now calls `reraise_if_strict(e)` first,
# which re-raises NameError / AttributeError / TypeError / UnboundLocalError when this is set.
#
# Default is OFF, so production is untouched; under test a typo'd name fails loudly instead of
# silently emitting a turn with no animation. `setdefault` so a test that needs the production
# behaviour can still export "0" for itself.
os.environ.setdefault("GOB_STRICT_EXCEPTIONS", "1")

# Ensure the project root is on sys.path so 'import BackEnd' succeeds
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# DB safety guard — see tests/db_guard.py. ONE module, shared by every pytest tree, so the
# two conftests cannot drift (BackEnd/tests/conftest.py's docstring warns about exactly that:
# "a guard that covers some directories reads as protection everywhere, which is worse than no
# guard at all").
#
# It is now an ALLOW-LIST. The block-list that used to live here permitted every name it had
# not been told about, which is the wrong default for a guard whose failure mode is silent
# data loss. An in-memory store is allowed whatever it is called; a real connection is allowed
# only if its name is a recognised disposable one, or GOB_ALLOW_DESTRUCTIVE_TESTS=1 is set.
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    from tests.known_failures import apply_known_failures

    apply_known_failures(items)


def pytest_configure(config):
    from tests.db_guard import enforce

    enforce(pytest, "tests/")


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
def seed_canonical_teams_for_mongomock(request):
    """Mongomock starts empty; API tests need teams.name → team_id for summarize_game_state
    keys, and anything that tips off needs five eligible bodies to seat or
    ``build_lineup_from_mongo`` raises. See tests/roster_fixtures.py, which also documents
    the one module that must keep an empty roster.
    """
    from BackEnd.db import players_collection, teams_collection

    from tests.roster_fixtures import seed_universal_rosters

    seed_universal_rosters(
        teams_collection, players_collection, module_name=request.path.stem
    )
    yield


@pytest.fixture(autouse=True)
def seed_rng_streams(request, override_auth_for_tests, seed_canonical_teams_for_mongomock):
    """Pin every RNG stream per test, so a subset run reproduces the full-suite result.

    Depends on the other two autouse fixtures ON PURPOSE, to run LAST. Seeding earlier
    would not survive them: ``seed_canonical_teams_for_mongomock`` does a variable amount
    of mongomock work depending on what the previous test left behind, and DB writes
    consume the stdlib stream (see tests/rng_fixtures.py). The test body would then start
    from a stream position that depends on its predecessors — the very coupling this
    removes.
    """
    from tests.rng_fixtures import seed_all_streams

    seed_all_streams(request.node.nodeid)
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

