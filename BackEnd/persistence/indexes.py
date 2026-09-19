"""Idempotent index helpers. Same behaviour as the historical db.py ensure_* functions.

Callers may monkeypatch module-level collection names on ``BackEnd.db``; the
facade therefore invokes these helpers with those names so tests keep working.
"""

from __future__ import annotations

import sys
from typing import Any


def ensure_ftd_index(*, client: Any, franchise_team_data_collection: Any) -> None:
    """Unique compound index on franchise_team_data (franchise_id, team_id)."""
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


def ensure_fpd_index(*, client: Any, franchise_players_data_collection: Any) -> None:
    """Unique compound index on franchise_players_data (franchise_id, player_id)."""
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


def ensure_frd_index(*, client: Any, franchise_recruits_data_collection: Any) -> None:
    """Unique compound index on franchise_recruits_data (franchise_id, recruit_id)."""
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


def ensure_games_franchise_index(*, client: Any, games_collection: Any) -> None:
    """Index on games.franchise_id. Accept an equivalent existing index under any name."""
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


def ensure_franchises_user_id_index(*, client: Any, franchises_collection: Any) -> None:
    """Index on franchises.user_id for delete-current and admin lookups."""
    if not client:
        return
    try:
        franchises_collection.create_index(
            [("user_id", 1)],
            name="user_id_1",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_franchises_user_id_index: {e}", file=sys.stderr, flush=True)


def ensure_alpha_access_requests_email_index(
    *, client: Any, alpha_access_requests_collection: Any
) -> None:
    """Unique index on alpha_access_requests.email (one queue doc per email)."""
    if not client:
        return
    try:
        alpha_access_requests_collection.create_index(
            [("email", 1)],
            unique=True,
            name="email_unique",
        )
    except Exception as e:
        print(f"⚠️ [DB] ensure_alpha_access_requests_email_index: {e}", file=sys.stderr, flush=True)


def ensure_users_username_index(*, client: Any, users_collection: Any) -> None:
    """Unique sparse index on users.username_lower for case-insensitive uniqueness."""
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


def ensure_tutorial_game_ttl_index(
    *, client: Any, db: Any, games_collection: Any, ttl_days: int
) -> None:
    """TTL sweep for abandoned FTE tutorial games. Idempotent; safe on startup."""
    if not client:
        return
    want = ttl_days * 86400
    try:
        games_collection.create_index(
            [("tutorial_expires_at", 1)],
            expireAfterSeconds=want,
            name="tutorial_game_ttl",
        )
    except Exception as e:
        if getattr(e, "code", None) == 85:
            try:
                res = db.command("collMod", "games", index={
                    "keyPattern": {"tutorial_expires_at": 1}, "expireAfterSeconds": want})
                print(f"🔵 [DB] tutorial game TTL retuned "
                      f"{res.get('expireAfterSeconds_old')}s -> {res.get('expireAfterSeconds_new')}s",
                      file=sys.stderr, flush=True)
            except Exception as e2:
                print(f"⚠️ [DB] tutorial TTL collMod failed: {e2}", file=sys.stderr, flush=True)
        else:
            print(f"⚠️ [DB] ensure_tutorial_game_ttl_index: {e}", file=sys.stderr, flush=True)


def ensure_eog_band_log_index(
    *, client: Any, db: Any, eog_band_log_collection: Any, ttl_days: int
) -> None:
    """TTL on ``created_at`` plus a (franchise_id, week) index for extraction."""
    if not client:
        return
    want = ttl_days * 86400
    try:
        eog_band_log_collection.create_index(
            [("created_at", 1)], expireAfterSeconds=want, name="eog_band_ttl",
        )
    except Exception as e:
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
