from io import StringIO
from pathlib import Path

import mongomock
import pytest

from BackEnd.script_db import (
    _CLIENT_MUTATORS,
    _COLLECTION_MUTATORS,
    _DATABASE_MUTATORS,
    ScriptDatabaseError,
    ScriptWriteBlocked,
    connect_script_database,
    connect_production_cluster_scratch_database,
)


def _uri(db_name: str) -> str:
    return f"mongodb://example.invalid/{db_name}"


def _fake_factory(_uri_value: str, **_kwargs):
    return mongomock.MongoClient()


def test_explicit_target_must_match_uri_name_and_environment(tmp_path: Path):
    with pytest.raises(ScriptDatabaseError, match="target mismatch"):
        connect_script_database(
            target="gob-staging",
            access="read",
            pristine_env={
                "ENVIRONMENT": "staging",
                "MONGO_URI": _uri("gob"),
                "MONGO_DB_NAME": "gob-staging",
            },
            repo_root=tmp_path,
            client_factory=_fake_factory,
            output=StringIO(),
        )


def test_local_staging_uses_only_repo_env_local(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "ENVIRONMENT=production\nMONGO_URI=mongodb://example.invalid/gob\nMONGO_DB_NAME=gob\n"
    )
    with pytest.raises(ScriptDatabaseError, match="no .env fallback"):
        connect_script_database(
            target="gob-staging",
            access="read",
            pristine_env={},
            repo_root=tmp_path,
            client_factory=_fake_factory,
            output=StringIO(),
        )

    (tmp_path / ".env.local").write_text(
        "ENVIRONMENT=development\n"
        f"MONGO_URI={_uri('gob-staging')}\n"
        "MONGO_DB_NAME=gob-staging\n"
    )
    connection = connect_script_database(
        target="gob-staging",
        access="read",
        pristine_env={},
        repo_root=tmp_path,
        client_factory=_fake_factory,
        output=StringIO(),
    )
    assert connection.source.endswith(".env.local")
    connection.close()


def test_dual_target_tool_can_force_independent_local_staging_config(tmp_path: Path):
    (tmp_path / ".env.local").write_text(
        "ENVIRONMENT=development\n"
        f"MONGO_URI={_uri('gob-staging')}\n"
        "MONGO_DB_NAME=gob-staging\n"
    )
    connection = connect_script_database(
        target="gob-staging",
        access="write",
        pristine_env={
            "ENVIRONMENT": "production",
            "MONGO_URI": _uri("gob"),
            "MONGO_DB_NAME": "gob",
            "GOB_DB_ACCESS": "read",
        },
        repo_root=tmp_path,
        client_factory=_fake_factory,
        output=StringIO(),
        force_local_staging=True,
    )
    assert connection.target == "gob-staging"
    assert connection.environment == "development"
    assert connection.source.endswith(".env.local")
    connection.close()


@pytest.mark.parametrize("access", ["read", "write"])
def test_production_requires_matching_process_authorization(access: str, tmp_path: Path):
    base = {
        "ENVIRONMENT": "production",
        "MONGO_URI": _uri("gob"),
        "MONGO_DB_NAME": "gob",
    }
    with pytest.raises(ScriptDatabaseError, match=f"GOB_DB_ACCESS={access}"):
        connect_script_database(
            target="gob",
            access=access,
            pristine_env=base,
            repo_root=tmp_path,
            client_factory=_fake_factory,
            output=StringIO(),
        )

    connection = connect_script_database(
        target="gob",
        access=access,
        pristine_env={**base, "GOB_DB_ACCESS": access},
        repo_root=tmp_path,
        client_factory=_fake_factory,
        output=StringIO(),
    )
    assert connection.target == "gob"
    connection.close()


def test_destructive_production_write_requires_target_confirmation(tmp_path: Path):
    env = {
        "ENVIRONMENT": "production",
        "MONGO_URI": _uri("gob"),
        "MONGO_DB_NAME": "gob",
        "GOB_DB_ACCESS": "write",
    }
    with pytest.raises(ScriptDatabaseError, match="--confirm-db gob"):
        connect_script_database(
            target="gob",
            access="write",
            destructive=True,
            pristine_env=env,
            repo_root=tmp_path,
            client_factory=_fake_factory,
            output=StringIO(),
        )
    connection = connect_script_database(
        target="gob",
        access="write",
        destructive=True,
        confirm_db="gob",
        pristine_env=env,
        repo_root=tmp_path,
        client_factory=_fake_factory,
        output=StringIO(),
    )
    connection.close()


def test_read_connection_blocks_collection_database_client_and_aggregate_writes():
    connection = connect_script_database(
        target="scratch-test",
        access="read",
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "scratch-test",
        },
        output=StringIO(),
    )
    collection = connection.database["rows"]
    assert collection.find_one({}) is None
    with pytest.raises(ScriptWriteBlocked):
        collection.insert_one({"x": 1})
    with pytest.raises(ScriptWriteBlocked):
        collection.aggregate([{"$match": {}}, {"$out": "copy"}])
    with pytest.raises(ScriptWriteBlocked):
        connection.database.command("dropDatabase")
    with pytest.raises(ScriptWriteBlocked):
        connection.client.drop_database("scratch-test")
    with pytest.raises(ScriptWriteBlocked):
        connection.database["rows"].database["other"].insert_one({"x": 1})
    with pytest.raises(ScriptWriteBlocked):
        connection.client["scratch-test"]["other"].insert_one({"x": 1})
    connection.close()


def test_read_connection_blocks_every_declared_mutator():
    connection = connect_script_database(
        target="scratch-test",
        access="read",
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "scratch-test",
        },
        output=StringIO(),
    )
    collection = connection.database["rows"]
    for name in _COLLECTION_MUTATORS:
        with pytest.raises(ScriptWriteBlocked, match=name):
            getattr(collection, name)
    for name in _DATABASE_MUTATORS:
        with pytest.raises(ScriptWriteBlocked, match=name):
            getattr(connection.database, name)
    for name in _CLIENT_MUTATORS:
        with pytest.raises(ScriptWriteBlocked, match=name):
            getattr(connection.client, name)
    for terminal_stage in ({"$out": "copy"}, {"$merge": "copy"}):
        with pytest.raises(ScriptWriteBlocked, match="aggregate"):
            collection.aggregate([terminal_stage])
    connection.close()


def test_write_connection_allows_mutation_on_explicit_mongomock():
    connection = connect_script_database(
        target="scratch-test",
        access="write",
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "scratch-test",
        },
        output=StringIO(),
    )
    connection.database["rows"].insert_one({"x": 1})
    assert connection.database["rows"].count_documents({}) == 1
    connection.close()


def test_preflight_never_prints_uri_or_credentials():
    output = StringIO()
    secret_uri = "mongodb://secret-user:secret-password@example.invalid/gob-staging"
    connection = connect_script_database(
        target="gob-staging",
        access="read",
        pristine_env={
            "ENVIRONMENT": "staging",
            "MONGO_URI": secret_uri,
            "MONGO_DB_NAME": "gob-staging",
        },
        client_factory=_fake_factory,
        output=output,
    )
    rendered = output.getvalue()
    assert "secret-user" not in rendered
    assert "secret-password" not in rendered
    assert "database=gob-staging" in rendered
    assert "access=read" in rendered
    connection.close()


def test_production_cluster_scratch_never_accepts_live_target(tmp_path: Path):
    env = {
        "ENVIRONMENT": "production",
        "MONGO_URI": _uri("gob"),
        "MONGO_DB_NAME": "gob",
        "GOB_DB_ACCESS": "read",
    }
    with pytest.raises(ScriptDatabaseError, match="must not be gob"):
        connect_production_cluster_scratch_database(
            target="gob",
            access="write",
            pristine_env=env,
            client_factory=_fake_factory,
            output=StringIO(),
        )
    connection = connect_production_cluster_scratch_database(
        target="gob-scratch-test",
        access="write",
        pristine_env=env,
        client_factory=_fake_factory,
        output=StringIO(),
    )
    connection.database.rows.insert_one({"safe": True})
    assert connection.database.rows.count_documents({}) == 1
    connection.close()


def test_destructive_scratch_requires_its_exact_name(tmp_path: Path):
    env = {
        "ENVIRONMENT": "production",
        "MONGO_URI": _uri("gob"),
        "MONGO_DB_NAME": "gob",
        "GOB_DB_ACCESS": "read",
    }
    with pytest.raises(ScriptDatabaseError, match="--confirm-db gob-scratch-test"):
        connect_production_cluster_scratch_database(
            target="gob-scratch-test",
            access="write",
            destructive=True,
            pristine_env=env,
            client_factory=_fake_factory,
            output=StringIO(),
        )
