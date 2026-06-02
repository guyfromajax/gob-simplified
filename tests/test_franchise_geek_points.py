import unittest

import mongomock
from bson import ObjectId

import BackEnd.utils.franchise_geek_points as fgp


class TestFranchiseGeekPoints(unittest.TestCase):
    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.db
        self.users = self.db.users
        self._orig_db = fgp.db
        self._orig_users = fgp.users_collection
        self._orig_randint = fgp.random.randint
        fgp.db = self.db
        fgp.users_collection = self.users

        self.user_oid = ObjectId()
        self.team_oid = ObjectId()
        self.users.insert_one({"_id": self.user_oid, "geek_points": 0})
        self.db.teams.insert_one({"_id": self.team_oid, "team_id": "HOME"})

    def tearDown(self):
        fgp.db = self._orig_db
        fgp.users_collection = self._orig_users
        fgp.random.randint = self._orig_randint

    def _user(self):
        return self.users.find_one({"_id": self.user_oid})

    def test_non_bulk_win_doubles_base_award(self):
        fgp.random.randint = lambda _lo, _hi: 10

        fgp.maybe_award_franchise_win_geek_points(
            owner_user_id=str(self.user_oid),
            user_team_id_str=str(self.team_oid),
            winner_team_id=str(self.team_oid),
            week=1,
            eos_game_meta=None,
            bulk_sim_used=False,
        )

        user = self._user()
        self.assertEqual(user["geek_points"], 20)
        self.assertEqual(user["geek_points_by_team"]["HOME"], 20)

    def test_bulk_win_keeps_base_award(self):
        fgp.random.randint = lambda _lo, _hi: 10

        fgp.maybe_award_franchise_win_geek_points(
            owner_user_id=str(self.user_oid),
            user_team_id_str=str(self.team_oid),
            winner_team_id=str(self.team_oid),
            week=1,
            eos_game_meta=None,
            bulk_sim_used=True,
        )

        user = self._user()
        self.assertEqual(user["geek_points"], 10)
        self.assertEqual(user["geek_points_by_team"]["HOME"], 10)

    def test_non_bulk_loss_doubles_base_award(self):
        fgp.random.randint = lambda _lo, _hi: 2
        opponent_oid = ObjectId()
        self.db.teams.insert_one({"_id": opponent_oid, "team_id": "AWAY"})

        fgp.maybe_award_franchise_loss_geek_points(
            owner_user_id=str(self.user_oid),
            user_team_id_str=str(self.team_oid),
            winner_team_id=str(opponent_oid),
            participant_team_ids=(str(self.team_oid), str(opponent_oid)),
            bulk_sim_used=False,
        )

        user = self._user()
        self.assertEqual(user["geek_points"], 4)
        self.assertEqual(user["geek_points_by_team"]["HOME"], 4)

    def test_bulk_loss_keeps_base_award(self):
        fgp.random.randint = lambda _lo, _hi: 2
        opponent_oid = ObjectId()
        self.db.teams.insert_one({"_id": opponent_oid, "team_id": "AWAY"})

        fgp.maybe_award_franchise_loss_geek_points(
            owner_user_id=str(self.user_oid),
            user_team_id_str=str(self.team_oid),
            winner_team_id=str(opponent_oid),
            participant_team_ids=(str(self.team_oid), str(opponent_oid)),
            bulk_sim_used=True,
        )

        user = self._user()
        self.assertEqual(user["geek_points"], 2)
        self.assertEqual(user["geek_points_by_team"]["HOME"], 2)


if __name__ == "__main__":
    unittest.main()
