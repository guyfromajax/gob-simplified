"""The committed defense catalogue seed: real documents, mongomock only, upsert only."""

import mongomock
import pytest
from bson import ObjectId

from tests.roster_fixtures import (
    CANONICAL_DEFENSE_IDS,
    canonical_defense_rows,
    seed_universal_defenses,
)


def test_export_is_the_six_real_defenses():
    rows = canonical_defense_rows()
    assert {r["defense_id"] for r in rows} == CANONICAL_DEFENSE_IDS
    assert all(isinstance(r["_id"], ObjectId) for r in rows)
    names = {r["defense_id"]: r["name"] for r in rows}
    assert names == {
        "base-man": "Base Man",
        "man-tight": "Deny Man",
        "man-loose": "Loose Man",
        "2-3-zone": "2-3 Zone",
        "3-2-zone": "3-2 Zone",
        "1-3-1-zone": "1-3-1 Zone",
    }


def test_seed_is_idempotent_and_never_removes_documents():
    coll = mongomock.MongoClient()["gob-test"]["defenses"]
    coll.insert_one({"_id": "keep-me", "defense_id": "custom"})
    seed_universal_defenses(coll)
    seed_universal_defenses(coll)
    assert coll.count_documents({}) == 7
    assert coll.find_one({"_id": "keep-me"}) is not None


def test_seed_refuses_a_real_collection():
    class NotMongomock:
        def replace_one(self, *a, **k):  # pragma: no cover - must never be reached
            raise AssertionError("wrote to a non-mongomock collection")

    with pytest.raises(RuntimeError, match="non-mongomock"):
        seed_universal_defenses(NotMongomock())
