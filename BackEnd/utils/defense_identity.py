"""
Canonical defense identity: universal `defenses.defense_id` (slug).

Phase 2: half-court `scouting_data["defense"]` rows and `game_state["defense_playcall"]` use
canonical `defense_id` slugs (`man`, `2-3-zone`, …). This module still dual-reads legacy labels
via `resolve_to_defense_id` / `canonical_scouting_defense_key`.

- Catalog defenses: loaded from `defenses_collection`, keyed by `defense_id`.
- Synthetics (not in `defenses`): `vs_Fast_Break`, `FCP`, `HCT` — stable string ids.
- Dual-read: accept `defense_id`, legacy display names, `str(_id)`, playbook zone/man keys
  where mapped below.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId

# Non-catalog rows used in scouting templates / sim (stable, not Mongo `defense_id`).
SYNTHETIC_DEFENSE_IDS: frozenset[str] = frozenset({"vs_Fast_Break", "FCP", "HCT"})

# Playbook percentage keys → `defenses.defense_id` (see `playbook_settings_utils.ZONE_DEFENSE_ID_TO_NAME`).
PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID: Dict[str, str] = {
    "zone_23": "2-3-zone",
    "zone_32": "3-2-zone",
    "zone_131": "1-3-1-zone",
}

# Playbook man keys → primary `defense_id` (multiple man variants may share one doc in DB).
PLAYBOOK_MAN_KEY_TO_DEFENSE_ID: Dict[str, str] = {
    "man_normal": "man",
    "man_pressure": "man",
    "man_loose": "man",
}

# playbook `zone_23` / defenses.defense_id → inverse map for percentage lookup
DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY: Dict[str, str] = {
    v: k for k, v in PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID.items()
}

# Keys used in `scouting_data["defense"]` for half-court defense rows (Phase 2).
CANONICAL_HCO_DEFENSE_ROW_KEYS: Tuple[str, ...] = (
    "man",
    "2-3-zone",
    "3-2-zone",
    "1-3-1-zone",
)

# Offense Playcalls buckets vs_* keys from canonical defense row key
_OFFENSE_VS_KEY_BY_ROW_KEY: Dict[str, str] = {
    "man": "vs_man",
    "2-3-zone": "vs_2-3_zone",
    "3-2-zone": "vs_3-2_zone",
    "1-3-1-zone": "vs_1-3-1_zone",
}

# Zone shell geometry (boundaries) variant
_ZONE_SHELL_BY_ROW_KEY: Dict[str, str] = {
    "2-3-zone": "23",
    "3-2-zone": "32",
    "1-3-1-zone": "131",
}

# Legacy HCO display strings / aliases → ordered candidates to try against loaded `defense_id` keys.
_LEGACY_DEFENSE_ID_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "Man": ("man", "base-man"),
    "Man-to-Man": ("man", "base-man"),
    "Base Man": ("base-man", "man"),
    "Man Pressure": ("man", "base-man"),
    "Man Loose": ("man", "base-man"),
}

_lock = threading.Lock()
_by_defense_id: Dict[str, Dict[str, Any]] = {}
_name_to_defense_id: Dict[str, str] = {}
_oid_to_defense_id: Dict[str, str] = {}


def clear_defense_identity_cache() -> None:
    """Test helper / rare admin use."""
    global _by_defense_id, _name_to_defense_id, _oid_to_defense_id
    with _lock:
        _by_defense_id = {}
        _name_to_defense_id = {}
        _oid_to_defense_id = {}


def refresh_defense_identity_cache() -> None:
    """Load all universal defenses and rebuild lookup maps."""
    from BackEnd.db import defenses_collection

    by_id: Dict[str, Dict[str, Any]] = {}
    name_map: Dict[str, str] = {}
    oid_map: Dict[str, str] = {}

    for doc in defenses_collection.find({}):
        if not isinstance(doc, dict):
            continue
        did = doc.get("defense_id")
        if not did or not isinstance(did, str):
            continue
        did = did.strip()
        by_id[did] = doc
        name = doc.get("name")
        if isinstance(name, str) and name.strip():
            name_map[name.strip()] = did
        oid = doc.get("_id")
        if oid is not None:
            oid_map[str(oid)] = did

    with _lock:
        global _by_defense_id, _name_to_defense_id, _oid_to_defense_id
        _by_defense_id = by_id
        _name_to_defense_id = name_map
        _oid_to_defense_id = oid_map


def _ensure_cache() -> None:
    with _lock:
        empty = not _by_defense_id
    if empty:
        refresh_defense_identity_cache()


def get_defense_doc(defense_id: str) -> Optional[Dict[str, Any]]:
    """Return universal defense document for `defense_id`, or None."""
    if not defense_id or not isinstance(defense_id, str):
        return None
    _ensure_cache()
    with _lock:
        return _by_defense_id.get(defense_id)


def defense_display_name(defense_id: str) -> str:
    """Human-readable name for UI / logging; falls back to `defense_id`."""
    doc = get_defense_doc(defense_id)
    if doc:
        name = doc.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return defense_id


def is_zone_defense_id(defense_id: str) -> bool:
    """True if catalog defense is zone type; synthetics return False unless overridden."""
    if defense_id in SYNTHETIC_DEFENSE_IDS:
        return False
    doc = get_defense_doc(defense_id)
    if not doc:
        return False
    dtype = doc.get("defense_type")
    if isinstance(dtype, str) and dtype.strip().lower() == "zone":
        return True
    return False


def canonical_scouting_defense_key(value: Any) -> Optional[str]:
    """
    Key used in `scouting_data["defense"]` for half-court rows.

    Collapses man catalog variants (e.g. base-man) to `man` so one row tracks all man usage.
    """
    if value is None or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    did = resolve_to_defense_id(raw)
    if not did:
        return None
    if did == "base-man":
        return "man"
    return did


def defense_scouting_row_key(value: Any) -> str:
    """Like `canonical_scouting_defense_key` but never None — defaults to `man`."""
    ck = canonical_scouting_defense_key(value)
    if ck:
        return ck
    return "man"


def offense_vs_key_from_defense_input(value: Any) -> Optional[str]:
    """Map defense playcall / id to offense Playcalls vs_* bucket (e.g. vs_man)."""
    ck = canonical_scouting_defense_key(value)
    if not ck and isinstance(value, str) and value.strip():
        ck = canonical_scouting_defense_key(resolve_to_defense_id(value.strip()))
    if not ck:
        return None
    return _OFFENSE_VS_KEY_BY_ROW_KEY.get(ck)


def defense_zone_shell_variant(value: Any) -> Optional[str]:
    """For zone defenses: '23', '32', or '131' boundary set; None if not a zone row key."""
    ck = canonical_scouting_defense_key(value)
    if not ck and isinstance(value, str) and value.strip():
        ck = canonical_scouting_defense_key(resolve_to_defense_id(value.strip()))
    if not ck:
        return None
    return _ZONE_SHELL_BY_ROW_KEY.get(ck)


def resolve_to_defense_id(value: Any) -> Optional[str]:
    """
    Normalize mixed legacy inputs to canonical `defense_id`, or None if unknown.

    Accepts:
    - `defense_id` already (if present in DB or synthetic)
    - Legacy display `name` from `defenses.name`
    - `str(ObjectId)` if it matches a defense doc
    - Playbook keys: `zone_23`, `man_normal`, etc.
    - "Zone" → treated as 2-3 zone display path via `defense_utils`
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None

    if raw in SYNTHETIC_DEFENSE_IDS:
        return raw

    _ensure_cache()

    with _lock:
        if raw in _by_defense_id:
            return raw
        if raw in _oid_to_defense_id:
            return _oid_to_defense_id[raw]
        if raw in _name_to_defense_id:
            return _name_to_defense_id[raw]

    # Playbook slug keys
    if raw in PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID:
        return PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID[raw]
    if raw in PLAYBOOK_MAN_KEY_TO_DEFENSE_ID:
        return PLAYBOOK_MAN_KEY_TO_DEFENSE_ID[raw]

    # 24-char hex could be ObjectId string not yet in oid map (empty DB)
    if len(raw) == 24:
        try:
            oid = ObjectId(raw)
            from BackEnd.db import defenses_collection

            doc = defenses_collection.find_one({"_id": oid})
            if doc and isinstance(doc.get("defense_id"), str):
                refresh_defense_identity_cache()
                return doc["defense_id"].strip()
        except Exception:
            pass

    # Legacy display aliases (Man / base-man split across seed scripts)
    candidates = _LEGACY_DEFENSE_ID_CANDIDATES.get(raw)
    if candidates:
        with _lock:
            for c in candidates:
                if c in _by_defense_id:
                    return c

    # "Zone" → "2-3 Zone" name path
    from BackEnd.utils.defense_utils import map_defense_playcall_to_tracking_name

    mapped = map_defense_playcall_to_tracking_name(raw)
    if mapped != raw:
        return resolve_to_defense_id(mapped)

    return None
