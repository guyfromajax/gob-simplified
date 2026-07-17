"""
Helpers for migrating playbook settings across multiple persistence generations.

The backend now needs to tolerate:
- legacy percentage maps keyed by play name
- intermediate play_id-keyed maps split across set-play focus buckets
- new simplified settings using:
  - motion
  - set_plays
  - fast_breaks
  - man_defense
  - zone_defense
  - pc_order

These helpers normalize payloads for API responses and resolve weights safely at
runtime while we transition the UI and stored docs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


PLAYBOOK_PERCENTAGE_KEYS = (
    "motion",
    "set_plays",
)

# Sections that may carry durable per-play locks (Playbooks redesign enforced model).
PLAYBOOK_LOCK_SECTION_KEYS = (
    "motion",
    "set_plays",
    "fast_breaks",
    "hc_traps",
    "man_defense",
    "zone_defense",
)

LEGACY_SET_PLAY_KEYS = (
    "set_play_inside",
    "set_play_attack",
    "set_play_outside",
)

MAN_DEFENSE_ID_TO_NAME = {
    "man_normal": "Man",
    "man_pressure": "Man Pressure",
    "man_loose": "Man Loose",
}
ZONE_DEFENSE_ID_TO_NAME = {
    "zone_23": "2-3 Zone",
    "zone_32": "3-2 Zone",
    "zone_131": "1-3-1 Zone",
}
FAST_BREAK_ID_ALIASES = {
    "triangle": "triangle",
    "Triangle": "triangle",
    "rim_runner": "rim_runner",
    "Rim Runner": "rim_runner",
    "covert_release": "covert_release",
    "Covert Release": "covert_release",
}
HCT_TRAP_ID_ALIASES = {
    "standard_trap": "standard_trap",
    "Standard Trap": "standard_trap",
    "straight_pressure": "straight_pressure",
    "Straight Pressure": "straight_pressure",
    "standard_diamond": "standard_diamond",
    "Standard Diamond": "standard_diamond",
    # Legacy aliases migrate onto standard_diamond.
    "diamond": "standard_diamond",
    "Diamond": "standard_diamond",
}
DEFENSE_NAME_TO_ID = {
    **{v: k for k, v in MAN_DEFENSE_ID_TO_NAME.items()},
    **{v: k for k, v in ZONE_DEFENSE_ID_TO_NAME.items()},
}


def build_play_lookups_from_team_plays(plays: Dict[str, Dict[str, Any]] | None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build play_id/name lookup maps from a team plays dictionary."""
    plays_by_id: Dict[str, Dict[str, Any]] = {}
    plays_by_name: Dict[str, Dict[str, Any]] = {}

    if not isinstance(plays, dict):
        return plays_by_id, plays_by_name

    for play_name, play_data in plays.items():
        if not isinstance(play_data, dict):
            continue
        resolved_name = play_data.get("name") or play_name
        if resolved_name:
            plays_by_name[resolved_name] = play_data
        play_id = play_data.get("play_id")
        if play_id:
            plays_by_id[str(play_id)] = play_data

    return plays_by_id, plays_by_name


def build_play_lookups_from_universal_plays(plays: Iterable[Dict[str, Any]] | None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build play_id/name lookup maps from universal play docs."""
    plays_by_id: Dict[str, Dict[str, Any]] = {}
    plays_by_name: Dict[str, Dict[str, Any]] = {}

    if not plays:
        return plays_by_id, plays_by_name

    for play in plays:
        if not isinstance(play, dict):
            continue
        play_name = play.get("name")
        play_id = play.get("play_id") or play.get("_id")
        if play_name:
            plays_by_name[play_name] = play
        if play_id:
            plays_by_id[str(play_id)] = play

    return plays_by_id, plays_by_name


def normalize_percentage_map_to_play_ids(
    percentage_map: Dict[str, Any] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """
    Convert a legacy or mixed percentage map into a play_id-keyed map.

    Unresolvable entries are preserved under their original key so no data is silently dropped.
    """
    if not isinstance(percentage_map, dict):
        return {}

    normalized: Dict[str, Any] = {}
    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}

    for raw_key, raw_value in percentage_map.items():
        normalized_key = raw_key

        if raw_key in plays_by_id:
            normalized_key = raw_key
        else:
            play_data = plays_by_name.get(raw_key)
            if isinstance(play_data, dict) and play_data.get("play_id"):
                normalized_key = str(play_data["play_id"])

        normalized[normalized_key] = raw_value

    return normalized


def resolve_playbook_percentage(
    percentage_map: Dict[str, Any] | None,
    *,
    play_id: str | None = None,
    play_name: str | None = None,
    default: Any = 0,
) -> Any:
    """Resolve a percentage from a mixed legacy/new playbook map."""
    if not isinstance(percentage_map, dict):
        return default

    if play_id is not None:
        play_id = str(play_id)
        if play_id in percentage_map:
            return percentage_map[play_id]

    if play_name is not None and play_name in percentage_map:
        return percentage_map[play_name]

    return default


def normalize_slot_assignments_to_play_ids(
    slot_assignments: Dict[str, Dict[str, Any]] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Dict[str, Any]]:
    """Ensure play slot assignments store playId as play_id and playName as display text."""
    if not isinstance(slot_assignments, dict):
        return {}

    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}
    normalized: Dict[str, Dict[str, Any]] = {}

    for slot_key, assignment in slot_assignments.items():
        if not isinstance(assignment, dict):
            continue

        normalized_assignment = dict(assignment)
        play_id = assignment.get("playId")
        play_name = assignment.get("playName")
        play_data = None

        if play_id is not None:
            play_data = plays_by_id.get(str(play_id))
        if play_data is None and play_name:
            play_data = plays_by_name.get(play_name)
        if play_data is None and isinstance(play_id, str):
            play_data = plays_by_name.get(play_id)

        if isinstance(play_data, dict):
            resolved_play_id = play_data.get("play_id") or play_id
            resolved_play_name = play_data.get("name") or play_name
            if resolved_play_id:
                normalized_assignment["playId"] = str(resolved_play_id)
            if resolved_play_name:
                normalized_assignment["playName"] = resolved_play_name

        normalized[str(slot_key)] = normalized_assignment

    return normalized


def normalize_motion_dropdowns_to_play_ids(
    motion_dropdowns: Dict[str, Any] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """Ensure motion dropdown settings are keyed by play_id when possible."""
    if not isinstance(motion_dropdowns, dict):
        return {}

    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}
    normalized: Dict[str, Any] = {}

    for raw_key, raw_value in motion_dropdowns.items():
        normalized_key = raw_key

        if raw_key in plays_by_id:
            normalized_key = raw_key
        else:
            play_data = plays_by_name.get(raw_key)
            if isinstance(play_data, dict) and play_data.get("play_id"):
                normalized_key = str(play_data["play_id"])

        normalized[normalized_key] = raw_value

    return normalized


def _coerce_int(value: Any) -> int:
    """Best-effort int coercion (non-numeric → 0)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_string_keyed_map(
    raw_map: Dict[str, Any] | None,
    aliases: Dict[str, str] | None,
) -> Dict[str, Any]:
    """Normalize a simple string-keyed map through an alias table."""
    if not isinstance(raw_map, dict):
        return {}

    aliases = aliases or {}
    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in raw_map.items():
        normalized[aliases.get(raw_key, raw_key)] = raw_value
    return normalized


def merge_percentage_maps(*maps: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge percentage maps left-to-right, keeping the latest value for each key."""
    merged: Dict[str, Any] = {}
    for raw_map in maps:
        if not isinstance(raw_map, dict):
            continue
        for raw_key, raw_value in raw_map.items():
            merged[raw_key] = raw_value
    return merged


def empty_playbook_locks() -> Dict[str, List[str]]:
    """Canonical empty locks object — every percentage section has a list."""
    return {key: [] for key in PLAYBOOK_LOCK_SECTION_KEYS}


def _resolve_lock_entry_id(
    raw_key: Any,
    *,
    section_key: str,
    plays_by_id: Dict[str, Dict[str, Any]],
    plays_by_name: Dict[str, Dict[str, Any]],
    aliases: Dict[str, str],
) -> str | None:
    if raw_key is None:
        return None
    key = str(raw_key).strip()
    if not key:
        return None

    if section_key in ("motion", "set_plays"):
        if key in plays_by_id:
            return key
        play_data = plays_by_name.get(key)
        if isinstance(play_data, dict):
            play_id = play_data.get("play_id") or play_data.get("_id")
            if play_id:
                return str(play_id)
        return key

    return aliases.get(key, key)


def normalize_playbook_locks(
    raw_locks: Any,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, List[str]]:
    """
    Normalize durable playbook locks into:

        {
          "motion": [play_id, ...],
          "set_plays": [...],
          "fast_breaks": [...],
          "hc_traps": [...],
          "man_defense": [...],
          "zone_defense": [...],
        }

    Accepts per-section lists of ids/names, or dicts of id → truthy (locked).
    Missing / invalid input → empty lists. Order preserved; duplicates dropped.
    """
    locks = empty_playbook_locks()
    if not isinstance(raw_locks, dict):
        return locks

    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}
    section_aliases = {
        "motion": {},
        "set_plays": {},
        "fast_breaks": FAST_BREAK_ID_ALIASES,
        "hc_traps": HCT_TRAP_ID_ALIASES,
        "man_defense": {**{v: k for k, v in MAN_DEFENSE_ID_TO_NAME.items()}, **{k: k for k in MAN_DEFENSE_ID_TO_NAME}},
        "zone_defense": {**{v: k for k, v in ZONE_DEFENSE_ID_TO_NAME.items()}, **{k: k for k in ZONE_DEFENSE_ID_TO_NAME}},
    }

    for section_key in PLAYBOOK_LOCK_SECTION_KEYS:
        raw_section = raw_locks.get(section_key)
        aliases = section_aliases[section_key]
        seen: set[str] = set()
        normalized_ids: List[str] = []

        def _append(raw_id: Any) -> None:
            resolved = _resolve_lock_entry_id(
                raw_id,
                section_key=section_key,
                plays_by_id=plays_by_id,
                plays_by_name=plays_by_name,
                aliases=aliases,
            )
            if not resolved or resolved in seen:
                return
            seen.add(resolved)
            normalized_ids.append(resolved)

        if isinstance(raw_section, list):
            for entry in raw_section:
                _append(entry)
        elif isinstance(raw_section, dict):
            for raw_id, flag in raw_section.items():
                if flag:
                    _append(raw_id)

        locks[section_key] = normalized_ids

    return locks


def normalize_pc_order(
    pc_order: Dict[str, Any] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, List[str]]:
    """Normalize pc_order to play_id / stable defense-id lists."""
    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}

    normalized = {
        "offense": [],
        "defense": [],
    }

    if not isinstance(pc_order, dict):
        return normalized

    for raw_item in pc_order.get("offense", []) or []:
        resolved_item = None
        if isinstance(raw_item, str):
            if raw_item in plays_by_id:
                resolved_item = raw_item
            else:
                play_data = plays_by_name.get(raw_item)
                if isinstance(play_data, dict) and play_data.get("play_id"):
                    resolved_item = str(play_data["play_id"])
        elif isinstance(raw_item, dict):
            play_id = raw_item.get("playId") or raw_item.get("play_id")
            play_name = raw_item.get("playName") or raw_item.get("name")
            if play_id and str(play_id) in plays_by_id:
                resolved_item = str(play_id)
            elif play_name:
                play_data = plays_by_name.get(play_name)
                if isinstance(play_data, dict) and play_data.get("play_id"):
                    resolved_item = str(play_data["play_id"])

        if resolved_item and resolved_item not in normalized["offense"]:
            normalized["offense"].append(resolved_item)

    for raw_item in pc_order.get("defense", []) or []:
        resolved_item = None
        if isinstance(raw_item, str):
            resolved_item = DEFENSE_NAME_TO_ID.get(raw_item, raw_item)
        elif isinstance(raw_item, dict):
            defense_id = raw_item.get("defenseId") or raw_item.get("id")
            defense_name = raw_item.get("name")
            if defense_id:
                resolved_item = defense_id
            elif defense_name:
                resolved_item = DEFENSE_NAME_TO_ID.get(defense_name, defense_name)
        if resolved_item and resolved_item not in normalized["defense"]:
            normalized["defense"].append(resolved_item)

    return normalized


def slot_assignments_to_pc_order(
    slot_assignments: Dict[str, Dict[str, Any]] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, List[str]]:
    """Convert legacy slot assignments into offense-only pc_order."""
    normalized_slots = normalize_slot_assignments_to_play_ids(
        slot_assignments,
        plays_by_id,
        plays_by_name,
    )

    offense: List[str] = []
    for _slot_num, assignment in sorted(
        normalized_slots.items(),
        key=lambda item: int(item[0]) if str(item[0]).isdigit() else 999,
    ):
        if not isinstance(assignment, dict):
            continue
        play_id = assignment.get("playId")
        if play_id and str(play_id) not in offense:
            offense.append(str(play_id))

    return {
        "offense": offense,
        "defense": [],
    }


def build_simplified_playbook_settings(
    playbook_settings: Dict[str, Any] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """Project any supported playbook_settings shape into the new simplified model."""
    playbook_settings = playbook_settings or {}
    plays_by_id = plays_by_id or {}
    plays_by_name = plays_by_name or {}

    motion = normalize_percentage_map_to_play_ids(
        playbook_settings.get("motion", {}),
        plays_by_id,
        plays_by_name,
    )

    set_plays = normalize_percentage_map_to_play_ids(
        playbook_settings.get("set_plays", {}),
        plays_by_id,
        plays_by_name,
    )
    if not set_plays:
        set_plays = merge_percentage_maps(
            normalize_percentage_map_to_play_ids(
                playbook_settings.get("set_play_inside", {}),
                plays_by_id,
                plays_by_name,
            ),
            normalize_percentage_map_to_play_ids(
                playbook_settings.get("set_play_attack", {}),
                plays_by_id,
                plays_by_name,
            ),
            normalize_percentage_map_to_play_ids(
                playbook_settings.get("set_play_outside", {}),
                plays_by_id,
                plays_by_name,
            ),
        )

    fast_breaks = normalize_string_keyed_map(
        playbook_settings.get("fast_breaks", playbook_settings.get("fast_break", {})),
        FAST_BREAK_ID_ALIASES,
    )
    hc_traps = normalize_string_keyed_map(
        playbook_settings.get("hc_traps", playbook_settings.get("hc_trap_plays", {})),
        HCT_TRAP_ID_ALIASES,
    )
    # Playbooks saved before hc_traps existed have no map → the display surfaces
    # would render "No plays assigned" even though gameplay falls back to the
    # DEFAULT_HCT_TRAP_WEIGHTS split (see _resolve_hct_trap_weights). Mirror that
    # fallback here so the UI reflects what the team actually runs.
    if not any(_coerce_int(value) > 0 for value in hc_traps.values()):
        from BackEnd.constants.hct_trap_play_types import DEFAULT_HCT_TRAP_WEIGHTS

        hc_traps = {
            key: value
            for key, value in DEFAULT_HCT_TRAP_WEIGHTS.items()
            if value > 0
        }
    zone_defense = normalize_string_keyed_map(
        playbook_settings.get("zone_defense", {}),
        DEFENSE_NAME_TO_ID,
    )
    man_defense = normalize_string_keyed_map(
        playbook_settings.get("man_defense", {}),
        DEFENSE_NAME_TO_ID,
    )

    if isinstance(playbook_settings.get("pc_order"), dict):
        pc_order = normalize_pc_order(
            playbook_settings.get("pc_order"),
            plays_by_id,
            plays_by_name,
        )
    else:
        pc_order = slot_assignments_to_pc_order(
            playbook_settings.get("slot_assignments", {}),
            plays_by_id,
            plays_by_name,
        )

    # Game / franchise snapshots often store defense in pc_order but offense only in
    # slot_assignments (or offense list empty after a partial write). If we only run
    # normalize_pc_order because pc_order is a dict, offense would stay empty forever.
    if not (pc_order.get("offense") or []):
        from_slots = slot_assignments_to_pc_order(
            playbook_settings.get("slot_assignments", {}),
            plays_by_id,
            plays_by_name,
        )
        slot_off = from_slots.get("offense") or []
        if slot_off:
            pc_order = dict(pc_order)
            pc_order["offense"] = list(slot_off)

    raw_meta = playbook_settings.get("_meta", {})
    meta = raw_meta.copy() if isinstance(raw_meta, dict) else {}
    meta = {
        "user_saved": bool(meta.get("user_saved", False)),
        "schema_version": meta.get("schema_version", 2),
    }

    locks = normalize_playbook_locks(
        playbook_settings.get("locks"),
        plays_by_id,
        plays_by_name,
    )

    return {
        "motion": motion,
        "set_plays": set_plays,
        "fast_breaks": fast_breaks,
        "hc_traps": hc_traps,
        "man_defense": man_defense,
        "zone_defense": zone_defense,
        "pc_order": pc_order,
        "locks": locks,
        "_meta": meta,
    }


def build_legacy_playbook_settings_view(
    simple_settings: Dict[str, Any] | None,
    plays_by_id: Dict[str, Dict[str, Any]] | None,
    plays_by_name: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """Provide a backward-compatible view for older frontend code."""
    simple_settings = simple_settings or {}
    plays_by_id = plays_by_id or {}

    set_play_inside: Dict[str, Any] = {}
    set_play_attack: Dict[str, Any] = {}
    set_play_outside: Dict[str, Any] = {}

    for play_id, percentage in (simple_settings.get("set_plays", {}) or {}).items():
        play_data = plays_by_id.get(str(play_id))
        play_focus = play_data.get("play_focus") if isinstance(play_data, dict) else None
        if play_focus == "attack":
            set_play_attack[str(play_id)] = percentage
        elif play_focus == "outside":
            set_play_outside[str(play_id)] = percentage
        else:
            set_play_inside[str(play_id)] = percentage

    offense_slots = {}
    for idx, play_id in enumerate(simple_settings.get("pc_order", {}).get("offense", []) or [], start=1):
        play_data = plays_by_id.get(str(play_id))
        play_focus = (play_data or {}).get("play_focus")
        if (play_data or {}).get("play_type") == "motion":
            section = "motion"
        elif play_focus == "attack":
            section = "set_play_attack"
        elif play_focus == "outside":
            section = "set_play_outside"
        else:
            section = "set_play_inside"
        offense_slots[str(idx)] = {
            "section": section,
            "playId": str(play_id),
            "playName": (play_data or {}).get("name") or str(play_id),
        }

    return {
        "motion": dict(simple_settings.get("motion", {}) or {}),
        "set_play_inside": set_play_inside,
        "set_play_attack": set_play_attack,
        "set_play_outside": set_play_outside,
        "fast_break": dict(simple_settings.get("fast_breaks", {}) or {}),
        "hc_traps": dict(simple_settings.get("hc_traps", {}) or {}),
        "man_defense": {
            MAN_DEFENSE_ID_TO_NAME.get(key, key): value
            for key, value in (simple_settings.get("man_defense", {}) or {}).items()
        },
        "zone_defense": {
            ZONE_DEFENSE_ID_TO_NAME.get(key, key): value
            for key, value in (simple_settings.get("zone_defense", {}) or {}).items()
        },
        "slot_assignments": offense_slots,
        "motion_dropdowns": {},
        "_meta": dict(simple_settings.get("_meta", {}) or {}),
    }
