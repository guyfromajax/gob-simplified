import os
from pathlib import Path
from pymongo import MongoClient
from pymongo.collection import Collection
from BackEnd.env_config import resolve_database_environment, resolve_runtime_db_access

# Snapshot the REAL process environment before any dotenv file is loaded. The prod-access
# opt-in below is read from this snapshot only, so that dropping GOB_DB_ACCESS=write into
# .env / .env.local cannot permanently disarm the guard for every local script. The opt-in
# has to be given per invocation, on the command line, or by the deployment platform.
_PRISTINE_ENV = dict(os.environ)

import sys
print("🔵 [DEBUG] db.py: Starting module", file=sys.stderr, flush=True)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_ENV = resolve_database_environment(
    pristine_env=_PRISTINE_ENV,
    repo_root=_REPO_ROOT,
    target_environ=os.environ,
)
MONGO_URI = DB_ENV.mongo_uri
DB_NAME = DB_ENV.db_name
USING_MONGOMOCK = DB_ENV.db_mode == "mongomock"
print(
    f"🔧 [DB CONFIG] source={DB_ENV.source} environment={DB_ENV.environment} "
    f"database={DB_NAME} mode={DB_ENV.db_mode}",
    file=sys.stderr,
    flush=True,
)

def _init_client(uri: str | None):
    """Initialize configured real Mongo. Errors intentionally propagate."""
    if not uri:
        raise RuntimeError("Real Mongo mode requires MONGO_URI")
    return MongoClient(uri, serverSelectionTimeoutMS=5000, connect=False)

# ── PRODUCTION ACCESS GUARD ──────────────────────────────────────────────────────────────
# Ad-hoc scripts should not be able to reach production by accident. Note that "read-only
# script" is not a safe assumption in this codebase: GameManager.__init__ ->
# _update_position_ratings() bulk_writes position_ratings on construction, so merely
# simulating a game writes. See projects/bugs.md.
#
# Resolution order (the opt-in is read from _PRISTINE_ENV, never from a dotenv file):
#   1. non-prod database                      -> "write"  (staging/local unaffected)
#   2. GOB_DB_ACCESS=write | read (real env)  -> as given (explicit, per invocation)
#   3. any RAILWAY_* var present              -> "write"  (this is the deployed app)
#   4. otherwise                              -> "refuse" (raise at import)
#
# Legitimate prod access is therefore:
#   read-only diagnostics:  GOB_DB_ACCESS=read  python script.py
#   deliberate migration:   GOB_DB_ACCESS=write python script.py
# Neither can be checked in, and neither persists past the command that used it.
class ProdAccessBlocked(RuntimeError):
    """Raised when a process reaches production without opting in."""


class ProdWriteBlocked(RuntimeError):
    """Raised when a GOB_DB_ACCESS=read process attempts a write."""


def _resolve_db_access(db_name: str) -> str:
    return resolve_runtime_db_access(db_name, DB_ENV.process_environment)


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


DB_ACCESS = _resolve_db_access(DB_NAME)
if DB_ACCESS == "refuse":
    raise ProdAccessBlocked(
        f"Refusing to connect to PRODUCTION database {DB_NAME!r} from an unrecognised "
        f"process.\n"
        f"  read-only:  GOB_DB_ACCESS=read  <your command>\n"
        f"  read-write: GOB_DB_ACCESS=write <your command>\n"
        f"If you meant to use staging, configure repo-root .env.local with "
        f"ENVIRONMENT=development and MONGO_DB_NAME=gob-staging."
    )
if DB_ACCESS == "read":
    print(f"🔒 [DB] PRODUCTION {DB_NAME!r} opened READ-ONLY (GOB_DB_ACCESS=read)",
          file=sys.stderr, flush=True)

if not USING_MONGOMOCK:
    client = _init_client(MONGO_URI)
    db = client[DB_NAME]
    if DB_ACCESS == "read":
        # Every collection below is derived via db["..."], so they all come back guarded.
        db = _ReadOnlyDatabase(db)
        client = _ReadOnlyClient(client)
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]
    franchise_state_collection = db["franchise_state"]
    franchises_collection = db["franchises"]
    franchise_team_data_collection = db["franchise_team_data"]
    franchise_players_data_collection = db["franchise_players_data"]
    franchise_recruits_data_collection = db["franchise_recruits_data"]
    plays_collection = db["plays"]
    defenses_collection = db["defenses"]
    fcp_skeletons_collection = db["fcp_skeletons"]
    hct_skeletons_collection = db["hct_skeletons"]
    # Alpha access control - OTP codes for gated signup
    alpha_otps_collection = db["alpha_otps"]
    # Alpha access code requests (signup page "Request Access Code" – admin checks and sends codes manually)
    access_code_requests_collection = db["access_code_requests"]
    # Users collection for authentication (Step 1)
    users_collection = db["users"]
    # Password reset tokens (Step 11 - minimal email)
    password_reset_tokens_collection = db["password_reset_tokens"]
    press_conference_sessions_collection = db["press_conference_sessions"]
    community_highlights_collection = db["community_highlights"]
    around_the_league_collection = db["around_the_league"]
    # Alpha 12-question feedback survey (lazily created on first insert; lands in
    # gob.alpha_feedback on prod, gob-staging.alpha_feedback on staging — DB chosen
    # by the validated DB_ENV identity, no per-env branching).
    alpha_feedback_collection = db["alpha_feedback"]
    # EOG band instrumentation. Durable home for the [EOG-BAND] records: Railway's
    # container filesystem is EPHEMERAL and declares no volume, so the file sink
    # produces nothing retrievable in production. TTL-expired, see ensure_eog_band_log_index.
    eog_band_log_collection = db["eog_band_log"]
    print("🔵 [DEBUG] db.py: Collections initialized", file=sys.stderr, flush=True)
else:
    print("🔵 [DEBUG] db.py: Using explicitly selected mongomock", file=sys.stderr, flush=True)
    import mongomock
    client = mongomock.MongoClient()
    db = client[DB_NAME]  # DB_NAME is defined at module level above
    players_collection = db["players"]
    teams_collection = db["teams"]
    games_collection = db["games"]
    tournaments_collection = db["tournaments"]
    training_log_collection = db["training_sessions"]
    franchise_state_collection = db["franchise_state"]
    franchises_collection = db["franchises"]
    franchise_team_data_collection = db["franchise_team_data"]
    franchise_players_data_collection = db["franchise_players_data"]
    franchise_recruits_data_collection = db["franchise_recruits_data"]
    plays_collection = db["plays"]
    defenses_collection = db["defenses"]
    fcp_skeletons_collection = db["fcp_skeletons"]
    hct_skeletons_collection = db["hct_skeletons"]
    # Alpha access control - OTP codes for gated signup
    alpha_otps_collection = db["alpha_otps"]
    # Alpha access code requests (signup page "Request Access Code")
    access_code_requests_collection = db["access_code_requests"]
    # Users collection for authentication (Step 1)
    users_collection = db["users"]
    # Password reset tokens (Step 11 - minimal email)
    password_reset_tokens_collection = db["password_reset_tokens"]
    press_conference_sessions_collection = db["press_conference_sessions"]
    community_highlights_collection = db["community_highlights"]
    around_the_league_collection = db["around_the_league"]
    # Alpha 12-question feedback survey (lazily created on first insert).
    alpha_feedback_collection = db["alpha_feedback"]
    eog_band_log_collection = db["eog_band_log"]
    print("🔵 [DEBUG] db.py: Mongomock collections initialized", file=sys.stderr, flush=True)

print("🔵 [DEBUG] db.py: Module initialization complete", file=sys.stderr, flush=True)


def ensure_ftd_index():
    """
    Ensure unique compound index on franchise_team_data (franchise_id, team_id).
    Idempotent; safe to call on startup or before FTD writes.
    Skips when using mongomock (no real MongoDB).
    """
    if not client:
        return
    try:
        franchise_team_data_collection.create_index(
            [("franchise_id", 1), ("team_id", 1)],
            unique=True,
            name="franchise_team_unique",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_ftd_index: {e}", file=sys.stderr, flush=True)


def ensure_fpd_index():
    """
    Ensure unique compound index on franchise_players_data (franchise_id, player_id).
    Idempotent; safe to call on startup or before FPD writes.
    Skips when using mongomock (no real MongoDB).
    """
    if not client:
        return
    try:
        franchise_players_data_collection.create_index(
            [("franchise_id", 1), ("player_id", 1)],
            unique=True,
            name="franchise_player_unique",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_fpd_index: {e}", file=sys.stderr, flush=True)


def ensure_frd_index():
    """
    Ensure unique compound index on franchise_recruits_data (franchise_id, recruit_id).
    Idempotent; safe to call on startup or before FRD writes.
    Skips when using mongomock (no real MongoDB).
    """
    if not client:
        return
    try:
        franchise_recruits_data_collection.create_index(
            [("franchise_id", 1), ("recruit_id", 1)],
            unique=True,
            name="franchise_recruit_unique",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_frd_index: {e}", file=sys.stderr, flush=True)


def ensure_games_franchise_index():
    """
    Index on games.franchise_id for franchise delete and any queries by franchise.
    Idempotent; safe to call on startup. Accept an equivalent existing index under
    any name so environments created by older migrations do not raise a harmless
    IndexOptionsConflict merely because the requested name changed.
    """
    if not client:
        return
    try:
        desired_key = [("franchise_id", 1)]
        for existing in games_collection.list_indexes():
            if list((existing.get("key") or {}).items()) == desired_key:
                return
        games_collection.create_index(
            desired_key,
            name="franchise_id_1",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_games_franchise_index: {e}", file=sys.stderr, flush=True)


def ensure_franchises_user_id_index():
    """
    Index on franchises.user_id for delete-current and admin lookups.
    Idempotent; safe to call on startup.
    """
    if not client:
        return
    try:
        franchises_collection.create_index(
            [("user_id", 1)],
            name="user_id_1",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_franchises_user_id_index: {e}", file=sys.stderr, flush=True)


def ensure_users_username_index():
    """
    Ensure unique index on users.username_lower for case-insensitive uniqueness.
    Sparse=True so documents without username_lower (pre-migration) don't conflict.
    """
    if not client:
        return
    try:
        users_collection.create_index(
            [("username_lower", 1)],
            unique=True,
            sparse=True,
            name="username_lower_unique",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_users_username_index: {e}", file=sys.stderr, flush=True)


# Retention for EOG band instrumentation. A franchise-season is ~36,600 rows / ~13 MiB as
# JSONL, so 50 concurrent seasons is well under a gigabyte — the TTL is housekeeping, not a
# capacity control. Override with GOB_EOG_BAND_TTL_DAYS.
# 180, not 90: the TTL runs from created_at, so a tester who takes two or three months to
# play 26 weeks loses their EARLY weeks — and a season with weeks 8-26 is unusable for a
# re-fit while still reading as nearly complete in eog_band_export.py --list. At ~9 MiB per
# franchise-season the storage is irrelevant; partial expiry is not.
EOG_BAND_LOG_TTL_DAYS = int(os.environ.get("GOB_EOG_BAND_TTL_DAYS", "180") or 180)


def ensure_eog_band_log_index():
    """TTL on `created_at` plus a (franchise_id, week) index for extraction.
    Idempotent; safe to call on startup. Skips when using mongomock."""
    if not client:
        return
    want = EOG_BAND_LOG_TTL_DAYS * 86400
    try:
        eog_band_log_collection.create_index(
            [("created_at", 1)], expireAfterSeconds=want, name="eog_band_ttl",
        )
    except Exception as e:
        # create_index REFUSES to change expireAfterSeconds on an existing index
        # (IndexOptionsConflict). Without this branch a later GOB_EOG_BAND_TTL_DAYS change
        # logs a warning and keeps the OLD retention — the env var reads as authoritative
        # while doing nothing. collMod is the only way to retune a live TTL.
        if getattr(e, "code", None) == 85:
            try:
                res = db.command("collMod", "eog_band_log", index={
                    "keyPattern": {"created_at": 1}, "expireAfterSeconds": want})
                print(f"🔵 [DB] eog_band TTL retuned "
                      f"{res.get('expireAfterSeconds_old')}s -> {res.get('expireAfterSeconds_new')}s",
                      file=sys.stderr, flush=True)
            except Exception as e2:
                print(f"⚠️ [DB] eog_band TTL collMod failed: {e2}", file=sys.stderr, flush=True)
        else:
            print(f"⚠️ [DB] eog_band ttl index: {e}", file=sys.stderr, flush=True)
    try:
        eog_band_log_collection.create_index(
            [("franchise_id", 1), ("week", 1)],
            name="eog_band_franchise_week",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_eog_band_log_index: {e}", file=sys.stderr, flush=True)
