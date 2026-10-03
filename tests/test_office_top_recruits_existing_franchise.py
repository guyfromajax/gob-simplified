"""Top Recruits on a franchise created before the Watchlist side existed (2026-10-03).

Jamie's online franchise showed no year and an empty Watchlist with starred recruits right
after polish/v3-office merged. The stored data was checked read-only on gob-staging: an
older franchise's recruit documents carry ``year`` as the full word ("Junior", "JH", ...)
exactly as a new franchise's do, its ``recruiting_watchlist`` is a list of recruit-id
strings on the franchise document, and its only extra key is ``development``. This pins
that the Office route builds both from that shape, on both stores, and always answers with
a ``watchlist`` block (so the page can tell "empty" from "not sent").
"""

from __future__ import annotations

import pytest
from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.persistence import create_store
from tests.test_career_data import _mongomock_env, _sqlite_env

USER = "t50"


def _recruit(rid: str, name: str, rt: int, region: str, year: str, *, older: bool, lean: str | None = None) -> dict:
    """A recruit document with the keys a stored one has (staging, both generations)."""
    doc = {
        "recruit_id": rid,
        "name": name,
        "Home Region": region,
        "Lean": {"1": lean, "2": None, "3": None},
        "archetype": "Slasher",
        "attributes": {"SC": 50, "SH": 50},
        "entry_tier": "B",
        "height": 76,
        "weight": 190,
        "image_id": rid,
        "position_intent": "SF",
        "position_ratings": {"SF": rt, "PF": rt - 4},
        "potential_factor": 1.0,
        "ps_season_stats": {},
        "training_focus": None,
        "training_position": None,
        "year": year,
    }
    if older:
        doc["development"] = {"seasons": 1}
    return doc


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    s = create_store(env)
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", s.franchise_players_data_collection)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", s.franchise_recruits_data_collection)
    return s


def _seed(store, *, older: bool) -> str:
    fid = str(ObjectId())
    rows = [
        _recruit("r1", "Region One", 91, "B", "Junior", older=older, lean=USER),
        _recruit("r2", "Region Two", 85, "B", "JH", older=older, lean="t9"),
        _recruit("r3", "Region Three", 80, "B", "Sophomore", older=older),
        _recruit("w1", "Far Watched", 96, "E", "Freshman", older=older, lean="t9"),
        _recruit("w2", "Far Watched Two", 70, "D", "JH", older=older),
        _recruit("x1", "Far Unwatched", 99, "F", "Junior", older=older),
    ]
    for row in rows:
        store.franchise_recruits_data_collection.insert_one(dict(row, franchise_id=fid))
    return fid


def _blocks(fid: str, franchise_extra: dict, week: int = 12):
    franchise = {"_id": ObjectId(fid), "user_id": "u1", "current_season": 2, "week": week, "schedule": []}
    franchise.update(franchise_extra)
    response = {"user_conference": 3, "user_region": "B", "rankings": [],
                "team_name_map": {"t9": "Team 9", USER: "Lancaster"}, "next_game_summary": None}
    _preview, recruits = franchise_routes._office_preview_blocks(response, franchise, USER, week, [])
    return recruits


@pytest.mark.parametrize("older", [True, False], ids=["older-franchise", "new-franchise"])
def test_rows_carry_the_year_and_the_watchlist_is_the_franchises_own(store, older):
    fid = _seed(store, older=older)
    recruits = _blocks(fid, {"recruiting_watchlist": ["w2", "r2", "w1"]})

    # Top: the region's recruits, each with its year abbreviated.
    assert [(row["recruit_id"], row["year"]) for row in recruits["rows"]] == [
        ("r1", "JR"), ("r2", "JH"), ("r3", "SO"),
    ]
    assert recruits["rows"][0]["lean_is_user"] is True
    # Watchlist: the starred recruits from any region, best first, with their years.
    assert recruits["watchlist"]["count"] == 3
    assert [(row["recruit_id"], row["year"], row["lean_team_name"]) for row in recruits["watchlist"]["rows"]] == [
        ("w1", "FR", "Team 9"), ("r2", "JH", "Team 9"), ("w2", "JH", None),
    ]


def test_an_older_and_a_new_franchise_answer_the_same(store):
    older = _blocks(_seed(store, older=True), {"recruiting_watchlist": ["w1", "r2"]})
    newer = _blocks(_seed(store, older=False), {"recruiting_watchlist": ["w1", "r2"]})
    assert older == newer


@pytest.mark.parametrize("extra", [{}, {"recruiting_watchlist": []}, {"recruiting_watchlist": None}],
                         ids=["no-field", "empty-list", "null"])
def test_nothing_starred_is_an_empty_block_never_a_missing_one(store, extra):
    """This server always answers with a watchlist block: empty means empty."""
    recruits = _blocks(_seed(store, older=True), extra)
    assert recruits["watchlist"] == {"count": 0, "rows": []}
    assert len(recruits["rows"]) == 3


def test_a_starred_recruit_who_is_gone_is_not_listed(store):
    recruits = _blocks(_seed(store, older=True), {"recruiting_watchlist": ["signed-elsewhere", "w1"]})
    assert recruits["watchlist"]["count"] == 1
    assert [row["recruit_id"] for row in recruits["watchlist"]["rows"]] == ["w1"]
