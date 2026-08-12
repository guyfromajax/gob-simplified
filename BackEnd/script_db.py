"""Shared database boundary for maintenance scripts.

Scripts must declare a target database and access intent. Production credentials and
authorization come from the invoking process only. This module never loads a production
dotenv file; local staging may use the repository-root `.env.local`.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any, Callable, Iterable, Mapping

from dotenv import dotenv_values
from pymongo import MongoClient

from BackEnd.env_config import EnvironmentConfigurationError, database_name_from_uri


PRODUCTION_DB = "gob"
STAGING_DB = "gob-staging"
LIVE_DATABASES = frozenset({PRODUCTION_DB, STAGING_DB})
ACCESS_MODES = frozenset({"read", "write"})


class ScriptDatabaseError(RuntimeError):
    """Unsafe or incomplete script database configuration."""


class ScriptWriteBlocked(ScriptDatabaseError):
    """A write was attempted through a read-only script connection."""


_COLLECTION_MUTATORS = frozenset(
    {
        "insert_one",
        "insert_many",
        "update_one",
        "update_many",
        "replace_one",
        "delete_one",
        "delete_many",
        "bulk_write",
        "find_one_and_update",
        "find_one_and_replace",
        "find_one_and_delete",
        "drop",
        "rename",
        "create_index",
        "create_indexes",
        "drop_index",
        "drop_indexes",
        "create_search_index",
        "create_search_indexes",
        "update_search_index",
        "drop_search_index",
        "initialize_ordered_bulk_op",
        "initialize_unordered_bulk_op",
        "map_reduce",
    }
)
_DATABASE_MUTATORS = frozenset({"create_collection", "drop_collection", "validate_collection"})
_CLIENT_MUTATORS = frozenset({"drop_database", "start_session"})


def _blocked(kind: str, name: str, target: str) -> ScriptWriteBlocked:
    return ScriptWriteBlocked(
        f"Write operation {kind}.{name} blocked on {target!r}; "
        "re-run through an explicitly authorized write connection"
    )


class ReadOnlyCollection:
    def __init__(self, collection: Any, target: str):
        object.__setattr__(self, "_collection", collection)
        object.__setattr__(self, "_target", target)

    @property
    def name(self) -> str:
        return self._collection.name

    @property
    def database(self):
        return ReadOnlyDatabase(self._collection.database, self._target)

    def with_options(self, *args: Any, **kwargs: Any):
        return ReadOnlyCollection(
            self._collection.with_options(*args, **kwargs), self._target
        )

    def aggregate(self, pipeline: Iterable[Mapping[str, Any]], *args: Any, **kwargs: Any):
        stages = list(pipeline)
        if any(isinstance(stage, Mapping) and ({"$out", "$merge"} & set(stage)) for stage in stages):
            raise _blocked("collection", "aggregate($out/$merge)", self._target)
        return self._collection.aggregate(stages, *args, **kwargs)

    def __getattr__(self, name: str):
        if name in _COLLECTION_MUTATORS:
            raise _blocked("collection", name, self._target)
        return getattr(self._collection, name)

    def __getitem__(self, key: str):
        return ReadOnlyCollection(self._collection[key], self._target)


def _looks_like_collection(value: Any) -> bool:
    return hasattr(value, "find_one") and hasattr(value, "database") and hasattr(value, "name")


class ReadOnlyDatabase:
    def __init__(self, database: Any, target: str):
        object.__setattr__(self, "_database", database)
        object.__setattr__(self, "_target", target)

    @property
    def name(self) -> str:
        return self._database.name

    @property
    def client(self):
        return ReadOnlyClient(self._database.client, self._target)

    def command(self, *_args: Any, **_kwargs: Any):
        # Mongo commands are an extensible write surface (collMod, dropDatabase,
        # createIndexes, eval-like admin actions). Read-mode scripts use collection
        # reads; command() is deliberately denied rather than maintained as an allowlist.
        raise _blocked("database", "command", self._target)

    def get_collection(self, name: str, *args: Any, **kwargs: Any):
        return ReadOnlyCollection(
            self._database.get_collection(name, *args, **kwargs), self._target
        )

    def __getattr__(self, name: str):
        if name in _DATABASE_MUTATORS:
            raise _blocked("database", name, self._target)
        value = getattr(self._database, name)
        return ReadOnlyCollection(value, self._target) if _looks_like_collection(value) else value

    def __getitem__(self, key: str):
        return ReadOnlyCollection(self._database[key], self._target)


class ReadOnlyClient:
    def __init__(self, client: Any, target: str):
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_target", target)

    def close(self) -> None:
        self._client.close()

    def get_database(self, name: str | None = None, *args: Any, **kwargs: Any):
        resolved = name or self._target
        return ReadOnlyDatabase(
            self._client.get_database(resolved, *args, **kwargs), resolved
        )

    def get_default_database(self, *args: Any, **kwargs: Any):
        database = self._client.get_default_database(*args, **kwargs)
        return ReadOnlyDatabase(database, database.name)

    def __getattr__(self, name: str):
        if name in _CLIENT_MUTATORS:
            raise _blocked("client", name, self._target)
        value = getattr(self._client, name)
        if hasattr(value, "get_collection") and hasattr(value, "name"):
            return ReadOnlyDatabase(value, value.name)
        return value

    def __getitem__(self, key: str):
        return ReadOnlyDatabase(self._client[key], key)


@dataclass
class ScriptDatabaseConnection:
    target: str
    access: str
    environment: str
    source: str
    client: Any
    database: Any
    using_mongomock: bool

    def close(self) -> None:
        self.client.close()


def _local_staging_values(repo_root: Path) -> dict[str, str]:
    path = repo_root / ".env.local"
    if not path.is_file():
        raise ScriptDatabaseError(
            f"Staging access requires process configuration or {path}; no .env fallback is allowed"
        )
    raw = dotenv_values(path)
    if raw.get("GOB_DB_ACCESS") or raw.get("GOB_DB_MODE"):
        raise ScriptDatabaseError(
            "GOB_DB_ACCESS and GOB_DB_MODE cannot be supplied by .env.local"
        )
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _expected_environment(target: str) -> frozenset[str]:
    if target == PRODUCTION_DB:
        return frozenset({"production"})
    if target == STAGING_DB:
        return frozenset({"development", "staging"})
    return frozenset({"test"})


def _validate_identity(values: Mapping[str, str], target: str) -> tuple[str, str]:
    uri = str(values.get("MONGO_URI") or "").strip()
    named = str(values.get("MONGO_DB_NAME") or "").strip()
    environment = str(values.get("ENVIRONMENT") or "").strip().lower()
    if not uri or not named or not environment:
        raise ScriptDatabaseError(
            "Real database scripts require ENVIRONMENT, MONGO_URI, and MONGO_DB_NAME"
        )
    try:
        uri_name = database_name_from_uri(uri)
    except EnvironmentConfigurationError as exc:
        raise ScriptDatabaseError(str(exc)) from exc
    identities = {target, named, uri_name}
    if len(identities) != 1:
        raise ScriptDatabaseError(
            f"Database target mismatch: requested={target!r}, MONGO_DB_NAME={named!r}, "
            f"MONGO_URI database={uri_name!r}"
        )
    allowed_environments = _expected_environment(target)
    if environment not in allowed_environments:
        raise ScriptDatabaseError(
            f"Database {target!r} requires ENVIRONMENT in {sorted(allowed_environments)}, "
            f"got {environment!r}"
        )
    return uri, environment


def _confirm_destructive_production(
    target: str,
    *,
    confirm_db: str | None,
    interactive: bool,
    input_fn: Callable[[str], str],
) -> None:
    if confirm_db == target:
        return
    if interactive:
        typed = input_fn(f"Type the production database name {target!r} to continue: ").strip()
        if typed == target:
            return
    raise ScriptDatabaseError(
        f"Destructive production access requires --confirm-db {target} or matching interactive confirmation"
    )


def connect_script_database(
    *,
    target: str,
    access: str,
    destructive: bool = False,
    confirm_db: str | None = None,
    interactive: bool = False,
    pristine_env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
    client_factory: Callable[..., Any] = MongoClient,
    output: Any = sys.stderr,
    input_fn: Callable[[str], str] = input,
    force_local_staging: bool = False,
) -> ScriptDatabaseConnection:
    """Open one explicitly targeted script database connection.

    `pristine_env` is the process environment captured by the script before any dotenv
    loading. Task 6 removes caller-owned dotenv loaders so this boundary is authoritative.
    """
    target = str(target or "").strip()
    access = str(access or "").strip().lower()
    if not target:
        raise ScriptDatabaseError("A target database is required")
    if access not in ACCESS_MODES:
        raise ScriptDatabaseError("Access intent must be 'read' or 'write'")

    pristine = dict(os.environ if pristine_env is None else pristine_env)
    root = repo_root or Path(__file__).resolve().parent.parent
    mode = str(pristine.get("GOB_DB_MODE") or "mongo").strip().lower()
    if mode not in {"mongo", "mongomock"}:
        raise ScriptDatabaseError("GOB_DB_MODE must be 'mongo' or 'mongomock'")

    if target == PRODUCTION_DB:
        authorization = str(pristine.get("GOB_DB_ACCESS") or "").strip().lower()
        if authorization != access:
            raise ScriptDatabaseError(
                f"Production {access} access requires process-level GOB_DB_ACCESS={access}"
            )
        if mode == "mongomock":
            raise ScriptDatabaseError("Production target cannot use mongomock")
        if destructive and access == "write":
            _confirm_destructive_production(
                target,
                confirm_db=confirm_db,
                interactive=interactive,
                input_fn=input_fn,
            )

    if mode == "mongomock":
        if target in LIVE_DATABASES:
            raise ScriptDatabaseError("Mongomock target must not be gob or gob-staging")
        environment = str(pristine.get("ENVIRONMENT") or "test").strip().lower()
        if environment != "test":
            raise ScriptDatabaseError("Mongomock scripts require ENVIRONMENT=test")
        import mongomock

        raw_client = mongomock.MongoClient()
        source = "explicit-mongomock"
        using_mongomock = True
    else:
        has_process_config = bool(
            str(pristine.get("MONGO_URI") or "").strip()
            or str(pristine.get("MONGO_DB_NAME") or "").strip()
        )
        if target == STAGING_DB and (force_local_staging or not has_process_config):
            local_values = _local_staging_values(root)
            if force_local_staging:
                # Dual-target tools carry production identity in the process. Do not
                # let it override the independently validated staging configuration.
                non_database_process_values = {
                    key: value
                    for key, value in pristine.items()
                    if key not in {"MONGO_URI", "MONGO_DB_NAME", "ENVIRONMENT"}
                }
                values = {**local_values, **non_database_process_values}
            else:
                values = {**local_values, **pristine}
            source = str(root / ".env.local")
        else:
            values = pristine
            source = "process"
        uri, environment = _validate_identity(values, target)
        raw_client = client_factory(uri, serverSelectionTimeoutMS=5000, connect=False)
        using_mongomock = False

    raw_database = raw_client[target]
    if access == "read":
        client: Any = ReadOnlyClient(raw_client, target)
        database: Any = ReadOnlyDatabase(raw_database, target)
    else:
        client = raw_client
        database = raw_database

    print(
        f"[DB PREFLIGHT] environment={environment} database={target} "
        f"access={access} destructive={'yes' if destructive else 'no'} "
        f"mode={'mongomock' if using_mongomock else 'mongo'} source={source}",
        file=output,
        flush=True,
    )
    return ScriptDatabaseConnection(
        target=target,
        access=access,
        environment=environment,
        source=source,
        client=client,
        database=database,
        using_mongomock=using_mongomock,
    )


def connect_production_cluster_scratch_database(
    *,
    target: str,
    access: str,
    destructive: bool = False,
    confirm_db: str | None = None,
    pristine_env: Mapping[str, str] | None = None,
    client_factory: Callable[..., Any] = MongoClient,
    output: Any = sys.stderr,
) -> ScriptDatabaseConnection:
    """Open an explicitly named non-live scratch DB on the production URI's cluster.

    The production database itself remains read-only: process configuration must carry
    ``GOB_DB_ACCESS=read``. This special boundary exists for measurement harnesses that
    clone production reference data into an isolated scratch database.
    """
    target = str(target or "").strip()
    access = str(access or "").strip().lower()
    if not target or target in LIVE_DATABASES:
        raise ScriptDatabaseError("Scratch target must be explicit and must not be gob or gob-staging")
    if not target.startswith("gob-"):
        raise ScriptDatabaseError("Scratch target must use the 'gob-' database prefix")
    if access not in ACCESS_MODES:
        raise ScriptDatabaseError("Access intent must be 'read' or 'write'")
    pristine = dict(os.environ if pristine_env is None else pristine_env)
    if str(pristine.get("GOB_DB_ACCESS") or "").strip().lower() != "read":
        raise ScriptDatabaseError(
            "Production-cluster scratch access requires process-level GOB_DB_ACCESS=read"
        )
    uri, environment = _validate_identity(pristine, PRODUCTION_DB)
    if destructive and access == "write" and confirm_db != target:
        raise ScriptDatabaseError(
            f"Destructive scratch access requires --confirm-db {target}"
        )
    raw_client = client_factory(uri, serverSelectionTimeoutMS=5000, connect=False)
    raw_database = raw_client[target]
    if access == "read":
        client: Any = ReadOnlyClient(raw_client, target)
        database: Any = ReadOnlyDatabase(raw_database, target)
    else:
        client = raw_client
        database = raw_database
    print(
        f"[DB PREFLIGHT] environment={environment} database={target} "
        f"access={access} destructive={'yes' if destructive else 'no'} "
        "mode=mongo source=production-cluster-process",
        file=output,
        flush=True,
    )
    return ScriptDatabaseConnection(
        target=target,
        access=access,
        environment=environment,
        source="production-cluster-process",
        client=client,
        database=database,
        using_mongomock=False,
    )
