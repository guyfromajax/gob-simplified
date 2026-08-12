"""Team Builder unfinished-program drafts (`team_builder_wizard_drafts`).

New-format drafts are stamped with ``schema_version`` == SCHEMA_VERSION.
Absence of that marker means old (pre–Team Mod) rows: discard on read, never migrate.

One active draft per ``(user_id, replaced_object_id)``. ``draft_id`` is a stable
UUID minted once for that slot document so walk-ons / portraits stay idempotent;
it is not a second axis that multiplies unfinished programs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

SCHEMA_VERSION = 2

DRAFT_COLLECTION = "team_builder_wizard_drafts"


def _col(db: Any):
    return db[DRAFT_COLLECTION]


def is_new_format(doc: dict[str, Any] | None) -> bool:
    if not isinstance(doc, dict):
        return False
    try:
        return int(doc.get("schema_version") or 0) == SCHEMA_VERSION
    except (TypeError, ValueError):
        return False


def discard_old_format_for_user(db: Any, *, user_id: str) -> int:
    """Delete every draft row for this user that lacks the new schema stamp."""
    user_key = str(user_id or "").strip()
    if not user_key:
        return 0
    result = _col(db).delete_many(
        {
            "user_id": user_key,
            "$or": [
                {"schema_version": {"$exists": False}},
                {"schema_version": {"$ne": SCHEMA_VERSION}},
            ],
        }
    )
    return int(getattr(result, "deleted_count", 0) or 0)


def list_unfinished_drafts(db: Any, *, user_id: str) -> list[dict[str, Any]]:
    """Server-side unfinished drafts for Program Select. Never keyed on localStorage."""
    user_key = str(user_id or "").strip()
    if not user_key:
        return []
    discard_old_format_for_user(db, user_id=user_key)
    cursor = _col(db).find(
        {"user_id": user_key, "schema_version": SCHEMA_VERSION},
        {"_id": 0},
    )
    rows = [doc for doc in cursor if isinstance(doc, dict)]
    # Deterministic: one per slot by construction; sort by updated_at desc for the card.
    rows.sort(key=lambda d: str(d.get("updated_at") or ""), reverse=True)
    return rows


def get_draft_for_slot(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
) -> dict[str, Any] | None:
    user_key = str(user_id or "").strip()
    slot_key = str(replaced_object_id or "").strip()
    if not user_key or not slot_key:
        return None
    discard_old_format_for_user(db, user_id=user_key)
    doc = _col(db).find_one(
        {
            "user_id": user_key,
            "replaced_object_id": slot_key,
            "schema_version": SCHEMA_VERSION,
        },
        {"_id": 0},
    )
    return doc if isinstance(doc, dict) else None


def upsert_draft(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
    patch: dict[str, Any],
    draft_id: str | None = None,
) -> dict[str, Any]:
    """
    Upsert the single active draft for ``(user_id, replaced_object_id)``.

    Reuses an existing ``draft_id`` when present so walk-on / portrait keys stay stable.
    """
    user_key = str(user_id or "").strip()
    slot_key = str(replaced_object_id or "").strip()
    if not user_key or not slot_key:
        raise ValueError("draft_key_incomplete")

    discard_old_format_for_user(db, user_id=user_key)
    existing = get_draft_for_slot(
        db, user_id=user_key, replaced_object_id=slot_key
    )
    stable_id = str(
        (existing or {}).get("draft_id")
        or draft_id
        or ("draft-" + uuid.uuid4().hex[:16])
    ).strip()
    if len(stable_id) < 8:
        stable_id = "draft-" + uuid.uuid4().hex[:16]

    now = datetime.utcnow()
    payload = {
        "user_id": user_key,
        "replaced_object_id": slot_key,
        "draft_id": stable_id,
        "schema_version": SCHEMA_VERSION,
        "updated_at": now,
    }
    for key, value in (patch or {}).items():
        if key in ("user_id", "replaced_object_id", "draft_id", "schema_version", "_id"):
            continue
        payload[key] = value

    set_on_insert: dict[str, Any] = {"created_at": now}
    if existing is None:
        # Preserve walk_ons / portraits if a legacy same-key row somehow remains —
        # discard_old_format already cleared non-versioned docs.
        pass

    _col(db).update_one(
        {
            "user_id": user_key,
            "replaced_object_id": slot_key,
            "schema_version": SCHEMA_VERSION,
        },
        {"$set": payload, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    doc = get_draft_for_slot(db, user_id=user_key, replaced_object_id=slot_key)
    if not doc:
        raise RuntimeError("draft_upsert_failed")
    return doc


def delete_draft_for_slot(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str | None = None,
    draft_id: str | None = None,
) -> int:
    """Delete on Establish or explicit discard. Nowhere else."""
    user_key = str(user_id or "").strip()
    if not user_key:
        return 0
    query: dict[str, Any] = {"user_id": user_key}
    if replaced_object_id:
        query["replaced_object_id"] = str(replaced_object_id).strip()
    if draft_id:
        query["draft_id"] = str(draft_id).strip()
    result = _col(db).delete_many(query)
    return int(getattr(result, "deleted_count", 0) or 0)


def ensure_draft_id_for_slot(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
) -> str:
    """Mint or return the stable draft_id for walk-on / portrait idempotency."""
    doc = upsert_draft(
        db,
        user_id=user_id,
        replaced_object_id=replaced_object_id,
        patch={},
    )
    return str(doc["draft_id"])
