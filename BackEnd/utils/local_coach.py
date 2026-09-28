"""Career record and championships for the local desktop principal.

Online these live on ``users`` (read via /api/auth/me). The SQLite save refuses the
remote ``users`` collection, so the desktop coach keeps the same fields on one
``save_meta`` doc, incremented by the same helpers (user_game_commit,
franchise_championships) and read back in the /api/auth/me shape.
"""

from __future__ import annotations

from typing import Any

from BackEnd.local_identity import LOCAL_PRINCIPAL, LOCAL_USER_ID
from BackEnd.utils.franchise_championships import TITLE_KINDS
from BackEnd.utils.user_tracking import compute_lead_archetype, default_user_tracking

LOCAL_COACH_ID = "local_coach"


def is_local_owner(user_id: Any) -> bool:
    return str(user_id or "").strip() == LOCAL_USER_ID


def coach_collection():
    from BackEnd.persistence import get_store

    return get_store().db["save_meta"]


def local_coach_doc() -> dict:
    return coach_collection().find_one({"_id": LOCAL_COACH_ID}) or {}


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
    return {
        "user_id": str(principal.get("user_id") or ""),
        "username": doc.get("username") or principal.get("username") or "Coach",
        "record": record,
        "archetypes": archetypes,
        "lead_archetype": lead,
        "championships_total": {k: int(raw_champs.get(k, 0) or 0) for k in TITLE_KINDS},
    }
