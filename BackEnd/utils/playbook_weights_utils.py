"""
Helpers for deriving position shot weights from playbook settings and Playcall Center.

The resulting values are cached inside playbook_settings so multiple pages can
read the same backend-derived result without recalculating it in the browser.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from bson import ObjectId

from BackEnd.utils.playbook_settings_utils import build_simplified_playbook_settings
from BackEnd.utils.team_play_utils import build_team_play_indexes


POSITION_ORDER = ("PG", "SG", "SF", "PF", "C")
NON_SUCCESS_VARIANTS = ("mid_play_change", "contested", "broken")
SET_PLAY_POSITION_ALIASES = ("target_shooter", "pos1", "pos2", "pos3", "pos4")
WEIGHTS_ALGORITHM_VERSION = 1


def _zero_weights() -> Dict[str, int]:
    return {position: 0 for position in POSITION_ORDER}


def _zero_float_weights() -> Dict[str, float]:
    return {position: 0.0 for position in POSITION_ORDER}


def _normalize_position(value: Any) -> str | None:
    if value is None:
        return None
    position = str(value).strip().upper()
    return position if position in POSITION_ORDER else None


def _build_set_play_alias_map(target_shooter: str | None) -> Dict[str, str]:
    normalized_target = _normalize_position(target_shooter)
    if not normalized_target:
        return {}

    remaining = [position for position in POSITION_ORDER if position != normalized_target]
    alias_map = {"target_shooter": normalized_target}
    for index, position in enumerate(remaining, start=1):
        alias_map[f"pos{index}"] = position
    return alias_map


def _remap_event_positions(event: dict[str, Any], alias_map: Dict[str, str]) -> dict[str, Any]:
    if not isinstance(event, dict) or not alias_map:
        return event

    updated = copy.deepcopy(event)
    for field in ("by", "for", "from", "to"):
        value = updated.get(field)
        if value in alias_map:
            updated[field] = alias_map[value]
    return updated


def _remap_skeleton_steps(steps: List[dict[str, Any]], target_shooter: str | None) -> List[dict[str, Any]]:
    alias_map = _build_set_play_alias_map(target_shooter)
    if not alias_map:
        return list(steps or [])

    updated_steps: List[dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        updated_step = copy.deepcopy(step)
        pos_actions = updated_step.get("pos_actions") or {}
        remapped_pos_actions = {}
        for position, action_info in pos_actions.items():
            remapped_pos_actions[alias_map.get(position, position)] = action_info
        updated_step["pos_actions"] = remapped_pos_actions
        events = updated_step.get("events") or []
        updated_step["events"] = [_remap_event_positions(event, alias_map) for event in events]
        updated_steps.append(updated_step)
    return updated_steps


def _iter_variant_instances(variant_data: dict[str, Any] | None) -> Iterable[List[dict[str, Any]]]:
    if not isinstance(variant_data, dict):
        return []

    versions = variant_data.get("versions")
    if isinstance(versions, list):
        return [
            list(version.get("steps") or [])
            for version in versions
            if isinstance(version, dict) and (version.get("steps") or [])
        ]

    steps = variant_data.get("steps") or []
    if steps:
        return [list(steps)]

    return []


def _extract_successful_shooter_from_steps(steps: List[dict[str, Any]]) -> str | None:
    for step in reversed(steps or []):
        events = step.get("events") or []
        for event in reversed(events):
            if str(event.get("type") or "").strip().lower() == "shot":
                by = _normalize_position(event.get("by"))
                if by:
                    return by

        pos_actions = step.get("pos_actions") or {}
        for position, action_info in pos_actions.items():
            if str((action_info or {}).get("action") or "").strip().lower() == "shoot":
                normalized_position = _normalize_position(position)
                if normalized_position:
                    return normalized_position
    return None


def _extract_explicit_non_success_shooters(play_doc: dict[str, Any], target_shooter: str | None) -> List[str]:
    alias_map = _build_set_play_alias_map(target_shooter)
    shooters: List[str] = []
    for field in ("pos1", "pos2", "pos3", "pos4"):
        raw_value = play_doc.get(field)
        if raw_value is None:
            continue
        mapped = alias_map.get(raw_value, raw_value)
        normalized = _normalize_position(mapped)
        if normalized:
            shooters.append(normalized)
    return shooters


def _extract_non_success_shooters_from_skeletons(play_doc: dict[str, Any], target_shooter: str | None) -> List[str]:
    skeletons = play_doc.get("skeletons") or {}
    shooters: List[str] = []
    for variant_name in NON_SUCCESS_VARIANTS:
        for steps in _iter_variant_instances(skeletons.get(variant_name)):
            remapped_steps = _remap_skeleton_steps(steps, target_shooter)
            shooter = _extract_successful_shooter_from_steps(remapped_steps)
            if shooter:
                shooters.append(shooter)
    return shooters


def _resolve_target_shooter(team_play: dict[str, Any], play_doc: dict[str, Any]) -> str | None:
    team_target = _normalize_position((team_play or {}).get("target_shooter"))

    successful_variant = ((play_doc or {}).get("skeletons") or {}).get("successful")
    successful_instances = list(_iter_variant_instances(successful_variant))
    successful_steps = successful_instances[0] if successful_instances else []
    remapped_successful_steps = _remap_skeleton_steps(successful_steps, team_target or play_doc.get("target_shooter"))
    successful_shooter = _extract_successful_shooter_from_steps(remapped_successful_steps)
    if successful_shooter:
        return successful_shooter

    return team_target or _normalize_position((play_doc or {}).get("target_shooter"))


def _calculate_single_play_distribution(
    team_play: dict[str, Any],
    play_doc: dict[str, Any],
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    target_shooter = _resolve_target_shooter(team_play, play_doc)
    if not target_shooter:
        return _zero_float_weights(), {
            "target_shooter": None,
            "non_success_shooters": [],
            "source": "missing_target",
        }

    explicit_shooters = _extract_explicit_non_success_shooters(play_doc, target_shooter)
    non_success_shooters = explicit_shooters or _extract_non_success_shooters_from_skeletons(play_doc, target_shooter)
    source = "explicit_fields" if explicit_shooters else "skeletons"

    distribution = _zero_float_weights()
    if not non_success_shooters:
        distribution[target_shooter] = 100.0
        return distribution, {
            "target_shooter": target_shooter,
            "non_success_shooters": [],
            "source": f"{source}:target_only",
        }

    counts = _zero_float_weights()
    for shooter in non_success_shooters:
        normalized = _normalize_position(shooter)
        if normalized:
            counts[normalized] += 1

    total_non_success = sum(counts.values())
    distribution[target_shooter] += 60.0
    if total_non_success > 0:
        for position in POSITION_ORDER:
            if counts[position] > 0:
                distribution[position] += 40.0 * (counts[position] / total_non_success)

    return distribution, {
        "target_shooter": target_shooter,
        "non_success_shooters": non_success_shooters,
        "source": source,
    }


def _round_weights_to_100(weight_map: Dict[str, float]) -> Dict[str, int]:
    raw_values = {position: float(weight_map.get(position, 0.0) or 0.0) for position in POSITION_ORDER}
    floors = {position: int(raw_values[position]) for position in POSITION_ORDER}
    remainder = 100 - sum(floors.values())

    if remainder > 0:
        ranked = sorted(
            POSITION_ORDER,
            key=lambda position: (raw_values[position] - floors[position], raw_values[position], position),
            reverse=True,
        )
        for position in ranked[:remainder]:
            floors[position] += 1
    elif remainder < 0:
        ranked = sorted(
            POSITION_ORDER,
            key=lambda position: (raw_values[position] - floors[position], raw_values[position], position),
        )
        to_remove = abs(remainder)
        for position in ranked:
            if to_remove <= 0:
                break
            if floors[position] <= 0:
                continue
            floors[position] -= 1
            to_remove -= 1

    return floors


def _fetch_universal_play_docs_by_id(play_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    from BackEnd.db import plays_collection

    object_ids = []
    string_ids = []
    for play_id in play_ids:
        if not play_id:
            continue
        try:
            object_ids.append(ObjectId(str(play_id)))
        except Exception:
            string_ids.append(str(play_id))

    query = {"$or": []}
    if object_ids:
        query["$or"].append({"_id": {"$in": object_ids}})
    if string_ids:
        query["$or"].append({"_id": {"$in": string_ids}})
    if not query["$or"]:
        return {}

    docs = list(plays_collection.find(query, {"name": 1, "play_type": 1, "target_shooter": 1, "pos1": 1, "pos2": 1, "pos3": 1, "pos4": 1, "skeletons": 1}))
    return {str(doc.get("_id")): doc for doc in docs if doc.get("_id") is not None}


def compute_position_shot_weights(
    playbook_settings: Dict[str, Any] | None,
    team_plays: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, Any]:
    playbook_settings = dict(playbook_settings or {})
    team_plays = team_plays or {}
    _, team_plays_by_id, team_plays_by_name = build_team_play_indexes(team_plays)
    simplified = build_simplified_playbook_settings(playbook_settings, team_plays_by_id, team_plays_by_name)

    play_ids = set()
    play_ids.update(str(play_id) for play_id in (simplified.get("motion") or {}).keys())
    play_ids.update(str(play_id) for play_id in (simplified.get("set_plays") or {}).keys())
    play_ids.update(str(play_id) for play_id in ((simplified.get("pc_order") or {}).get("offense") or []))
    universal_plays_by_id = _fetch_universal_play_docs_by_id(play_ids)

    playbook_totals = _zero_float_weights()
    playcall_center_totals = _zero_float_weights()
    source_signature = {
        "algorithm_version": WEIGHTS_ALGORITHM_VERSION,
        "playbooks": [],
        "playcall_center": [],
    }

    for section_key in ("motion", "set_plays"):
        for play_id, raw_percentage in (simplified.get(section_key) or {}).items():
            percentage = float(raw_percentage or 0)
            if percentage <= 0:
                continue
            team_play = team_plays_by_id.get(str(play_id)) or {}
            play_doc = universal_plays_by_id.get(str(play_id))
            if not play_doc:
                continue
            distribution, signature = _calculate_single_play_distribution(team_play, play_doc)
            source_signature["playbooks"].append({
                "play_id": str(play_id),
                "weight": percentage,
                "signature": signature,
            })
            for position in POSITION_ORDER:
                playbook_totals[position] += distribution[position] * (percentage / 100.0)

    offense_pc_order = [str(play_id) for play_id in ((simplified.get("pc_order") or {}).get("offense") or []) if str(play_id)]
    if offense_pc_order:
        per_play_weight = 100.0 / len(offense_pc_order)
        for play_id in offense_pc_order:
            team_play = team_plays_by_id.get(play_id) or {}
            play_doc = universal_plays_by_id.get(play_id)
            if not play_doc:
                continue
            distribution, signature = _calculate_single_play_distribution(team_play, play_doc)
            source_signature["playcall_center"].append({
                "play_id": play_id,
                "weight": per_play_weight,
                "signature": signature,
            })
            for position in POSITION_ORDER:
                playcall_center_totals[position] += distribution[position] * (per_play_weight / 100.0)

    source_hash = hashlib.sha1(json.dumps(source_signature, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "playbooks": _round_weights_to_100(playbook_totals),
        "playcall_center": _round_weights_to_100(playcall_center_totals),
        "_meta": {
            "algorithm_version": WEIGHTS_ALGORITHM_VERSION,
            "source_hash": source_hash,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def weights_cache_is_stale(
    cached_weights: Dict[str, Any] | None,
    fresh_weights: Dict[str, Any] | None,
) -> bool:
    cached_meta = (cached_weights or {}).get("_meta") or {}
    fresh_meta = (fresh_weights or {}).get("_meta") or {}
    if cached_meta.get("algorithm_version") != fresh_meta.get("algorithm_version"):
        return True
    return cached_meta.get("source_hash") != fresh_meta.get("source_hash")
