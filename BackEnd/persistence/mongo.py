"""Mongo / mongomock persistence backend. Same behaviour as historical db.py."""

from __future__ import annotations

import os
import sys
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

from BackEnd.env_config import DatabaseEnvironment, resolve_runtime_db_access
from BackEnd.persistence import indexes
from BackEnd.persistence.guards import (
    ProdAccessBlocked,
    _ReadOnlyClient,
    _ReadOnlyDatabase,
)
from BackEnd.persistence.protocol import FranchiseBundle


# Collection attribute name -> Mongo collection name. training_log_collection
# is the historical Python name for the training_sessions collection.
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


def _init_client(uri: str | None):
    """Initialize configured real Mongo. Errors intentionally propagate."""
    if not uri:
        raise RuntimeError("Real Mongo mode requires MONGO_URI")
    return MongoClient(uri, serverSelectionTimeoutMS=5000, connect=False)


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


class MongoStore:
    """pymongo / mongomock store exposing the 25 historical collection handles."""

    def __init__(self, db_env: DatabaseEnvironment):
        self.DB_ENV = db_env
        self.DB_NAME = db_env.db_name
        self.USING_MONGOMOCK = db_env.db_mode == "mongomock"
        self.EOG_BAND_LOG_TTL_DAYS = int(os.environ.get("GOB_EOG_BAND_TTL_DAYS", "180") or 180)
        self.TUTORIAL_GAME_TTL_DAYS = int(os.environ.get("GOB_TUTORIAL_GAME_TTL_DAYS", "7") or 7)
        self.DB_ACCESS = resolve_runtime_db_access(self.DB_NAME, db_env.process_environment)
        if self.DB_ACCESS == "refuse":
            raise ProdAccessBlocked(
                f"Refusing to connect to PRODUCTION database {self.DB_NAME!r} from an unrecognised "
                f"process.\n"
                f"  read-only:  GOB_DB_ACCESS=read  <your command>\n"
                f"  read-write: GOB_DB_ACCESS=write <your command>\n"
                f"If you meant to use staging, configure repo-root .env.local with "
                f"ENVIRONMENT=development and MONGO_DB_NAME=gob-staging."
            )
        if self.DB_ACCESS == "read":
            print(
                f"🔒 [DB] PRODUCTION {self.DB_NAME!r} opened READ-ONLY (GOB_DB_ACCESS=read)",
                file=sys.stderr,
                flush=True,
            )

        if not self.USING_MONGOMOCK:
            self.client = _init_client(db_env.mongo_uri)
            self.db = self.client[self.DB_NAME]
            if self.DB_ACCESS == "read":
                # Every collection below is derived via db["..."], so they all come back guarded.
                self.db = _ReadOnlyDatabase(self.db)
                self.client = _ReadOnlyClient(self.client)
            self._bind_collections()
            print("🔵 [DEBUG] db.py: Collections initialized", file=sys.stderr, flush=True)
        else:
            print("🔵 [DEBUG] db.py: Using explicitly selected mongomock", file=sys.stderr, flush=True)
            import mongomock
            self.client = mongomock.MongoClient()
            self.db = self.client[self.DB_NAME]
            self._bind_collections()
            print("🔵 [DEBUG] db.py: Mongomock collections initialized", file=sys.stderr, flush=True)

    def _bind_collections(self) -> None:
        for attr, name in _COLLECTION_BINDINGS:
            setattr(self, attr, self.db[name])

    def read_franchise(self, franchise_id: Any) -> FranchiseBundle:
        oid, sid = _id_pair(franchise_id)
        either = {"franchise_id": {"$in": [oid, sid]}}
        return {
            "franchise": self.franchises_collection.find_one({"_id": oid}),
            "franchise_team_data": list(
                self.franchise_team_data_collection.find({"franchise_id": oid})
            ),
            "franchise_players_data": list(
                self.franchise_players_data_collection.find({"franchise_id": sid})
            ),
            "franchise_recruits_data": list(
                self.franchise_recruits_data_collection.find({"franchise_id": sid})
            ),
            "games": list(self.games_collection.find({"franchise_id": sid})),
            "press_conference_sessions": list(
                self.press_conference_sessions_collection.find(either)
            ),
            "training_sessions": list(self.training_log_collection.find(either)),
            "tournaments": list(self.tournaments_collection.find(either)),
            "franchise_state": list(self.franchise_state_collection.find(either)),
            "eog_band_log": list(self.eog_band_log_collection.find(either)),
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
        if "eog_band_log" in bundle:
            _replace_many(
                self.eog_band_log_collection,
                either,
                _stamp(_copy_docs(bundle.get("eog_band_log")), "franchise_id", sid),
            )

    def delete_franchise(self, franchise_id: Any) -> None:
        """Wipe one franchise. Mirrors franchise_routes._cascade_delete_franchise.

        FTD: ObjectId franchise_id; FPD/FRD/games: string; press sessions:
        ObjectId or string; franchises by _id. Also drops franchise-scoped
        training_sessions, tournaments, franchise_state, and eog_band_log.
        """
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
        self.eog_band_log_collection.delete_many(either)
        self.franchises_collection.delete_one({"_id": oid})

    def ensure_ftd_index(self) -> None:
        indexes.ensure_ftd_index(
            client=self.client,
            franchise_team_data_collection=self.franchise_team_data_collection,
        )

    def ensure_fpd_index(self) -> None:
        indexes.ensure_fpd_index(
            client=self.client,
            franchise_players_data_collection=self.franchise_players_data_collection,
        )

    def ensure_frd_index(self) -> None:
        indexes.ensure_frd_index(
            client=self.client,
            franchise_recruits_data_collection=self.franchise_recruits_data_collection,
        )

    def ensure_games_franchise_index(self) -> None:
        indexes.ensure_games_franchise_index(
            client=self.client,
            games_collection=self.games_collection,
        )

    def ensure_franchises_user_id_index(self) -> None:
        indexes.ensure_franchises_user_id_index(
            client=self.client,
            franchises_collection=self.franchises_collection,
        )

    def ensure_alpha_access_requests_email_index(self) -> None:
        indexes.ensure_alpha_access_requests_email_index(
            client=self.client,
            alpha_access_requests_collection=self.alpha_access_requests_collection,
        )

    def ensure_users_username_index(self) -> None:
        indexes.ensure_users_username_index(
            client=self.client,
            users_collection=self.users_collection,
        )

    def ensure_tutorial_game_ttl_index(self) -> None:
        indexes.ensure_tutorial_game_ttl_index(
            client=self.client,
            db=self.db,
            games_collection=self.games_collection,
            ttl_days=self.TUTORIAL_GAME_TTL_DAYS,
        )

    def ensure_eog_band_log_index(self) -> None:
        indexes.ensure_eog_band_log_index(
            client=self.client,
            db=self.db,
            eog_band_log_collection=self.eog_band_log_collection,
            ttl_days=self.EOG_BAND_LOG_TTL_DAYS,
        )
