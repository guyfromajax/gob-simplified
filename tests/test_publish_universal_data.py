from types import SimpleNamespace

import mongomock

import scripts.publish_universal_data as publisher


def test_publish_replaces_only_explicitly_selected_collection(monkeypatch, tmp_path):
    staging_client = mongomock.MongoClient()
    production_client = mongomock.MongoClient()
    staging_db = staging_client[publisher.STAGING_DB]
    production_db = production_client[publisher.PRODUCTION_DB]
    staging_db.recruit_sets.insert_one({"_id": "set_0001", "version": "staging"})
    staging_db.teams.insert_one({"_id": "team-a", "name": "staging team"})
    production_db.recruit_sets.insert_one({"_id": "old-set", "version": "production"})
    production_db.teams.insert_one({"_id": "team-a", "name": "production team"})

    def connection(target, **_kwargs):
        if target == publisher.STAGING_DB:
            return SimpleNamespace(database=staging_db, close=lambda: None)
        return SimpleNamespace(database=production_db, close=lambda: None)

    monkeypatch.setattr(publisher, "connect_script_database", connection)
    monkeypatch.setattr(
        publisher.sys,
        "argv",
        [
            "publish_universal_data.py",
            "--collection",
            "recruit_sets",
            "--apply",
            "--confirm-db",
            "gob",
            "--backup-dir",
            str(tmp_path),
        ],
    )

    assert publisher.main() == 0
    assert list(production_db.recruit_sets.find({})) == [
        {"_id": "set_0001", "version": "staging"}
    ]
    assert production_db.teams.find_one({"_id": "team-a"})["name"] == "production team"

    backups = list(tmp_path.glob("gob-before-publish-*/recruit_sets.json"))
    assert len(backups) == 1
    assert backups[0].stat().st_mode & 0o777 == 0o600
