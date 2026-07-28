"""Team Builder identity: simulate-quarter matchup must not require display-name equality."""
from types import SimpleNamespace
from unittest import TestCase

import mongomock
from bson import ObjectId

import BackEnd.utils.franchise_geek_points as fgp


def _request_side_matches_gm_team(request_name, request_id, gm_team) -> bool:
    """Mirror of api._request_side_matches_gm_team (kept local so we don't boot FastAPI)."""
    gm_tid = getattr(gm_team, "team_id", None)
    gm_name = getattr(gm_team, "name", None)
    if request_id and gm_tid and fgp.teams_match_for_franchise(request_id, gm_tid):
        return True
    if request_name and gm_name and request_name == gm_name:
        return True
    if request_name and gm_tid and fgp.teams_match_for_franchise(request_name, gm_tid):
        return True
    if request_id and gm_name and fgp.teams_match_for_franchise(request_id, gm_name):
        return True
    return False


class TestTbMatchupIdentity(TestCase):
    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.db
        self._orig_db = fgp.db
        fgp.db = self.db
        self.home_oid = ObjectId()
        self.away_oid = ObjectId()
        self.db.teams.insert_one(
            {"_id": self.home_oid, "team_id": "HARDWOOD_FIELDS", "name": "Hardwood Fields"}
        )
        self.db.teams.insert_one(
            {"_id": self.away_oid, "team_id": "RIVER_CITY", "name": "River City"}
        )

    def tearDown(self):
        fgp.db = self._orig_db

    def test_hanson_overlay_core_name_payload_matches_via_object_id(self):
        """Exact staging failure: body sends Hardwood Fields; GM.name is Hanson."""
        gm_home = SimpleNamespace(name="Hanson", team_id="HARDWOOD_FIELDS")
        gm_away = SimpleNamespace(name="River City", team_id="RIVER_CITY")

        # Name-only equality would fail (the old gate)
        self.assertNotEqual("Hardwood Fields", gm_home.name)

        self.assertTrue(
            _request_side_matches_gm_team(
                "Hardwood Fields", str(self.home_oid), gm_home
            )
        )
        self.assertTrue(
            _request_side_matches_gm_team("River City", str(self.away_oid), gm_away)
        )

    def test_hanson_display_name_payload_also_matches(self):
        gm_home = SimpleNamespace(name="Hanson", team_id="HARDWOOD_FIELDS")
        self.assertTrue(_request_side_matches_gm_team("Hanson", str(self.home_oid), gm_home))
        self.assertTrue(_request_side_matches_gm_team("Hanson", None, gm_home))

    def test_wrong_matchup_rejected(self):
        gm_home = SimpleNamespace(name="Hanson", team_id="HARDWOOD_FIELDS")
        self.assertFalse(
            _request_side_matches_gm_team("River City", str(self.away_oid), gm_home)
        )
