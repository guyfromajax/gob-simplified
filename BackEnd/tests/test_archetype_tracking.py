"""Tests for the per-period archetype stash (BackEnd/utils/archetype_tracking.py).

Uses a real mongomock collection so the $exists filter + dotted $set behave like
MongoDB. gm / body / team / player are lightweight fakes.
"""

import unittest

import mongomock
from bson import ObjectId

from BackEnd.utils.archetype_tracking import stash_period_archetype


class FakePlayer:
    def __init__(self, pid, attrs):
        self.player_id = pid
        self.attributes = attrs


class FakeTeam:
    def __init__(self, players):
        self._by_id = {p.player_id: p for p in players}

    def get_player_by_id(self, pid):
        return self._by_id.get(pid)


class FakeGM:
    def __init__(self, home_team, away_team, side):
        self.home_team = home_team
        self.away_team = away_team
        self.game_state = {"user_team_side": side}


class FakeBody:
    def __init__(self, **kw):
        self.franchise_id = kw.get("franchise_id", "franch1")
        self.quarter = kw.get("quarter", 1)
        self.user_team_side = kw.get("user_team_side")
        self.home_lineup = kw.get("home_lineup")
        self.away_lineup = kw.get("away_lineup")


def _profile(rb_st_iq=True):
    """Attrs that classify to rebounding_king ({RB,ST,IQ} top-3) or, if False,
    to an offense pool ({SC,SH,ID})."""
    base = {a: 1 for a in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ")}
    hot = ("RB", "ST", "IQ") if rb_st_iq else ("SC", "SH", "ID")
    for k in hot:
        base[k] = 100
    return {f"anchor_{k}": v for k, v in base.items()}


def _team_with_lineup(prefix, profile_rb_st_iq=True):
    players = [FakePlayer(f"{prefix}{i}", _profile(profile_rb_st_iq)) for i in range(1, 6)]
    lineup = {pos: f"{prefix}{i}" for i, pos in enumerate(("PG", "SG", "SF", "PF", "C"), start=1)}
    return FakeTeam(players), lineup


class TestStashPeriodArchetype(unittest.TestCase):
    def setUp(self):
        self.col = mongomock.MongoClient().db.games
        self.gid = ObjectId()
        self.col.insert_one({"_id": self.gid})
        self.home_team, self.home_lineup = _team_with_lineup("h", True)
        self.away_team, self.away_lineup = _team_with_lineup("a", True)
        self.gm = FakeGM(self.home_team, self.away_team, "home")

    def _body(self, **kw):
        kw.setdefault("home_lineup", self.home_lineup)
        kw.setdefault("away_lineup", self.away_lineup)
        return FakeBody(**kw)

    def _periods(self):
        return self.col.find_one({"_id": self.gid}).get("archetype_periods", {})

    def test_stashes_archetype_for_quarter(self):
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=1), mode="franchise",
            game_id=self.gid, games_collection=self.col,
        )
        self.assertEqual(self._periods().get("1"), "rebounding_king")

    def test_idempotent_same_quarter_not_overwritten(self):
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=1), mode="franchise",
            game_id=self.gid, games_collection=self.col,
        )
        # Re-enter Q1 with a lineup that WOULD classify differently — dedup must hold.
        other_team, other_lineup = _team_with_lineup("h", False)
        self.gm.home_team = other_team
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=1, home_lineup=other_lineup),
            mode="franchise", game_id=self.gid, games_collection=self.col,
        )
        self.assertEqual(self._periods().get("1"), "rebounding_king")  # unchanged

    def test_multiple_periods_accumulate(self):
        for q in (1, 2, 3, 4, 5):  # 4 + one OT
            stash_period_archetype(
                gm=self.gm, body=self._body(quarter=q), mode="franchise",
                game_id=self.gid, games_collection=self.col,
            )
        self.assertEqual(set(self._periods().keys()), {"1", "2", "3", "4", "5"})

    def test_non_franchise_is_noop(self):
        for m in ("single", "tournament", "scrimmage", None):
            stash_period_archetype(
                gm=self.gm, body=self._body(quarter=1), mode=m,
                game_id=self.gid, games_collection=self.col,
            )
        self.assertEqual(self._periods(), {})

    def test_incomplete_lineup_skipped(self):
        partial = dict(list(self.home_lineup.items())[:4])  # only 4 starters
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=1, home_lineup=partial),
            mode="franchise", game_id=self.gid, games_collection=self.col,
        )
        self.assertEqual(self._periods(), {})

    def test_away_side_uses_away_lineup(self):
        self.gm.game_state["user_team_side"] = "away"
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=2), mode="franchise",
            game_id=self.gid, games_collection=self.col,
        )
        self.assertEqual(self._periods().get("2"), "rebounding_king")

    def test_missing_user_side_is_noop(self):
        self.gm.game_state["user_team_side"] = None
        stash_period_archetype(
            gm=self.gm, body=self._body(quarter=1, user_team_side=None),
            mode="franchise", game_id=self.gid, games_collection=self.col,
        )
        self.assertEqual(self._periods(), {})


if __name__ == "__main__":
    unittest.main()
