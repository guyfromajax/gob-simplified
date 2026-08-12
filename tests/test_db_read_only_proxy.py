import mongomock
import pytest

from BackEnd.db import (
    ProdWriteBlocked,
    _CLIENT_MUTATORS,
    _DATABASE_MUTATORS,
    _MUTATORS,
    _ReadOnlyClient,
    _ReadOnlyDatabase,
)


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

