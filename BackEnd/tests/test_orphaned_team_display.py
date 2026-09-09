"""Reseeded `teams` orphans older franchises — never render the raw ObjectId.

`repopulate_teams_gob_staging.py` used to delete_many + insert_many, minting fresh
_ids that publish_universal_data copied into production. Franchises created before
that point keep a `user_team_object_id` with no core `teams` doc behind it, and the
mode-select card rendered the bare ObjectId as the program name.
"""
from __future__ import annotations

import unittest
from unittest import mock

from bson import ObjectId

from BackEnd.utils.franchise_team_display import resolve_team_display

ORPHANED_OID = "68c98b09674d3f9b04546b32"


class TestResolveTeamDisplayCoreMiss(unittest.TestCase):
    def test_missing_core_doc_does_not_echo_object_id_as_name(self):
        display = resolve_team_display({}, ORPHANED_OID, core_doc={})
        self.assertTrue(display["core_missing"])
        self.assertEqual(display["name"], "")
        self.assertNotEqual(display["name"], ORPHANED_OID)

    def test_missing_core_doc_leaves_name_falsy_for_or_fallbacks(self):
        # The whole class of bugs was a truthy placeholder defeating
        # `display.get("name") or <better source>` at the call sites.
        display = resolve_team_display({}, ORPHANED_OID, core_doc={})
        self.assertFalse(display.get("name") or "")

    def test_present_core_doc_is_unchanged_and_not_flagged(self):
        core = {"_id": ORPHANED_OID, "name": "Morristown", "team_id": "morristown"}
        display = resolve_team_display({}, ORPHANED_OID, core_doc=core)
        self.assertFalse(display["core_missing"])
        self.assertEqual(display["name"], "Morristown")

    def test_overlay_branch_also_reports_core_missing(self):
        franchise = {
            "_id": "507f1f77bcf86cd799439099",
            "team_builder": {
                "replaced_object_id": ORPHANED_OID,
                "name": "Hanson",
                "abbreviation": "HAN",
                "asset_strategy": "generated",
            },
        }
        display = resolve_team_display(franchise, ORPHANED_OID, core_doc={})
        self.assertTrue(display["is_custom"])
        self.assertTrue(display["core_missing"])
        # A custom overlay still names itself; only the core join is missing.
        self.assertEqual(display["name"], "Hanson")

    def test_abbreviation_never_leaks_object_id_hex(self):
        display = resolve_team_display({}, ORPHANED_OID, core_doc={})
        self.assertNotIn(display["abbreviation"].lower(), ORPHANED_OID.lower())


class TestFranchiseListCardName(unittest.TestCase):
    """`/franchise/list` must fall back to the baked `user_team_id` NAME."""

    def _summary(self, doc):
        from BackEnd.api import franchise_routes

        with mock.patch(
            "BackEnd.utils.franchise_team_display._core_team_doc",
            return_value={},
        ):
            return franchise_routes._franchise_summary_for_list(doc)

    def test_orphaned_object_id_falls_back_to_baked_team_name(self):
        summary = self._summary({
            "_id": ObjectId("507f1f77bcf86cd799439099"),
            "user_team_id": "Morristown",
            "user_team_object_id": ORPHANED_OID,
            "week": 3,
            "home_slot": 1,
        })
        self.assertEqual(summary["user_team_id"], "Morristown")
        self.assertNotEqual(summary["user_team_id"], ORPHANED_OID)

    def test_core_name_still_wins_when_teams_doc_exists(self):
        from BackEnd.api import franchise_routes

        with mock.patch(
            "BackEnd.utils.franchise_team_display._core_team_doc",
            return_value={"_id": ORPHANED_OID, "name": "Core Name", "team_id": "cn"},
        ):
            summary = franchise_routes._franchise_summary_for_list({
                "_id": ObjectId("507f1f77bcf86cd799439099"),
                "user_team_id": "Stale Baked Name",
                "user_team_object_id": ORPHANED_OID,
                "week": 3,
            })
        self.assertEqual(summary["user_team_id"], "Core Name")

    def test_no_object_id_present_is_untouched(self):
        summary = self._summary({
            "_id": ObjectId("507f1f77bcf86cd799439099"),
            "user_team_id": "Morristown",
            "week": 1,
        })
        self.assertEqual(summary["user_team_id"], "Morristown")


if __name__ == "__main__":
    unittest.main()
