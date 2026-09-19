import ast
from pathlib import Path

import pytest
from bson import ObjectId

from BackEnd.env_config import (
    EnvironmentConfigurationError,
    resolve_database_environment,
)
from BackEnd.persistence import create_store, get_store
from BackEnd.persistence.guards import (
    ProdAccessBlocked,
    ProdWriteBlocked,
    _ReadOnlyCollection,
    _ReadOnlyDatabase,
)
from BackEnd.persistence.mongo import MongoStore


ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_DIR = ROOT / "BackEnd" / "persistence"


def _mongomock_env(tmp_path: Path, **extra):
    pristine = {
        "GOB_DB_MODE": "mongomock",
        "ENVIRONMENT": "test",
        "MONGO_DB_NAME": "gob-test",
        **extra,
    }
    return resolve_database_environment(
        pristine_env=pristine,
        repo_root=tmp_path,
        target_environ={},
    )


def _production_env(tmp_path: Path, **extra):
    return resolve_database_environment(
        pristine_env={
            "ENVIRONMENT": "production",
            "MONGO_URI": "mongodb://example.invalid/gob",
            "MONGO_DB_NAME": "gob",
            **extra,
        },
        repo_root=tmp_path,
        target_environ={},
    )


def test_persistence_field_defaults_to_mongo(tmp_path: Path):
    config = _mongomock_env(tmp_path)
    assert config.persistence == "mongo"


def test_persistence_field_reads_pristine_env(tmp_path: Path):
    config = _mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite")
    assert config.persistence == "sqlite"


def test_unknown_persistence_value_errors(tmp_path: Path):
    with pytest.raises(EnvironmentConfigurationError, match="GOB_PERSISTENCE"):
        _mongomock_env(tmp_path, GOB_PERSISTENCE="postgres")


def test_sqlite_backend_is_not_implemented(tmp_path: Path):
    env = _mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite")
    with pytest.raises(EnvironmentConfigurationError, match="not implemented"):
        create_store(env)


def test_get_store_is_singleton():
    assert get_store() is get_store()


def test_get_store_exposes_all_legacy_collection_handles():
    store = get_store()
    expected = (
        "players_collection",
        "teams_collection",
        "games_collection",
        "tournaments_collection",
        "training_log_collection",
        "franchise_state_collection",
        "franchises_collection",
        "franchise_team_data_collection",
        "franchise_players_data_collection",
        "franchise_recruits_data_collection",
        "plays_collection",
        "defenses_collection",
        "fcp_skeletons_collection",
        "hct_skeletons_collection",
        "alpha_otps_collection",
        "access_code_requests_collection",
        "alpha_access_requests_collection",
        "users_collection",
        "password_reset_tokens_collection",
        "press_conference_sessions_collection",
        "community_highlights_collection",
        "around_the_league_collection",
        "alpha_feedback_collection",
        "eog_band_log_collection",
        "stripe_events_collection",
    )
    for name in expected:
        assert getattr(store, name) is not None, name
    assert store.db is not None
    assert store.client is not None
    assert store.USING_MONGOMOCK is True


def test_franchise_scoped_round_trip_on_mongomock(tmp_path: Path):
    store = MongoStore(_mongomock_env(tmp_path))
    fid = ObjectId()
    bundle = {
        "franchise": {"user_id": "u1", "week": 4},
        "franchise_team_data": [{"team_id": "t1", "wins": 2}],
        "franchise_players_data": [{"player_id": "p1", "season_stats": {}}],
        "franchise_recruits_data": [{"recruit_id": "r1"}],
        "games": [{"_id": "g1", "week": 4}],
        "press_conference_sessions": [{"topic": "win"}],
        "training_sessions": [{"session_type": "lift"}],
        "tournaments": [{"name": "eos"}],
        "franchise_state": [{"week": 4}],
        "eog_band_log": [{"week": 4, "record_type": "band"}],
    }
    store.write_franchise(fid, bundle)
    read = store.read_franchise(str(fid))

    assert read["franchise"]["user_id"] == "u1"
    assert read["franchise"]["_id"] == fid
    assert read["franchise_team_data"][0]["franchise_id"] == fid
    assert read["franchise_players_data"][0]["franchise_id"] == str(fid)
    assert read["franchise_recruits_data"][0]["franchise_id"] == str(fid)
    assert read["games"][0]["franchise_id"] == str(fid)
    assert read["press_conference_sessions"][0]["franchise_id"] == fid
    assert read["training_sessions"][0]["franchise_id"] == str(fid)
    assert read["tournaments"][0]["franchise_id"] == str(fid)
    assert read["franchise_state"][0]["franchise_id"] == str(fid)
    assert read["eog_band_log"][0]["franchise_id"] == str(fid)

    other = ObjectId()
    store.write_franchise(other, {
        "franchise": {"user_id": "u2"},
        "games": [{"_id": "g-other"}],
    })
    store.delete_franchise(fid)
    gone = store.read_franchise(fid)
    assert gone["franchise"] is None
    assert gone["games"] == []
    assert gone["franchise_team_data"] == []
    remaining = store.read_franchise(other)
    assert remaining["franchise"]["user_id"] == "u2"
    assert remaining["games"][0]["_id"] == "g-other"


def test_delete_franchise_mirrors_cascade_id_types(tmp_path: Path):
    store = MongoStore(_mongomock_env(tmp_path))
    fid = ObjectId()
    store.franchise_team_data_collection.insert_one({"franchise_id": fid, "team_id": "t"})
    store.franchise_players_data_collection.insert_one({"franchise_id": str(fid), "player_id": "p"})
    store.franchise_recruits_data_collection.insert_one({"franchise_id": str(fid), "recruit_id": "r"})
    store.games_collection.insert_one({"franchise_id": str(fid), "_id": "g"})
    store.press_conference_sessions_collection.insert_one({"franchise_id": str(fid)})
    store.franchises_collection.insert_one({"_id": fid, "user_id": "u"})
    store.training_log_collection.insert_one({"franchise_id": str(fid)})
    store.eog_band_log_collection.insert_one({"franchise_id": fid, "week": 1})

    store.delete_franchise(fid)

    assert store.franchise_team_data_collection.find_one({}) is None
    assert store.franchise_players_data_collection.find_one({}) is None
    assert store.franchise_recruits_data_collection.find_one({}) is None
    assert store.games_collection.find_one({}) is None
    assert store.press_conference_sessions_collection.find_one({}) is None
    assert store.franchises_collection.find_one({}) is None
    assert store.training_log_collection.find_one({}) is None
    assert store.eog_band_log_collection.find_one({}) is None


def test_adapter_refuses_production_without_opt_in(tmp_path: Path):
    with pytest.raises(ProdAccessBlocked, match="Refusing to connect to PRODUCTION"):
        MongoStore(_production_env(tmp_path))


def test_adapter_wraps_collections_when_production_read(tmp_path: Path):
    store = MongoStore(_production_env(tmp_path, GOB_DB_ACCESS="read"))
    assert isinstance(store.db, _ReadOnlyDatabase)
    assert isinstance(store.games_collection, _ReadOnlyCollection)
    with pytest.raises(ProdWriteBlocked, match="delete_many"):
        store.games_collection.delete_many({})
    with pytest.raises(ProdWriteBlocked, match="insert_one"):
        store.franchises_collection.insert_one({"_id": ObjectId()})
    # First-class franchise write must hit the same wrap — this is the
    # silent-until-prod failure mode if the adapter ever bypasses the guard.
    with pytest.raises(ProdWriteBlocked):
        store.write_franchise(ObjectId(), {"franchise": {"user_id": "blocked"}})


def test_persistence_modules_do_not_use_random():
    offenders = []
    for path in sorted(PERSISTENCE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "random" or alias.name.startswith("random."):
                        offenders.append(f"{path.name}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "random" or (node.module or "").startswith("random."):
                    names = ", ".join(alias.name for alias in node.names)
                    offenders.append(f"{path.name}:{node.lineno}: from {node.module} import {names}")
            elif isinstance(node, ast.Name) and node.id == "random":
                offenders.append(f"{path.name}:{node.lineno}: name 'random'")
    assert offenders == []
