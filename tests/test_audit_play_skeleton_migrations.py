from __future__ import annotations

import mongomock

from scripts.audit_play_skeleton_migrations import audit_database


def test_play_skeleton_audit_is_read_only_and_reports_legacy_shapes():
    client = mongomock.MongoClient()
    db = client.catalog
    db.plays.insert_many([
        {
            "name": "Motion",
            "play_type": "motion",
            "skeletons": {"base_loop": {"versions": [{"version": "v0", "steps": []}]}},
        },
        {
            "name": "Set",
            "play_type": "set_play",
            "game_stats": {},
            "skeletons": {"standard": {"steps": []}, "successful": {"steps": []}},
        },
    ])
    db.fcp_skeletons.insert_one({"field": "Legacy", "variants": {"base": {"steps": []}}})
    db.hct_skeletons.insert_one({
        "name": "Standard",
        "variants": {"base": {"versions": [{"version": "v1", "steps": []}]}},
    })

    before = list(db.plays.find({}))
    report = audit_database(db)
    assert list(db.plays.find({})) == before
    assert report["plays"]["legacy_standard"] == 1
    assert report["plays"]["root_fields"]["game_stats"] == 1
    assert report["plays"]["motion_base_loop_shapes"] == {"versions-valid": 1}
    assert "old_names_still_present" in report["play_renames"]
    assert report["fcp_skeletons"]["legacy_field"] == 1
    assert report["hct_skeletons"]["variant_shapes"] == {"versions-valid": 1}
