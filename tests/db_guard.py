"""THE test-database safety guard. One module, imported by every pytest tree.

WHY AN ALLOW-LIST
-----------------
This replaced a DENY-LIST (``frozenset({"gob", "gob-staging"})``) that blocked two known names
and permitted everything else. A dozen-plus test files across both trees call
``delete_many({})`` / ``drop()`` on shared collections, so any database whose name was not one
of those two got emptied with nothing to stop it. ``gob-staging.defenses`` was emptied four
times in about a month before even the deny-list existed (see ``BackEnd/tests/conftest.py``).

A deny-list has to predict every dangerous name. An allow-list only has to recognise the
disposable ones, and an unrecognised name aborts. That is the right direction for a guard whose
failure mode is silent data loss.

THE CHECK IS TWO-STAGE, AND THE ORDER MATTERS
---------------------------------------------
1. **Is this store genuinely in memory?** If yes, ALLOW it whatever it is called — a mongomock
   store cannot lose anybody's data, and aborting on its name would be a false positive.
2. **Otherwise it is a real connection.** Allow ONLY a name matching the disposable pattern, or
   an explicit, loud opt-in.

MOCK-NESS IS DETECTED FROM THE OBJECT'S TYPE, NOT FROM AN ENV VAR
------------------------------------------------------------------
The signal is ``type(db).__module__`` rooted at ``mongomock`` — i.e. what the object actually
IS, checked on the live handle the tests will use.

Why not ``GOB_DB_MODE``: that is an *input* that selects which store to build, and it is
exactly the thing we are trying not to trust — a stale or mistaken value is how this goes
wrong. Why not ``USING_MONGOMOCK``: it is set as ``db_env.db_mode == "mongomock"``
(``persistence/mongo.py:96``), so it is that same env var wearing a different name. Why not the
database name: a name is a label anyone can set, which is the whole point of stage 2.

A type cannot be spoofed by a name or an env var. If the object is a
``mongomock.database.Database`` then writes go to a dict in this process and vanish on exit;
if it is a ``pymongo.database.Database`` they go to a server. That is the actual question.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple, Optional

#: Databases a destructive test suite may use. NARROW ON PURPOSE — an unrecognised name aborts.
#:
#: Derived from an inventory of every database name in the repo, its configs and its scripts
#: (see reports/test-db-allowlist.md):
#:   gob-test          the default this repo's conftests set, and what CI runs on
#:   gob-scratch-test  the script-database scratch target in tests/test_script_db.py
#: The optional suffix admits per-worker databases (``gob-test-w1``) for parallel runs without
#: admitting anything that is not already explicitly a test database.
#:
#: Deliberately NOT allowed, and each is listed with its reason in the report:
#:   gob, gob-staging               production and staging
#:   gob-remote-memory              a real remote client in persistence/sqlite.py
#:   gob-s11-league-convergence     a script scratch DB, never a pytest session DB
#:   scratch-test                   no ``gob-`` prefix; appears only as a mongomock script
#:                                  target inside a test, never as the session database
ALLOWED_DB_NAME_PATTERN = r"^gob-(?:test|scratch-test)(?:-[A-Za-z0-9._-]+)?$"
_ALLOWED_RE = re.compile(ALLOWED_DB_NAME_PATTERN)

#: Explicit, deliberate opt-in for a real throwaway database whose name is not in the pattern.
#: Absent, a real connection with an unrecognised name aborts.
ESCAPE_HATCH_ENV = "GOB_ALLOW_DESTRUCTIVE_TESTS"

#: The root package a genuine in-memory store's objects belong to.
_MOCK_ROOT = "mongomock"

#: Attributes a wrapper (e.g. the read-only proxy) may hide the real handle behind. Checked so a
#: proxied mongomock store is still recognised as in-memory.
_UNWRAP_ATTRS = ("_database", "_db", "_wrapped", "_delegate", "_collection", "_client")


class Verdict(NamedTuple):
    allowed: bool
    reason: str
    #: "mock" | "allowed-name" | "escape-hatch" | "refused"
    basis: str


def _module_root(obj: Any) -> str:
    return type(obj).__module__.split(".")[0] if obj is not None else ""


def is_in_memory_store(db: Any, client: Any = None, _depth: int = 0) -> bool:
    """True when the live handle is a genuine in-memory (mongomock) object.

    Checks the object's TYPE, then its ``client``, then a small set of wrapper attributes, so a
    proxied or wrapped mongomock store is still recognised. Bounded depth: a guard that can
    recurse forever on a self-referential proxy is its own outage.
    """
    if db is None and client is None:
        return False
    if _depth > 4:
        return False
    for obj in (db, client):
        if obj is None:
            continue
        if _module_root(obj) == _MOCK_ROOT:
            return True
    for obj in (db, client):
        if obj is None:
            continue
        inner_client = getattr(obj, "client", None)
        if inner_client is not None and inner_client is not obj:
            if _module_root(inner_client) == _MOCK_ROOT:
                return True
        for attr in _UNWRAP_ATTRS:
            inner = getattr(obj, attr, None)
            if inner is not None and inner is not obj:
                if is_in_memory_store(inner, None, _depth + 1):
                    return True
    return False


def _escape_hatch_on(env) -> bool:
    return str((env or {}).get(ESCAPE_HATCH_ENV, "")).strip() == "1"


def evaluate(db: Any, client: Any = None, env: Optional[dict] = None) -> Verdict:
    """The whole decision, as a pure function so it can be tested without a database."""
    name = getattr(db, "name", None)

    if is_in_memory_store(db, client):
        return Verdict(True, f"in-memory (mongomock) store {name!r} — nothing to lose", "mock")

    if isinstance(name, str) and _ALLOWED_RE.match(name):
        return Verdict(True, f"real connection to {name!r}, which matches the allow pattern",
                       "allowed-name")

    if _escape_hatch_on(env):
        return Verdict(
            True,
            f"real connection to {name!r} permitted by {ESCAPE_HATCH_ENV}=1",
            "escape-hatch",
        )

    return Verdict(
        False,
        f"real connection to {name!r}, which is not an allowed test database",
        "refused",
    )


def refusal_message(verdict: Verdict, tree: str) -> str:
    return (
        f"\n❌ Refusing to run pytest ({tree}): {verdict.reason}.\n\n"
        f"This suite contains destructive delete_many({{}}) / drop() calls. "
        f"gob-staging.defenses has been emptied FOUR times this way, and an empty defenses "
        f"collection also collapses sim speed ~60x.\n\n"
        f"Allowed without any opt-in:\n"
        f"  * any in-memory store (GOB_DB_MODE=mongomock) — whatever it is named\n"
        f"  * a real database whose name matches {ALLOWED_DB_NAME_PATTERN}\n"
        f"    (gob-test, gob-scratch-test, and per-worker suffixes like gob-test-w1)\n\n"
        f"If you really do mean to run destructively against this database, opt in "
        f"explicitly:\n"
        f"  {ESCAPE_HATCH_ENV}=1 pytest ...\n"
    )


def enforce(pytest_module, tree: str, env: Optional[dict] = None) -> Optional[Verdict]:
    """Session guard. Imports the live db, evaluates, and aborts the run if refused.

    Returns the verdict so a caller (or a test) can assert on it; returns None only when the db
    module cannot be imported, which is left to surface as a normal error rather than masked.
    """
    import os

    env = os.environ if env is None else env
    try:
        from BackEnd.db import client as _client, db as _db
    except Exception:
        # Can't import db — let the normal run surface that rather than masking it behind a
        # guard failure. Unchanged from the behaviour this replaced.
        return None

    verdict = evaluate(_db, _client, env)
    if not verdict.allowed:
        pytest_module.exit(refusal_message(verdict, tree), returncode=2)
    if verdict.basis == "escape-hatch":
        # LOUD on purpose: a destructive run against a real database should never be quiet.
        name = getattr(_db, "name", None)
        print(
            f"\n⚠️  {ESCAPE_HATCH_ENV}=1 — destructive tests are running against the REAL "
            f"database {name!r} ({tree}). This bypasses the name allow-list.\n",
            flush=True,
        )
    return verdict
