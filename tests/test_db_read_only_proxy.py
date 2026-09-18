import mongomock
import pytest
from bson import ObjectId

from BackEnd.db import (
    ProdWriteBlocked,
    _CLIENT_MUTATORS,
    _DATABASE_MUTATORS,
    _MUTATORS,
    _ReadOnlyClient,
    _ReadOnlyDatabase,
)
from BackEnd.env_config import resolve_database_environment
from BackEnd.persistence.guards import (
    ProdWriteBlocked as AdapterProdWriteBlocked,
    _CLIENT_MUTATORS as ADAPTER_CLIENT_MUTATORS,
    _DATABASE_MUTATORS as ADAPTER_DATABASE_MUTATORS,
    _MUTATORS as ADAPTER_MUTATORS,
    _ReadOnlyClient as AdapterReadOnlyClient,
    _ReadOnlyCollection as AdapterReadOnlyCollection,
    _ReadOnlyDatabase as AdapterReadOnlyDatabase,
)
from BackEnd.persistence.mongo import MongoStore


def test_application_read_proxy_blocks_all_declared_write_surfaces():
    raw_client = mongomock.MongoClient()
    client = _ReadOnlyClient(raw_client)
    database = _ReadOnlyDatabase(raw_client["gob"])
    collection = database["rows"]

    assert collection.find_one({}) is None
    for name in _MUTATORS:
        with pytest.raises(ProdWriteBlocked, match=name):
            getattr(collection, name)
    for name in _DATABASE_MUTATORS:
        with pytest.raises(ProdWriteBlocked, match=name):
            getattr(database, name)
    for name in _CLIENT_MUTATORS:
        with pytest.raises(ProdWriteBlocked, match=name):
            getattr(client, name)
    for stage in ({"$out": "copy"}, {"$merge": "copy"}):
        with pytest.raises(ProdWriteBlocked, match="aggregate"):
            collection.aggregate([stage])
    with pytest.raises(ProdWriteBlocked, match="command"):
        database.command("dropDatabase")
    with pytest.raises(ProdWriteBlocked):
        client["gob"]["rows"].delete_many({})


def test_db_facade_reexports_adapter_guard_objects():
    assert ProdWriteBlocked is AdapterProdWriteBlocked
    assert _MUTATORS is ADAPTER_MUTATORS
    assert _DATABASE_MUTATORS is ADAPTER_DATABASE_MUTATORS
    assert _CLIENT_MUTATORS is ADAPTER_CLIENT_MUTATORS
    assert _ReadOnlyClient is AdapterReadOnlyClient
    assert _ReadOnlyDatabase is AdapterReadOnlyDatabase


def test_adapter_read_proxy_blocks_all_declared_write_surfaces():
    raw_client = mongomock.MongoClient()
    client = AdapterReadOnlyClient(raw_client)
    database = AdapterReadOnlyDatabase(raw_client["gob"])
    collection = database["rows"]

    assert collection.find_one({}) is None
    for name in ADAPTER_MUTATORS:
        with pytest.raises(AdapterProdWriteBlocked, match=name):
            getattr(collection, name)
    for name in ADAPTER_DATABASE_MUTATORS:
        with pytest.raises(AdapterProdWriteBlocked, match=name):
            getattr(database, name)
    for name in ADAPTER_CLIENT_MUTATORS:
        with pytest.raises(AdapterProdWriteBlocked, match=name):
            getattr(client, name)
    for stage in ({"$out": "copy"}, {"$merge": "copy"}):
        with pytest.raises(AdapterProdWriteBlocked, match="aggregate"):
            collection.aggregate([stage])
    with pytest.raises(AdapterProdWriteBlocked, match="command"):
        database.command("dropDatabase")
    with pytest.raises(AdapterProdWriteBlocked):
        client["gob"]["rows"].delete_many({})


def test_adapter_store_wraps_real_mongo_collections_when_access_is_read(tmp_path):
    env = resolve_database_environment(
        pristine_env={
            "ENVIRONMENT": "production",
            "MONGO_URI": "mongodb://example.invalid/gob",
            "MONGO_DB_NAME": "gob",
            "GOB_DB_ACCESS": "read",
        },
        repo_root=tmp_path,
        target_environ={},
    )
    store = MongoStore(env)
    assert isinstance(store.db, AdapterReadOnlyDatabase)
    assert isinstance(store.games_collection, AdapterReadOnlyCollection)
    with pytest.raises(AdapterProdWriteBlocked, match="insert_one"):
        store.players_collection.insert_one({"_id": ObjectId()})
    with pytest.raises(AdapterProdWriteBlocked, match="delete_many"):
        store.delete_franchise(ObjectId())

