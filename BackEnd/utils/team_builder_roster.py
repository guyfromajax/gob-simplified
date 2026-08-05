"""Team Builder roster helpers — slot load, edit diffs, wizard walk-ons (§4.5b/c)."""
from __future__ import annotations

import random
import uuid
from copy import deepcopy
from typing import Any, Mapping, Sequence

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS, LEAGUE_MEDIAN_HEIGHT_IN
from BackEnd.constants.team_builder_budget import (
    ATTR_MAX,
    ATTR_MIN,
    CORE_12_ATTRS,
    TB_HEIGHT_MAX_IN,
    TB_HEIGHT_MIN_IN,
    TOPUP_FLOOR,
    apply_capped_topup,
    capped_budget_for_inherited,
    class_rank_from_year,
    clamp_attr,
    clamp_tb_height,
    core12_total,
    force_core12_to_budget,
    normalize_attribute_mode,
)
from BackEnd.utils.player_generation import weight_from_height
from BackEnd.models.franchise_manager import (
    advance_recruit_year,
    choose_franchise_first_name,
    generate_walk_on_profile,
    get_franchise_name_assets,
)
from BackEnd.models.player import Player
from BackEnd.utils.franchise_rank_prestige import core_total_player_attrs
from BackEnd.utils.player_year import format_player_year_abbrev, normalize_player_year
from BackEnd.utils.position_ratings import compute_position_ratings
from BackEnd.utils.player_development import entry_tier_at_year

# Intangibles and non-editor identity — never overwritten from an edit/import row.
_PRESERVE_ATTR_KEYS = ("CH", "EM", "MO", "NG")
_META_INHERIT_KEYS = (
    "archetype",
    "Home Region",
    "scouting_report",
    # Portrait kit reference (recruit_set / builder_set / upload key). Not a
    # flat base-league photo path — those are stripped at Apply (§4.5c).
    "image_id",
    "portrait",
)

ROSTER_SIZE = 15
MAX_ROSTER_SIZE = 15
AUTHORED_ROSTER_SIZE = 15
SCHOLARSHIP_SIZE = 12
WALK_ON_COUNT = 3

_CLASS_YEAR_IMPORT: dict[str, str] = {
    "fr": "Freshman",
    "freshman": "Freshman",
    "1": "Freshman",
    "so": "Sophomore",
    "sophomore": "Sophomore",
    "2": "Sophomore",
    "jr": "Junior",
    "junior": "Junior",
    "3": "Junior",
    "sr": "Senior",
    "senior": "Senior",
    "4": "Senior",
}

_EXPORTABLE_CLASS_YEARS = frozenset({"FR", "SO", "JR", "SR"})


def _zero_stats_block() -> dict[str, Any]:
    zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []
    return zero_stats


def _safe_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tb_class_rank_for_budget(year: Any) -> int:
    """Class spend rank for TB budgets. JH is not a TB value — count as FR."""
    if format_player_year_abbrev(year) == "JH":
        return 1
    return class_rank_from_year(year)


def tb_class_rank_table() -> dict[str, int]:
    """Domain data for the renderer — FR/SO/JR/SR spend ranks (§10.3)."""
    return {"FR": 1, "SO": 2, "JR": 3, "SR": 4}


def compute_inherited_shape_budgets(
    scholarship_players: Sequence[Mapping[str, Any]],
    walk_ons: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Height/class team budgets for the authored 15 (core 12 + wizard walk-ons).

    Shipped to the FE as data — the renderer must not derive these totals.
    """
    height_budget = 0
    class_budget = 0
    for row in list(scholarship_players or [])[:SCHOLARSHIP_SIZE]:
        height_budget += int(
            _safe_int(row.get("height_in"), _safe_int(row.get("height"), 0)) or 0
        )
        class_budget += _tb_class_rank_for_budget(
            row.get("class_year") or row.get("year")
        )
    for row in list(walk_ons or [])[:WALK_ON_COUNT]:
        height_budget += int(
            _safe_int(row.get("height_in"), _safe_int(row.get("height"), 0)) or 0
        )
        class_budget += _tb_class_rank_for_budget(
            row.get("class_year") or row.get("year")
        )
    return {
        "height_budget": height_budget,
        "class_budget": class_budget,
        "class_rank": tb_class_rank_table(),
        "height_min_in": TB_HEIGHT_MIN_IN,
        "height_max_in": TB_HEIGHT_MAX_IN,
    }


def load_core_roster_rows_for_slot(db: Any, team_object_id: ObjectId) -> list[dict[str, Any]]:
    """Core scholarship rows (height/year) for inherited shape budgets."""
    team_doc = db.teams.find_one({"_id": team_object_id}, {"player_ids": 1}) or {}
    raw_ids = team_doc.get("player_ids") or []
    id_variants: list[Any] = []
    keys: list[str] = []
    for pid in raw_ids:
        keys.append(str(pid))
        id_variants.append(pid)
        try:
            id_variants.append(ObjectId(str(pid)))
        except Exception:
            pass
        id_variants.append(str(pid))
    by_id: dict[str, dict[str, Any]] = {}
    if id_variants:
        for doc in db.players.find(
            {"_id": {"$in": id_variants}},
            {"height": 1, "year": 1},
        ):
            by_id[str(doc.get("_id"))] = doc
    rows: list[dict[str, Any]] = []
    for key in keys[:SCHOLARSHIP_SIZE]:
        doc = by_id.get(key) or {}
        rows.append({"height": doc.get("height"), "year": doc.get("year")})
    return rows


def class_year_for_export(year: Any) -> str:
    """Map core year to FR/SO/JR/SR for JSON slot-roster; blank when not applicable."""
    abbrev = format_player_year_abbrev(year)
    return abbrev if abbrev in _EXPORTABLE_CLASS_YEARS else ""


def parse_import_class_year(raw: Any) -> str | None:
    """Return canonical class year (Freshman…) or None when unrecognized.

    Named for historical CSV import; still used by edit-row diffs.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    mapped = _CLASS_YEAR_IMPORT.get(text.lower())
    if mapped:
        return mapped
    normalized = normalize_player_year(text)
    if normalized in {"Freshman", "Sophomore", "Junior", "Senior"}:
        return normalized
    return None


_SLOT_ROSTER_PROJECTION: dict[str, int] = {
    "first_name": 1,
    "last_name": 1,
    "year": 1,
    "height": 1,
    "weight": 1,
    "jersey": 1,
    "attributes": 1,
    "position_ratings": 1,
    "player_id": 1,
}


def _ordered_slot_player_docs(db: Any, team_object_id: ObjectId) -> list[dict[str, Any]]:
    """Scholarship players for a core slot, ordered by ``teams.player_ids`` identity."""
    team_doc = db.teams.find_one({"_id": team_object_id}, {"player_ids": 1, "name": 1})
    if not team_doc:
        raise ValueError("team_not_found")

    player_ids_raw = team_doc.get("player_ids") or []
    player_ids: list[Any] = []
    for pid in player_ids_raw:
        try:
            player_ids.append(ObjectId(str(pid)))
        except Exception:
            player_ids.append(pid)

    players_by_id: dict[str, dict[str, Any]] = {}
    if player_ids:
        for doc in db.players.find(
            {"_id": {"$in": player_ids}},
            _SLOT_ROSTER_PROJECTION,
        ):
            players_by_id[str(doc["_id"])] = doc

    ordered: list[dict[str, Any]] = []
    for pid in player_ids_raw:
        key = str(pid)
        if key in players_by_id:
            ordered.append(players_by_id[key])
            continue
        try:
            alt = str(ObjectId(str(pid)))
            if alt in players_by_id:
                ordered.append(players_by_id[alt])
        except Exception:
            pass
    if not ordered:
        for doc in db.players.find(
            {"team_id": team_object_id},
            _SLOT_ROSTER_PROJECTION,
        ):
            ordered.append(doc)
    return ordered[:SCHOLARSHIP_SIZE]


def build_slot_roster_players(db: Any, team_object_id: ObjectId) -> list[dict[str, Any]]:
    """
    Scholarship roster as JSON rows for the Team Builder editor.

    Bound by ``source_player_id`` (stable core identity), never by find() ordinal.
    """
    ordered = _ordered_slot_player_docs(db, team_object_id)
    rows: list[dict[str, Any]] = []
    for doc in ordered:
        attrs = doc.get("attributes") or {}
        core_attrs = {key: attrs.get(key) for key in CORE_12_ATTRS}
        source_id = str(doc.get("player_id") or doc.get("_id") or "")
        rows.append(
            {
                "source_player_id": source_id,
                "first_name": doc.get("first_name") or "",
                "last_name": doc.get("last_name") or "",
                "class_year": class_year_for_export(doc.get("year")),
                "year": doc.get("year"),
                "height_in": doc.get("height") if doc.get("height") is not None else None,
                "weight_lb": doc.get("weight") if doc.get("weight") is not None else None,
                "jersey": doc.get("jersey") if doc.get("jersey") is not None else None,
                "attributes": core_attrs,
                "position_ratings": dict(doc.get("position_ratings") or {}),
                "walk_on": False,
            }
        )
    return rows


def _median_int(values: Sequence[int]) -> int:
    if not values:
        return 0
    sorted_vals = sorted(values)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) // 2


def slot_band_defaults(
    franchise_players_data_collection: Any,
    franchise_id: Any,
    team_object_id: ObjectId,
    player_ids: Sequence[str],
) -> dict[str, Any]:
    """Median height/weight/attrs from the slot's current franchise roster."""
    defaults: dict[str, Any] = {
        "height": LEAGUE_MEDIAN_HEIGHT_IN,
        "weight": 185,
        "attrs": {key: 40 for key in CORE_12_ATTRS},
    }
    if not player_ids:
        return defaults

    fpd_docs = list(
        franchise_players_data_collection.find(
            {
                "franchise_id": str(franchise_id),
                "player_id": {"$in": [str(pid) for pid in player_ids]},
            },
            {"attributes": 1, "meta.height": 1, "meta.weight": 1},
        )
    )
    if not fpd_docs:
        return defaults

    heights = [_safe_int(d.get("meta", {}).get("height")) for d in fpd_docs]
    weights = [_safe_int(d.get("meta", {}).get("weight")) for d in fpd_docs]
    heights = [h for h in heights if h is not None]
    weights = [w for w in weights if w is not None]
    if heights:
        defaults["height"] = _median_int(heights)
    if weights:
        defaults["weight"] = _median_int(weights)

    per_attr: dict[str, list[int]] = {key: [] for key in CORE_12_ATTRS}
    for doc in fpd_docs:
        attrs = doc.get("attributes") or {}
        for key in CORE_12_ATTRS:
            val = _safe_int(attrs.get(key))
            if val is not None:
                per_attr[key].append(val)
    for key in CORE_12_ATTRS:
        if per_attr[key]:
            defaults["attrs"][key] = _median_int(per_attr[key])
    return defaults


def _merge_row_core_attrs(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """Accept top-level core-12 keys or nested attributes{} from the editor."""
    raw = dict(row or {})
    nested = raw.get("attributes") if isinstance(raw.get("attributes"), Mapping) else {}
    merged: dict[str, Any] = {}
    for key in CORE_12_ATTRS:
        if key in raw and raw[key] not in (None, ""):
            merged[key] = raw[key]
        elif key in nested and nested[key] not in (None, ""):
            merged[key] = nested[key]
    return merged


def _row_has_core_attr_edits(row: Mapping[str, Any] | None) -> bool:
    return bool(_merge_row_core_attrs(row))


def _payload_from_fpd_doc(doc: Mapping[str, Any]) -> dict[str, Any]:
    """FPD → editable player payload (clone source for §4.5b)."""
    meta = dict(doc.get("meta") or {})
    payload: dict[str, Any] = {
        "meta": meta,
        "attributes": dict(doc.get("attributes") or {}),
        "position_ratings": dict(doc.get("position_ratings") or {}),
    }
    for key in ("entry_tier", "position_intent", "potential_factor", "development", "photo", "season", "career"):
        if doc.get(key) is not None:
            payload[key] = deepcopy(doc[key]) if key in ("season", "career", "development") else doc[key]
    # Core sometimes stores photo/archetype at top level; mirror into meta when absent.
    if doc.get("archetype") and not meta.get("archetype"):
        meta["archetype"] = doc["archetype"]
    if doc.get("Home Region") not in (None, "") and not meta.get("Home Region"):
        meta["Home Region"] = doc["Home Region"]
    if doc.get("photo") and not payload.get("photo"):
        payload["photo"] = doc["photo"]
    return payload


def _enrich_payload_from_core(payload: dict[str, Any], core: Mapping[str, Any] | None) -> dict[str, Any]:
    """Fill fields init drops (archetype, image_id, …) from the core player doc."""
    if not core:
        return payload
    meta = payload.setdefault("meta", {})
    for key in _META_INHERIT_KEYS:
        if meta.get(key) in (None, "") and core.get(key) not in (None, ""):
            meta[key] = core[key]
    # Never copy unrecolourable base-league photo paths (§4.5c).
    # Kit reference is meta.image_id (assigned in Phase 3d).
    payload.pop("photo", None)
    meta.pop("photo", None)
    if payload.get("entry_tier") is None and core.get("entry_tier") is not None:
        payload["entry_tier"] = core["entry_tier"]
    if payload.get("position_intent") is None and core.get("position_intent") is not None:
        payload["position_intent"] = core["position_intent"]
    if payload.get("potential_factor") is None and core.get("potential_factor") is not None:
        payload["potential_factor"] = core["potential_factor"]
    if payload.get("development") is None and core.get("development") is not None:
        payload["development"] = deepcopy(core["development"])
    if not payload.get("position_ratings") and core.get("position_ratings"):
        payload["position_ratings"] = dict(core["position_ratings"])
    return payload


def _payload_from_wizard_walk_on(
    wo: Mapping[str, Any],
    *,
    team_name: str,
    team_object_id: ObjectId,
) -> dict[str, Any]:
    """Wizard draft walk-on → inherited payload (their generated values are inherited)."""
    attrs = dict(wo.get("attributes") or {})
    # Ensure anchors for core-12.
    for key in CORE_12_ATTRS:
        if key in attrs and f"anchor_{key}" not in attrs:
            attrs[f"anchor_{key}"] = attrs[key]
    meta: dict[str, Any] = {
        "first_name": str(wo.get("first_name") or "").strip() or "Walk",
        "last_name": str(wo.get("last_name") or "").strip() or "On",
        "team": team_name,
        "team_id": str(team_object_id),
        "height": wo.get("height") if wo.get("height") is not None else LEAGUE_MEDIAN_HEIGHT_IN,
        "weight": wo.get("weight") if wo.get("weight") is not None else 185,
        "year": wo.get("year") or "Freshman",
        "jersey": wo.get("jersey"),
        "archetype": "Walk On",
    }
    if wo.get("Home Region") not in (None,):
        meta["Home Region"] = wo.get("Home Region")
    payload: dict[str, Any] = {
        "meta": meta,
        "attributes": attrs,
        "position_ratings": dict(wo.get("position_ratings") or {}),
        "entry_tier": wo.get("entry_tier") or "Poor",
        "position_intent": wo.get("position_intent"),
        "development": wo.get("development"),
        "potential_factor": wo.get("potential_factor"),
    }
    if wo.get("photo"):
        payload["photo"] = wo["photo"]
    return payload


def _lookup_core_player(players_collection: Any, player_id: str) -> dict[str, Any] | None:
    if players_collection is None or not player_id:
        return None
    pid = str(player_id)
    # Franchise rosters key core players by stable player_id (UUID), not Mongo _id.
    doc = players_collection.find_one({"player_id": pid})
    if doc:
        return doc
    try:
        return players_collection.find_one({"_id": ObjectId(pid)})
    except Exception:
        return None


def apply_row_diff_to_inherited(
    inherited: Mapping[str, Any],
    row: Mapping[str, Any] | None,
    *,
    team_name: str,
    team_object_id: ObjectId,
    attribute_mode: str = "capped",
    budget: int | None = None,
    apply_topup: bool = False,
) -> dict[str, Any]:
    """
    §4.5b: clone inherited player, overwrite only fields the editor sends.

    Blank optional cells mean inherit. CH/EM/MO and non-editor meta are never
    taken from the row.
    """
    out = deepcopy(dict(inherited))
    meta = dict(out.get("meta") or {})
    meta["team"] = team_name
    meta["team_id"] = str(team_object_id)
    row = row or {}
    meta_in = row.get("meta") if isinstance(row.get("meta"), Mapping) else {}

    first = str(row.get("first_name") or meta_in.get("first_name") or "").strip()
    last = str(row.get("last_name") or meta_in.get("last_name") or "").strip()
    if first:
        meta["first_name"] = first
    if last:
        meta["last_name"] = last

    height_raw = _safe_int(
        row.get("height_in"),
        _safe_int(row.get("height"), _safe_int(meta_in.get("height"))),
    )
    if height_raw is not None and (
        height_raw < TB_HEIGHT_MIN_IN or height_raw > TB_HEIGHT_MAX_IN
    ):
        raise ValueError(
            f"height_out_of_range:{height_raw}:{TB_HEIGHT_MIN_IN}:{TB_HEIGHT_MAX_IN}"
        )
    height = clamp_tb_height(height_raw) if height_raw is not None else None
    # §10.2: weight is derived at stamp time from player_id — ignore authored weight.
    jersey = _safe_int(row.get("jersey"), _safe_int(meta_in.get("jersey")))
    height_changed = False
    if height is not None and height != meta.get("height"):
        meta["height"] = height
        height_changed = True
    elif height is not None:
        meta["height"] = height
    if jersey is not None:
        meta["jersey"] = jersey

    # class_year blank → inherit. Same class as inherited → keep exact source string.
    # JH is not a Team Builder value (§10.3) — rejected when the row sends it.
    year_raw = row.get("class_year")
    if year_raw is None or str(year_raw).strip() == "":
        year_raw = row.get("year") if row.get("year") not in (None, "") else meta_in.get("year")
    if year_raw not in (None, ""):
        yr_text = str(year_raw).strip().lower()
        if yr_text in {"jh", "junior high", "junior-high", "juniorhigh"}:
            raise ValueError("class_year_jh_forbidden")
    parsed_year = parse_import_class_year(year_raw) if year_raw not in (None, "") else None
    if parsed_year:
        if format_player_year_abbrev(meta.get("year")) != format_player_year_abbrev(parsed_year):
            meta["year"] = parsed_year

    attrs = dict(out.get("attributes") or {})
    preserved = {key: attrs[key] for key in _PRESERVE_ATTR_KEYS if key in attrs}
    for key in list(attrs):
        if key.startswith("anchor_") and key[7:] in _PRESERVE_ATTR_KEYS:
            preserved[key] = attrs[key]

    merged_core = _merge_row_core_attrs(row)
    core_changed = False
    if merged_core:
        mode = normalize_attribute_mode(attribute_mode)
        # If the row restates inherited core-12 exactly, leave attrs untouched
        # (no clamp/top-up/force reshuffle).
        restates_inherited = all(
            _safe_int(merged_core[key]) == _safe_int(attrs.get(key))
            for key in CORE_12_ATTRS
            if key in merged_core
        ) and all(key in merged_core for key in CORE_12_ATTRS)
        # §4.5c: capped top-up / budget force still apply on a zero-edit restatement
        # (Keep exemption retired — below-floor players must rise to 60).
        if restates_inherited and apply_topup and mode == "capped":
            raw_total = core12_total(attrs)
            if raw_total < TOPUP_FLOOR or (
                budget is not None and raw_total != int(budget)
            ):
                restates_inherited = False
        if not restates_inherited:
            pre_clamp: dict[str, int] = {}
            for key in CORE_12_ATTRS:
                if key in merged_core:
                    pre_clamp[key] = int(_safe_int(merged_core[key], ATTR_MIN) or ATTR_MIN)
                else:
                    pre_clamp[key] = int(_safe_int(attrs.get(key), ATTR_MIN) or ATTR_MIN)

            if apply_topup and mode == "capped":
                topped = apply_capped_topup(pre_clamp)
                core_vals = {key: int(topped["attrs"][key]) for key in CORE_12_ATTRS}
            else:
                core_vals = {key: clamp_attr(pre_clamp[key]) for key in CORE_12_ATTRS}

            if mode == "capped" and budget is not None:
                core_vals = force_core12_to_budget(core_vals, int(budget))

            for key in CORE_12_ATTRS:
                new_v = int(core_vals[key])
                old_v = _safe_int(attrs.get(key))
                if old_v != new_v:
                    core_changed = True
                attrs[key] = new_v
                attrs[f"anchor_{key}"] = new_v
            attrs.update(preserved)

    is_walk_on = bool(row.get("walk_on")) or str(
        meta_in.get("archetype") or row.get("archetype") or meta.get("archetype") or ""
    ) == "Walk On"
    if is_walk_on:
        meta["archetype"] = "Walk On"

    out["meta"] = meta
    out["attributes"] = attrs

    # Recompute ratings only when editor-visible inputs actually changed.
    if core_changed or height_changed:
        name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
        out["position_ratings"] = compute_position_ratings(
            {"attributes": attrs, "height": meta.get("height"), "name": name},
        )

    # Walk-on wizard may re-send these; blank/absent means keep inherited.
    if row.get("entry_tier") not in (None, ""):
        out["entry_tier"] = row.get("entry_tier")
    if row.get("position_intent") not in (None, ""):
        out["position_intent"] = row.get("position_intent")
    if "development" in row and row.get("development") is not None:
        out["development"] = row.get("development")

    return out


def _normalize_import_core_attrs(
    raw: Mapping[str, Any] | None,
    band_defaults: Mapping[str, Any],
    *,
    attribute_mode: str = "capped",
    apply_topup: bool = False,
) -> dict[str, int]:
    """Build core-12 attrs in [5, 99], filling blanks from slot medians.

    Top-up must see pre-clamp inherited totals. Clamping first turns Jason Potter
    (24) into 63 and skips the §4.3 raise-to-exactly-60 path.
    """
    band_attrs = band_defaults.get("attrs") or {}
    merged = _merge_row_core_attrs(raw)
    pre_clamp: dict[str, int] = {}
    for key in CORE_12_ATTRS:
        val = _safe_int(merged.get(key))
        if val is None:
            val = _safe_int(band_attrs.get(key), ATTR_MIN)
        pre_clamp[key] = int(val if val is not None else ATTR_MIN)

    mode = normalize_attribute_mode(attribute_mode)
    if apply_topup and mode == "capped":
        topped = apply_capped_topup(pre_clamp)
        attrs = {key: int(topped["attrs"][key]) for key in CORE_12_ATTRS}
    else:
        attrs = {
            key: max(ATTR_MIN, min(ATTR_MAX, pre_clamp[key])) for key in CORE_12_ATTRS
        }

    out: dict[str, int] = {}
    for key in CORE_12_ATTRS:
        out[key] = attrs[key]
        out[f"anchor_{key}"] = attrs[key]
    return out


def _finalize_franchise_attributes(raw_core: dict[str, int]) -> dict[str, Any]:
    """Randomize CH/EM/MO like season init; ignore any client intangibles."""
    attrs = dict(raw_core)
    return Player.randomize_game_attributes(attrs)


def _build_fpd_doc(
    *,
    franchise_id: Any,
    player_id: str,
    meta: dict[str, Any],
    attributes: dict[str, Any],
    entry_tier: str | None = None,
    position_intent: str | None = None,
    development: Any = None,
    position_ratings: Mapping[str, Any] | None = None,
    photo: Any = None,
    season: Mapping[str, Any] | None = None,
    career: Mapping[str, Any] | None = None,
    potential_factor: float | None = None,
) -> dict[str, Any]:
    zero = _zero_stats_block()
    name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
    ratings = dict(position_ratings or {})
    if not ratings:
        ratings = compute_position_ratings(
            {"attributes": attributes, "height": meta.get("height"), "name": name},
        )
    if not position_intent:
        position_intent = (max(ratings, key=ratings.get) if ratings else "SF")
    if not entry_tier:
        # Derive-and-STORE now (year-aware, from the player's current-year ratings) so a
        # later rollover never re-derives from RT — which misclassifies once pillar-3
        # coaching quality has pushed RT off the ladder. Imported/band rosters carry no
        # tier, so this is the explicit-carry point for them.
        entry_tier = entry_tier_at_year(ratings, meta.get("year") or "FR")
    # Resolve-and-STORE the potential scalar the same way as entry_tier: carry a
    # genuine stored value, else derive a stable one from player_id (imported/band
    # rosters carry none). resolve_potential_factor logs the legacy fallback.
    from BackEnd.utils.player_generation import resolve_potential_factor
    potential_factor = resolve_potential_factor(player_id, potential_factor)
    doc = {
        "franchise_id": str(franchise_id),
        "player_id": player_id,
        "meta": meta,
        "season": dict(season) if season is not None else zero.copy(),
        "career": dict(career) if career is not None else zero.copy(),
        "attributes": attributes,
        "position_ratings": ratings,
        "entry_tier": entry_tier,
        "position_intent": position_intent,
        "potential_factor": potential_factor,
    }
    if development is not None:
        doc["development"] = development
    if photo not in (None, ""):
        doc["photo"] = photo
    return doc


def slot_per_player_budgets(
    source_fpd_docs: Sequence[Mapping[str, Any]],
    *,
    attribute_mode: str = "capped",
) -> list[int]:
    """Capped budgets from the slot roster (post-top-up floors applied)."""
    if normalize_attribute_mode(attribute_mode) != "capped":
        return []
    budgets: list[int] = []
    for doc in source_fpd_docs:
        raw = core12_total(doc.get("attributes") or {})
        budgets.append(capped_budget_for_inherited(raw))
    return budgets


def count_importable_players(
    imported_players: Sequence[Mapping[str, Any]] | None,
) -> int:
    """Count authored rows with a name. Class year may be blank (inherit — §4.5b)."""
    if not imported_players:
        return 0
    count = 0
    for row in imported_players:
        meta_in = row.get("meta") if isinstance(row.get("meta"), Mapping) else {}
        first = str(row.get("first_name") or meta_in.get("first_name") or "").strip()
        last = str(row.get("last_name") or meta_in.get("last_name") or "").strip()
        if not first or not last:
            continue
        count += 1
    return count


def build_wizard_walk_on_players() -> list[dict[str, Any]]:
    """
    Three walk-ons for the Team Builder wizard (§4.5a).

    Uses generate_walk_on_profile() — same producer as season init. Assigns a
    stable wizard_player_id per draw. Persistence / idempotency is owned by
    get_or_create_wizard_walk_ons().
    """
    players: list[dict[str, Any]] = []
    for _ in range(WALK_ON_COUNT):
        wo = generate_walk_on_profile()
        name = str(wo.get("name") or "").strip()
        first_name, _, last_name = name.partition(" ")
        # Match initialize_season: rolled year advances one step onto the roster.
        year = advance_recruit_year(wo.get("year"))
        attrs = dict(wo.get("attributes") or {})
        players.append(
            {
                "wizard_player_id": str(uuid.uuid4()),
                "first_name": first_name.strip() or "Walk",
                "last_name": last_name.strip() or "On",
                "year": year,
                "height": wo.get("height"),
                "weight": wo.get("weight"),
                "jersey": None,
                "attributes": attrs,
                "position_ratings": dict(wo.get("position_ratings") or {}),
                "walk_on": True,
                "archetype": "Walk On",
                "entry_tier": wo.get("entry_tier") or "Poor",
                "position_intent": wo.get("position_intent"),
                "development": wo.get("development"),
                "potential_factor": wo.get("potential_factor"),
            }
        )
    return players


def get_or_create_wizard_walk_ons(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
    draft_id: str,
) -> list[dict[str, Any]]:
    """
    Idempotent wizard walk-ons keyed on (user_id, draft_id, replaced_object_id).

    First call draws via generate_walk_on_profile() and persists. Later calls
    return the same three players (same wizard_player_id + attributes) so a
    reload or retry cannot re-roll capped budgets (Decision #25).
    """
    from datetime import datetime

    user_key = str(user_id or "").strip()
    slot_key = str(replaced_object_id or "").strip()
    draft_key = str(draft_id or "").strip()
    if not user_key or not slot_key or not draft_key:
        raise ValueError("wizard_walk_ons_key_incomplete")

    from BackEnd.utils.team_builder_drafts import SCHEMA_VERSION

    col = db["team_builder_wizard_drafts"]
    # One draft per (user, slot) — draft_id is a stable field, not a second axis.
    query = {
        "user_id": user_key,
        "replaced_object_id": slot_key,
        "schema_version": SCHEMA_VERSION,
    }
    existing = col.find_one(query, {"walk_ons": 1, "draft_id": 1})
    stored = (existing or {}).get("walk_ons") if existing else None
    if isinstance(stored, list) and len(stored) == WALK_ON_COUNT:
        return stored

    walk_ons = build_wizard_walk_on_players()
    stable_draft = str((existing or {}).get("draft_id") or draft_key).strip()
    col.update_one(
        query,
        {
            "$set": {
                **query,
                "draft_id": stable_draft,
                "walk_ons": walk_ons,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )
    # Re-read in case of a concurrent first write — loser takes the winner's draw.
    again = col.find_one(query, {"walk_ons": 1}) or {}
    final = again.get("walk_ons")
    if isinstance(final, list) and len(final) == WALK_ON_COUNT:
        return final
    return walk_ons


def clear_wizard_walk_ons_for_user(db: Any, *, user_id: str, draft_id: str | None = None) -> None:
    """Drop persisted wizard walk-ons after Apply (or when abandoning a draft)."""
    query: dict[str, Any] = {"user_id": str(user_id or "").strip()}
    if draft_id:
        query["draft_id"] = str(draft_id).strip()
    if not query["user_id"]:
        return
    db["team_builder_wizard_drafts"].delete_many(query)


def _player_from_walk_on_profile(
    wo: Mapping[str, Any],
    *,
    team_name: str,
    team_object_id: ObjectId,
) -> dict[str, Any]:
    name = str(wo.get("name") or "").strip()
    first_name, _, last_name = name.partition(" ")
    year = advance_recruit_year(wo.get("year"))
    raw_attrs = dict(wo.get("attributes") or {})
    core = {
        key: int(raw_attrs.get(key) or ATTR_MIN) for key in CORE_12_ATTRS
    }
    for key in CORE_12_ATTRS:
        core[f"anchor_{key}"] = core[key]
    # Preserve generator CH/EM/MO when present; randomize_game_attributes fills gaps.
    attrs = _finalize_franchise_attributes(core)
    for key in ("CH", "EM", "MO", "NG"):
        if key in raw_attrs and raw_attrs[key] is not None:
            attrs[key] = raw_attrs[key]
            attrs[f"anchor_{key}"] = raw_attrs[key]
    return {
        "meta": {
            "first_name": first_name.strip() or "Walk",
            "last_name": last_name.strip() or "On",
            "team": team_name,
            "team_id": str(team_object_id),
            "height": wo.get("height") or LEAGUE_MEDIAN_HEIGHT_IN,
            "weight": wo.get("weight") or 185,
            "year": year,
            "jersey": None,
            "archetype": "Walk On",
        },
        "attributes": attrs,
        "entry_tier": wo.get("entry_tier") or "Poor",
        "position_intent": wo.get("position_intent"),
        "development": wo.get("development"),
        "potential_factor": wo.get("potential_factor"),
    }


def _random_scholarship_name() -> tuple[str, str]:
    first_names, last_names, first_name_weights = get_franchise_name_assets()
    first = choose_franchise_first_name(first_names, first_name_weights)
    last = random.choice(last_names).title()
    return first, last


def _walk_on_class_year() -> str:
    """Freshman–Senior only for generated scholarship-style rows."""
    return random.choice(["Freshman", "Sophomore", "Junior", "Senior"])


def _is_walk_on_doc(doc: Mapping[str, Any]) -> bool:
    meta = doc.get("meta") if isinstance(doc.get("meta"), Mapping) else {}
    return str(meta.get("archetype") or "") == "Walk On"


def generate_roster_at_band(
    *,
    source_fpd_docs: Sequence[Mapping[str, Any]],
    team_name: str,
    team_object_id: ObjectId,
    roster_size: int = AUTHORED_ROSTER_SIZE,
    attribute_mode: str = "capped",
    apply_topup: bool = False,
) -> list[dict[str, Any]]:
    """
    Generate an authored 15: 12 band-resampled scholarship players + 3 walk-ons
    from generate_walk_on_profile() (§4.5a).
    """
    del roster_size  # always authored size; signature kept for callers
    sources = list(source_fpd_docs)
    scholarship_sources = [d for d in sources if not _is_walk_on_doc(d)]
    if not scholarship_sources:
        scholarship_sources = list(sources[:SCHOLARSHIP_SIZE]) or list(sources)

    if not scholarship_sources:
        # Empty slot — fill scholarship slots from Poor walk-on profiles as templates.
        for _ in range(SCHOLARSHIP_SIZE):
            wo = generate_walk_on_profile()
            scholarship_sources.append(
                {
                    "meta": {
                        "height": wo.get("height"),
                        "weight": wo.get("weight"),
                        "year": advance_recruit_year(wo.get("year")),
                    },
                    "attributes": wo.get("attributes") or {},
                }
            )

    templates = list(scholarship_sources)
    while len(templates) < SCHOLARSHIP_SIZE:
        templates.append(random.choice(scholarship_sources))
    random.shuffle(templates)

    generated: list[dict[str, Any]] = []
    for template in templates[:SCHOLARSHIP_SIZE]:
        first, last = _random_scholarship_name()
        meta_template = template.get("meta") or {}
        attrs_template = template.get("attributes") or {}
        band = {"attrs": {key: _safe_int(attrs_template.get(key), 40) for key in CORE_12_ATTRS}}
        core = _normalize_import_core_attrs(
            {key: attrs_template.get(key) for key in CORE_12_ATTRS},
            band,
            attribute_mode=attribute_mode,
            apply_topup=apply_topup,
        )
        attrs = _finalize_franchise_attributes(core)
        generated.append(
            {
                "meta": {
                    "first_name": first,
                    "last_name": last,
                    "team": team_name,
                    "team_id": str(team_object_id),
                    "height": meta_template.get("height") or LEAGUE_MEDIAN_HEIGHT_IN,
                    "weight": meta_template.get("weight") or 185,
                    "year": meta_template.get("year") or _walk_on_class_year(),
                    "jersey": None,
                },
                "attributes": attrs,
            }
        )

    for _ in range(WALK_ON_COUNT):
        generated.append(
            _player_from_walk_on_profile(
                generate_walk_on_profile(),
                team_name=team_name,
                team_object_id=team_object_id,
            )
        )
    return generated


def _stamp_walk_on_slots(players: list[dict[str, Any]]) -> None:
    """Indices 12–14 are walk-ons: scholarship_players = players[:12]."""
    for player in players[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]:
        meta = player.setdefault("meta", {})
        meta["archetype"] = "Walk On"
        if not player.get("entry_tier"):
            player["entry_tier"] = "Poor"


def _budgets_for_authored_roster(
    *,
    attr_mode: str,
    source_fpd: Sequence[Mapping[str, Any]],
    imported_players: Sequence[Mapping[str, Any]] | None,
    explicit_budgets: Sequence[int] | None,
    generated_players: Sequence[Mapping[str, Any]] | None = None,
    ordered_fpd: Sequence[Mapping[str, Any]] | None = None,
) -> list[int]:
    if attr_mode != "capped":
        return []
    if explicit_budgets is not None and len(explicit_budgets) >= AUTHORED_ROSTER_SIZE:
        return [int(b) for b in explicit_budgets[:AUTHORED_ROSTER_SIZE]]

    # Prefer roster-order FPD (FTD players[]) — Mongo find() order is not stable.
    bases = list(ordered_fpd) if ordered_fpd is not None else []
    if len(bases) < SCHOLARSHIP_SIZE:
        scholarship_fpd = [d for d in source_fpd if not _is_walk_on_doc(d)]
        if not scholarship_fpd:
            scholarship_fpd = list(source_fpd[:SCHOLARSHIP_SIZE])
        bases = list(scholarship_fpd[:SCHOLARSHIP_SIZE])

    budgets: list[int] = []
    for i in range(SCHOLARSHIP_SIZE):
        if i < len(bases):
            raw = core12_total(bases[i].get("attributes") or {})
        else:
            raw = TOPUP_FLOOR
        budgets.append(capped_budget_for_inherited(raw))

    walk_rows = list(imported_players or [])[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]
    gen_walk = list(generated_players or [])[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]
    ordered_walk = list(ordered_fpd or [])[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]
    for i in range(WALK_ON_COUNT):
        row = walk_rows[i] if i < len(walk_rows) else None
        if row is not None and row.get("budget") is not None:
            try:
                budgets.append(capped_budget_for_inherited(int(row["budget"])))
                continue
            except (TypeError, ValueError):
                pass
        if row is not None:
            raw = core12_total(_merge_row_core_attrs(row))
            if raw > 0:
                budgets.append(capped_budget_for_inherited(raw))
                continue
        if i < len(gen_walk):
            budgets.append(
                capped_budget_for_inherited(core12_total(gen_walk[i].get("attributes") or {}))
            )
            continue
        if i < len(ordered_walk):
            budgets.append(
                capped_budget_for_inherited(
                    core12_total(ordered_walk[i].get("attributes") or {})
                )
            )
            continue
        budgets.append(TOPUP_FLOOR)
    return budgets


def build_fpd_docs_from_players(
    *,
    franchise_id: Any,
    players: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    player_ids: list[str] = []
    docs: list[dict[str, Any]] = []
    for player in players:
        meta = dict(player.get("meta") or {})
        # §6.5 seed stability: wizard-minted player_id carries through Apply.
        pid = str(
            player.get("player_id")
            or meta.get("player_id")
            or ""
        ).strip() or str(uuid.uuid4())
        meta.pop("player_id", None)
        image_id = player.get("image_id") or meta.get("image_id")
        if image_id:
            meta["image_id"] = str(image_id).strip()
        else:
            meta.pop("image_id", None)
        player_ids.append(pid)
        docs.append(
            _build_fpd_doc(
                franchise_id=franchise_id,
                player_id=pid,
                meta=meta,
                attributes=dict(player.get("attributes") or {}),
                entry_tier=player.get("entry_tier"),
                position_intent=player.get("position_intent"),
                development=player.get("development"),
                position_ratings=player.get("position_ratings"),
                photo=None,  # §4.5c / §6.5 — kit via meta.image_id only
                season=player.get("season"),
                career=player.get("career"),
                potential_factor=player.get("potential_factor"),
            )
        )
    return player_ids, docs


def _fpd_by_player_id(
    source_fpd: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Index FPD docs by player_id. Query result order is never used as a key."""
    return {str(d.get("player_id")): d for d in source_fpd if d.get("player_id")}


def _ordered_source_fpd(
    source_fpd: Sequence[Mapping[str, Any]],
    old_player_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """
    Bind FPD docs to FTD roster slots by player_id identity (§4.5b / Decision #29).

    Never trust find() ordinal order. Never sort the query to "match" — look up
    each FTD player_id in a map built from the result set.
    """
    by_id = _fpd_by_player_id(source_fpd)
    ordered = [dict(by_id[pid]) for pid in old_player_ids if pid in by_id]
    if len(ordered) >= AUTHORED_ROSTER_SIZE:
        return list(ordered[:AUTHORED_ROSTER_SIZE])
    # Incomplete identity map — fill remaining slots without using find() order
    # as a positional key (prefer walk-on flag, then leftover ids).
    seen = {str(d.get("player_id")) for d in ordered}
    leftovers = [dict(d) for d in source_fpd if str(d.get("player_id")) not in seen]
    scholarship = [d for d in leftovers if not _is_walk_on_doc(d)]
    walk = [d for d in leftovers if _is_walk_on_doc(d)]
    while len(ordered) < SCHOLARSHIP_SIZE and scholarship:
        ordered.append(scholarship.pop(0))
    while len(ordered) < AUTHORED_ROSTER_SIZE and walk:
        ordered.append(walk.pop(0))
    while len(ordered) < AUTHORED_ROSTER_SIZE and leftovers:
        cand = leftovers.pop(0)
        if str(cand.get("player_id")) not in {str(d.get("player_id")) for d in ordered}:
            ordered.append(cand)
    return list(ordered[:AUTHORED_ROSTER_SIZE])


def _build_inherited_roster_payloads(
    *,
    ordered_fpd: Sequence[Mapping[str, Any]],
    old_player_ids: Sequence[str],
    team_name: str,
    team_object_id: ObjectId,
    players_collection: Any = None,
    wizard_walk_ons: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Clone bases for all 15 slots — core/FPD for 0–11, wizard walk-ons for 12–14."""
    inherited: list[dict[str, Any]] = []
    for i in range(SCHOLARSHIP_SIZE):
        fpd = ordered_fpd[i] if i < len(ordered_fpd) else {}
        payload = _payload_from_fpd_doc(fpd) if fpd else {"meta": {}, "attributes": {}}
        core_id = old_player_ids[i] if i < len(old_player_ids) else ""
        core = _lookup_core_player(players_collection, core_id)
        inherited.append(_enrich_payload_from_core(payload, core))

    for i in range(WALK_ON_COUNT):
        if wizard_walk_ons and i < len(wizard_walk_ons):
            inherited.append(
                _payload_from_wizard_walk_on(
                    wizard_walk_ons[i],
                    team_name=team_name,
                    team_object_id=team_object_id,
                )
            )
            continue
        fpd_i = SCHOLARSHIP_SIZE + i
        fpd = ordered_fpd[fpd_i] if fpd_i < len(ordered_fpd) else {}
        if fpd:
            inherited.append(_payload_from_fpd_doc(fpd))
        else:
            inherited.append(
                {
                    "meta": {
                        "first_name": "Walk",
                        "last_name": "On",
                        "team": team_name,
                        "team_id": str(team_object_id),
                        "archetype": "Walk On",
                        "year": "Freshman",
                    },
                    "attributes": {},
                    "entry_tier": "Poor",
                }
            )
    return inherited


def apply_diffs_to_inherited_roster(
    *,
    inherited: Sequence[Mapping[str, Any]],
    imported_players: Sequence[Mapping[str, Any]],
    team_name: str,
    team_object_id: ObjectId,
    attribute_mode: str,
    apply_topup: bool,
    budgets: Sequence[int] | None,
) -> list[dict[str, Any]]:
    """§4.5b edit/import: diff each row onto its inherited clone."""
    mode = normalize_attribute_mode(attribute_mode)
    out: list[dict[str, Any]] = []
    rows = list(imported_players or [])
    for i in range(AUTHORED_ROSTER_SIZE):
        base = inherited[i] if i < len(inherited) else {"meta": {}, "attributes": {}}
        row = rows[i] if i < len(rows) else {}
        budget = None
        if mode == "capped" and budgets is not None and i < len(budgets):
            budget = int(budgets[i])
        out.append(
            apply_row_diff_to_inherited(
                base,
                row,
                team_name=team_name,
                team_object_id=team_object_id,
                attribute_mode=mode,
                budget=budget,
                apply_topup=apply_topup,
            )
        )
    return out


def replace_slot_roster(
    *,
    franchise_id: Any,
    team_object_id: ObjectId,
    team_name: str,
    roster_mode: str,
    imported_players: Sequence[Mapping[str, Any]] | None,
    franchise_team_data_collection: Any,
    franchise_players_data_collection: Any,
    attribute_mode: str = "capped",
    team_pool: int | None = None,
    per_player_budgets: Sequence[int] | None = None,
    players_collection: Any = None,
    wizard_walk_ons: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Replace the replaced slot's franchise roster after season init.

    §4.5c: edit only. Authors exactly 15 players, mints fresh player_ids,
    and applies capped top-up universally. Init's 15 FPD ids are deleted so
    orphans do not remain.

    Edit (§4.5b): clone each inherited player and overwrite only fields the
    row sends.

    Portrait kit reference is ``meta.image_id`` — a recruit_set id, builder_set
    id, or later an upload key. Flat base-league ``photo`` paths are stripped
    (unrecolourable masters). Assignment is Phase 3d.

    Returns (new_player_ids, fpd_docs).
    """
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": team_object_id},
        {"players": 1},
    ) or {}
    old_player_ids = [str(pid) for pid in (ftd.get("players") or []) if pid]

    source_fpd = list(
        franchise_players_data_collection.find(
            {
                "franchise_id": str(franchise_id),
                "player_id": {"$in": old_player_ids},
            }
        )
    ) if old_player_ids else []
    ordered_fpd = _ordered_source_fpd(source_fpd, old_player_ids)

    mode = (roster_mode or "edit").strip().lower()
    if mode != "edit":
        raise ValueError(f"roster_mode_invalid:{mode}")
    attr_mode = normalize_attribute_mode(attribute_mode)
    # §4.5c: Keep retired — capped top-up on every rewrite path.
    apply_topup = attr_mode == "capped"
    players: list[dict[str, Any]]

    offered = count_importable_players(imported_players)
    if offered != AUTHORED_ROSTER_SIZE:
        raise ValueError(f"roster_size_invalid:{offered}:{AUTHORED_ROSTER_SIZE}")
    budgets = _budgets_for_authored_roster(
        attr_mode=attr_mode,
        source_fpd=source_fpd,
        imported_players=imported_players,
        explicit_budgets=per_player_budgets,
        ordered_fpd=ordered_fpd,
    )
    inherited = _build_inherited_roster_payloads(
        ordered_fpd=ordered_fpd,
        old_player_ids=old_player_ids,
        team_name=team_name,
        team_object_id=team_object_id,
        players_collection=players_collection,
        wizard_walk_ons=wizard_walk_ons,
    )
    players = apply_diffs_to_inherited_roster(
        inherited=inherited,
        imported_players=imported_players or [],
        team_name=team_name,
        team_object_id=team_object_id,
        attribute_mode=attr_mode,
        apply_topup=apply_topup,
        budgets=budgets if attr_mode == "capped" else None,
    )
    if len(players) != AUTHORED_ROSTER_SIZE:
        raise ValueError(
            f"roster_size_invalid:{len(players)}:{AUTHORED_ROSTER_SIZE}"
        )
    _stamp_walk_on_slots(players)

    # §6.5: stamp wizard-minted player_id + meta.image_id from authored rows.
    # §10.3b: derive weight from height + player_id after the id is known.
    rows = list(imported_players or [])
    for i, player in enumerate(players):
        row = rows[i] if i < len(rows) else {}
        meta = dict(player.get("meta") or {})
        meta.pop("photo", None)
        # Accept top-level image_id (Apply FE) or nested meta.image_id (defensive).
        row_meta = row.get("meta") if isinstance(row.get("meta"), Mapping) else {}
        image_id = (
            row.get("image_id")
            or (row_meta.get("image_id") if isinstance(row_meta, Mapping) else None)
            or meta.get("image_id")
        )
        if image_id:
            meta["image_id"] = str(image_id).strip()
            player["image_id"] = meta["image_id"]
        else:
            meta.pop("image_id", None)
            player.pop("image_id", None)
        player_id = row.get("player_id") or player.get("player_id")
        if player_id:
            player["player_id"] = str(player_id).strip()
        else:
            player["player_id"] = str(uuid.uuid4())
        pid = str(player.get("player_id") or "").strip()
        height_val = _safe_int(meta.get("height"))
        if height_val is not None and pid:
            meta["weight"] = weight_from_height(height_val, player_id=pid)
        player["meta"] = meta
        player.pop("photo", None)

    if len(players) != AUTHORED_ROSTER_SIZE:
        raise ValueError(f"roster_size_invalid:{len(players)}:{AUTHORED_ROSTER_SIZE}")

    # §10: capped height (≤ inherited) + class (exact spend) over all 15.
    if attr_mode == "capped":
        height_budget = sum(
            int(_safe_int((p.get("meta") or {}).get("height"), 0) or 0) for p in inherited
        )
        class_budget = sum(
            _tb_class_rank_for_budget((p.get("meta") or {}).get("year")) for p in inherited
        )
        height_total = sum(
            int(_safe_int((p.get("meta") or {}).get("height"), 0) or 0) for p in players
        )
        class_total = sum(
            _tb_class_rank_for_budget((p.get("meta") or {}).get("year")) for p in players
        )
        if height_total > height_budget:
            raise ValueError(
                f"height_budget_exceeded:{height_total}:{height_budget}"
            )
        if class_total != class_budget:
            raise ValueError(
                f"class_budget_mismatch:{class_total}:{class_budget}"
            )

    if attr_mode == "uncapped" and team_pool is not None:
        team_total = sum(core12_total(p.get("attributes") or {}) for p in players)
        if team_total > int(team_pool):
            raise ValueError(
                f"uncapped_pool_exceeded:{team_total}:{int(team_pool)}"
            )

    new_ids, new_docs = build_fpd_docs_from_players(franchise_id=franchise_id, players=players)
    # Delete every superseded FPD (init's 15, including its three walk-ons).
    removed_ids = [pid for pid in old_player_ids if pid not in set(new_ids)]

    if new_docs:
        franchise_players_data_collection.insert_many(new_docs)
    if removed_ids:
        franchise_players_data_collection.delete_many(
            {
                "franchise_id": str(franchise_id),
                "player_id": {"$in": removed_ids},
            }
        )

    scholarship = new_ids[:SCHOLARSHIP_SIZE]
    total_attrs = sum(core_total_player_attrs(doc.get("attributes") or {}) for doc in new_docs)

    franchise_team_data_collection.update_one(
        {"franchise_id": franchise_id, "team_id": team_object_id},
        {
            "$set": {
                "players": new_ids,
                "scholarship_players": scholarship,
                "training_squad_players": [],
                "total_player_attrs": total_attrs,
            }
        },
    )
    return new_ids, new_docs


def collect_budget_attrs(
    franchise_players_data_collection: Any,
    franchise_id: Any,
    player_ids: Sequence[str],
) -> list[dict[str, Any]]:
    if not player_ids:
        return []
    attrs_list: list[dict[str, Any]] = []
    for fpd in franchise_players_data_collection.find(
        {
            "franchise_id": str(franchise_id),
            "player_id": {"$in": [str(pid) for pid in player_ids]},
        },
        {"attributes": 1},
    ):
        attrs_list.append(fpd.get("attributes") or {})
    return attrs_list


def collect_roster_shape_fields(
    franchise_players_data_collection: Any,
    franchise_id: Any,
    player_ids: Sequence[str],
) -> dict[str, list[Any]]:
    """Attribute + height + class inputs for roster_shape_at_creation (§10.3a)."""
    if not player_ids:
        return {"attrs": [], "heights": [], "class_years": []}
    by_id: dict[str, dict[str, Any]] = {}
    for fpd in franchise_players_data_collection.find(
        {
            "franchise_id": str(franchise_id),
            "player_id": {"$in": [str(pid) for pid in player_ids]},
        },
        {"player_id": 1, "attributes": 1, "meta.height": 1, "meta.year": 1},
    ):
        by_id[str(fpd.get("player_id"))] = fpd
    attrs: list[dict[str, Any]] = []
    heights: list[int] = []
    class_years: list[Any] = []
    for pid in player_ids:
        doc = by_id.get(str(pid)) or {}
        meta = doc.get("meta") or {}
        attrs.append(doc.get("attributes") or {})
        heights.append(int(_safe_int(meta.get("height"), 0) or 0))
        class_years.append(meta.get("year"))
    return {"attrs": attrs, "heights": heights, "class_years": class_years}


__all__ = [
    "MAX_ROSTER_SIZE",
    "AUTHORED_ROSTER_SIZE",
    "SCHOLARSHIP_SIZE",
    "WALK_ON_COUNT",
    "apply_row_diff_to_inherited",
    "apply_diffs_to_inherited_roster",
    "build_slot_roster_players",
    "build_wizard_walk_on_players",
    "get_or_create_wizard_walk_ons",
    "clear_wizard_walk_ons_for_user",
    "class_year_for_export",
    "collect_budget_attrs",
    "collect_roster_shape_fields",
    "compute_inherited_shape_budgets",
    "load_core_roster_rows_for_slot",
    "parse_import_class_year",
    "replace_slot_roster",
    "slot_per_player_budgets",
    "tb_class_rank_table",
    "count_importable_players",
]
