import ast
import sqlite3
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
from BackEnd.persistence.sqlite import SqliteStore
from BackEnd.persistence.sqlite_collection import (
    NullCollection,
    RemoteUnavailable,
    SqliteCollection,
)
from BackEnd.persistence.sqlite_query import SqliteUnsupportedOperator


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


def test_sqlite_backend_is_selected(tmp_path: Path):
    env = _mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "save.sqlite"))
    store = create_store(env)
    assert isinstance(store, SqliteStore)
    assert store.USING_MONGOMOCK is False
    assert store.sqlite_path.endswith("save.sqlite")


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
    if getattr(store.DB_ENV, "persistence", "mongo") == "sqlite":
        assert store.USING_MONGOMOCK is False
        assert isinstance(store, SqliteStore)
    else:
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


def _sqlite_env(tmp_path: Path, **extra):
    return _mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "save.sqlite"), **extra)


def test_sqlite_path_reads_pristine_env(tmp_path: Path):
    config = _mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH="/tmp/franchise.db")
    assert config.sqlite_path == "/tmp/franchise.db"


def test_sqlite_franchise_scoped_round_trip(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
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
    assert read["games"][0]["franchise_id"] == str(fid)
    assert read["franchise_state"][0]["franchise_id"] == str(fid)
    assert read["eog_band_log"] == []

    other = ObjectId()
    store.write_franchise(other, {
        "franchise": {"user_id": "u2"},
        "games": [{"_id": "g-other"}],
    })
    store.delete_franchise(fid)
    gone = store.read_franchise(fid)
    assert gone["franchise"] is None
    assert gone["games"] == []
    remaining = store.read_franchise(other)
    assert remaining["franchise"]["user_id"] == "u2"
    assert remaining["games"][0]["_id"] == "g-other"


def test_sqlite_franchise_state_is_per_save_not_global(tmp_path: Path):
    """Mongo's _id=state singleton is not reproduced. State lives in this file."""
    first = SqliteStore(_mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "a.sqlite")))
    second = SqliteStore(_mongomock_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "b.sqlite")))
    first.franchise_state_collection.replace_one({"_id": "state"}, {"_id": "state", "week": 12}, upsert=True)
    assert first.franchise_state_collection.find_one({"_id": "state"})["week"] == 12
    assert second.franchise_state_collection.find_one({"_id": "state"}) is None
    fid = ObjectId()
    first.write_franchise(fid, {"franchise_state": [{"_id": "state", "week": 12}]})
    bundle = first.read_franchise(fid)
    assert bundle["franchise_state"][0]["week"] == 12
    assert second.read_franchise(fid)["franchise_state"] == []


def test_sqlite_eog_band_log_is_not_in_the_save(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    assert isinstance(store.eog_band_log_collection, NullCollection)
    store.eog_band_log_collection.insert_one({"week": 1, "record_type": "band"})
    assert store.eog_band_log_collection.find_one({}) is None
    fid = ObjectId()
    store.write_franchise(fid, {"eog_band_log": [{"week": 1}]})
    assert store.read_franchise(fid)["eog_band_log"] == []


def test_sqlite_eog_band_can_be_enabled_off_the_save(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path, GOB_EOG_BAND_ENABLED="1"))
    assert not isinstance(store.eog_band_log_collection, NullCollection)
    store.eog_band_log_collection.insert_one({"week": 2})
    assert store.eog_band_log_collection.find_one({"week": 2})["week"] == 2
    fid = ObjectId()
    store.write_franchise(fid, {"eog_band_log": [{"week": 9}]})
    assert store.read_franchise(fid)["eog_band_log"] == []


def test_sqlite_remote_collections_are_not_in_the_save_file(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    store.users_collection.insert_one({"_id": "u", "email": "a@b.c"})
    assert store.users_collection.find_one({"_id": "u"})["email"] == "a@b.c"
    import sqlite3
    store.db["feedback_submissions"].insert_one({"message": "hi"})
    names = {row[0] for row in sqlite3.connect(store.sqlite_path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "users" not in names
    assert "feedback_submissions" not in names
    assert "players" in names


def test_sqlite_read_access_blocks_local_writes(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path, GOB_DB_ACCESS="read"))
    assert store.DB_ACCESS == "read"
    assert isinstance(store.games_collection, _ReadOnlyCollection)
    with pytest.raises(ProdWriteBlocked):
        store.games_collection.insert_one({"_id": "g"})
    with pytest.raises(ProdWriteBlocked):
        store.write_franchise(ObjectId(), {"franchise": {"user_id": "blocked"}})


def test_sqlite_never_refuses_as_production_mongo(tmp_path: Path):
    env = _production_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "local.sqlite"))
    store = SqliteStore(env)
    assert store.DB_ACCESS == "write"
    store.games_collection.insert_one({"_id": "ok"})
    assert store.games_collection.find_one({"_id": "ok"})["_id"] == "ok"


def test_sqlite_refuses_remote_collections_outside_test(tmp_path: Path):
    env = _production_env(tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "local.sqlite"))
    store = SqliteStore(env)
    assert isinstance(store.users_collection, RemoteUnavailable)
    with pytest.raises(RuntimeError, match="refuses remote collection 'users'"):
        store.users_collection.find_one({"email": "a@b.c"})
    with pytest.raises(RuntimeError, match="refuses remote collection 'users'"):
        store.users_collection.insert_one({"email": "a@b.c"})
    with pytest.raises(RuntimeError, match="refuses remote"):
        store.db["feedback_submissions"].insert_one({"message": "hi"})


def test_sqlite_refuses_remote_collections_in_development(tmp_path: Path):
    env = resolve_database_environment(
        pristine_env={
            "ENVIRONMENT": "development",
            "MONGO_URI": "mongodb://example.invalid/gob-staging",
            "MONGO_DB_NAME": "gob-staging",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(tmp_path / "desktop.sqlite"),
        },
        repo_root=tmp_path,
        target_environ={},
    )
    store = SqliteStore(env)
    with pytest.raises(RuntimeError, match="refuses remote collection 'users'"):
        store.users_collection.find_one({})


def test_sqlite_team_builder_drafts_are_local_outside_test(tmp_path: Path):
    env = _production_env(
        tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "local.sqlite")
    )
    store = SqliteStore(env)
    coll = store.db["team_builder_wizard_drafts"]
    assert isinstance(coll, SqliteCollection)
    coll.insert_one(
        {"_id": "d1", "user_id": "local-desktop-user", "schema_version": 2}
    )
    found = store.db["team_builder_wizard_drafts"].find_one({"_id": "d1"})
    assert found["user_id"] == "local-desktop-user"
    names = {
        row[0]
        for row in sqlite3.connect(store.sqlite_path).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "team_builder_wizard_drafts" in names


def test_sqlite_recruit_sets_are_local_empty_outside_test(tmp_path: Path):
    env = _production_env(
        tmp_path, GOB_PERSISTENCE="sqlite", GOB_SQLITE_PATH=str(tmp_path / "local.sqlite")
    )
    store = SqliteStore(env)
    coll = store.db["recruit_sets"]
    assert isinstance(coll, SqliteCollection)
    assert list(coll.find({})) == []


def test_sqlite_collection_round_trip_queries(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    coll = store.players_collection
    assert isinstance(coll, SqliteCollection)
    coll.insert_many([
        {"_id": "p1", "team": "Lancaster", "rt": 10},
        {"_id": "p2", "team": "Bentley-Truman", "rt": 20},
    ])
    assert coll.count_documents({"team": {"$in": ["Lancaster", "Bentley-Truman"]}}) == 2
    coll.update_one({"_id": "p1"}, {"$set": {"rt": 11}})
    assert coll.find_one({"_id": "p1"})["rt"] == 11
    ids = {doc["_id"] for doc in coll.find({"team": "Lancaster"}, {"_id": 1})}
    assert ids == {"p1"}
    ranked = list(coll.aggregate([
        {"$match": {"rt": {"$gt": 0}}},
        {"$project": {"team": 1, "value": {"$ifNull": ["$rt", 0]}}},
        {"$sort": {"value": -1}},
        {"$limit": 1},
    ]))
    assert ranked[0]["team"] == "Bentley-Truman"
    assert ranked[0]["value"] == 20
    coll.update_one(
        {"slug": "p3", "team": "Lancaster"},
        {"$set": {"rt": 5}},
        upsert=True,
    )
    created = coll.find_one({"slug": "p3"})
    assert created["team"] == "Lancaster"
    assert created["rt"] == 5


def test_sqlite_roster_name_normalization_aggregate(tmp_path: Path):
    """Set Lineup looks up /roster/{teamName} via $addFields+$replaceAll+$toLower."""
    store = SqliteStore(_sqlite_env(tmp_path))
    coll = store.teams_collection
    coll.insert_one({"_id": "t1", "name": "Four-Corners", "team_id": "FOUR_CORNERS"})
    coll.insert_one({"_id": "t2", "name": "Lancaster", "team_id": "LANCASTER"})
    pipeline = [
        {
            "$addFields": {
                "normalized_name": {
                    "$toLower": {"$replaceAll": {"input": "$name", "find": "-", "replacement": " "}}
                }
            }
        },
        {"$match": {"normalized_name": "four corners"}},
        {"$limit": 1},
    ]
    hit = list(coll.aggregate(pipeline))
    assert len(hit) == 1
    assert hit[0]["team_id"] == "FOUR_CORNERS"
    assert hit[0]["normalized_name"] == "four corners"
    lanc = list(coll.aggregate([
        {
            "$addFields": {
                "normalized_name": {
                    "$toLower": {"$replaceAll": {"input": "$name", "find": "-", "replacement": " "}}
                }
            }
        },
        {"$match": {"normalized_name": "lancaster"}},
        {"$limit": 1},
    ]))
    assert lanc[0]["name"] == "Lancaster"


def test_sqlite_unsupported_operators_raise(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    coll = store.players_collection
    coll.insert_one({"_id": "p1", "team": "Lancaster", "rt": 10})
    with pytest.raises(SqliteUnsupportedOperator, match="Unsupported aggregate stage"):
        list(coll.aggregate([{"$lookup": {"from": "x"}}]))
    with pytest.raises(SqliteUnsupportedOperator, match="Unsupported expression operator"):
        list(coll.aggregate([{"$project": {"v": {"$concat": ["$team", "x"]}}}]))
    with pytest.raises(SqliteUnsupportedOperator, match="Unsupported query operator"):
        list(coll.aggregate([{"$match": {"rt": {"$mod": [2, 0]}}}]))
    with pytest.raises(SqliteUnsupportedOperator, match="Unsupported update operator"):
        coll.update_one({"_id": "p1"}, {"$rename": {"rt": "rating"}})


def test_sqlite_type_operator_matches_resume_anchor_objects(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    games = store.games_collection
    games.insert_one({"_id": "g1", "franchise_id": "f1", "is_final": False, "resume_anchor": {"snapshot": {}}})
    games.insert_one({"_id": "g2", "franchise_id": "f1", "is_final": False, "resume_anchor": "stale"})
    hits = list(games.find({"resume_anchor": {"$type": "object"}, "is_final": {"$ne": True}}))
    assert {doc["_id"] for doc in hits} == {"g1"}


def test_sqlite_generated_columns_and_real_indexes(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    fid = "aaaaaaaaaaaaaaaaaaaaaaaa"
    store.games_collection.insert_many(
        [
            {"_id": "g1", "franchise_id": fid, "week": 1},
            {"_id": "g2", "franchise_id": fid, "week": 2},
            {"_id": "g3", "franchise_id": "bbbbbbbbbbbbbbbbbbbbbbbb", "week": 1},
        ]
    )
    cols = {
        row[1]
        for row in store._conn.execute('PRAGMA table_xinfo("games")').fetchall()
    }
    assert {"g_franchise_id", "g_player_id", "g_team_id", "g_week"} <= cols
    indexes = [
        row[1]
        for row in store._conn.execute("PRAGMA index_list(games)").fetchall()
    ]
    assert any("g_franchise_id" in name for name in indexes)
    extracted = store._conn.execute(
        "SELECT g_franchise_id FROM games WHERE id = ?",
        ('raw:"g1"',),
    ).fetchone()
    assert extracted[0] == fid
    decoded = []

    def counting_select(self, filt=None, **kwargs):
        rows = orig_select(self, filt, **kwargs)
        if self.name == "games":
            decoded.append(len(rows))
        return rows

    from BackEnd.persistence.sqlite_collection import SqliteCollection

    orig_select = SqliteCollection._select
    SqliteCollection._select = counting_select
    try:
        hits = list(store.games_collection.find({"franchise_id": fid}))
        by_id = store.games_collection.find_one({"_id": "g2"})
        residual = store.games_collection.find_one({"_id": "g1", "week": 1})
        first = store.games_collection.find_one({"franchise_id": fid})
    finally:
        SqliteCollection._select = orig_select
    assert {doc["_id"] for doc in hits} == {"g1", "g2"}
    assert by_id["week"] == 2
    assert residual["_id"] == "g1"
    assert first["franchise_id"] == fid
    assert decoded == [2, 1, 1, 1]
    from BackEnd.persistence.sqlite_schema import compile_filter, filter_fully_compiled

    setup_filt = {
        "week": 2,
        "franchise_id": fid,
        "$or": [
            {"team1_id": "A", "team2_id": "B"},
            {"team1_id": "B", "team2_id": "A"},
        ],
    }
    sql, _params = compile_filter(setup_filt)
    assert "g_week" in sql and "g_franchise_id" in sql
    assert filter_fully_compiled(setup_filt) is False
    week_val = store._conn.execute(
        "SELECT g_week FROM games WHERE id = ?",
        ('raw:"g2"',),
    ).fetchone()[0]
    assert week_val == "2"


def test_sqlite_projection_skips_full_doc_decode(tmp_path: Path, monkeypatch):
    store = SqliteStore(_sqlite_env(tmp_path))
    fat = {"_id": "p1", "franchise_id": "fid", "team_id": "t1", "blob": "x" * 5000}
    store.franchise_team_data_collection.insert_one(fat)
    decoded = []
    from BackEnd.persistence import sqlite_collection as sc

    orig = sc.decode_doc

    def counting(raw):
        decoded.append(len(raw) if isinstance(raw, str) else 0)
        return orig(raw)

    monkeypatch.setattr(sc, "decode_doc", counting)
    docs = list(
        store.franchise_team_data_collection.find(
            {"franchise_id": "fid"},
            {"team_id": 1},
        )
    )
    assert docs[0]["team_id"] == "t1"
    assert "blob" not in docs[0]
    assert decoded == []


def test_sqlite_week_range_compiles_and_skips_decode(tmp_path: Path, monkeypatch):
    """$gte/$lte on g_week (TEXT) must be numeric, and the inclusion projection applies."""
    from BackEnd.persistence.sqlite_schema import compile_filter, filter_fully_compiled

    store = SqliteStore(_sqlite_env(tmp_path))
    games = store.games_collection
    for week in (1, 3, 10, 26, 27):
        games.insert_one(
            {
                "_id": f"g{week}",
                "franchise_id": "fid",
                "week": week,
                "team1_id": ObjectId("69a6fcb68d2c56aa82e48a54"),
                "home_team_id": "LANCASTER",
                "blob": "x" * 4000,
            }
        )
    games.insert_one(
        {
            "_id": "gabc",
            "franchise_id": "fid",
            "week": "abc",
            "team1_id": "t",
            "blob": "x" * 4000,
        }
    )
    games.insert_one(
        {
            "_id": "gother",
            "franchise_id": "other",
            "week": 10,
            "team1_id": "z",
            "blob": "y" * 4000,
        }
    )

    filt = {"franchise_id": "fid", "week": {"$gte": 1, "$lte": 26}}
    assert filter_fully_compiled(filt) is True
    sql, params = compile_filter(filt)
    assert "CAST(g_week AS REAL)" in sql
    assert "g_franchise_id" in sql
    assert params[params.index(1) :][:1] == [1]
    assert 26 in params

    # Lexicographic TEXT order would drop week 10 ("10" > "26") and keep nothing useful.
    decoded = []
    from BackEnd.persistence import sqlite_collection as sc

    orig = sc.decode_doc

    def counting(raw):
        decoded.append(1)
        return orig(raw)

    monkeypatch.setattr(sc, "decode_doc", counting)
    projection = {"_id": 1, "week": 1, "team1_id": 1, "home_team_id": 1}
    docs = list(games.find(filt, projection))
    assert sorted(doc["week"] for doc in docs) == [1, 3, 10, 26]
    assert all("blob" not in doc for doc in docs)
    assert decoded == []
    week_10 = next(doc for doc in docs if doc["week"] == 10)
    assert week_10["team1_id"] == ObjectId("69a6fcb68d2c56aa82e48a54")
    assert week_10["home_team_id"] == "LANCASTER"

    # Same rows as a full decode + Python match, so the SQL predicate is equivalent.
    monkeypatch.setattr(sc, "decode_doc", orig)
    full = list(games.find(filt))
    assert sorted(doc["week"] for doc in full) == [1, 3, 10, 26]

    adjacent = {"franchise_id": "fid", "week": {"$in": [1, 10, 27], "$gte": 10, "$lte": 26}}
    assert filter_fully_compiled(adjacent) is True
    assert sorted(doc["week"] for doc in games.find(adjacent, {"week": 1})) == [10]

    open_high = {"franchise_id": "fid", "week": {"$gt": 3, "$lt": 26}}
    assert filter_fully_compiled(open_high) is True
    assert sorted(doc["week"] for doc in games.find(open_high, {"week": 1})) == [10]

    assert filter_fully_compiled({"franchise_id": "fid", "week": {"$ne": 10}}) is False
    assert filter_fully_compiled({"team_id": {"$gte": "L", "$lt": "M"}}) is True
    team_sql, _team_params = compile_filter({"team_id": {"$gte": "L", "$lt": "M"}})
    assert "CAST(" not in team_sql
    assert "g_team_id >= ?" in team_sql


def test_sqlite_find_one_sort_matches_find_and_mongo(tmp_path: Path):
    docs = [
        {"_id": "a", "franchise_id": "fid", "n": 1},
        {"_id": "c", "franchise_id": "fid", "n": 3},
        {"_id": "b", "franchise_id": "fid", "n": 2},
    ]
    sqlite_store = SqliteStore(_sqlite_env(tmp_path))
    mongo_store = MongoStore(_mongomock_env(tmp_path))
    for doc in docs:
        sqlite_store.games_collection.insert_one(dict(doc))
        mongo_store.games_collection.insert_one(dict(doc))

    filt = {"franchise_id": "fid"}
    for spec in ([("n", -1)], [("n", 1)], [("_id", -1)], [("_id", 1)]):
        sqlite_hit = sqlite_store.games_collection.find_one(filt, sort=spec)
        via_find = next(iter(sqlite_store.games_collection.find(filt).sort(spec).limit(1)))
        mongo_hit = mongo_store.games_collection.find_one(filt, sort=spec)
        assert sqlite_hit["_id"] == via_find["_id"] == mongo_hit["_id"]

    assert sqlite_store.games_collection.find_one({"franchise_id": "missing"}, sort=[("_id", -1)]) is None

    # Unsorted find_one still seeks one row (SQL LIMIT 1), not the whole match set.
    decoded = []
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    orig_select = SqliteCollection._select

    def counting_select(self, filt=None, **kwargs):
        rows = orig_select(self, filt, **kwargs)
        if self.name == "games":
            decoded.append(len(rows))
        return rows

    SqliteCollection._select = counting_select
    try:
        hit = sqlite_store.games_collection.find_one({"_id": "b"})
    finally:
        SqliteCollection._select = orig_select
    assert hit["n"] == 2
    assert decoded == [1]


def test_sqlite_persist_transaction_is_one_commit(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    path = store.sqlite_path
    with store.transaction():
        store.games_collection.insert_one({"_id": "a", "franchise_id": "f"})
        store.games_collection.update_one({"_id": "a"}, {"$set": {"week": 1}})
        store.games_collection.update_one({"_id": "a"}, {"$set": {"week": 2}})
        other = sqlite3.connect(path)
        unseen = other.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        other.close()
        assert unseen == 0
    assert store.games_collection.find_one({"_id": "a"})["week"] == 2
    other = sqlite3.connect(path)
    seen = other.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    other.close()
    assert seen == 1


def test_sqlite_migrates_nonempty_legacy_table(tmp_path: Path):
    path = tmp_path / "save.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE games (id TEXT PRIMARY KEY, doc TEXT NOT NULL)")
    con.execute(
        "INSERT INTO games(id, doc) VALUES (?, ?)",
        ('raw:"g1"', '{"_id":"g1","franchise_id":"fid"}'),
    )
    con.commit()
    con.close()
    store = SqliteStore(_sqlite_env(tmp_path))
    assert store.games_collection.find_one({"franchise_id": "fid"})["_id"] == "g1"
    assert store._conn.execute("SELECT g_franchise_id FROM games").fetchone()[0] == "fid"


def test_sqlite_generated_schema_survives_reopen(tmp_path: Path):
    env = _sqlite_env(tmp_path)
    first = SqliteStore(env)
    first.games_collection.insert_one({"_id": "g1", "franchise_id": "fid"})
    first._conn.close()
    second = SqliteStore(env)
    row = second._conn.execute(
        "SELECT g_franchise_id FROM games WHERE id = ?",
        ('raw:"g1"',),
    ).fetchone()
    assert row[0] == "fid"
