"""Team Builder roster export, import, and generate helpers (§8, §8.8)."""
from __future__ import annotations

import csv
import io
import random
import uuid
from typing import Any, Mapping, Sequence

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS, LEAGUE_MEDIAN_HEIGHT_IN
from BackEnd.constants.team_builder_budget import CORE_12_ATTRS
from BackEnd.models.franchise_manager import generate_walk_on_profile, get_franchise_name_assets, choose_franchise_first_name
from BackEnd.models.player import Player
from BackEnd.utils.franchise_rank_prestige import core_total_player_attrs
from BackEnd.utils.player_year import format_player_year_abbrev, normalize_player_year
from BackEnd.utils.position_ratings import compute_position_ratings

ROSTER_CSV_HEADERS: tuple[str, ...] = (
    "first_name",
    "last_name",
    "class_year",
    "height_in",
    "weight_lb",
    "jersey",
    *CORE_12_ATTRS,
    "CH",
    "EM",
    "MO",
)

MAX_ROSTER_SIZE = 15
SCHOLARSHIP_SIZE = 12

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
    for key in ("CH", "EM", "MO"):
        row[key] = ""
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


def _normalize_import_core_attrs(
    raw: Mapping[str, Any] | None,
    band_defaults: Mapping[str, Any],
) -> dict[str, int]:
    """Build core-12 attrs, filling blanks from slot medians."""
    band_attrs = band_defaults.get("attrs") or {}
    attrs: dict[str, int] = {}
    for key in CORE_12_ATTRS:
        val = _safe_int((raw or {}).get(key))
        if val is None:
            val = _safe_int(band_attrs.get(key), 1)
        attrs[key] = max(1, val or 1)
        attrs[f"anchor_{key}"] = attrs[key]
    return attrs


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
) -> dict[str, Any]:
    zero = _zero_stats_block()
    name = f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip()
    position_ratings = compute_position_ratings(
        {"attributes": attributes, "height": meta.get("height"), "name": name},
    )
    return {
        "franchise_id": str(franchise_id),
        "player_id": player_id,
        "meta": meta,
        "season": zero.copy(),
        "career": zero.copy(),
        "attributes": attributes,
        "position_ratings": position_ratings,
    }


def normalize_imported_players(
    imported_players: Sequence[Mapping[str, Any]] | None,
    *,
    band_defaults: Mapping[str, Any],
    team_name: str,
    team_object_id: ObjectId,
) -> list[dict[str, Any]]:
    """Validate import rows; return normalized player payloads (max 15)."""
    if not imported_players:
        return []

    normalized: list[dict[str, Any]] = []
    for row in imported_players:
        if len(normalized) >= MAX_ROSTER_SIZE:
            break
        first = str(row.get("first_name") or "").strip()
        last = str(row.get("last_name") or "").strip()
        if not first or not last:
            continue
        year = parse_import_class_year(row.get("class_year"))
        if not year:
            continue

        height = _safe_int(row.get("height_in"), band_defaults.get("height", LEAGUE_MEDIAN_HEIGHT_IN))
        weight = _safe_int(row.get("weight_lb"), band_defaults.get("weight", 185))
        jersey = _safe_int(row.get("jersey"))

        core_attrs = _normalize_import_core_attrs(row, band_defaults)
        attributes = _finalize_franchise_attributes(core_attrs)

        normalized.append(
            {
                "meta": {
                    "first_name": first,
                    "last_name": last,
                    "team": team_name,
                    "team_id": str(team_object_id),
                    "height": height,
                    "weight": weight,
                    "year": year,
                    "jersey": jersey,
                },
                "attributes": attributes,
            }
        )
    return normalized


def _random_scholarship_name() -> tuple[str, str]:
    first_names, last_names, first_name_weights = get_franchise_name_assets()
    first = choose_franchise_first_name(first_names, first_name_weights)
    last = random.choice(last_names).title()
    return first, last


def _walk_on_class_year() -> str:
    """Freshman–Senior only for generated scholarship-style rows."""
    return random.choice(["Freshman", "Sophomore", "Junior", "Senior"])


def generate_roster_at_band(
    *,
    source_fpd_docs: Sequence[Mapping[str, Any]],
    team_name: str,
    team_object_id: ObjectId,
    roster_size: int = MAX_ROSTER_SIZE,
) -> list[dict[str, Any]]:
    """
    Resample random names while preserving the slot's core-12 totals distribution.
    When the post-init roster has walk-ons, their attribute templates are reshuffled too.
    """
    roster_size = min(max(1, roster_size), MAX_ROSTER_SIZE)
    sources = list(source_fpd_docs)
    if not sources:
        for _ in range(roster_size):
            wo = generate_walk_on_profile()
            sources.append(
                {
                    "meta": {
                        "height": wo.get("height"),
                        "weight": wo.get("weight"),
                        "year": wo.get("year"),
                        "archetype": "Walk On",
                    },
                    "attributes": wo.get("attributes") or {},
                }
            )

    templates = list(sources)
    while len(templates) < roster_size:
        templates.append(random.choice(sources))

    random.shuffle(templates)
    generated: list[dict[str, Any]] = []

    for template in templates[:roster_size]:
        first, last = _random_scholarship_name()
        meta_template = template.get("meta") or {}
        attrs_template = template.get("attributes") or {}
        band = {"attrs": {key: _safe_int(attrs_template.get(key), 40) for key in CORE_12_ATTRS}}
        core = _normalize_import_core_attrs(
            {key: attrs_template.get(key) for key in CORE_12_ATTRS},
            band,
        )
        attrs = _finalize_franchise_attributes(core)

        meta: dict[str, Any] = {
            "first_name": first,
            "last_name": last,
            "team": team_name,
            "team_id": str(team_object_id),
            "height": meta_template.get("height") or LEAGUE_MEDIAN_HEIGHT_IN,
            "weight": meta_template.get("weight") or 185,
            "year": meta_template.get("year") or _walk_on_class_year(),
            "jersey": None,
        }
        if meta_template.get("archetype"):
            meta["archetype"] = meta_template["archetype"]
        generated.append({"meta": meta, "attributes": attrs})
    return generated


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
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Replace the replaced slot's franchise roster after season init.

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
    if mode == "import":
        players = normalize_imported_players(
            imported_players,
            band_defaults=band_defaults,
            team_name=team_name,
            team_object_id=team_object_id,
        )
        if not players:
            return old_player_ids, []
    elif mode == "generate":
        players = generate_roster_at_band(
            source_fpd_docs=source_fpd,
            team_name=team_name,
            team_object_id=team_object_id,
            roster_size=MAX_ROSTER_SIZE,
        )
    else:
        return old_player_ids, []

    new_ids, new_docs = build_fpd_docs_from_players(franchise_id=franchise_id, players=players)
    removed_ids = [pid for pid in old_player_ids if pid not in new_ids]

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
    "build_slot_roster_csv",
    "class_year_for_export",
    "collect_budget_attrs",
    "normalize_imported_players",
    "parse_import_class_year",
    "replace_slot_roster",
]
