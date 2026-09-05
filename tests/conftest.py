import os
import sys

import pytest

# Tests select in-memory Mongo explicitly. This must happen before pytest_configure
# imports BackEnd.db; missing/failed real Mongo configuration no longer falls back.
os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")

# Ensure the project root is on sys.path so 'import BackEnd' succeeds
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# DB safety guard — block-list of databases the test suite must NEVER touch.
#
# Several existing tests (notably tests/test_franchise_complete_week.py) call
# ``db.games.delete_many({})`` / ``db.teams.delete_many({})`` /
# ``db.franchises.delete_many({})`` at setup with no internal guard. If the
# active environment (.env.local / .env / system env) points at a real DB,
# those calls wipe production data. This has happened twice — see
# memory/feedback_no_pytest.md and Tournament_Execution_System.md.
#
# This guard runs once at pytest session start (before test collection and
# before any fixture). It imports the project ``db`` and aborts the entire
# session with a non-zero exit code if ``db.name`` is on the block-list.
# Tests literally cannot run against ``gob`` or ``gob-staging``.
#
# To run tests locally, use explicit GOB_DB_MODE=mongomock (the default established
# above) or a separately configured throwaway DB whose name is not blocked.
# ---------------------------------------------------------------------------
_BLOCKED_DB_NAMES = frozenset({"gob", "gob-staging"})


def pytest_configure(config):
    try:
        from BackEnd.db import db
    except Exception:
        # If we can't even import the db module, let the regular test run surface that.
        return
    name = getattr(db, "name", None)
    if name in _BLOCKED_DB_NAMES:
        pytest.exit(
            f"\n❌ Refusing to run pytest: connected DB is {name!r}, which is on "
            f"the safety block-list {set(_BLOCKED_DB_NAMES)}.\n\n"
            f"The test suite contains destructive delete_many({{}}) calls that "
            f"have wiped this database before. Point .env.local (or your active "
            f"MONGO_URI) at a throwaway DB whose name is NOT on the block-list "
            f"before running tests.\n",
            returncode=2,
        )


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

