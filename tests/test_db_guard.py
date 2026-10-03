"""The test-database guard, tested INVERTED.

A guard that only ever passes is worthless — the deny-list it replaced "passed" every run right
up to the four times it let ``gob-staging.defenses`` be emptied. So these assert what it
REFUSES as hard as what it permits, and each rule is poison-tested in
reports/test-db-allowlist.md.

The four cases the brief requires are the first four tests below.
"""

import re

import pytest

from tests.db_guard import (
    ALLOWED_DB_NAME_PATTERN,
    ESCAPE_HATCH_ENV,
    evaluate,
    is_in_memory_store,
    refusal_message,
)


class _RealDb:
    """Stands in for a pymongo Database: a real handle whose module is NOT mongomock."""

    def __init__(self, name):
        self.name = name


class _RealClient:
    pass


class _MockDb:
    """Stands in for a mongomock Database by carrying a mongomock-rooted type module."""

    def __init__(self, name):
        self.name = name


_MockDb.__module__ = "mongomock.database"


class _MockClient:
    pass


_MockClient.__module__ = "mongomock.mongo_client"


# ── the four required cases ─────────────────────────────────────────────────


def test_aborts_on_a_real_connection_with_a_disallowed_name():
    """THE case the whole guard exists for."""
    for name in ("gob", "gob-staging", "gob-remote-memory", "prod", "", None):
        v = evaluate(_RealDb(name), _RealClient(), env={})
        assert not v.allowed, f"a real connection to {name!r} was permitted"
        assert v.basis == "refused"


def test_allows_a_mock_store_even_with_a_disallowed_name():
    """The .env.local shape: mongomock carrying a production-ish name is harmless, and
    aborting on it would be a false positive that trains people to bypass the guard."""
    for name in ("gob-staging", "gob", "gob-eog-memory", "anything-at-all"):
        v = evaluate(_MockDb(name), _MockClient(), env={})
        assert v.allowed, f"an in-memory store named {name!r} was refused"
        assert v.basis == "mock"


def test_allows_a_real_connection_with_an_allowed_name():
    for name in ("gob-test", "gob-scratch-test", "gob-test-w1", "gob-scratch-test-2"):
        v = evaluate(_RealDb(name), _RealClient(), env={})
        assert v.allowed, f"a real connection to {name!r} was refused"
        assert v.basis == "allowed-name"


def test_the_escape_hatch_works_and_is_off_by_default():
    db = _RealDb("gob-someones-throwaway")
    assert not evaluate(db, _RealClient(), env={}).allowed, "escape hatch is on by default"
    assert not evaluate(db, _RealClient(), env={ESCAPE_HATCH_ENV: "0"}).allowed
    assert not evaluate(db, _RealClient(), env={ESCAPE_HATCH_ENV: "true"}).allowed, \
        "only the exact string '1' opts in"
    v = evaluate(db, _RealClient(), env={ESCAPE_HATCH_ENV: "1"})
    assert v.allowed and v.basis == "escape-hatch"


# ── the allow pattern is narrow ─────────────────────────────────────────────


def test_the_pattern_does_not_admit_near_misses():
    """Each of these is one character or one prefix away from an allowed name."""
    for name in (
        "gob-testing",        # substring, not the name
        "gobtest",            # missing separator
        "gob-test ",          # trailing space
        " gob-test",          # leading space
        "GOB-TEST",           # case
        "scratch-test",       # no gob- prefix
        "gob-scratch",        # truncated
        "x-gob-test",         # prefixed
        "gob-test/../gob",    # path-ish
        "gob-s11-league-convergence",   # a script scratch DB, deliberately not admitted
    ):
        v = evaluate(_RealDb(name), _RealClient(), env={})
        assert not v.allowed, f"{name!r} matched the allow pattern and should not have"


def test_the_pattern_is_anchored_at_both_ends():
    assert ALLOWED_DB_NAME_PATTERN.startswith("^")
    assert ALLOWED_DB_NAME_PATTERN.endswith("$")
    assert re.compile(ALLOWED_DB_NAME_PATTERN).match("gob-test")
    assert not re.compile(ALLOWED_DB_NAME_PATTERN).match("gob-test\nnewline-smuggled")


# ── mock detection is by TYPE, not by a name or an env var ──────────────────


def test_mock_detection_cannot_be_spoofed_by_a_name():
    """A real object that merely CALLS itself mongomock is still a real object."""
    class _Liar:
        name = "mongomock"
        USING_MONGOMOCK = True
        db_mode = "mongomock"

    assert not is_in_memory_store(_Liar(), None)
    assert not evaluate(_Liar(), None, env={}).allowed


def test_mock_detection_does_not_read_the_environment():
    """GOB_DB_MODE is an input that selects the store; it is not evidence about the store."""
    real = _RealDb("gob-staging")
    v = evaluate(real, _RealClient(), env={"GOB_DB_MODE": "mongomock"})
    assert not v.allowed, "GOB_DB_MODE was trusted over the object's actual type"


def test_a_wrapped_mock_is_still_recognised():
    """The read-only proxy wraps the handle; a proxied mongomock store must still be allowed."""
    class _Proxy:
        name = "gob-staging"

        def __init__(self, inner):
            self._database = inner

    assert is_in_memory_store(_Proxy(_MockDb("gob-staging")), None)


def test_a_mock_client_alone_is_enough():
    """Some stores expose the mock only on the client handle."""
    assert is_in_memory_store(_RealDb("gob-staging"), _MockClient())


def test_detection_terminates_on_a_self_referential_proxy():
    """A guard that can hang or recurse forever is its own outage."""
    class _Loop:
        name = "gob-staging"

        def __init__(self):
            self._database = self

    assert is_in_memory_store(_Loop(), None) is False


# ── the refusal is actionable ───────────────────────────────────────────────


def test_the_refusal_message_says_how_to_proceed():
    v = evaluate(_RealDb("gob-staging"), _RealClient(), env={})
    msg = refusal_message(v, "tests/")
    assert "gob-staging" in msg
    assert ESCAPE_HATCH_ENV in msg, "the message must name the opt-in"
    assert "mongomock" in msg
    assert ALLOWED_DB_NAME_PATTERN in msg


def test_no_db_at_all_is_refused_not_allowed():
    """A missing handle must not read as 'safe'."""
    assert not evaluate(None, None, env={}).allowed
