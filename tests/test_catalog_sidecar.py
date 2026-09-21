from pathlib import Path

import pytest
from bson import ObjectId

from BackEnd.env_config import resolve_database_environment
from BackEnd.persistence.catalog import (
    CATALOG_COLLECTIONS,
    catalog_version,
    load_repo_fixture_docs,
    write_catalog_sqlite,
)
from BackEnd.persistence.guards import CatalogWriteBlocked
from BackEnd.persistence.sqlite import SqliteStore


def _sqlite_env(tmp_path: Path, catalog: Path, **extra):
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


def _fixture_catalog(path: Path) -> Path:
    write_catalog_sqlite(load_repo_fixture_docs(), path, source="repo-fixtures")
    return path


def test_two_exports_of_same_docs_are_byte_identical(tmp_path: Path):
    docs = load_repo_fixture_docs()
    first = tmp_path / "a.sqlite"
    second = tmp_path / "b.sqlite"
    write_catalog_sqlite(docs, first, source="repo-fixtures")
    write_catalog_sqlite(docs, second, source="repo-fixtures")
    assert first.read_bytes() == second.read_bytes()
    assert catalog_version(docs) == catalog_version(load_repo_fixture_docs())


def test_sqlite_store_reads_sidecar_and_save_has_no_catalog_rows(tmp_path: Path):
    catalog = _fixture_catalog(tmp_path / "catalog.sqlite")
    store = SqliteStore(_sqlite_env(tmp_path, catalog))
    assert store.plays_collection.count_documents({}) == 7
    assert store.defenses_collection.count_documents({}) == 6
    assert store.fcp_skeletons_collection.count_documents({}) >= 1
    assert store.hct_skeletons_collection.count_documents({}) >= 1
    tables = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert not (set(CATALOG_COLLECTIONS) & tables)
    stamp = store.db["save_meta"].find_one({"_id": "catalog_sidecar"})
    assert stamp is not None
    assert stamp["catalog_version"] == store.catalog_version


def test_catalog_writes_fail_loudly(tmp_path: Path):
    catalog = _fixture_catalog(tmp_path / "catalog.sqlite")
    store = SqliteStore(_sqlite_env(tmp_path, catalog))
    with pytest.raises(CatalogWriteBlocked, match="app update"):
        store.plays_collection.insert_one({"_id": "nope", "name": "illegal"})
    with pytest.raises(CatalogWriteBlocked):
        store.defenses_collection.delete_one({"_id": ObjectId()})
    with pytest.raises(CatalogWriteBlocked):
        store.fcp_skeletons_collection.update_one({"_id": "x"}, {"$set": {"a": 1}})
    with pytest.raises(CatalogWriteBlocked):
        store.hct_skeletons_collection.drop()


def test_export_refuses_without_read_access(monkeypatch):
    from BackEnd.persistence.catalog import assert_export_is_read_only

    monkeypatch.setenv("GOB_DB_ACCESS", "write")
    with pytest.raises(RuntimeError, match="GOB_DB_ACCESS=read"):
        assert_export_is_read_only()
    monkeypatch.delenv("GOB_DB_ACCESS", raising=False)
    with pytest.raises(RuntimeError, match="GOB_DB_ACCESS=read"):
        assert_export_is_read_only()


def test_missing_sidecar_path_fails(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Catalog sidecar"):
        SqliteStore(_sqlite_env(tmp_path, tmp_path / "missing.sqlite"))


def test_test_env_ignores_bundled_sidecar_unless_explicit(tmp_path: Path, monkeypatch):
    """A catalog.sqlite at bundle_root must not leak into ENVIRONMENT=test."""
    from BackEnd.runtime_paths import bundle_path

    bundled = bundle_path("catalog.sqlite")
    env = resolve_database_environment(
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(tmp_path / "save.sqlite"),
        },
        repo_root=tmp_path,
        target_environ={},
    )
    store = SqliteStore(env)
    assert store.catalog_path is None
    if bundled.is_file():
        assert store.plays_collection.count_documents({}) == 0
