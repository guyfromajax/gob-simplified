"""§6.3b — court parameters round-trip through the team_builder overlay."""
from __future__ import annotations

import unittest
from unittest import mock

from bson import ObjectId

from BackEnd.utils.franchise_team_display import (
    normalize_court_params,
    resolve_team_display,
)


DISTINGUISHING_COURT = {
    "hardwoodStyle": "dark_light",
    "oobColor": "#112233",
    "laneColor": "#AABBCC",
    "outsideWoodColor": "#FFEEDD",
    "halfArcFillColor": "#010203",
}


class TestNormalizeCourtParams(unittest.TestCase):
    def test_absent_returns_none(self):
        self.assertIsNone(normalize_court_params(None))
        self.assertIsNone(normalize_court_params({}))
        self.assertIsNone(normalize_court_params({"hardwoodStyle": ""}))

    def test_round_trip_fields(self):
        out = normalize_court_params(DISTINGUISHING_COURT)
        self.assertEqual(out, DISTINGUISHING_COURT)

    def test_invalid_style_falls_back(self):
        out = normalize_court_params(
            {**DISTINGUISHING_COURT, "hardwoodStyle": "not_a_style"},
            primary_color="#ec1d28",
            secondary_color="#cccccc",
        )
        self.assertEqual(out["hardwoodStyle"], "medium_medium")
        self.assertEqual(out["oobColor"], "#112233")

    def test_invalid_hex_falls_back_to_team_colours(self):
        out = normalize_court_params(
            {
                "hardwoodStyle": "medium_medium",
                "oobColor": "nope",
                "laneColor": "nope",
                "outsideWoodColor": "nope",
                "halfArcFillColor": "nope",
            },
            primary_color="#ec1d28",
            secondary_color="#00ff00",
        )
        self.assertEqual(out["oobColor"], "#ec1d28")
        self.assertEqual(out["laneColor"], "#ec1d28")
        self.assertEqual(out["outsideWoodColor"], "#DBB891")
        self.assertEqual(out["halfArcFillColor"], "#00ff00")

    def test_no_image_keys(self):
        out = normalize_court_params(
            {**DISTINGUISHING_COURT, "image": "data:image/jpeg;base64,xxx", "url": "/x.jpg"}
        )
        self.assertNotIn("image", out)
        self.assertNotIn("url", out)
        self.assertEqual(set(out.keys()), set(DISTINGUISHING_COURT.keys()))


class TestResolveTeamDisplayCourt(unittest.TestCase):
    def test_overlay_court_surfaces(self):
        oid = "507f1f77bcf86cd799439011"
        franchise = {
            "_id": "507f1f77bcf86cd799439099",
            "team_builder": {
                "replaced_object_id": oid,
                "name": "Hanson",
                "abbreviation": "HAN",
                "primary_color": "#ec1d28",
                "secondary_color": "#15181f",
                "asset_strategy": "generated",
                "court": DISTINGUISHING_COURT,
            },
        }
        core = {
            "_id": oid,
            "name": "Concord",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "team_id": "concord",
        }
        display = resolve_team_display(franchise, oid, core_doc=core)
        self.assertTrue(display["is_custom"])
        self.assertEqual(display["court"], DISTINGUISHING_COURT)

    def test_legacy_overlay_omits_court(self):
        oid = "507f1f77bcf86cd799439011"
        franchise = {
            "_id": "507f1f77bcf86cd799439099",
            "team_builder": {
                "replaced_object_id": oid,
                "name": "Hanson",
                "abbreviation": "HAN",
                "primary_color": "#ec1d28",
                "secondary_color": "#15181f",
                "asset_strategy": "generated",
            },
        }
        core = {"_id": oid, "name": "Concord", "primary_color": "#111111", "team_id": "concord"}
        display = resolve_team_display(franchise, oid, core_doc=core)
        self.assertTrue(display["is_custom"])
        self.assertNotIn("court", display)


class TestEnsureFtdIdentityCache(unittest.TestCase):
    def test_heals_missing_ftd_fields_from_overlay(self):
        from BackEnd.utils import franchise_team_display as ftdisp

        oid = "507f1f77bcf86cd799439011"
        fid = "507f1f77bcf86cd799439099"
        franchise = {
            "_id": ObjectId(fid),
            "team_builder": {
                "replaced_object_id": oid,
                "name": "Hanson",
                "abbreviation": "HAN",
                "primary_color": "#ec1d28",
                "secondary_color": "#00ff00",
                "asset_strategy": "generated",
            },
        }
        core = {
            "_id": ObjectId(oid),
            "name": "Concord",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "team_id": "concord",
        }
        writes = []

        class FakeCol:
            def find_one(self, *a, **k):
                return None

            def update_one(self, filt, update):
                writes.append((filt, update))
                return None

        with mock.patch.object(ftdisp, "franchise_team_data_collection", FakeCol()), mock.patch.object(
            ftdisp, "_core_team_doc", return_value=core
        ):
            out = ftdisp.ensure_ftd_identity_cache(
                franchise,
                oid,
                ftd_doc={},  # present row, empty identity cache
                write_back=True,
            )
        self.assertEqual(out["team_name"], "Hanson")
        self.assertEqual(out["primary_color"], "#ec1d28")
        self.assertEqual(out["secondary_color"], "#00ff00")
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1]["$set"]["team_name"], "Hanson")

    def test_complete_cache_skips_write(self):
        from BackEnd.utils import franchise_team_display as ftdisp

        oid = "507f1f77bcf86cd799439011"
        franchise = {
            "_id": ObjectId("507f1f77bcf86cd799439099"),
            "team_builder": {
                "replaced_object_id": oid,
                "name": "Hanson",
                "abbreviation": "HAN",
                "primary_color": "#ec1d28",
                "secondary_color": "#00ff00",
                "asset_strategy": "generated",
            },
        }
        core = {
            "_id": ObjectId(oid),
            "name": "Concord",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "team_id": "concord",
        }
        writes = []

        class FakeCol:
            def update_one(self, *a, **k):
                writes.append(True)

        with mock.patch.object(ftdisp, "franchise_team_data_collection", FakeCol()), mock.patch.object(
            ftdisp, "_core_team_doc", return_value=core
        ):
            out = ftdisp.ensure_ftd_identity_cache(
                franchise,
                oid,
                ftd_doc={
                    "team_name": "Hanson",
                    "primary_color": "#ec1d28",
                    "secondary_color": "#00ff00",
                },
                write_back=True,
            )
        self.assertEqual(out["team_name"], "Hanson")
        self.assertEqual(writes, [])


class TestApplyRequestDeclaresCourt(unittest.TestCase):
    def test_model_accepts_court(self):
        from BackEnd.api.franchise_routes import TeamBuilderApplyRequest

        body = TeamBuilderApplyRequest(
            replaced_object_id="507f1f77bcf86cd799439011",
            name="Hanson",
            abbreviation="HAN",
            primary_color="#ec1d28",
            secondary_color="#15181f",
            court=DISTINGUISHING_COURT,
        )
        self.assertIsNotNone(body.court)
        self.assertEqual(body.court.outsideWoodColor, "#FFEEDD")
        self.assertEqual(body.court.hardwoodStyle, "dark_light")


if __name__ == "__main__":
    unittest.main()
