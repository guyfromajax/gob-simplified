"""
Franchise team display resolver (Team Builder §3.2).

Canonical key: (franchise_id, team ObjectId).
Pass-through no-op when the franchise has no Team Builder overlay — existing
franchises stay byte-identical on every display field.

**Where the overlay lives:** the franchise Mongo document
(``franchises`` collection), field ``team_builder`` — one object holding
name, abbreviation, mascot, ``primary_color``, ``secondary_color``,
``jersey_preset``, ``asset_strategy``, and ``court`` (five colour parameters).
Written only at Apply. Not FTD.

Roster joins that need the custom display name read ``franchises.team_builder``
directly (one franchise-document read). FTD does not mirror identity fields.
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

# Court hardwood style keys — same nine as generate_non_a1_courts.mjs / TeamCourtGenerator.
HARDWOOD_STYLE_KEYS = frozenset(
    {
        "light_light",
        "light_medium",
        "light_dark",
        "medium_light",
        "medium_medium",
        "medium_dark",
        "dark_light",
        "dark_medium",
        "dark_dark",
    }
)

COURT_PARAM_KEYS = (
    "hardwoodStyle",
    "oobColor",
    "laneColor",
    "outsideWoodColor",
    "insideWoodColor",
    "halfArcFillColor",
)

# Fixed court line colour (teamCourtGenerator COLORS.line). Custom inside wood
# must clear WCAG non-text contrast against this (see decision / measurement note).
COURT_LINE_COLOR = "#6e675f"
INSIDE_WOOD_LINE_CONTRAST_MIN = 3.0


def _srgb_to_lin(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    text = str(hex_color or "").strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return 0.0
    r = int(text[1:3], 16)
    g = int(text[3:5], 16)
    b = int(text[5:7], 16)
    return (
        0.2126 * _srgb_to_lin(r)
        + 0.7152 * _srgb_to_lin(g)
        + 0.0722 * _srgb_to_lin(b)
    )


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colours."""
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    lighter = max(la, lb)
    darker = min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def inside_wood_contrast_ok(hex_color: str | None) -> bool:
    """True when custom inside wood clears the line-colour floor (or is absent)."""
    text = str(hex_color or "").strip()
    if not text:
        return True
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", text, flags=re.IGNORECASE):
        return False
    return contrast_ratio(text, COURT_LINE_COLOR) >= INSIDE_WOOD_LINE_CONTRAST_MIN


# Banner compositions — chevron retired; baseline is the default.
BANNER_VARIANT_KEYS = frozenset({"baseline", "keel", "plate", "sash"})
DEFAULT_BANNER_VARIANT = "baseline"


def normalize_banner_variant(value: Any) -> str:
    """Persisted banner_variant key. Unknown / chevron → baseline."""
    key = str(value or "").strip().lower()
    if key == "chevron" or key not in BANNER_VARIANT_KEYS:
        return DEFAULT_BANNER_VARIANT
    return key


def normalize_jersey_preset(value: Any) -> int:
    """1 = SOLID, 2 = SOLID WITH TRIM. Anything else → SOLID."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return JERSEY_PRESET_SOLID
    return JERSEY_PRESET_SOLID_WITH_TRIM if n == JERSEY_PRESET_SOLID_WITH_TRIM else JERSEY_PRESET_SOLID


def _normalize_hex_color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text
    if re.fullmatch(r"#[0-9A-Fa-f]{3}", text):
        return "#" + "".join(ch * 2 for ch in text[1:])
    fb = str(fallback or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", fb):
        return fb
    return "#DBB891"


def normalize_court_params(
    value: Any,
    *,
    primary_color: str | None = None,
    secondary_color: str | None = None,
) -> Optional[dict[str, str]]:
    """
    Normalize the five court parameters for the team_builder overlay.

    Returns None when ``value`` is absent/empty — callers omit the key so
    existing franchises keep lazy FE defaults (no backfill).
    When present, always returns all five keys (invalid pieces fall back).
    Never stores a rendered image.
    """
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump()
        except Exception:
            value = None
    elif hasattr(value, "dict"):
        try:
            value = value.dict()
        except Exception:
            value = None
    if not isinstance(value, Mapping):
        return None
    if not any(value.get(k) not in (None, "") for k in COURT_PARAM_KEYS):
        return None

    primary = _normalize_hex_color(primary_color, "#27408E")
    secondary = _normalize_hex_color(secondary_color, "#15181f")
    style = str(value.get("hardwoodStyle") or "medium_medium").strip()
    if style not in HARDWOOD_STYLE_KEYS:
        style = "medium_medium"

    out: dict[str, str] = {
        "hardwoodStyle": style,
        "oobColor": _normalize_hex_color(value.get("oobColor"), primary),
        "laneColor": _normalize_hex_color(value.get("laneColor"), primary),
        "outsideWoodColor": _normalize_hex_color(value.get("outsideWoodColor"), "#DBB891"),
        "halfArcFillColor": _normalize_hex_color(value.get("halfArcFillColor"), secondary),
    }
    # Optional custom inside-wood override (symmetric with outside). Absent →
    # style-key tone at render time. Present → must already have cleared the
    # contrast floor at Apply (caller refuses); we only normalize the hex.
    raw_inside = value.get("insideWoodColor")
    if raw_inside not in (None, ""):
        out["insideWoodColor"] = _normalize_hex_color(raw_inside, out["outsideWoodColor"])
    return out


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
      core_missing (bool): no core ``teams`` doc for this ObjectId,
      jersey_preset (custom only: 1 SOLID | 2 SOLID WITH TRIM),
      court (custom only, optional): five colour parameters — never a render

    When the franchise has no overlay, or the ObjectId is not the replaced
    slot, values come from core ``teams`` unchanged.

    ``name`` is "" when the core doc is missing (a reseeded ``teams`` collection
    orphans older franchises' ObjectIds). Callers holding a better source — e.g.
    ``franchises.user_team_id``, which bakes the team NAME — must branch on
    ``core_missing`` rather than relying on ``name`` being falsy alone.

    Note: legacy overlays may still carry stale ``short_name``, ``accent_color``,
    or ``city_state`` keys; they are ignored (no consumer, no migration).
    Legacy overlays without ``court`` omit the key — FE derives defaults from
    primary/secondary (no backfill).
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
        # Never echo the ObjectId back as a display name. It is truthy, so it silently
        # defeats every downstream `display.get("name") or <fallback>` and surfaces a raw
        # id to the player. Branch on ``core_missing`` instead.
        "name": core_name,
        "abbreviation": abbr_from_name(core_name),
        "mascot": core_mascot,
        "primary_color": core_primary,
        "secondary_color": core_secondary,
        "asset_strategy": "core",
        "is_custom": False,
        "replaced_name": None,
        "conference": core.get("conference"),
        "region": core.get("region"),
        "core_missing": not core,
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

    out = {
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
        "banner_variant": normalize_banner_variant(overlay.get("banner_variant")),
        "core_missing": not core,
    }
    # Parameters only — never a render. Absent on legacy overlays → FE defaults.
    court = normalize_court_params(
        overlay.get("court"),
        primary_color=str(primary) if primary is not None else None,
        secondary_color=str(secondary) if secondary is not None else None,
    )
    if court is not None:
        out["court"] = court
    return out


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
