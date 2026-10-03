"""Career record and championships for the local desktop principal.

Online these live on ``users`` (read via /api/auth/me). The SQLite save refuses the
remote ``users`` collection, so the desktop coach keeps the same fields on one
``save_meta`` doc, incremented by the same helpers (user_game_commit,
franchise_championships) and read back in the /api/auth/me shape.
"""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from BackEnd.local_identity import LOCAL_PRINCIPAL, LOCAL_USER_ID
from BackEnd.persistence import get_store
from BackEnd.utils.franchise_championships import TITLE_KINDS
from BackEnd.utils.user_tracking import compute_lead_archetype, default_user_tracking

logger = logging.getLogger(__name__)

users_collection = get_store().users_collection

LOCAL_COACH_ID = "local_coach"


def is_local_owner(user_id: Any) -> bool:
    return str(user_id or "").strip() == LOCAL_USER_ID


def coach_collection():
    from BackEnd.persistence import get_store

    return get_store().db["save_meta"]


def local_coach_doc() -> dict:
    return coach_collection().find_one({"_id": LOCAL_COACH_ID}) or {}


def coach_target(owner_user_id: Any):
    """``(collection, doc_id, is_local)`` for the coach who owns ``owner_user_id``.

    The one place that decides desktop ``save_meta``/``local_coach`` vs online
    ``users``, so every career field lands in the same doc as the rest.
    ``None`` when an online id is not an ObjectId (no doc to write).
    """
    if is_local_owner(owner_user_id):
        return coach_collection(), LOCAL_COACH_ID, True
    try:
        return users_collection, ObjectId(str(owner_user_id)), False
    except Exception:
        logger.warning("[COACH] invalid owner_user_id=%r", owner_user_id)
        return None


def coach_fields(owner_user_id: Any, *fields: str) -> dict:
    """One projected read of just ``fields`` — never the whole coach doc."""
    target = coach_target(owner_user_id)
    if target is None or not fields:
        return {}
    coll, doc_id, _local = target
    projection = {field: 1 for field in fields}
    projection["_id"] = 0
    return coll.find_one({"_id": doc_id}, projection) or {}


def coach_field(owner_user_id: Any, field: str) -> Any:
    """One projected read of a single coach field. ``None`` when absent."""
    return coach_fields(owner_user_id, field).get(field)


def coach_career_payload(doc: dict | None, principal: dict | None = None) -> dict:
    """The /api/auth/me career fields: record, archetypes, lead_archetype, championships_total."""
    doc = doc or {}
    principal = principal or LOCAL_PRINCIPAL
    defaults = default_user_tracking()
    record = {**defaults["record"], **(doc.get("record") or {})}
    archetypes = {**defaults["archetypes"], **(doc.get("archetypes") or {})}
    lead = doc.get("lead_archetype")
    if lead is None:
        lead = compute_lead_archetype(archetypes)
    raw_champs = doc.get("championships_total") or {}
    championships_total = {k: int(raw_champs.get(k, 0) or 0) for k in TITLE_KINDS}
    return {
        "user_id": str(principal.get("user_id") or ""),
        "username": doc.get("username") or principal.get("username") or "Coach",
        "record": record,
        "archetypes": archetypes,
        "lead_archetype": lead,
        "championships_total": championships_total,
        # The sum across kinds, so the client shows a single titles numeral without
        # doing arithmetic (Ch7 PR2: the online strip and the offline zone both read it).
        "titles_total": sum(championships_total.values()),
    }
