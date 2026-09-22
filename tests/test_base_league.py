from pathlib import Path

import pytest
from bson import ObjectId

from BackEnd.env_config import resolve_database_environment
from BackEnd.persistence.base_league import (
    fixture_league_docs,
    league_version,
    write_league_sqlite,
)
from BackEnd.persistence.sqlite import SqliteStore


def _sqlite_env(tmp_path: Path, catalog: Path, **extra):
    from BackEnd.persistence.catalog import load_repo_fixture_docs, write_catalog_sqlite

    if not catalog.is_file():
        write_catalog_sqlite(load_repo_fixture_docs(), catalog, source="repo-fixtures")
    return resolve_database_environment(
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(tmp_path / "save.sqlite"),
            "GOB_CATALOG_SQLITE": str(catalog),
            **extra,
        },
        repo_root=tmp_path,
        target_environ={},
    )


def _fixture_league(path: Path) -> Path:
    write_league_sqlite(fixture_league_docs(), path, source="repo-fixtures")
    return path


def test_two_exports_of_same_docs_are_byte_identical(tmp_path: Path):
    docs = fixture_league_docs()
    first = tmp_path / "a.sqlite"
    second = tmp_path / "b.sqlite"
    write_league_sqlite(docs, first, source="repo-fixtures")
    write_league_sqlite(docs, second, source="repo-fixtures")
    assert first.read_bytes() == second.read_bytes()
    assert league_version(docs) == league_version(fixture_league_docs())


def test_export_refuses_without_read_access(monkeypatch):
    from BackEnd.persistence.base_league import assert_export_is_read_only

    monkeypatch.setenv("GOB_DB_ACCESS", "write")
    with pytest.raises(RuntimeError, match="GOB_DB_ACCESS=read"):
        assert_export_is_read_only()
    monkeypatch.delenv("GOB_DB_ACCESS", raising=False)
    with pytest.raises(RuntimeError, match="GOB_DB_ACCESS=read"):
        assert_export_is_read_only()


def test_empty_save_copies_bundled_league(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite"
    league = _fixture_league(tmp_path / "base_league.sqlite")
    store = SqliteStore(_sqlite_env(tmp_path, catalog, GOB_BASE_LEAGUE_SQLITE=str(league)))
    assert store.teams_collection.count_documents({}) == 2
    assert store.players_collection.count_documents({}) == 2
    lancaster = store.teams_collection.find_one({"name": "Test Lancaster"})
    assert lancaster is not None
    assert lancaster["mascot"] == "Pioneers"
    assert lancaster["primary_color"] == "#1a1a5c"
    player = store.players_collection.find_one({"last_name": "Guard"})
    assert player["team"] == "Test Lancaster"
    stamp = store.db["save_meta"].find_one({"_id": "base_league"})
    assert stamp is not None
    assert stamp["league_version"] == store.league_version
    assert stamp["source"] == "repo-fixtures"


def test_existing_save_is_not_overwritten(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite"
    league = _fixture_league(tmp_path / "base_league.sqlite")
    env = _sqlite_env(tmp_path, catalog, GOB_BASE_LEAGUE_SQLITE=str(league))
    first = SqliteStore(env)
    first.teams_collection.update_one(
        {"name": "Test Lancaster"},
        {"$set": {"prestige": 999}},
    )
    first.players_collection.update_one(
        {"last_name": "Guard"},
        {"$set": {"year": "Sr"}},
    )
    second = SqliteStore(env)
    assert second.teams_collection.find_one({"name": "Test Lancaster"})["prestige"] == 999
    assert second.players_collection.find_one({"last_name": "Guard"})["year"] == "Sr"
    assert second.teams_collection.count_documents({}) == 2


def test_test_env_ignores_bundled_league_unless_explicit(tmp_path: Path):
    catalog = tmp_path / "catalog.sqlite"
    store = SqliteStore(_sqlite_env(tmp_path, catalog))
    assert store.teams_collection.count_documents({}) == 0
    assert store.players_collection.count_documents({}) == 0
    assert store.db["save_meta"].find_one({"_id": "base_league"}) is None


def test_missing_league_bundle_fails_outside_test(tmp_path: Path):
    from BackEnd.persistence.catalog import load_repo_fixture_docs, write_catalog_sqlite

    catalog = tmp_path / "catalog.sqlite"
    write_catalog_sqlite(load_repo_fixture_docs(), catalog, source="repo-fixtures")
    env = resolve_database_environment(
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(tmp_path / "save.sqlite"),
            "GOB_CATALOG_SQLITE": str(catalog),
            "GOB_BASE_LEAGUE_SQLITE": str(tmp_path / "missing.sqlite"),
        },
        repo_root=tmp_path,
        target_environ={},
    )
    with pytest.raises(FileNotFoundError, match="Base league bundle"):
        SqliteStore(env)


def test_seed_uses_collection_insert_not_file_copy(tmp_path: Path):
    league = _fixture_league(tmp_path / "base_league.sqlite")
    catalog = tmp_path / "catalog.sqlite"
    store = SqliteStore(_sqlite_env(tmp_path, catalog, GOB_BASE_LEAGUE_SQLITE=str(league)))
    tables = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "teams" in tables
    assert "players" in tables
    assert "league_meta" not in tables
    mutated_id = ObjectId()
    store.teams_collection.insert_one({"_id": mutated_id, "name": "Walk-On U"})
    assert store.teams_collection.count_documents({}) == 3
