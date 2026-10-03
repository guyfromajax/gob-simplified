"""Franchise ``last_played_at``: when the user last advanced a week or finished a game.

Written at the route level only (``marks_last_played`` on the advance / game routes).
Not used by the sim, ``cpu_week_pool``, ``sim_rng``, or finalize internals.
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from bson import ObjectId

logger = logging.getLogger(__name__)

LAST_PLAYED_FIELD = "last_played_at"


def franchise_collection():
    from BackEnd.persistence import get_store

    return get_store().franchises_collection


def _key(franchise_id: Any) -> Any:
    if isinstance(franchise_id, ObjectId):
        return franchise_id
    text = str(franchise_id or "").strip()
    try:
        return ObjectId(text)
    except Exception:
        return text or None


def stamp_last_played(franchise_id: Any, now: datetime | None = None) -> None:
    """Best-effort: a failed stamp never fails the route that played."""
    key = _key(franchise_id)
    if key is None:
        return
    try:
        franchise_collection().update_one(
            {"_id": key},
            {"$set": {LAST_PLAYED_FIELD: now or datetime.now(timezone.utc)}},
        )
    except Exception:
        logger.exception("[LAST-PLAYED] stamp failed franchise_id=%s", franchise_id)


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    # Mongo hands back naive UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def last_played_iso(doc: dict) -> str | None:
    when = _as_utc((doc or {}).get(LAST_PLAYED_FIELD))
    if when is None:
        return None
    return when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _created_at(doc: dict) -> datetime | None:
    raw = (doc or {}).get("_id")
    if isinstance(raw, ObjectId):
        return raw.generation_time
    try:
        return ObjectId(str(raw)).generation_time
    except Exception:
        return None


def most_recent_franchise_id(docs: Iterable[dict]) -> str | None:
    """Latest ``last_played_at``; a never-played franchise ranks by creation time, below any played one."""
    best = None
    best_rank = None
    for doc in docs:
        played = _as_utc(doc.get(LAST_PLAYED_FIELD))
        created = _created_at(doc)
        floor = datetime.min.replace(tzinfo=timezone.utc)
        rank = (played is not None, played or floor, created or floor)
        if best_rank is None or rank > best_rank:
            best, best_rank = doc, rank
    return str(best["_id"]) if best is not None else None


def marks_last_played(func):
    """Stamp the request's franchise after the route returns a non-idempotent success."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if isinstance(result, dict) and result.get("idempotent") is True:
            return result
        req = kwargs.get("req") if "req" in kwargs else (args[0] if args else None)
        franchise_id = getattr(req, "franchise_id", None)
        if franchise_id:
            stamp_last_played(franchise_id)
        return result

    return wrapper
