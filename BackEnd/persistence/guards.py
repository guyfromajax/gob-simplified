"""Production access guard — same behaviour as the historical db.py wrappers.

Ad-hoc scripts should not reach production by accident. Note that "read-only
script" is not a safe assumption in this codebase: GameManager.__init__ ->
_update_position_ratings() bulk_writes position_ratings on construction, so
merely simulating a game writes. See projects/bugs.md.
"""

from pymongo.collection import Collection


class ProdAccessBlocked(RuntimeError):
    """Raised when a process reaches production without opting in."""


class ProdWriteBlocked(RuntimeError):
    """Raised when a GOB_DB_ACCESS=read process attempts a write."""


class CatalogWriteBlocked(RuntimeError):
    """Raised when a process tries to write a bundled desktop catalog collection."""


_MUTATORS = frozenset({
    "insert_one", "insert_many", "update_one", "update_many", "replace_one",
    "delete_one", "delete_many", "bulk_write", "find_one_and_update",
    "find_one_and_replace", "find_one_and_delete", "drop", "rename",
    "create_index", "create_indexes", "drop_index", "drop_indexes",
    "create_search_index", "create_search_indexes", "update_search_index",
    "drop_search_index", "initialize_ordered_bulk_op",
    "initialize_unordered_bulk_op", "map_reduce",
})
_DATABASE_MUTATORS = frozenset({"create_collection", "drop_collection", "validate_collection"})
_CLIENT_MUTATORS = frozenset({"drop_database", "start_session"})


class _ReadOnlyCollection:
    """Delegate reads while blocking the complete supported collection write surface."""

    def __init__(self, coll):
        object.__setattr__(self, "_coll", coll)

    def __getattr__(self, name):
        if name in _MUTATORS:
            raise ProdWriteBlocked(
                f"Write '{name}' blocked on production collection "
                f"'{self._coll.name}' (GOB_DB_ACCESS=read). "
                f"Re-run with GOB_DB_ACCESS=write if the write is intended."
            )
        return getattr(self._coll, name)

    @property
    def database(self):
        return _ReadOnlyDatabase(self._coll.database)

    def aggregate(self, pipeline, *args, **kwargs):
        stages = list(pipeline)
        if any(isinstance(stage, dict) and ({"$out", "$merge"} & set(stage)) for stage in stages):
            raise ProdWriteBlocked(
                f"Write 'aggregate($out/$merge)' blocked on production collection "
                f"'{self._coll.name}' (GOB_DB_ACCESS=read)."
            )
        return self._coll.aggregate(stages, *args, **kwargs)

    def __getitem__(self, key):
        return _ReadOnlyCollection(self._coll[key])

    def __repr__(self):
        return f"<read-only {self._coll!r}>"


class _ReadOnlyDatabase:
    def __init__(self, database):
        object.__setattr__(self, "_db", database)

    def __getattr__(self, name):
        if name in _DATABASE_MUTATORS:
            raise ProdWriteBlocked(
                f"Write 'database.{name}' blocked on production (GOB_DB_ACCESS=read)."
            )
        value = getattr(self._db, name)
        return _ReadOnlyCollection(value) if isinstance(value, Collection) else value

    @property
    def client(self):
        return _ReadOnlyClient(self._db.client)

    def command(self, *_args, **_kwargs):
        raise ProdWriteBlocked(
            "Write-capable database.command blocked on production (GOB_DB_ACCESS=read)."
        )

    def __getitem__(self, key):
        return _ReadOnlyCollection(self._db[key])

    def __repr__(self):
        return f"<read-only {self._db!r}>"


class _ReadOnlyClient:
    def __init__(self, client):
        object.__setattr__(self, "_client", client)

    def close(self):
        return self._client.close()

    def __getattr__(self, name):
        if name in _CLIENT_MUTATORS:
            raise ProdWriteBlocked(
                f"Write 'client.{name}' blocked on production (GOB_DB_ACCESS=read)."
            )
        return getattr(self._client, name)

    def __getitem__(self, key):
        return _ReadOnlyDatabase(self._client[key])
