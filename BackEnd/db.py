"""Compatibility facade over the persistence adapter.

Application code is migrating to ``BackEnd.persistence.get_store()``. Tests and
scripts may keep importing this module. Collection handles, index helpers,
TTL constants, and the production access guard are the same objects the
adapter created.
"""

import sys

from BackEnd.persistence import (
    ProdAccessBlocked,
    ProdWriteBlocked,
    _CLIENT_MUTATORS,
    _DATABASE_MUTATORS,
    _MUTATORS,
    _ReadOnlyClient,
    _ReadOnlyCollection,
    _ReadOnlyDatabase,
    get_store,
)
from BackEnd.persistence import indexes as _indexes

print("🔵 [DEBUG] db.py: Starting module", file=sys.stderr, flush=True)

_store = get_store()

DB_ENV = _store.DB_ENV
MONGO_URI = DB_ENV.mongo_uri
DB_NAME = _store.DB_NAME
USING_MONGOMOCK = _store.USING_MONGOMOCK
DB_ACCESS = _store.DB_ACCESS

client = _store.client
db = _store.db

players_collection = _store.players_collection
teams_collection = _store.teams_collection
games_collection = _store.games_collection
tournaments_collection = _store.tournaments_collection
training_log_collection = _store.training_log_collection
franchise_state_collection = _store.franchise_state_collection
franchises_collection = _store.franchises_collection
franchise_team_data_collection = _store.franchise_team_data_collection
franchise_players_data_collection = _store.franchise_players_data_collection
franchise_recruits_data_collection = _store.franchise_recruits_data_collection
plays_collection = _store.plays_collection
defenses_collection = _store.defenses_collection
fcp_skeletons_collection = _store.fcp_skeletons_collection
hct_skeletons_collection = _store.hct_skeletons_collection
alpha_otps_collection = _store.alpha_otps_collection
access_code_requests_collection = _store.access_code_requests_collection
alpha_access_requests_collection = _store.alpha_access_requests_collection
users_collection = _store.users_collection
password_reset_tokens_collection = _store.password_reset_tokens_collection
press_conference_sessions_collection = _store.press_conference_sessions_collection
community_highlights_collection = _store.community_highlights_collection
around_the_league_collection = _store.around_the_league_collection
alpha_feedback_collection = _store.alpha_feedback_collection
eog_band_log_collection = _store.eog_band_log_collection
stripe_events_collection = _store.stripe_events_collection

EOG_BAND_LOG_TTL_DAYS = _store.EOG_BAND_LOG_TTL_DAYS
TUTORIAL_GAME_TTL_DAYS = _store.TUTORIAL_GAME_TTL_DAYS

print("🔵 [DEBUG] db.py: Module initialization complete", file=sys.stderr, flush=True)


def ensure_ftd_index():
    """
    Ensure unique compound index on franchise_team_data (franchise_id, team_id).
    Idempotent; safe to call on startup or before FTD writes.
    Skips when using mongomock (no real MongoDB).
    """
    _indexes.ensure_ftd_index(
        client=client,
        franchise_team_data_collection=franchise_team_data_collection,
    )


def ensure_fpd_index():
    """
    Ensure unique compound index on franchise_players_data (franchise_id, player_id).
    Idempotent; safe to call on startup or before FPD writes.
    Skips when using mongomock (no real MongoDB).
    """
    _indexes.ensure_fpd_index(
        client=client,
        franchise_players_data_collection=franchise_players_data_collection,
    )


def ensure_frd_index():
    """
    Ensure unique compound index on franchise_recruits_data (franchise_id, recruit_id).
    Idempotent; safe to call on startup or before FRD writes.
    Skips when using mongomock (no real MongoDB).
    """
    _indexes.ensure_frd_index(
        client=client,
        franchise_recruits_data_collection=franchise_recruits_data_collection,
    )


def ensure_games_franchise_index():
    """
    Index on games.franchise_id for franchise delete and any queries by franchise.
    Idempotent; safe to call on startup. Accept an equivalent existing index under
    any name so environments created by older migrations do not raise a harmless
    IndexOptionsConflict merely because the requested name changed.
    """
    _indexes.ensure_games_franchise_index(
        client=client,
        games_collection=games_collection,
    )


def ensure_franchises_user_id_index():
    """
    Index on franchises.user_id for delete-current and admin lookups.
    Idempotent; safe to call on startup.
    """
    _indexes.ensure_franchises_user_id_index(
        client=client,
        franchises_collection=franchises_collection,
    )


def ensure_alpha_access_requests_email_index():
    """Unique index on alpha_access_requests.email (one queue doc per email)."""
    _indexes.ensure_alpha_access_requests_email_index(
        client=client,
        alpha_access_requests_collection=alpha_access_requests_collection,
    )


def ensure_users_username_index():
    """
    Ensure unique index on users.username_lower for case-insensitive uniqueness.
    Sparse=True so documents without username_lower (pre-migration) don't conflict.
    """
    _indexes.ensure_users_username_index(
        client=client,
        users_collection=users_collection,
    )


def ensure_tutorial_game_ttl_index():
    """TTL sweep for abandoned FTE tutorial games. Idempotent; safe on startup.

    Keyed on `tutorial_expires_at`, which ONLY tutorial game docs carry — Mongo
    ignores documents missing the field, so franchise/tournament/single games can
    never be touched by this index no matter how it is retuned.
    """
    _indexes.ensure_tutorial_game_ttl_index(
        client=client,
        db=db,
        games_collection=games_collection,
        ttl_days=TUTORIAL_GAME_TTL_DAYS,
    )


def ensure_eog_band_log_index():
    """TTL on `created_at` plus a (franchise_id, week) index for extraction.
    Idempotent; safe to call on startup. Skips when using mongomock."""
    _indexes.ensure_eog_band_log_index(
        client=client,
        db=db,
        eog_band_log_collection=eog_band_log_collection,
        ttl_days=EOG_BAND_LOG_TTL_DAYS,
    )
