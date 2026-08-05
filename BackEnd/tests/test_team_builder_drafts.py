"""Team Builder draft schema + one-per-slot keying."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from BackEnd.utils.team_builder_drafts import (
    SCHEMA_VERSION,
    discard_old_format_for_user,
    get_draft_for_slot,
    is_new_format,
    list_unfinished_drafts,
    upsert_draft,
)


class FakeCol:
    def __init__(self):
        self.docs = []

    def _match(self, query, doc):
        for k, v in query.items():
            if k == "$or":
                if not any(self._match(clause, doc) for clause in v):
                    return False
                continue
            if isinstance(v, dict):
                if "$exists" in v:
                    exists = k in doc
                    if bool(v["$exists"]) != exists:
                        return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                continue
            if doc.get(k) != v:
                return False
        return True

    def find(self, query, projection=None):
        return [d for d in self.docs if self._match(query, d)]

    def find_one(self, query, projection=None):
        for d in self.docs:
            if self._match(query, d):
                return dict(d)
        return None

    def update_one(self, query, update, upsert=False):
        for i, d in enumerate(self.docs):
            if self._match(query, d):
                d.update(update.get("$set") or {})
                self.docs[i] = d
                return
        if upsert:
            doc = {}
            doc.update(update.get("$setOnInsert") or {})
            doc.update(update.get("$set") or {})
            self.docs.append(doc)

    def delete_many(self, query):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._match(query, d)]

        class R:
            deleted_count = before - len(self.docs)

        return R()


class TestTeamBuilderDrafts(unittest.TestCase):
    def setUp(self):
        self.col = FakeCol()
        self.db = MagicMock()
        self.db.__getitem__ = MagicMock(return_value=self.col)

    def test_old_format_discarded_without_schema_version(self):
        self.col.docs.append(
            {
                "user_id": "u1",
                "replaced_object_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
                "draft_id": "draft-old-format01",
                "walk_ons": [1, 2, 3],
            }
        )
        n = discard_old_format_for_user(self.db, user_id="u1")
        self.assertEqual(n, 1)
        self.assertEqual(self.col.docs, [])

    def test_one_draft_per_slot_reuses_draft_id(self):
        a = upsert_draft(
            self.db,
            user_id="u1",
            replaced_object_id="bbbbbbbbbbbbbbbbbbbbbbbb",
            patch={"chapter": "identity", "identity": {"name": "Cascade"}},
        )
        b = upsert_draft(
            self.db,
            user_id="u1",
            replaced_object_id="bbbbbbbbbbbbbbbbbbbbbbbb",
            patch={"chapter": "roster"},
        )
        self.assertEqual(a["draft_id"], b["draft_id"])
        self.assertEqual(len(self.col.docs), 1)
        self.assertEqual(b["chapter"], "roster")
        self.assertTrue(is_new_format(b))
        self.assertEqual(b["schema_version"], SCHEMA_VERSION)

    def test_list_skips_old_and_returns_new(self):
        self.col.docs.append(
            {
                "user_id": "u1",
                "replaced_object_id": "cccccccccccccccccccccccc",
                "draft_id": "draft-legacy00001",
            }
        )
        upsert_draft(
            self.db,
            user_id="u1",
            replaced_object_id="dddddddddddddddddddddddd",
            patch={"chapter": "claim"},
        )
        rows = list_unfinished_drafts(self.db, user_id="u1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["replaced_object_id"], "dddddddddddddddddddddddd")
        self.assertIsNone(
            get_draft_for_slot(
                self.db,
                user_id="u1",
                replaced_object_id="cccccccccccccccccccccccc",
            )
        )


if __name__ == "__main__":
    unittest.main()
