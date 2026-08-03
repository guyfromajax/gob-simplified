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


class TestCustomNameJoinMap(unittest.TestCase):
    """
    Roster join path: custom display name must resolve even when FTD has no
    identity mirror (the pre-fix miss — core-name joins worked, custom missed).
    """

    def test_custom_name_joins_without_ftd_identity_fields(self):
        from BackEnd.utils import franchise_team_display as ftdisp
        from BackEnd.utils import stat_updater as su

        fid = ObjectId("507f1f77bcf86cd799439099")
        replaced = ObjectId("507f1f77bcf86cd799439011")
        other = ObjectId("507f1f77bcf86cd799439012")

        ftd_rows = [
            {"team_id": replaced},  # no team_name / colours — mirror absent
            {"team_id": other},
        ]
        team_rows = [
            {"_id": replaced, "name": "Concord", "team_id": "concord"},
            {"_id": other, "name": "Ada", "team_id": "ada"},
        ]

        class FakeFtd:
            def find(self, *a, **k):
                return list(ftd_rows)

        class FakeTeams:
            def find(self, *a, **k):
                return list(team_rows)

        with mock.patch("BackEnd.db.franchise_team_data_collection", FakeFtd()), mock.patch(
            "BackEnd.db.teams_collection", FakeTeams()
        ), mock.patch.object(
            ftdisp,
            "get_team_builder_overlay",
            return_value={
                "replaced_object_id": str(replaced),
                "name": "Hanson",
                "primary_color": "#ec1d28",
                "secondary_color": "#15181f",
                "asset_strategy": "generated",
            },
        ):
            name_to_id, _canon = su._build_franchise_team_maps_from_ftd(fid)

        self.assertEqual(name_to_id["Concord"], str(replaced))
        self.assertEqual(name_to_id["Ada"], str(other))
        self.assertEqual(
            name_to_id["Hanson"],
            str(replaced),
            "custom name must join even with no FTD identity mirror",
        )

    def test_without_overlay_custom_name_absent(self):
        """Documents the old miss: core names only when overlay is not consulted."""
        from BackEnd.utils import franchise_team_display as ftdisp
        from BackEnd.utils import stat_updater as su

        fid = ObjectId("507f1f77bcf86cd799439099")
        replaced = ObjectId("507f1f77bcf86cd799439011")

        class FakeFtd:
            def find(self, *a, **k):
                return [{"team_id": replaced}]

        class FakeTeams:
            def find(self, *a, **k):
                return [{"_id": replaced, "name": "Concord", "team_id": "concord"}]

        with mock.patch("BackEnd.db.franchise_team_data_collection", FakeFtd()), mock.patch(
            "BackEnd.db.teams_collection", FakeTeams()
        ), mock.patch.object(ftdisp, "get_team_builder_overlay", return_value=None):
            name_to_id, _ = su._build_franchise_team_maps_from_ftd(fid)

        self.assertEqual(name_to_id.get("Concord"), str(replaced))
        self.assertNotIn("Hanson", name_to_id)


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
