"""Command-center resume lookup: week type on both stores, and the unscoped fallback."""

from pathlib import Path

import pytest

from BackEnd.api import franchise_routes
from BackEnd.persistence.mongo import MongoStore
from BackEnd.persistence.sqlite import SqliteStore
from BackEnd.persistence.sqlite_schema import filter_fully_compiled
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

USER = "aaaaaaaaaaaaaaaaaaaaaaaa"
OPP = "bbbbbbbbbbbbbbbbbbbbbbbb"
FID = "cccccccccccccccccccccccc"


def _store(tmp_path: Path, kind: str):
    if kind == "mongo":
        return MongoStore(_mongomock_env(tmp_path))
    return SqliteStore(_sqlite_env(tmp_path))


def _schedule(week: int) -> list:
    rows = [[[OPP, OPP]] for _ in range(week - 1)]
    rows.append([[USER, OPP]])
    return rows


def _franchise(week: int = 5) -> dict:
    return {"_id": FID, "week": week, "schedule": _schedule(week)}


def _game(game_id: str, *, week, anchor: dict, is_final: bool = False, home=OPP, away=USER) -> dict:
    doc = {
        "_id": game_id,
        "franchise_id": FID,
        "is_final": is_final,
        "home_team_id": home,
        "away_team_id": away,
        "quarter": anchor["quarter"],
        "resume_anchor": anchor,
    }
    if week is not None:
        doc["week"] = week
    return doc


def _anchor(kind: str, quarter: int, time_remaining: int) -> dict:
    clock = "8:00" if kind == "quarter_break" else "4:00"
    return {
        "anchor_type": kind,
        "quarter": quarter,
        "clock": clock,
        "time_remaining": time_remaining,
        "resume_from_timeout": kind == "timeout",
        "timeout_next_play_type": "SIDE_INBOUND" if kind == "timeout" else None,
        "snapshot": {
            "quarter": quarter,
            "time_remaining": time_remaining,
            "clock": clock,
            "home_team_id": OPP,
            "away_team_id": USER,
            "home_score": 14,
            "away_score": 11,
            "timeout_next_play_type": "SIDE_INBOUND" if kind == "timeout" else None,
        },
    }


def _lookup(store, franchise, monkeypatch):
    monkeypatch.setattr(franchise_routes, "db", store.db)
    return franchise_routes._find_active_user_game_resume(franchise, USER)


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_week_equality_matches_real_storage(tmp_path: Path, kind: str):
    """Games store week as a JSON integer. SQLite's index column is TEXT of that integer."""
    store = _store(tmp_path, kind)
    store.games_collection.insert_many([
        _game("open", week=5, anchor=_anchor("quarter_break", 2, 480)),
        _game("final", week=5, anchor=_anchor("quarter_break", 2, 480), is_final=True),
        _game("other-week", week=4, anchor=_anchor("quarter_break", 2, 480)),
    ])
    query = franchise_routes._active_resume_game_query(FID, 5)
    assert query["week"] == 5 and isinstance(query["week"], int)
    assert filter_fully_compiled(query) is True
    hits = list(store.games_collection.find(query))
    assert [doc["_id"] for doc in hits] == ["open"]
    assert isinstance(hits[0]["week"], int)

    if kind == "sqlite":
        row = store.games_collection._conn.execute(
            "SELECT g_week, typeof(g_week), json_type(doc, '$.week') FROM games WHERE id LIKE '%open%'"
        ).fetchone()
        assert row == ("5", "text", "integer")


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
@pytest.mark.parametrize(
    "anchor_kind,quarter,remaining,expected_status",
    [
        ("quarter_break", 2, 480, "stoppage_anchor"),
        ("timeout", 1, 240, "stoppage_anchor"),
    ],
)
def test_in_progress_game_is_returned(tmp_path, monkeypatch, kind, anchor_kind, quarter, remaining, expected_status):
    store = _store(tmp_path, kind)
    store.games_collection.insert_one(
        _game("live", week=5, anchor=_anchor(anchor_kind, quarter, remaining))
    )
    calls = []
    original = store.db.games.find

    def wrapped(query, *args, **kwargs):
        calls.append(dict(query))
        return original(query, *args, **kwargs)

    monkeypatch.setattr(store.db.games, "find", wrapped)
    payload = _lookup(store, _franchise(5), monkeypatch)
    assert payload is not None
    assert payload["game_id"] == "live"
    assert payload["quarter"] == quarter
    assert payload["time_remaining"] == remaining
    assert payload["anchor_type"] == anchor_kind
    assert payload["status"] == expected_status
    assert payload["resume_from_timeout"] is (anchor_kind == "timeout")
    assert len(calls) == 1
    assert calls[0]["week"] == 5


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
@pytest.mark.parametrize("stored_week", [None, 4, "5"])
def test_fallback_when_scoped_week_misses(tmp_path, monkeypatch, kind, stored_week):
    """Missing week, a different week, or a string week (Mongo equality is typed)."""
    store = _store(tmp_path, kind)
    store.games_collection.insert_one(
        _game("live", week=stored_week, anchor=_anchor("quarter_break", 2, 480))
    )
    # A finished game on the schedule week must not satisfy the scoped seek.
    store.games_collection.insert_one(
        _game("done", week=5, anchor=_anchor("quarter_break", 2, 480), is_final=True)
    )
    calls = []
    original = store.db.games.find

    def wrapped(query, *args, **kwargs):
        calls.append(dict(query))
        return original(query, *args, **kwargs)

    monkeypatch.setattr(store.db.games, "find", wrapped)
    payload = _lookup(store, _franchise(5), monkeypatch)
    assert payload["game_id"] == "live"
    assert payload["quarter"] == 2
    assert len(calls) == 2
    assert calls[0]["week"] == 5
    assert "week" not in calls[1]
    assert filter_fully_compiled(calls[1]) is True


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_no_fallback_when_scoped_seek_returns_a_row(tmp_path, monkeypatch, kind):
    store = _store(tmp_path, kind)
    other_home = "dddddddddddddddddddddddd"
    other_away = "eeeeeeeeeeeeeeeeeeeeeeee"
    other_anchor = _anchor("quarter_break", 2, 480)
    other_anchor["snapshot"]["home_team_id"] = other_home
    other_anchor["snapshot"]["away_team_id"] = other_away
    store.games_collection.insert_many([
        _game(
            "other-open",
            week=5,
            anchor=other_anchor,
            home=other_home,
            away=other_away,
        ),
        _game("stale-user", week=3, anchor=_anchor("quarter_break", 3, 100)),
    ])
    calls = []
    original = store.db.games.find

    def wrapped(query, *args, **kwargs):
        calls.append(dict(query))
        return original(query, *args, **kwargs)

    monkeypatch.setattr(store.db.games, "find", wrapped)
    assert _lookup(store, _franchise(5), monkeypatch) is None
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_eos_week_match_and_week_mismatch_fallback(tmp_path, monkeypatch, kind):
    store = _store(tmp_path, kind)
    franchise = {
        "_id": FID,
        "week": 27,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {"round1": [{"away_team": USER, "home_team": OPP}]},
            }
        },
        "schedule": [],
    }
    store.games_collection.insert_one(
        _game("eos-live", week=27, anchor=_anchor("quarter_break", 2, 480))
    )
    payload = _lookup(store, franchise, monkeypatch)
    assert payload["game_id"] == "eos-live"
    assert payload["week"] == 27
    assert payload["quarter"] == 2

    store.games_collection.delete_many({})
    store.games_collection.insert_one(
        _game("eos-unscoped", week=None, anchor=_anchor("timeout", 1, 180))
    )
    payload = _lookup(store, franchise, monkeypatch)
    assert payload["game_id"] == "eos-unscoped"
    assert payload["anchor_type"] == "timeout"
    assert payload["quarter"] == 1
    assert payload["week"] == 27
