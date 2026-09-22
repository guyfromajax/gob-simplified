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

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId

from BackEnd.persistence import get_store
_store = get_store()
defenses_collection = _store.defenses_collection

logger = logging.getLogger(__name__)

# Non-catalog rows used in scouting templates / sim (stable, not Mongo `defense_id`).
SYNTHETIC_DEFENSE_IDS: frozenset[str] = frozenset({"vs_Fast_Break", "FCP", "HCT"})

# Playbook percentage keys → `defenses.defense_id` (see `playbook_settings_utils.ZONE_DEFENSE_ID_TO_NAME`).
PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID: Dict[str, str] = {
    "zone_23": "2-3-zone",
    "zone_32": "3-2-zone",
    "zone_131": "1-3-1-zone",
}

# Playbook man keys → catalog `defense_id`. First-class man plays (integrating_new_d_plays.md): deny
# (tight) and loose are DISTINCT catalog ids; only they get their own posture. Phase-1 scope keeps the
# base/normal man on the legacy `man` id (= Base alias per §6) — the full `man_normal → base-man`
# migration is Phase 2 (scouting rows). All three remain man-family (`is_zone_defense` = False).
# Coach-facing display: Base Man / Deny Man / Loose Man; posture from `hco_defense_posture_from_call`.
PLAYBOOK_MAN_KEY_TO_DEFENSE_ID: Dict[str, str] = {
    "man_normal": "man",          # Phase 1: base stays `man`; → `base-man` in Phase 2
    "man_tight": "man-tight",     # Deny Man (renamed from legacy `man_pressure`)
    "man_pressure": "man-tight",  # legacy alias → tight/deny
    "man_loose": "man-loose",     # Loose Man
}


def hco_defense_posture_from_call(raw_call: Any) -> str:
    """Map a raw defense playcall (any string variant, user- or CPU-selected) to the HCO team
    **posture** keyword the placement geometry uses: ``"tight"`` / ``"loose"`` / ``"normal"``.

    Coach-facing name ``deny`` ↔ internal posture ``tight`` (owner decision 2026-07-19: keep the
    mapping at this boundary, do NOT rename internal `tight`). ``man loose`` → ``loose``; everything
    else (``man normal``, plain ``man``, and every zone — zone posture parity is a separate S4 slice)
    → ``normal``. Keyword-based so it's robust to spacing / casing / `_`/`-` variants
    (``man deny`` / ``man_pressure`` / ``Man Loose`` …). Retires the interim random posture roll."""
    s = str(raw_call or "").strip().lower().replace("-", " ").replace("_", " ")
    if not s:
        return "normal"
    if "deny" in s or "pressure" in s or "tight" in s:
        return "tight"
    if "loose" in s or "sag" in s:
        return "loose"
    return "normal"

# playbook `zone_23` / defenses.defense_id → inverse map for percentage lookup
DEFENSE_ID_TO_PLAYBOOK_ZONE_KEY: Dict[str, str] = {
    v: k for k, v in PLAYBOOK_ZONE_KEY_TO_DEFENSE_ID.items()
}

# Keys used in `scouting_data["defense"]` for half-court defense rows. `man-tight`/`man-loose` are the
# first-class man plays (integrating_new_d_plays.md Step A) — own rows; stats route here after the
# Step C `canonical_scouting_defense_key` flip (until then they collapse to `man` and stay at 0).
CANONICAL_HCO_DEFENSE_ROW_KEYS: Tuple[str, ...] = (
    "man",
    "man-tight",
    "man-loose",
    "2-3-zone",
    "3-2-zone",
    "1-3-1-zone",
)

# When scouting was keyed by display names, these alternate keys may hold the same row dict.
_SCOUTING_DEFENSE_LEGACY_KEYS_BY_CANONICAL: Dict[str, Tuple[str, ...]] = {
    "man": ("Man", "man"),
    "man-tight": ("Deny Man", "man-tight"),
    "man-loose": ("Loose Man", "man-loose"),
    "2-3-zone": ("2-3 Zone", "2-3-zone"),
    "3-2-zone": ("3-2 Zone", "3-2-zone"),
    "1-3-1-zone": ("1-3-1 Zone", "1-3-1-zone"),
}


def read_scouting_defense_row(defense_scouting: Any, canonical_row_key: str) -> Dict[str, Any]:
    """
    Return `scouting_data['defense'][*]` row dict for a canonical slug (`man`, `2-3-zone`, …).

    Dual-read: try canonical key first, then legacy display / casing variants so APIs (e.g.
    GET /api/playbooks) still surface effectiveness when persisted data uses pre-migration keys.
    """
    if not isinstance(defense_scouting, dict) or not canonical_row_key:
        return {}
    ck = canonical_row_key.strip()
    if not ck:
        return {}
    row = defense_scouting.get(ck)
    if isinstance(row, dict):
        return row
    for alt in _SCOUTING_DEFENSE_LEGACY_KEYS_BY_CANONICAL.get(ck, ()):
        row = defense_scouting.get(alt)
        if isinstance(row, dict):
            return row
    return {}

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

# LOADED-NESS IS TRACKED SEPARATELY FROM CONTENTS, and that separation is load-bearing.
# `_ensure_cache` used to test `not _by_defense_id`, so an EMPTY catalog was
# indistinguishable from an unloaded one and every lookup re-read the whole collection.
# When gob-staging.defenses was emptied by an unguarded test, that turned a cached lookup
# into 4,664 DB reads per game — 374 s of a 397 s profile, 94.4% of wall time, a ~60x sim
# slowdown with no error and no log line. See projects/Sim_Perf_Capstone.md.
#
# But an empty or failed load is NOT final. It used to be: a process that read the
# catalog while it was empty (gob-staging.defenses was emptied four times by unguarded
# tests) played man for every zone call until restart, with one log line. An unreachable
# database raised out of every lookup instead; it now degrades the same way.
# No real database has a legitimate empty window — publish_defenses upserts and the
# staging copy renames a temp collection — so "empty" and "failed" are both DEGRADED.
# Degraded states retry on the next lookup once DEFENSE_CATALOG_RETRY_SECONDS have
# passed: at most one catalog read per window, which keeps the perf guard above.
DEFENSE_CATALOG_RETRY_SECONDS = 30.0

_CATALOG_UNLOADED = "unloaded"
_CATALOG_LOADED = "loaded"
_CATALOG_EMPTY = "empty"
_CATALOG_FAILED = "failed"

_catalog_status: str = _CATALOG_UNLOADED
_catalog_next_retry_at: float = 0.0


def clear_defense_identity_cache() -> None:
    """Test helper / rare admin use."""
    global _by_defense_id, _name_to_defense_id, _oid_to_defense_id
    global _catalog_status, _catalog_next_retry_at
    with _lock:
        _by_defense_id = {}
        _name_to_defense_id = {}
        _oid_to_defense_id = {}
        _catalog_status = _CATALOG_UNLOADED
        _catalog_next_retry_at = 0.0


def _read_catalog_documents():
    """The one place the catalog is read. Raises if the database cannot be read."""

    return list(defenses_collection.find({}))


def _load_catalog(*, raise_on_error: bool) -> str:
    """Read the catalog and publish it. Returns the resulting catalog status.

    The status comes from what the READ did, not from guessing at the maps: an exception
    is ``failed``, a successful read with no usable documents is ``empty``.
    """
    global _by_defense_id, _name_to_defense_id, _oid_to_defense_id
    global _catalog_status, _catalog_next_retry_at

    with _lock:
        previous = _catalog_status
    try:
        docs = _read_catalog_documents()
    except Exception as exc:
        with _lock:
            _catalog_status = _CATALOG_FAILED
            _catalog_next_retry_at = time.monotonic() + DEFENSE_CATALOG_RETRY_SECONDS
        logger.error(
            "🛑 [DEFENSE-IDENTITY] Could not read the defense catalog (%s: %s). Zone calls "
            "will be played as MAN until it loads; retrying in %.0fs.",
            type(exc).__name__, exc, DEFENSE_CATALOG_RETRY_SECONDS,
        )
        if raise_on_error:
            raise
        return _CATALOG_FAILED

    by_id: Dict[str, Dict[str, Any]] = {}
    name_map: Dict[str, str] = {}
    oid_map: Dict[str, str] = {}

    for doc in docs:
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

    status = _CATALOG_LOADED if by_id else _CATALOG_EMPTY
    with _lock:
        _by_defense_id = by_id
        _name_to_defense_id = name_map
        _oid_to_defense_id = oid_map
        _catalog_status = status
        _catalog_next_retry_at = (
            0.0 if status == _CATALOG_LOADED
            else time.monotonic() + DEFENSE_CATALOG_RETRY_SECONDS
        )

    if status == _CATALOG_EMPTY:
        # Loud on every attempt. Attempts are already bounded to one per retry window.
        logger.error(
            "🛑 [DEFENSE-IDENTITY] Loaded the defense catalog and found ZERO usable "
            "documents (need a string `defense_id` field). Zone calls will be played as "
            "MAN until it loads; retrying in %.0fs. This is a DATA problem — the "
            "`defenses` collection is empty or malformed. Repopulate it.",
            DEFENSE_CATALOG_RETRY_SECONDS,
        )
    elif previous in (_CATALOG_EMPTY, _CATALOG_FAILED):
        logger.warning(
            "✅ [DEFENSE-IDENTITY] Defense catalog recovered after a %s load: %d documents.",
            previous, len(by_id),
        )
    return status


def refresh_defense_identity_cache() -> None:
    """Load all universal defenses and rebuild lookup maps. Raises if the read fails."""
    _load_catalog(raise_on_error=True)


def _ensure_cache() -> None:
    """Load the catalog on first use; retry a degraded (empty/failed) load after backoff."""
    with _lock:
        status = _catalog_status
        due = time.monotonic() >= _catalog_next_retry_at
    if status == _CATALOG_LOADED:
        return
    if status != _CATALOG_UNLOADED and not due:
        return
    _load_catalog(raise_on_error=False)


def defense_catalog_status() -> str:
    """``loaded`` / ``empty`` / ``failed`` after ensuring a load was attempted."""
    _ensure_cache()
    with _lock:
        return _catalog_status


# Canonical zone call → short shell label. Recognises that a ZONE WAS CALLED; it never
# decides whether a zone is played (that stays with the catalog via is_zone_defense).
_ZONE_CALL_SHORT_LABEL: Dict[str, str] = {
    "2-3-zone": "2-3",
    "3-2-zone": "3-2",
    "1-3-1-zone": "1-3-1",
    "zone_23": "2-3",
    "zone_32": "3-2",
    "zone_131": "1-3-1",
}


def zone_call_played_as_man(raw_call: Any) -> Optional[str]:
    """If ``raw_call`` is a zone call that will be placed as MAN, return its short label.

    That happens when the catalog is degraded or lacks the id. Returns None when the call
    is not a zone call or the zone resolves normally.
    """
    if not isinstance(raw_call, str):
        return None
    short = _ZONE_CALL_SHORT_LABEL.get(raw_call.strip())
    if short is None:
        return None
    from BackEnd.utils.defense_utils import is_zone_defense

    if is_zone_defense(raw_call):
        return None
    return short


def announce_zone_played_as_man(raw_call: Any, context: str) -> Optional[str]:
    """Log every zone call that is being substituted with man placement (policy 26b)."""
    short = zone_call_played_as_man(raw_call)
    if short is not None:
        with _lock:
            status = _catalog_status
        logger.warning(
            "⚠️ [DEFENSE-IDENTITY SUBSTITUTION] %s called %r but the defense catalog is %s → "
            "playing MAN placement for this possession.",
            context, raw_call, status,
        )
    return short


def defense_playcall_display_label(defense_id: str) -> str:
    """User-facing label for the defense actually being played.

    While a zone call is substituted with man, say so instead of naming the zone. The
    label deliberately avoids the word "zone" so the scoreboard buckets it as Man.
    """
    short = zone_call_played_as_man(defense_id)
    if short is not None:
        return f"Man ({short} unavailable)"
    return defense_display_name(defense_id)


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
    # First-class man plays (integrating_new_d_plays.md Step C, 2026-07-19): `man-tight` (Deny) and
    # `man-loose` (Loose) now have their OWN scouting rows (own EFF/MOM/CLK/usage) — no longer collapsed.
    # `base-man` still folds to the legacy `man` row (Base keeps its trained EFF there; the base→base-man
    # scouting split is a later migration). The row templates already carry man-tight/man-loose (Step A),
    # so stat increments land on real rows.
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
