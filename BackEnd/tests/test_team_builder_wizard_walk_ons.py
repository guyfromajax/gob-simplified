"""Idempotent wizard walk-ons keyed on draft + slot."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from BackEnd.constants.team_builder_budget import core12_total
from BackEnd.utils.team_builder_roster import get_or_create_wizard_walk_ons


class TestWizardWalkOnsIdempotent(unittest.TestCase):
    def test_three_calls_same_draft_slot_return_identical_ids_and_attrs(self):
        stored = {}

        class FakeCol:
            def find_one(self, query, projection=None):
                key = (
                    query.get("user_id"),
                    query.get("replaced_object_id"),
                    query.get("schema_version"),
                )
                doc = stored.get(key)
                if not doc:
                    return None
                if projection:
                    return {k: doc[k] for k in projection if k in doc}
                return doc

            def update_one(self, query, update, upsert=False):
                key = (
                    query.get("user_id"),
                    query.get("replaced_object_id"),
                    query.get("schema_version"),
                )
                doc = stored.get(key, {})
                doc.update(query)
                doc.update(update.get("$set") or {})
                if key not in stored and "$setOnInsert" in update:
                    doc.update(update["$setOnInsert"])
                stored[key] = doc

        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=FakeCol())

        kwargs = dict(
            user_id="user-1",
            replaced_object_id="69a6fcb68d2c56aa82e48a65",
            draft_id="draft-abc-12345",
        )
        a = get_or_create_wizard_walk_ons(db, **kwargs)
        b = get_or_create_wizard_walk_ons(db, **kwargs)
        c = get_or_create_wizard_walk_ons(db, **kwargs)

        self.assertEqual(len(a), 3)
        ids = [p["wizard_player_id"] for p in a]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual([p["wizard_player_id"] for p in b], ids)
        self.assertEqual([p["wizard_player_id"] for p in c], ids)
        self.assertEqual(
            [core12_total(p.get("attributes")) for p in a],
            [core12_total(p.get("attributes")) for p in b],
        )
        self.assertEqual(a[0]["attributes"], b[0]["attributes"])
        self.assertEqual(a[0]["first_name"], c[0]["first_name"])

    def test_different_slot_draws_new_walk_ons(self):
        stored = {}

        class FakeCol:
            def find_one(self, query, projection=None):
                key = (
                    query.get("user_id"),
                    query.get("replaced_object_id"),
                    query.get("schema_version"),
                )
                return stored.get(key)

            def update_one(self, query, update, upsert=False):
                key = (
                    query.get("user_id"),
                    query.get("replaced_object_id"),
                    query.get("schema_version"),
                )
                doc = dict(query)
                doc.update(update.get("$set") or {})
                stored[key] = doc

        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=FakeCol())

        a = get_or_create_wizard_walk_ons(
            db,
            user_id="user-1",
            replaced_object_id="aaaaaaaaaaaaaaaaaaaaaaaa",
            draft_id="draft-1",
        )
        b = get_or_create_wizard_walk_ons(
            db,
            user_id="user-1",
            replaced_object_id="bbbbbbbbbbbbbbbbbbbbbbbb",
            draft_id="draft-1",
        )
        self.assertNotEqual(
            [p["wizard_player_id"] for p in a],
            [p["wizard_player_id"] for p in b],
        )


if __name__ == "__main__":
    unittest.main()
