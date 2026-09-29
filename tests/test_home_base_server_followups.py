"""Chapter 7 PR2 server follow-ups.

- ``/api/auth/leaderboard`` returns up to 15 ranked rows (titles stays at 5), so
  1920 can fill its taller list; the current user pins only past the cut.
- ``around_the_league._hydrate_slot`` carries ``team_slug`` and ``asset_strategy``
  so a program (including a Team Builder / custom one) loads its own banner art.

(``coach-career`` ``titles_total`` is covered in ``tests/test_home_base_data.py``.)
"""

from __future__ import annotations

import asyncio

import pytest
from bson import ObjectId

import BackEnd.api.auth_routes as auth_routes
import BackEnd.utils.around_the_league as atl
import BackEnd.utils.franchise_team_display as ftd
import BackEnd.utils.team_slug as tslug


class _FakeUsers:
    """Minimal stand-in: the leaderboard route only calls ``find({}, projection)``."""

    def __init__(self, docs):
        self._docs = docs

    def find(self, *_args, **_kwargs):
        return list(self._docs)


def _run(coro):
    return asyncio.run(coro)


def test_leaderboard_returns_up_to_15_rows_titles_stay_5(monkeypatch):
    # 20 users, geek_points strictly descending, so rank == index + 1.
    docs = [
        {"_id": f"u{i}", "username": f"coach{i:02d}", "geek_points": 2000 - i,
         "championships_total": {"national": 1}}
        for i in range(20)
    ]
    monkeypatch.setattr(auth_routes, "users_collection", _FakeUsers(docs))

    # A viewer whose rank is past the cut (u18 -> rank 19) is pinned separately.
    resp = _run(auth_routes.get_leaderboard({"user_id": "u18"}))
    assert len(resp.top) == 15
    assert len(resp.titles_top) == 5
    assert resp.current_user is not None
    assert resp.current_user.rank == 19

    # A viewer inside the top 15 is not pinned (already shown in the list).
    resp_in = _run(auth_routes.get_leaderboard({"user_id": "u03"}))
    assert resp_in.current_user is None
    monkeypatched_ids = [e.username for e in resp_in.top]
    assert monkeypatched_ids[0] == "coach00"


@pytest.mark.parametrize("asset_strategy", ["core", "generated"])
def test_hydrate_slot_carries_team_slug_and_asset_strategy(monkeypatch, asset_strategy):
    user_oid = ObjectId()
    franchise_oid = ObjectId()
    team_oid = ObjectId()

    class _FakeUsersOne:
        def find_one(self, *_a, **_k):
            return {"username": "coach", "lead_archetype": ""}

    monkeypatch.setattr(atl, "users_collection", _FakeUsersOne())
    monkeypatch.setattr(
        atl, "_resolve_franchise_doc_for_slot",
        lambda stored, uid, uoid: {"_id": franchise_oid, "week": 14, "current_season": 3},
    )
    monkeypatch.setattr(atl, "_resolve_user_team", lambda fd: ("Lancaster", str(team_oid)))
    monkeypatch.setattr(atl, "_ftd_team_display", lambda fid, tid: ("Lancaster", "#fff", "#000", 9))
    monkeypatch.setattr(atl, "_user_regular_season_record", lambda fd, tid: "12-5")
    monkeypatch.setattr(atl, "_resolve_next_opponent", lambda fd, tid: {"team_name": "Xavien", "is_away": False})
    monkeypatch.setattr(atl, "_display_username_for_highlight", lambda doc: "coach")

    # The two new sources, imported inside _hydrate_slot from their own modules.
    monkeypatch.setattr(ftd, "resolve_team_display", lambda fid, tid: {"asset_strategy": asset_strategy})
    monkeypatch.setattr(tslug, "path_slug_for_display_name", lambda name: "lancaster")

    stored = {
        "user_id": str(user_oid),
        "last_game": {"won": True, "is_away": False, "opponent": "Xavien", "user_score": 80, "opp_score": 70},
        "completed_at": "2026-09-28T12:00:00Z",
    }
    result = atl._hydrate_slot(stored)
    assert result is not None
    assert result["team_slug"] == "lancaster"
    assert result["asset_strategy"] == asset_strategy
    # The pre-existing fields still ride alongside them.
    assert result["team_name"] == "Lancaster"
    assert result["current_season"] == 3
