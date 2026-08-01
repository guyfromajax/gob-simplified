"""Team Builder Phase 0: identity is core; display stays at the response edge.

Matchup gate is strict name equality on TeamManager.name (core). Display names
must never be used as request home_team/away_team or score keys.
"""
from types import SimpleNamespace
from unittest import TestCase

import mongomock
from bson import ObjectId

import BackEnd.utils.franchise_geek_points as fgp


def _strict_matchup_matches(body, gm) -> bool:
    """Mirror of simulate-quarter strict gate (core names only)."""
    return body.home_team == gm.home_team.name and body.away_team == gm.away_team.name


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

    def test_strict_gate_accepts_core_names(self):
        """Payload and GM both use core names — gate passes (TB overlay on display_name only)."""
        gm = SimpleNamespace(
            home_team=SimpleNamespace(name="Hardwood Fields", display_name="Hanson", team_id="HARDWOOD_FIELDS"),
            away_team=SimpleNamespace(name="River City", display_name="River City", team_id="RIVER_CITY"),
        )
        body = SimpleNamespace(
            home_team="Hardwood Fields",
            away_team="River City",
            home_id=str(self.home_oid),
            away_id=str(self.away_oid),
        )
        self.assertTrue(_strict_matchup_matches(body, gm))

    def test_strict_gate_rejects_display_name_payload(self):
        """Display name in home_team must fail — that is the leak this phase closes."""
        gm = SimpleNamespace(
            home_team=SimpleNamespace(name="Hardwood Fields", display_name="Hanson", team_id="HARDWOOD_FIELDS"),
            away_team=SimpleNamespace(name="River City", display_name="River City", team_id="RIVER_CITY"),
        )
        body = SimpleNamespace(
            home_team="Hanson",
            away_team="River City",
            home_id=str(self.home_oid),
            away_id=str(self.away_oid),
        )
        self.assertFalse(_strict_matchup_matches(body, gm))

    def test_strict_gate_rejects_wrong_matchup(self):
        gm = SimpleNamespace(
            home_team=SimpleNamespace(name="Hardwood Fields", team_id="HARDWOOD_FIELDS"),
            away_team=SimpleNamespace(name="River City", team_id="RIVER_CITY"),
        )
        body = SimpleNamespace(home_team="River City", away_team="Hardwood Fields")
        self.assertFalse(_strict_matchup_matches(body, gm))

    def test_object_id_helpers_still_resolve_slot(self):
        """ObjectId/slug helpers remain for FTD/schedule — not a substitute for the gate."""
        self.assertTrue(fgp.teams_match_for_franchise(str(self.home_oid), "HARDWOOD_FIELDS"))
        self.assertTrue(fgp.teams_match_for_franchise("Hardwood Fields", "HARDWOOD_FIELDS"))
        self.assertFalse(fgp.teams_match_for_franchise("Hanson", "HARDWOOD_FIELDS"))
