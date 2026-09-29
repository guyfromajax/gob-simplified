"""Account Geek Points display names: stored / TB chrome, never reformatted."""
from __future__ import annotations

import unittest

import mongomock
from bson import ObjectId

import BackEnd.utils.franchise_team_display as ftd
from BackEnd.utils.team_builder_leak_detector import scan_json_for_replaced_name


class TestGeekPointsTeamDisplay(unittest.TestCase):
    def setUp(self):
        self.client = mongomock.MongoClient()
        self.db = self.client.db
        self._orig_teams = ftd.teams_collection
        self._orig_fr = ftd.franchises_collection
        ftd.teams_collection = self.db.teams
        ftd.franchises_collection = self.db.franchises

        self.user_id = ObjectId()
        self.bt = ObjectId()
        self.ida = ObjectId()
        self.sea = ObjectId()
        self.prov = ObjectId()
        self.db.teams.insert_many([
            {"_id": self.bt, "team_id": "BENTLEY_TRUMAN", "name": "Bentley-Truman"},
            {"_id": self.ida, "team_id": "IDA", "name": "IDA"},
            {"_id": self.sea, "team_id": "SEATTLE_AAA", "name": "Seattle AAA"},
            {"_id": self.prov, "team_id": "PROVIDENCE", "name": "Providence"},
        ])

    def tearDown(self):
        ftd.teams_collection = self._orig_teams
        ftd.franchises_collection = self._orig_fr

    def test_stored_names_keep_hyphens_and_caps(self):
        rows = ftd.resolve_geek_points_teams(
            {"BENTLEY_TRUMAN": 300, "IDA": 400, "SEATTLE_AAA": 150},
            str(self.user_id),
        )
        by_id = {r["team_id"]: r["display_name"] for r in rows}
        self.assertEqual(by_id["BENTLEY_TRUMAN"], "Bentley-Truman")
        self.assertEqual(by_id["IDA"], "IDA")
        self.assertEqual(by_id["SEATTLE_AAA"], "Seattle AAA")
        self.assertEqual(rows[0]["team_id"], "IDA")

    def test_unknown_key_is_shown_unchanged(self):
        rows = ftd.resolve_geek_points_teams({"MIDDLE_TEX": 10}, str(self.user_id))
        self.assertEqual(rows[0]["display_name"], "MIDDLE_TEX")

    def test_team_builder_overlay_is_chrome(self):
        self.db.franchises.insert_one({
            "user_id": str(self.user_id),
            "team_builder": {
                "replaced_object_id": str(self.prov),
                "name": "HA Rushmore",
                "abbreviation": "HAR",
            },
        })
        rows = ftd.resolve_geek_points_teams({"PROVIDENCE": 80}, str(self.user_id))
        self.assertEqual(rows[0]["display_name"], "HA Rushmore")
        payload = {
            "geek_points_by_team": {"PROVIDENCE": 80},
            "geek_points_teams": rows,
        }
        self.assertEqual(scan_json_for_replaced_name(payload, "Providence"), [])
