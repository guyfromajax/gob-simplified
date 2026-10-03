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

The guard itself now lives in ``tests/db_guard.py`` and is imported by BOTH conftests, so
there is nothing left to keep in sync. If you add a third test tree, import the same module —
a guard that covers some directories reads as protection everywhere, which is worse than no
guard at all.
"""

import os
import sys

import pytest

# Must happen before anything imports BackEnd.db. Mirrors tests/conftest.py.
os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def pytest_configure(config):
    # THE guard lives in tests/db_guard.py and is shared with tests/conftest.py, so the two
    # trees cannot drift apart. The sys.path insert above is what makes it importable from
    # here. It is an ALLOW-LIST: see that module for why.
    from tests.db_guard import enforce

    enforce(pytest, "BackEnd/tests/")
