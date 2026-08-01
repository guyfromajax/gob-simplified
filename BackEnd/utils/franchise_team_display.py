"""
Franchise team display resolver (Team Builder §3.2).

Canonical key: (franchise_id, team ObjectId).
Pass-through no-op when the franchise has no Team Builder overlay — existing
franchises stay byte-identical on every display field.

Overlay lives on the franchise document under ``team_builder`` and is written
only at franchise creation (Apply). Shared producers call into this module
instead of reading core ``teams`` identity directly.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, MutableMapping, Optional

from bson import ObjectId

from BackEnd.db import franchises_collection, teams_collection

# Franchise-doc field holding the per-save Team Builder overlay.
TEAM_BUILDER_FIELD = "team_builder"


def _as_object_id_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(ObjectId(text))
    except Exception:
        return None


def _load_franchise_doc(
    franchise: Any,
    projection: Mapping[str, int] | None = None,
) -> Optional[dict[str, Any]]:
    if franchise is None:
        return None
    if isinstance(franchise, Mapping) and ("_id" in franchise or TEAM_BUILDER_FIELD in franchise):
        return dict(franchise)
    try:
        fid = ObjectId(str(franchise))
    except Exception:
        return None
    proj = dict(projection or {TEAM_BUILDER_FIELD: 1, "user_team_object_id": 1, "user_team_id": 1})
    if "_id" not in proj:
        proj["_id"] = 1
    return franchises_collection.find_one({"_id": fid}, proj)


def get_team_builder_overlay(franchise: Any) -> Optional[dict[str, Any]]:
    """Return the Team Builder overlay dict, or None when absent / empty."""
    doc = _load_franchise_doc(franchise)
    if not doc:
        return None
    overlay = doc.get(TEAM_BUILDER_FIELD)
    if not isinstance(overlay, dict) or not overlay:
        return None
    replaced = _as_object_id_str(overlay.get("replaced_object_id") or overlay.get("object_id"))
    if not replaced:
        return None
    return overlay


def _core_team_doc(team_object_id: str) -> dict[str, Any]:
    try:
        oid = ObjectId(team_object_id)
    except Exception:
        return {}
    return teams_collection.find_one({"_id": oid}) or {}


# Shared empty token when a name yields no alnum chars (BE + FE must match).
ABBR_EMPTY = "???"


def abbr_from_name(name: str) -> str:
    """
    Single abbreviation derivation: alnum chars of ``name``, uppercased, first 3.

    Used by rendering fallbacks and Apply/wizard uniqueness checks alike.
    """
    clean = re.sub(r"[^A-Za-z0-9]", "", (name or "").strip())
    return (clean[:3] or ABBR_EMPTY).upper()


# Back-compat alias used by older call sites / tests.
_abbr_from_name = abbr_from_name

# Jersey presets that map to teams_uniforms body/trim (§6.4).
JERSEY_PRESET_SOLID = 1
JERSEY_PRESET_SOLID_WITH_TRIM = 2


def normalize_jersey_preset(value: Any) -> int:
    """1 = SOLID, 2 = SOLID WITH TRIM. Anything else → SOLID."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return JERSEY_PRESET_SOLID
    return JERSEY_PRESET_SOLID_WITH_TRIM if n == JERSEY_PRESET_SOLID_WITH_TRIM else JERSEY_PRESET_SOLID


def resolve_team_abbreviation(
    franchise: Any,
    team_object_id: Any,
    *,
    core_doc: Mapping[str, Any] | None = None,
    name: str | None = None,
) -> str:
    """
    Single abbreviation resolver (Team Builder §3.1a chrome).

    Overlay abbreviation when this ObjectId is the franchise's replaced slot;
    otherwise ``abbr_from_name`` on the display/core name.
    """
    display = resolve_team_display(franchise, team_object_id, core_doc=core_doc)
    abbr = str(display.get("abbreviation") or "").strip().upper()[:3]
    if abbr and abbr != ABBR_EMPTY:
        return abbr
    return abbr_from_name(name or display.get("name") or "")


def resolve_team_display(
    franchise: Any,
    team_object_id: Any,
    *,
    core_doc: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve display identity for one team in one franchise.

    Returns a stable dict:
      object_id, team_id (slug), name, abbreviation, mascot,
      primary_color, secondary_color,
      asset_strategy ("core" | "generated"),
      is_custom (bool), replaced_name (optional),
      jersey_preset (custom only: 1 SOLID | 2 SOLID WITH TRIM)

    When the franchise has no overlay, or the ObjectId is not the replaced
    slot, values come from core ``teams`` unchanged.

    Note: legacy overlays may still carry stale ``short_name``, ``accent_color``,
    or ``city_state`` keys; they are ignored (no consumer, no migration).
    """
    oid = _as_object_id_str(team_object_id)
    core = dict(core_doc) if core_doc is not None else (_core_team_doc(oid) if oid else {})
    core_name = str(core.get("name") or "")
    core_primary = core.get("primary_color") or "#27408E"
    core_secondary = core.get("secondary_color") or "#15181f"
    core_mascot = core.get("mascot") or ""
    core_slug = core.get("team_id")

    base = {
        "object_id": oid,
        "team_id": core_slug,
        "name": core_name or (oid or "?"),
        "abbreviation": abbr_from_name(core_name),
        "mascot": core_mascot,
        "primary_color": core_primary,
        "secondary_color": core_secondary,
        "asset_strategy": "core",
        "is_custom": False,
        "replaced_name": None,
        "conference": core.get("conference"),
        "region": core.get("region"),
    }

    overlay = get_team_builder_overlay(franchise)
    if not overlay or not oid:
        return base

    replaced = _as_object_id_str(overlay.get("replaced_object_id") or overlay.get("object_id"))
    if replaced != oid:
        return base

    name = str(overlay.get("name") or core_name or "?").strip() or base["name"]
    abbreviation = str(overlay.get("abbreviation") or abbr_from_name(name)).strip().upper()[:3]
    mascot = str(overlay.get("mascot") if overlay.get("mascot") is not None else core_mascot)
    primary = overlay.get("primary_color") or core_primary
    secondary = overlay.get("secondary_color") or core_secondary

    return {
        "object_id": oid,
        "team_id": core_slug,  # slug stays the slot's canonical code
        "name": name,
        "abbreviation": abbreviation or abbr_from_name(name),
        "mascot": mascot,
        "primary_color": primary,
        "secondary_color": secondary,
        "asset_strategy": str(overlay.get("asset_strategy") or "generated"),
        "is_custom": True,
        "replaced_name": overlay.get("replaced_name") or core_name or None,
        "conference": core.get("conference"),
        "region": core.get("region"),
        "jersey_preset": normalize_jersey_preset(overlay.get("jersey_preset")),
    }


def resolve_team_name_map(
    franchise: Any,
    team_ids: list[Any] | None = None,
) -> dict[str, str]:
    """
    ObjectId-string → display name map for a franchise.

    Drop-in upgrade for ``_format_team_name_map`` when a franchise is in scope.
    Pass-through identical to core names when no overlay is present.
    """
    query: dict[str, Any] = {}
    oids: list[ObjectId] = []
    if team_ids:
        for value in team_ids:
            try:
                oids.append(ObjectId(str(value)))
            except Exception:
                continue
        if oids:
            query = {"_id": {"$in": oids}}

    overlay = get_team_builder_overlay(franchise)
    replaced = _as_object_id_str((overlay or {}).get("replaced_object_id")) if overlay else None

    result: dict[str, str] = {}
    for team in teams_collection.find(query, {"name": 1, "primary_color": 1, "secondary_color": 1, "mascot": 1, "team_id": 1}):
        oid = str(team["_id"])
        if overlay and replaced and oid == replaced:
            result[oid] = resolve_team_display(franchise, oid, core_doc=team)["name"]
        else:
            result[oid] = team.get("name", oid)
    return result


def apply_overlay_to_identity_writes(
    franchise_doc: MutableMapping[str, Any],
    *,
    user_team_object_id: str,
) -> dict[str, Any]:
    """
    Values to write at franchise creation when a Team Builder overlay is present.

    Used so FPD meta.team / franchise.user_team_id bake the custom name at
    write time (news and game docs do not exist yet at create).
    """
    display = resolve_team_display(franchise_doc, user_team_object_id)
    return {
        "user_team_id": display["name"],
        "display": display,
    }
