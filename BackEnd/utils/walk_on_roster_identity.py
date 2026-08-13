"""Stamp jersey + walk-on portrait when a Walk On survives onto the active 12.

Called after user/CPU camp cuts finalize ``FTD.players``. Skips players that
already have ``meta.jersey`` / ``meta.image_id``. League-wide (per franchise
season) portrait de-dupe via ``franchises.walk_on_image_ids_used``.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Mapping, Optional

from BackEnd.utils.jersey_assignment import jersey_position_for_player, pick_jersey_number
from BackEnd.utils.walk_on_portraits import (
    FRANCHISE_USED_FIELD,
    is_walk_on_fpd,
    pick_walk_on_image_id,
)

logger = logging.getLogger(__name__)


def _meta_jersey(doc: Mapping[str, Any] | None) -> Any:
    if not doc:
        return None
    meta = doc.get("meta") if isinstance(doc.get("meta"), Mapping) else {}
    return meta.get("jersey")


def _meta_image_id(doc: Mapping[str, Any] | None) -> str | None:
    if not doc:
        return None
    meta = doc.get("meta") if isinstance(doc.get("meta"), Mapping) else {}
    raw = meta.get("image_id") or doc.get("image_id")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _taken_jerseys_on_roster(
    active_player_ids: list[str],
    fpd_map: Mapping[str, dict[str, Any]],
) -> set[int]:
    taken: set[int] = set()
    for pid in active_player_ids:
        j = _meta_jersey(fpd_map.get(pid))
        try:
            if j is not None:
                taken.add(int(j))
        except (TypeError, ValueError):
            continue
    return taken


def assign_walk_ons_making_active_roster(
    *,
    franchise_id: Any,
    team_id: Any,
    active_player_ids: list[str],
    fpd_map: dict[str, dict[str, Any]],
    franchise_players_data_collection: Any,
    franchises_collection: Any,
    teams_collection: Any = None,
    franchise_doc: Optional[dict[str, Any]] = None,
    warm: bool = False,
    rng: Optional[random.Random] = None,
) -> dict[str, Any]:
    """Assign missing jersey/image_id to Walk Ons on the active 12.

    Returns a summary dict. When ``warm`` is True, eagerly paints the team's
    newly stamped masters (user path); CPU stays lazy via ensure_player_image.
    """
    summary = {
        "considered": 0,
        "jersey_assigned": 0,
        "image_assigned": 0,
        "skipped_not_walk_on": 0,
        "skipped_has_jersey": 0,
        "skipped_has_image": 0,
        "warmed": 0,
        "assignments": [],  # [{player_id, jersey, image_id}]
    }
    fid_str = str(franchise_id)
    team_id_str = str(team_id) if team_id is not None else ""

    walk_ons: list[tuple[str, dict[str, Any]]] = []
    for pid in active_player_ids:
        doc = fpd_map.get(pid) or {}
        if not is_walk_on_fpd(doc):
            summary["skipped_not_walk_on"] += 1
            continue
        summary["considered"] += 1
        walk_ons.append((pid, doc))

    if not walk_ons:
        return summary

    # Fresh used-list from franchise (shared across all teams this season).
    fran = franchises_collection.find_one(
        {"_id": franchise_id}, {FRANCHISE_USED_FIELD: 1}
    ) or {}
    used_ids = [str(x) for x in (fran.get(FRANCHISE_USED_FIELD) or []) if x]
    taken = _taken_jerseys_on_roster(active_player_ids, fpd_map)
    newly_used: list[str] = []
    to_warm: list[dict[str, Any]] = []

    for pid, doc in walk_ons:
        meta = dict(doc.get("meta") or {})
        # Merge top-level identity fields for jersey position resolution.
        player_view = {
            **doc,
            "meta": meta,
            "position_intent": doc.get("position_intent") or meta.get("position_intent"),
            "position_ratings": doc.get("position_ratings") or meta.get("position_ratings"),
        }
        set_fields: dict[str, Any] = {}
        jersey = _meta_jersey(doc)
        image_id = _meta_image_id(doc)

        if jersey is not None:
            summary["skipped_has_jersey"] += 1
            try:
                taken.add(int(jersey))
            except (TypeError, ValueError):
                pass
        else:
            pos = jersey_position_for_player(player_view)
            jersey = pick_jersey_number(pos, taken, rng=rng)
            taken.add(int(jersey))
            set_fields["meta.jersey"] = jersey
            summary["jersey_assigned"] += 1

        if image_id:
            summary["skipped_has_image"] += 1
        else:
            image_id = pick_walk_on_image_id(used_ids + newly_used, rng=rng)
            if image_id:
                set_fields["meta.image_id"] = image_id
                newly_used.append(image_id)
                summary["image_assigned"] += 1

        if not set_fields:
            continue

        franchise_players_data_collection.update_one(
            {"franchise_id": fid_str, "player_id": str(pid)},
            {"$set": set_fields},
        )
        # Keep in-memory map coherent for subsequent teammates.
        meta.update({k.split(".", 1)[1]: v for k, v in set_fields.items()})
        doc["meta"] = meta
        if "meta.image_id" in set_fields:
            doc["image_id"] = set_fields["meta.image_id"]

        summary["assignments"].append({
            "player_id": str(pid),
            "jersey": meta.get("jersey"),
            "image_id": meta.get("image_id"),
            "team_id": team_id_str,
        })
        if warm and set_fields.get("meta.image_id"):
            to_warm.append({
                "player_id": str(pid),
                "image_id": set_fields["meta.image_id"],
                "team_id": team_id_str,
            })

    if newly_used:
        franchises_collection.update_one(
            {"_id": franchise_id},
            {"$addToSet": {FRANCHISE_USED_FIELD: {"$each": newly_used}}},
        )

    if warm and to_warm:
        summary["warmed"] = _warm_walk_on_masters(
            franchise_id=franchise_id,
            franchise_doc=franchise_doc,
            team_id=team_id_str,
            entries=to_warm,
            teams_collection=teams_collection,
        )

    if summary["jersey_assigned"] or summary["image_assigned"]:
        logger.info(
            "[WALK-ON-ROSTER] franchise=%s team=%s jersey=%s image=%s warm=%s",
            fid_str,
            team_id_str,
            summary["jersey_assigned"],
            summary["image_assigned"],
            summary["warmed"],
        )
    return summary


def _warm_walk_on_masters(
    *,
    franchise_id: Any,
    franchise_doc: Optional[dict[str, Any]],
    team_id: str,
    entries: list[dict[str, Any]],
    teams_collection: Any,
) -> int:
    """Best-effort paint into players/master/<player_id>.png (never raises)."""
    try:
        from BackEnd.services import recruit_image, r2_images
        from BackEnd.utils.team_builder_portraits import resolve_kit_keys
        from bson import ObjectId
    except Exception:
        logger.exception("[WALK-ON-ROSTER] warm imports failed")
        return 0

    # `teams_collection is None`, NOT `not teams_collection`: pymongo's Collection raises
    # NotImplementedError on bool(), so the truthiness form threw out of a function whose
    # docstring promises it never raises. `or` short-circuits, so it only fired when R2 was
    # configured AND there were entries — i.e. exactly when there was work to do. The user
    # team's eager warm (warm=True, franchise_routes.py:13485) therefore never painted a
    # single master; the caller's try/except swallowed it into a logged traceback.
    if not r2_images.is_configured() or not entries or teams_collection is None:
        return 0

    team = None
    try:
        if ObjectId.is_valid(team_id):
            team = teams_collection.find_one({"_id": ObjectId(team_id)})
    except Exception:
        team = None
    if not team:
        return 0

    primary = team.get("primary_color", "#000000")
    secondary = team.get("secondary_color", "#ffffff")
    wordmark = team.get("mascot", "")
    if franchise_doc:
        try:
            from BackEnd.utils.franchise_team_display import resolve_team_display
            disp = resolve_team_display(franchise_id, team_id, core_doc=team)
            primary = disp.get("primary_color") or primary
            secondary = disp.get("secondary_color") or secondary
            if disp.get("mascot") is not None:
                wordmark = disp.get("mascot")
        except Exception:
            pass

    painted = 0
    for entry in entries:
        player_id = str(entry["player_id"])
        image_id = entry["image_id"]
        master_key = f"players/master/{player_id}.png"
        try:
            if r2_images.exists(master_key):
                continue
            kit_keys = resolve_kit_keys(image_id)
            if not kit_keys:
                continue
            kit_key, mask_key = kit_keys
            if not (r2_images.exists(kit_key) and r2_images.exists(mask_key)):
                continue
            master = recruit_image.make_signed_master(
                r2_images.get(kit_key),
                r2_images.get(mask_key),
                primary,
                secondary,
                wordmark,
            )
            r2_images.put(master_key, master)
            painted += 1
        except Exception:
            logger.exception(
                "[WALK-ON-ROSTER] warm paint failed franchise=%s player=%s",
                str(franchise_id),
                player_id,
            )
    return painted
