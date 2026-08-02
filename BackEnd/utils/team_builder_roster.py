"""Team Builder roster export, import, and generate helpers (§8, §8.8)."""
from __future__ import annotations

import csv
import io
import random
import uuid
from typing import Any, Mapping, Sequence

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS, LEAGUE_MEDIAN_HEIGHT_IN
from BackEnd.constants.team_builder_budget import (
    ATTR_MAX,
    ATTR_MIN,
    CORE_12_ATTRS,
    TOPUP_FLOOR,
    apply_capped_topup,
    capped_budget_for_inherited,
    core12_total,
    force_core12_to_budget,
    normalize_attribute_mode,
)
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

ROSTER_CSV_HEADERS: tuple[str, ...] = (
    "first_name",
    "last_name",
    "class_year",
    "height_in",
    "weight_lb",
    "jersey",
    *CORE_12_ATTRS,
)

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


def class_year_for_export(year: Any) -> str:
    """Map core year to FR/SO/JR/SR for CSV export; blank when not applicable."""
    abbrev = format_player_year_abbrev(year)
    return abbrev if abbrev in _EXPORTABLE_CLASS_YEARS else ""


def parse_import_class_year(raw: Any) -> str | None:
    """Return canonical class year (Freshman…) or None when unrecognized."""
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


def _player_row_for_csv(player: Mapping[str, Any]) -> dict[str, Any]:
    attrs = player.get("attributes") or {}
    row = {
        "first_name": player.get("first_name") or "",
        "last_name": player.get("last_name") or "",
        "class_year": class_year_for_export(player.get("year")),
        "height_in": player.get("height") if player.get("height") is not None else "",
        "weight_lb": player.get("weight") if player.get("weight") is not None else "",
        "jersey": player.get("jersey") if player.get("jersey") is not None else "",
    }
    for key in CORE_12_ATTRS:
        val = attrs.get(key)
        row[key] = val if val is not None and val != "" else ""
    return row


def build_slot_roster_csv(db: Any, team_object_id: ObjectId) -> str:
    """Export a core team's scholarship roster as CSV (walk-ons excluded)."""
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
            {
                "first_name": 1,
                "last_name": 1,
                "year": 1,
                "height": 1,
                "weight": 1,
                "jersey": 1,
                "attributes": 1,
            },
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
            {
                "first_name": 1,
                "last_name": 1,
                "year": 1,
                "height": 1,
                "weight": 1,
                "jersey": 1,
                "attributes": 1,
            },
        ):
            ordered.append(doc)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(ROSTER_CSV_HEADERS), lineterminator="\n")
    writer.writeheader()
    for player in ordered[:MAX_ROSTER_SIZE]:
        writer.writerow(_player_row_for_csv(player))
    return buf.getvalue()


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
) -> dict[str, Any]:
    zero = _zero_stats_block()
    name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
    position_ratings = compute_position_ratings(
        {"attributes": attributes, "height": meta.get("height"), "name": name},
    )
    if not position_intent:
        position_intent = (max(position_ratings, key=position_ratings.get)
                           if position_ratings else "SF")
    if not entry_tier:
        # Derive-and-STORE now (year-aware, from the player's current-year ratings) so a
        # later rollover never re-derives from RT — which misclassifies once pillar-3
        # coaching quality has pushed RT off the ladder. Imported/band rosters carry no
        # tier, so this is the explicit-carry point for them.
        entry_tier = entry_tier_at_year(position_ratings, meta.get("year") or "FR")
    doc = {
        "franchise_id": str(franchise_id),
        "player_id": player_id,
        "meta": meta,
        "season": zero.copy(),
        "career": zero.copy(),
        "attributes": attributes,
        "position_ratings": position_ratings,
        "entry_tier": entry_tier,
        "position_intent": position_intent,
    }
    if development is not None:
        doc["development"] = development
    return doc


def normalize_imported_players(
    imported_players: Sequence[Mapping[str, Any]] | None,
    *,
    band_defaults: Mapping[str, Any],
    team_name: str,
    team_object_id: ObjectId,
    attribute_mode: str = "capped",
    apply_topup: bool = False,
    per_player_budgets: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """Validate import/edit rows; return normalized player payloads (max 15).

    In capped mode, when per_player_budgets is provided (slot order), each player's
    core-12 is forced to that budget so points cannot cross player boundaries.
    """
    if not imported_players:
        return []

    mode = normalize_attribute_mode(attribute_mode)
    normalized: list[dict[str, Any]] = []
    for row in imported_players:
        if len(normalized) >= MAX_ROSTER_SIZE:
            break
        meta_in = row.get("meta") if isinstance(row.get("meta"), Mapping) else {}
        first = str(row.get("first_name") or meta_in.get("first_name") or "").strip()
        last = str(row.get("last_name") or meta_in.get("last_name") or "").strip()
        if not first or not last:
            continue
        year = parse_import_class_year(
            row.get("class_year") or meta_in.get("year") or row.get("year")
        )
        if not year:
            continue

        height = _safe_int(
            row.get("height_in"),
            _safe_int(row.get("height"), _safe_int(meta_in.get("height"), band_defaults.get("height", LEAGUE_MEDIAN_HEIGHT_IN))),
        )
        weight = _safe_int(
            row.get("weight_lb"),
            _safe_int(row.get("weight"), _safe_int(meta_in.get("weight"), band_defaults.get("weight", 185))),
        )
        jersey = _safe_int(row.get("jersey"), _safe_int(meta_in.get("jersey")))

        core_attrs = _normalize_import_core_attrs(
            row,
            band_defaults,
            attribute_mode=mode,
            apply_topup=apply_topup,
        )
        idx = len(normalized)
        if mode == "capped" and per_player_budgets is not None and idx < len(per_player_budgets):
            forced = force_core12_to_budget(core_attrs, int(per_player_budgets[idx]))
            core_attrs = {key: forced[key] for key in CORE_12_ATTRS}
            for key in CORE_12_ATTRS:
                core_attrs[f"anchor_{key}"] = core_attrs[key]
        attributes = _finalize_franchise_attributes(core_attrs)

        is_walk_on = bool(row.get("walk_on")) or str(
            meta_in.get("archetype") or row.get("archetype") or ""
        ) == "Walk On"
        meta: dict[str, Any] = {
            "first_name": first,
            "last_name": last,
            "team": team_name,
            "team_id": str(team_object_id),
            "height": height,
            "weight": weight,
            "year": year,
            "jersey": jersey,
        }
        if is_walk_on:
            meta["archetype"] = "Walk On"
        entry = {
            "meta": meta,
            "attributes": attributes,
        }
        if row.get("entry_tier") or meta_in.get("entry_tier"):
            entry["entry_tier"] = row.get("entry_tier") or meta_in.get("entry_tier")
        if row.get("position_intent") or meta_in.get("position_intent"):
            entry["position_intent"] = row.get("position_intent") or meta_in.get(
                "position_intent"
            )
        if row.get("development") is not None:
            entry["development"] = row.get("development")
        elif is_walk_on:
            entry["entry_tier"] = entry.get("entry_tier") or "Poor"
        normalized.append(entry)
    return normalized


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
    """Count rows that would normalize (name + class year), uncapped by roster max."""
    if not imported_players:
        return 0
    count = 0
    for row in imported_players:
        meta_in = row.get("meta") if isinstance(row.get("meta"), Mapping) else {}
        first = str(row.get("first_name") or meta_in.get("first_name") or "").strip()
        last = str(row.get("last_name") or meta_in.get("last_name") or "").strip()
        if not first or not last:
            continue
        year = parse_import_class_year(
            row.get("class_year") or meta_in.get("year") or row.get("year")
        )
        if not year:
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

    col = db["team_builder_wizard_drafts"]
    query = {
        "user_id": user_key,
        "draft_id": draft_key,
        "replaced_object_id": slot_key,
    }
    existing = col.find_one(query, {"walk_ons": 1})
    stored = (existing or {}).get("walk_ons") if existing else None
    if isinstance(stored, list) and len(stored) == WALK_ON_COUNT:
        return stored

    walk_ons = build_wizard_walk_on_players()
    col.update_one(
        query,
        {
            "$set": {
                **query,
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
) -> list[int]:
    if attr_mode != "capped":
        return []
    if explicit_budgets is not None and len(explicit_budgets) >= AUTHORED_ROSTER_SIZE:
        return [int(b) for b in explicit_budgets[:AUTHORED_ROSTER_SIZE]]

    budgets: list[int] = []
    scholarship_fpd = [d for d in source_fpd if not _is_walk_on_doc(d)]
    if not scholarship_fpd:
        scholarship_fpd = list(source_fpd[:SCHOLARSHIP_SIZE])
    for i in range(SCHOLARSHIP_SIZE):
        if i < len(scholarship_fpd):
            raw = core12_total(scholarship_fpd[i].get("attributes") or {})
        else:
            raw = TOPUP_FLOOR
        budgets.append(capped_budget_for_inherited(raw))

    walk_rows = list(imported_players or [])[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]
    gen_walk = list(generated_players or [])[SCHOLARSHIP_SIZE:AUTHORED_ROSTER_SIZE]
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
        pid = str(uuid.uuid4())
        player_ids.append(pid)
        docs.append(
            _build_fpd_doc(
                franchise_id=franchise_id,
                player_id=pid,
                meta=dict(player.get("meta") or {}),
                attributes=dict(player.get("attributes") or {}),
                entry_tier=player.get("entry_tier"),
                position_intent=player.get("position_intent"),
                development=player.get("development"),
            )
        )
    return player_ids, docs


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
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Replace the replaced slot's franchise roster after season init.

    Path 1 keep is handled by the caller (no call / no rewrite). Paths 2–4
    author exactly 15 players (§4.5a): edit/import supply 15; generate builds
    12 band + 3 walk-ons. Init's 15 FPD ids are deleted so orphans do not remain.

    Returns (new_player_ids, fpd_docs).
    """
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": team_object_id},
        {"players": 1},
    ) or {}
    old_player_ids = [str(pid) for pid in (ftd.get("players") or []) if pid]

    band_defaults = slot_band_defaults(
        franchise_players_data_collection,
        franchise_id,
        team_object_id,
        old_player_ids,
    )

    source_fpd = list(
        franchise_players_data_collection.find(
            {
                "franchise_id": str(franchise_id),
                "player_id": {"$in": old_player_ids},
            }
        )
    ) if old_player_ids else []

    mode = (roster_mode or "keep").strip().lower()
    attr_mode = normalize_attribute_mode(attribute_mode)
    apply_topup = attr_mode == "capped" and mode != "keep"
    players: list[dict[str, Any]]

    if mode in ("import", "edit"):
        offered = count_importable_players(imported_players)
        if offered != AUTHORED_ROSTER_SIZE:
            raise ValueError(f"roster_size_invalid:{offered}:{AUTHORED_ROSTER_SIZE}")
        budgets = _budgets_for_authored_roster(
            attr_mode=attr_mode,
            source_fpd=source_fpd,
            imported_players=imported_players,
            explicit_budgets=per_player_budgets,
        )
        players = normalize_imported_players(
            imported_players,
            band_defaults=band_defaults,
            team_name=team_name,
            team_object_id=team_object_id,
            attribute_mode=attr_mode,
            apply_topup=apply_topup,
            per_player_budgets=budgets if attr_mode == "capped" else None,
        )
        if len(players) != AUTHORED_ROSTER_SIZE:
            raise ValueError(
                f"roster_size_invalid:{len(players)}:{AUTHORED_ROSTER_SIZE}"
            )
        _stamp_walk_on_slots(players)
    elif mode == "generate":
        if not source_fpd:
            raise ValueError("capped_roster_empty_slot")
        players = generate_roster_at_band(
            source_fpd_docs=source_fpd,
            team_name=team_name,
            team_object_id=team_object_id,
            roster_size=AUTHORED_ROSTER_SIZE,
            attribute_mode=attr_mode,
            apply_topup=apply_topup,
        )
        _stamp_walk_on_slots(players)
        budgets = _budgets_for_authored_roster(
            attr_mode=attr_mode,
            source_fpd=source_fpd,
            imported_players=None,
            explicit_budgets=per_player_budgets,
            generated_players=players,
        )
        if attr_mode == "capped" and budgets:
            for i, player in enumerate(players):
                if i >= len(budgets):
                    break
                forced = force_core12_to_budget(player.get("attributes") or {}, budgets[i])
                core = {key: forced[key] for key in CORE_12_ATTRS}
                for key in CORE_12_ATTRS:
                    core[f"anchor_{key}"] = core[key]
                player["attributes"] = _finalize_franchise_attributes(core)
    else:
        return old_player_ids, []

    if len(players) != AUTHORED_ROSTER_SIZE:
        raise ValueError(f"roster_size_invalid:{len(players)}:{AUTHORED_ROSTER_SIZE}")

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


__all__ = [
    "ROSTER_CSV_HEADERS",
    "MAX_ROSTER_SIZE",
    "AUTHORED_ROSTER_SIZE",
    "SCHOLARSHIP_SIZE",
    "WALK_ON_COUNT",
    "build_slot_roster_csv",
    "build_wizard_walk_on_players",
    "get_or_create_wizard_walk_ons",
    "clear_wizard_walk_ons_for_user",
    "class_year_for_export",
    "collect_budget_attrs",
    "normalize_imported_players",
    "parse_import_class_year",
    "replace_slot_roster",
    "slot_per_player_budgets",
    "count_importable_players",
]
