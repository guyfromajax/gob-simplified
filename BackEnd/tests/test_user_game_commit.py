"""Tests for committing a finished franchise game to the user record (Phase 5).

Uses mongomock collections, monkeypatched onto the helper module, so $inc /
find_one_and_update behave like MongoDB.
"""

import unittest

import mongomock
from bson import ObjectId

import BackEnd.utils.user_game_commit as ugc
from BackEnd.utils.user_tracking import default_user_tracking


def _game(*, side="home", home_score=80, away_score=70, periods=None, by="teams"):
    g = {
        "_id": ObjectId(),
        "user_team_side": side,
        "home_team_id": "H",
        "away_team_id": "A",
        "archetype_periods": periods or {},
    }
    if by == "teams":
        g["teams"] = {
            "H": {"name": "Home", "score": home_score},
            "A": {"name": "Away", "score": away_score},
        }
    else:  # name-keyed score map, no team-object scores
        g["score"] = {"Home": home_score, "Away": away_score}
    return g


class TestCommitUserGameRecord(unittest.TestCase):
    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.db
        self.users = self.db.users
        self._orig_db, self._orig_users = ugc.db, ugc.users_collection
        ugc.db, ugc.users_collection = self.db, self.users

        self.user_oid = ObjectId()
        self.users.insert_one({"_id": self.user_oid, **default_user_tracking()})
        self.fid = ObjectId()
        self.db.franchises.insert_one({"_id": self.fid, "user_id": str(self.user_oid)})

    def tearDown(self):
        ugc.db, ugc.users_collection = self._orig_db, self._orig_users

    def _commit(self, game):
        ugc.commit_user_game_record(game, self.fid, "Home", "Away")

    def _record(self):
        return self.users.find_one({"_id": self.user_oid})["record"]

    def _archetypes(self):
        return self.users.find_one({"_id": self.user_oid})["archetypes"]

    def test_home_win(self):
        self._commit(_game(side="home", home_score=88, away_score=80))
        rec = self._record()
        self.assertEqual((rec["wins"], rec["losses"], rec["total_games"], rec["win_rate"]), (1, 0, 1, 100))

    def test_away_loss(self):
        self._commit(_game(side="away", home_score=88, away_score=80))
        rec = self._record()
        self.assertEqual((rec["wins"], rec["losses"], rec["total_games"], rec["win_rate"]), (0, 1, 1, 0))

    def test_archetypes_folded_with_total(self):
        periods = {"1": "pure_offense", "2": "pure_offense", "3": "rebounding_king", "4": "mr_unconventional"}
        self._commit(_game(side="home", periods=periods))
        a = self._archetypes()
        self.assertEqual(a["pure_offense"], 2)
        self.assertEqual(a["rebounding_king"], 1)
        self.assertEqual(a["mr_unconventional"], 1)
        self.assertEqual(a["total"], 4)

    def test_win_rate_recomputes_across_two_games(self):
        self._commit(_game(side="home", home_score=88, away_score=80))   # win
        self._commit(_game(side="home", home_score=70, away_score=80))   # loss
        rec = self._record()
        self.assertEqual((rec["wins"], rec["losses"], rec["total_games"], rec["win_rate"]), (1, 1, 2, 50))

    def test_score_map_by_name_path(self):
        self._commit(_game(side="home", home_score=90, away_score=60, by="score_map"))
        self.assertEqual(self._record()["wins"], 1)

    def test_cpu_game_no_user_side_is_noop(self):
        self._commit(_game(side=None))
        self.assertEqual(self._record(), default_user_tracking()["record"])

    def test_franchise_without_user_id_is_noop(self):
        self.db.franchises.update_one({"_id": self.fid}, {"$unset": {"user_id": ""}})
        self._commit(_game(side="home"))
        self.assertEqual(self._record(), default_user_tracking()["record"])

    def test_tie_score_is_noop(self):
        self._commit(_game(side="home", home_score=80, away_score=80))
        self.assertEqual(self._record(), default_user_tracking()["record"])

    def test_discount_fields_untouched(self):
        self._commit(_game(side="home"))
        rec = self._record()
        self.assertEqual(rec["discount_wins"], 0)
        self.assertEqual(rec["discount_losses"], 0)


if __name__ == "__main__":
    unittest.main()
