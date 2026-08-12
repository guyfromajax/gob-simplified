"""DB safety guard for the ``BackEnd/tests`` tree.

WHY THIS FILE EXISTS
--------------------
``tests/conftest.py`` carries the block-list guard whose docstring claims "Tests literally
cannot run against ``gob`` or ``gob-staging``". **That claim was false for this directory.**
A conftest only applies to its own tree, and there was none here — so anything that reached
``BackEnd/tests`` directly got no mongomock default, no ``gob-test`` default, and no abort:

* ``pytest BackEnd/tests/`` or ``pytest BackEnd``
* an IDE "run test" gutter click on a file in this directory (the likeliest repeat offender —
  it runs the open file and ignores ``pytest.ini``'s ``python_files = tests/test_*.py``)
* any full-suite sweep with a widened ``python_files``

Three files here open with unguarded ``delete_many({})`` against real collections
(``test_defense_identity``, ``test_defense_phase3_contracts``, ``test_team_builder_drafts``).
When the active env pointed at staging, that wiped it. **``gob-staging.defenses`` was emptied
four times in about a month this way.**

It is not only a data-loss bug. An empty ``defenses`` collection also collapses sim
performance ~60x, because ``defense_identity._ensure_cache`` treats an empty catalog as
"never loaded" and re-reads the whole collection on every lookup — measured at 4,664 reads
per game, 94.4% of wall time. See ``projects/Sim_Perf_Capstone.md``.

Keep this in sync with ``tests/conftest.py``. If you add a third test tree, give it a guard
too — a guard that covers some directories reads as protection everywhere, which is worse
than no guard at all.
"""

import os
import sys

import pytest

# Must happen before anything imports BackEnd.db. Mirrors tests/conftest.py.
os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

_BLOCKED_DB_NAMES = frozenset({"gob", "gob-staging"})


def pytest_configure(config):
    try:
        from BackEnd.db import db
    except Exception:
        # Can't import db — let the normal run surface that rather than masking it.
        return
    name = getattr(db, "name", None)
    if name in _BLOCKED_DB_NAMES:
        pytest.exit(
            f"\n❌ Refusing to run pytest: connected DB is {name!r}, which is on "
            f"the safety block-list {set(_BLOCKED_DB_NAMES)}.\n\n"
            f"Tests in BackEnd/tests/ contain destructive delete_many({{}}) calls. "
            f"gob-staging.defenses has been emptied FOUR times this way — and an empty "
            f"defenses collection also collapses sim speed ~60x.\n\n"
            f"Use the default in-memory mode (GOB_DB_MODE=mongomock) or point at a "
            f"throwaway DB whose name is NOT on the block-list.\n",
            returncode=2,
        )
