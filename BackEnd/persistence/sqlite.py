"""SQLite JSON1 persistence backend. One file is one local save.

Remote-only collections never enter the save file. franchise_state in this
file is this save's state — not Mongo's process-global ``_id: "state"``
singleton. The adapter never imports or draws from ``random``.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from bson import ObjectId

from BackEnd.env_config import DatabaseEnvironment
from BackEnd.persistence.base_league import (
    resolve_base_league_sqlite_path,
    seed_empty_save,
)
from BackEnd.persistence.catalog import (
    bind_catalog_collections,
    empty_memory_catalog,
    open_catalog_connection,
    read_catalog_meta,
    resolve_catalog_sqlite_path,
)
from BackEnd.persistence.guards import _ReadOnlyCollection
from BackEnd.persistence.protocol import FranchiseBundle
from BackEnd.persistence.sqlite_collection import (
    NullCollection,
    RemoteUnavailable,
    SqliteCollection,
)
from BackEnd.persistence.sqlite_schema import (
    SqliteConnState,
    ensure_generated_schema,
    store_transaction,
)


LOCAL_COLLECTIONS: tuple[str, ...] = (
    "players",
    "teams",
    "games",
    "franchises",
    "franchise_state",
    "franchise_team_data",
    "franchise_players_data",
    "franchise_recruits_data",
    "training_sessions",
    "press_conference_sessions",
    "tournaments",
    "save_meta",
    "team_builder_wizard_drafts",
    "recruit_sets",
)

REMOTE_COLLECTIONS: tuple[str, ...] = (
    "users",
    "password_reset_tokens",
    "alpha_otps",
    "access_code_requests",
    "alpha_access_requests",
    "alpha_feedback",
    "community_highlights",
    "around_the_league",
    "stripe_events",
    "feedback_submissions",
)

_COLLECTION_BINDINGS: tuple[tuple[str, str], ...] = (
    ("players_collection", "players"),
    ("teams_collection", "teams"),
    ("games_collection", "games"),
    ("tournaments_collection", "tournaments"),
    ("training_log_collection", "training_sessions"),
    ("franchise_state_collection", "franchise_state"),
    ("franchises_collection", "franchises"),
    ("franchise_team_data_collection", "franchise_team_data"),
    ("franchise_players_data_collection", "franchise_players_data"),
    ("franchise_recruits_data_collection", "franchise_recruits_data"),
    ("plays_collection", "plays"),
    ("defenses_collection", "defenses"),
    ("fcp_skeletons_collection", "fcp_skeletons"),
    ("hct_skeletons_collection", "hct_skeletons"),
    ("alpha_otps_collection", "alpha_otps"),
    ("access_code_requests_collection", "access_code_requests"),
    ("alpha_access_requests_collection", "alpha_access_requests"),
    ("users_collection", "users"),
    ("password_reset_tokens_collection", "password_reset_tokens"),
    ("press_conference_sessions_collection", "press_conference_sessions"),
    ("community_highlights_collection", "community_highlights"),
    ("around_the_league_collection", "around_the_league"),
    ("alpha_feedback_collection", "alpha_feedback"),
    ("eog_band_log_collection", "eog_band_log"),
    ("stripe_events_collection", "stripe_events"),
)


def _as_object_id(franchise_id: Any) -> ObjectId:
    if isinstance(franchise_id, ObjectId):
        return franchise_id
    return ObjectId(str(franchise_id))


def _id_pair(franchise_id: Any) -> tuple[ObjectId, str]:
    oid = _as_object_id(franchise_id)
    return oid, str(oid)


def _copy_docs(docs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(doc) for doc in (docs or [])]


def _stamp(docs: list[dict[str, Any]], field: str, value: Any) -> list[dict[str, Any]]:
    stamped = []
    for doc in docs:
        copied = dict(doc)
        copied[field] = value
        stamped.append(copied)
    return stamped


def _replace_many(collection: Any, query: dict[str, Any], docs: list[dict[str, Any]]) -> None:
    collection.delete_many(query)
    if docs:
        collection.insert_many(docs)


def _eog_enabled(process_environment: dict[str, str] | Any) -> bool:
    raw = str(process_environment.get("GOB_EOG_BAND_ENABLED") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class SqliteDatabase:
    def __init__(self, name: str, collections: dict[str, Any], client: Any, remote_db: Any = None):
        self.name = name
        self._collections = collections
        self.client = client
        self._remote_db = remote_db

    def _collection(self, name: str):
        if name in self._collections:
            return self._collections[name]
        # Unknown names stay out of the save file.
        if self._remote_db is None:
            handle = RemoteUnavailable(name)
            self._collections[name] = handle
            return handle
        handle = self._remote_db[name]
        self._collections[name] = handle
        return handle

    def __getitem__(self, name: str):
        return self._collection(name)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._collection(name)
        except KeyError as exc:
            raise AttributeError(name) from exc

    def command(self, *_args, **_kwargs):
        raise NotImplementedError("SQLite profile has no Mongo collMod/command surface")

    def list_collection_names(self) -> list[str]:
        return list(self._collections.keys())

    def __repr__(self) -> str:
        return f"<SqliteDatabase {self.name!r}>"


class SqliteClient:
    def __init__(self, conn: sqlite3.Connection, database: SqliteDatabase):
        self._conn = conn
        self._database = database

    def close(self) -> None:
        self._conn.close()

    def server_info(self) -> dict[str, Any]:
        return {"version": "0.0.0", "versionArray": [0, 0, 0]}

    def __getitem__(self, name: str) -> SqliteDatabase:
        return self._database

    def __bool__(self) -> bool:
        return True


class SqliteStore:
    """One SQLite save file for local collections; remote handles stay out of the file."""

    def __init__(self, db_env: DatabaseEnvironment):
        self.DB_ENV = db_env
        self.DB_NAME = db_env.db_name
        self.USING_MONGOMOCK = False
        self.EOG_BAND_LOG_TTL_DAYS = int(os.environ.get("GOB_EOG_BAND_TTL_DAYS", "180") or 180)
        self.TUTORIAL_GAME_TTL_DAYS = int(os.environ.get("GOB_TUTORIAL_GAME_TTL_DAYS", "7") or 7)
        # A local file is not production Mongo. refuse never applies.
        # GOB_DB_ACCESS=read still means read-only — the concept is kept.
        explicit = str(db_env.process_environment.get("GOB_DB_ACCESS") or "").strip().lower()
        self.DB_ACCESS = "read" if explicit == "read" else "write"
        if self.DB_ACCESS == "read":
            print(
                f"🔒 [DB] SQLite save opened READ-ONLY (GOB_DB_ACCESS=read) path={self._resolve_path(db_env)}",
                file=sys.stderr,
                flush=True,
            )

        self.sqlite_path = self._resolve_path(db_env)
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        # FastAPI runs sync routes on worker threads; one connection is shared.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        writable = self.DB_ACCESS != "read"
        self._state = SqliteConnState(self._conn, self._lock)
        local: dict[str, Any] = {
            name: SqliteCollection(
                self._conn, name, writable=writable, lock=self._lock, state=self._state
            )
            for name in LOCAL_COLLECTIONS
        }
        ensure_generated_schema(self._conn, list(LOCAL_COLLECTIONS))
        self._conn.commit()

        explicit_catalog = str(
            db_env.process_environment.get("GOB_CATALOG_SQLITE") or ""
        ).strip()
        catalog_path = resolve_catalog_sqlite_path(db_env.process_environment)
        # Test isolation: do not auto-bind a shipping sidecar at bundle_root.
        # Pytest seeds plays on mongomock; sqlite tests that omit GOB_CATALOG_SQLITE
        # get an empty in-memory catalog so a committed catalog.sqlite cannot
        # change unit-test behaviour or block fixture writes.
        if str(db_env.environment).lower() == "test" and not explicit_catalog:
            self._catalog_conn = empty_memory_catalog()
            self.catalog_path = None
        elif catalog_path is None:
            from BackEnd.runtime_paths import bundle_path

            raise FileNotFoundError(
                "Bundled catalog.sqlite is missing at "
                f"{bundle_path('catalog.sqlite')}. Desktop reads plays/defenses/"
                "fcp_skeletons/hct_skeletons from that sidecar, not the save. "
                "Export with scripts/export_catalog_sidecar.py."
            )
        else:
            if not catalog_path.is_file():
                raise FileNotFoundError(f"Catalog sidecar is not a file: {catalog_path}")
            self._catalog_conn = open_catalog_connection(catalog_path)
            self.catalog_path = catalog_path
        catalog = bind_catalog_collections(self._catalog_conn, self._lock)
        self.catalog_version = str(read_catalog_meta(self._catalog_conn).get("version") or "unknown")
        local.update(catalog)

        allow_remote_memory = db_env.environment == "test"
        remote_db = None
        if allow_remote_memory:
            import mongomock
            remote_client = mongomock.MongoClient()
            remote_db = remote_client["gob-remote-memory"]
            remote = {name: remote_db[name] for name in REMOTE_COLLECTIONS}
        else:
            remote = {name: RemoteUnavailable(name) for name in REMOTE_COLLECTIONS}

        if _eog_enabled(db_env.process_environment):
            # January beta: keep producing calibration data, but never in the save.
            if remote_db is not None:
                eog = remote_db["eog_band_log"]
            else:
                import mongomock
                eog = mongomock.MongoClient()["gob-eog-memory"]["eog_band_log"]
        else:
            eog = NullCollection("eog_band_log")

        collections = {**local, **remote, "eog_band_log": eog}
        self.client = SqliteClient(self._conn, None)  # type: ignore[arg-type]
        self.db = SqliteDatabase(self.DB_NAME, collections, self.client, remote_db=remote_db)
        self.client._database = self.db
        # Only local/null handles belong on the SQLite database. Remote mongomock
        # collections keep their own client — rebound .database breaks $ operators.
        for coll in local.values():
            coll.database = self.db
        if isinstance(eog, (SqliteCollection, NullCollection)):
            eog.database = self.db

        if self.DB_ACCESS == "read":
            for name in LOCAL_COLLECTIONS:
                collections[name] = _ReadOnlyCollection(collections[name])
            self.db = SqliteDatabase(self.DB_NAME, collections, self.client, remote_db=remote_db)
            self.client._database = self.db

        for attr, name in _COLLECTION_BINDINGS:
            setattr(self, attr, collections[name])

        if writable:
            existing = local["save_meta"].find_one({"_id": "catalog_sidecar"})
            if existing is None:
                local["save_meta"].insert_one(
                    {"_id": "catalog_sidecar", "catalog_version": self.catalog_version}
                )
            self._seed_base_league_if_needed(
                local,
                db_env,
                writable=writable,
            )

        print(
            f"🔵 [DEBUG] db.py: SQLite collections initialized path={self.sqlite_path}",
            file=sys.stderr,
            flush=True,
        )

    def _seed_base_league_if_needed(
        self,
        local: dict[str, Any],
        db_env: DatabaseEnvironment,
        *,
        writable: bool,
    ) -> None:
        """Copy the bundled 128-team league into a brand-new save.

        Test isolation: do not auto-copy a committed bundle at bundle_root
        unless GOB_BASE_LEAGUE_SQLITE is set. Existing saves are never
        overwritten — play mutates teams and players.
        """
        self.league_path = None
        self.league_version = None
        if not writable:
            return
        if local["teams"].count_documents({}) > 0:
            stamp = local["save_meta"].find_one({"_id": "base_league"})
            if stamp:
                self.league_version = stamp.get("league_version")
            return
        explicit = str(db_env.process_environment.get("GOB_BASE_LEAGUE_SQLITE") or "").strip()
        if str(db_env.environment).lower() == "test" and not explicit:
            return
        league_path = resolve_base_league_sqlite_path(db_env.process_environment)
        if league_path is None:
            from BackEnd.runtime_paths import bundle_path

            raise FileNotFoundError(
                "Bundled base_league.sqlite is missing at "
                f"{bundle_path('base_league.sqlite')}. A new desktop save copies "
                "the universal teams and players from that bundle. "
                "Export with scripts/export_base_league.py."
            )
        if not league_path.is_file():
            raise FileNotFoundError(f"Base league bundle is not a file: {league_path}")
        stamp = seed_empty_save(
            teams_coll=local["teams"],
            players_coll=local["players"],
            save_meta=local["save_meta"],
            league_path=league_path,
        )
        self.league_path = league_path
        if stamp:
            self.league_version = stamp.get("league_version")
            print(
                "LEAGUE seeded "
                f"path={league_path} version={self.league_version} "
                f"teams={local['teams'].count_documents({})} "
                f"players={local['players'].count_documents({})}",
                file=sys.stderr,
                flush=True,
            )

    @staticmethod
    def _resolve_path(db_env: DatabaseEnvironment) -> str:
        configured = getattr(db_env, "sqlite_path", None) or db_env.process_environment.get("GOB_SQLITE_PATH")
        if configured:
            return str(configured)
        return str(Path(tempfile.gettempdir()) / f"gob-local-{os.getpid()}.sqlite")

    def read_franchise(self, franchise_id: Any) -> FranchiseBundle:
        oid, sid = _id_pair(franchise_id)
        either = {"franchise_id": {"$in": [oid, sid]}}
        state_rows = list(self.franchise_state_collection.find(either))
        if not state_rows:
            # Per-save state, not Mongo's process-global singleton.
            singleton = self.franchise_state_collection.find_one({"_id": "state"})
            if singleton is not None:
                state_rows = [singleton]
        return {
            "franchise": self.franchises_collection.find_one({"_id": oid}),
            "franchise_team_data": list(self.franchise_team_data_collection.find({"franchise_id": oid})),
            "franchise_players_data": list(self.franchise_players_data_collection.find({"franchise_id": sid})),
            "franchise_recruits_data": list(self.franchise_recruits_data_collection.find({"franchise_id": sid})),
            "games": list(self.games_collection.find({"franchise_id": sid})),
            "press_conference_sessions": list(self.press_conference_sessions_collection.find(either)),
            "training_sessions": list(self.training_log_collection.find(either)),
            "tournaments": list(self.tournaments_collection.find(either)),
            "franchise_state": state_rows,
            # Never part of the save file.
            "eog_band_log": [],
        }

    def write_franchise(self, franchise_id: Any, bundle: FranchiseBundle) -> None:
        oid, sid = _id_pair(franchise_id)
        either = {"franchise_id": {"$in": [oid, sid]}}

        if "franchise" in bundle:
            doc = bundle.get("franchise")
            if doc is None:
                self.franchises_collection.delete_one({"_id": oid})
            else:
                written = dict(doc)
                written["_id"] = oid
                self.franchises_collection.replace_one({"_id": oid}, written, upsert=True)

        if "franchise_team_data" in bundle:
            _replace_many(
                self.franchise_team_data_collection,
                {"franchise_id": oid},
                _stamp(_copy_docs(bundle.get("franchise_team_data")), "franchise_id", oid),
            )
        if "franchise_players_data" in bundle:
            _replace_many(
                self.franchise_players_data_collection,
                {"franchise_id": sid},
                _stamp(_copy_docs(bundle.get("franchise_players_data")), "franchise_id", sid),
            )
        if "franchise_recruits_data" in bundle:
            _replace_many(
                self.franchise_recruits_data_collection,
                {"franchise_id": sid},
                _stamp(_copy_docs(bundle.get("franchise_recruits_data")), "franchise_id", sid),
            )
        if "games" in bundle:
            _replace_many(
                self.games_collection,
                {"franchise_id": sid},
                _stamp(_copy_docs(bundle.get("games")), "franchise_id", sid),
            )
        if "press_conference_sessions" in bundle:
            _replace_many(
                self.press_conference_sessions_collection,
                either,
                _stamp(_copy_docs(bundle.get("press_conference_sessions")), "franchise_id", oid),
            )
        if "training_sessions" in bundle:
            _replace_many(
                self.training_log_collection,
                either,
                _stamp(_copy_docs(bundle.get("training_sessions")), "franchise_id", sid),
            )
        if "tournaments" in bundle:
            _replace_many(
                self.tournaments_collection,
                either,
                _stamp(_copy_docs(bundle.get("tournaments")), "franchise_id", sid),
            )
        if "franchise_state" in bundle:
            _replace_many(
                self.franchise_state_collection,
                either,
                _stamp(_copy_docs(bundle.get("franchise_state")), "franchise_id", sid),
            )
        # eog_band_log is intentionally ignored — it must not enter the save.

    def delete_franchise(self, franchise_id: Any) -> None:
        oid, sid = _id_pair(franchise_id)
        either = {"franchise_id": {"$in": [oid, sid]}}
        self.franchise_team_data_collection.delete_many({"franchise_id": oid})
        self.franchise_players_data_collection.delete_many({"franchise_id": sid})
        self.franchise_recruits_data_collection.delete_many({"franchise_id": sid})
        self.games_collection.delete_many({"franchise_id": sid})
        self.press_conference_sessions_collection.delete_many(either)
        self.training_log_collection.delete_many(either)
        self.tournaments_collection.delete_many(either)
        self.franchise_state_collection.delete_many(either)
        self.franchises_collection.delete_one({"_id": oid})

    def transaction(self):
        """One commit for a persist batch. Nested calls share the same txn."""
        return store_transaction(self._state)

    def ensure_ftd_index(self) -> None:
        self.franchise_team_data_collection.create_index(
            [("franchise_id", 1), ("team_id", 1)], unique=True, name="franchise_team_unique"
        )

    def ensure_fpd_index(self) -> None:
        self.franchise_players_data_collection.create_index(
            [("franchise_id", 1), ("player_id", 1)], unique=True, name="franchise_player_unique"
        )

    def ensure_frd_index(self) -> None:
        self.franchise_recruits_data_collection.create_index(
            [("franchise_id", 1), ("recruit_id", 1)], unique=True, name="franchise_recruit_unique"
        )

    def ensure_games_franchise_index(self) -> None:
        self.games_collection.create_index([("franchise_id", 1)], name="franchise_id_1")

    def ensure_franchises_user_id_index(self) -> None:
        self.franchises_collection.create_index([("user_id", 1)], name="user_id_1")

    def ensure_alpha_access_requests_email_index(self) -> None:
        return None

    def ensure_users_username_index(self) -> None:
        return None

    def ensure_tutorial_game_ttl_index(self) -> None:
        return None

    def ensure_eog_band_log_index(self) -> None:
        return None
