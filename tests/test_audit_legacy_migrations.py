from __future__ import annotations

import mongomock

from scripts.audit_legacy_migrations import audit_database


def test_legacy_audit_is_read_only_and_reports_failures():
    db = mongomock.MongoClient().db
    db.defenses.insert_one({"defense_id": "man"})
    db.teams.insert_one({"name": "Example", "player_ids": []})
    before = {name: list(db[name].find({})) for name in db.list_collection_names()}
    results = audit_database(db)
    after = {name: list(db[name].find({})) for name in db.list_collection_names()}
    assert before == after
    assert any(row["status"] == "FAIL" for row in results)
    assert any(row["status"] == "UNKNOWN" for row in results)
