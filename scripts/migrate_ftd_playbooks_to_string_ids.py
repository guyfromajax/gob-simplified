#!/usr/bin/env python3
"""
Migrate franchise_team_data (FTD) playbooks + plays to string-id keyed structure.

This script is intended for the live gob database migration after the staging
playbook overhaul. It updates existing FTD documents so they are retroactively
compatible with the current backend/frontend expectations.

What it does:
1. Re-keys `plays` from play names to string play_ids when resolvable.
2. Ensures each play entry has a string `play_id` and preserved `name`.
3. Migrates `playbook_settings` to the current canonical shape:
   - motion
   - set_plays
   - fast_breaks
   - man_defense
   - zone_defense
   - pc_order
   - position_filters
   - even_distribution_all
   - _meta
4. Preserves normalized legacy-compatible keys where helpful during transition:
   - set_play_inside / set_play_attack / set_play_outside
   - fast_break
   - slot_assignments
   - motion_dropdowns

Default mode is dry-run. Pass `--execute` to write changes.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target  # noqa: E402

from BackEnd.utils.playbook_settings_utils import (  # noqa: E402
    build_legacy_playbook_settings_view,
    build_play_lookups_from_team_plays,
    build_play_lookups_from_universal_plays,
    build_simplified_playbook_settings,
    normalize_motion_dropdowns_to_play_ids,
    normalize_slot_assignments_to_play_ids,
)


DEFAULT_COLLECTION = "franchise_team_data"
POSITION_FILTER_KEYS = ("standard", "PG", "SG", "SF", "PF", "C")


def merge_play_lookups(
    primary_by_id: dict[str, dict[str, Any]],
    primary_by_name: dict[str, dict[str, Any]],
    secondary_by_id: dict[str, dict[str, Any]],
    secondary_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    merged_by_id = dict(secondary_by_id or {})
    merged_by_id.update(primary_by_id or {})
    merged_by_name = dict(secondary_by_name or {})
    merged_by_name.update(primary_by_name or {})
    return merged_by_id, merged_by_name


def resolve_play_id(
    raw_key: str,
    play_data: dict[str, Any],
    universal_by_name: dict[str, dict[str, Any]],
) -> str | None:
    play_id = play_data.get("play_id")
    if play_id:
        return str(play_id)

    universal_play = None
    if raw_key in universal_by_name:
        universal_play = universal_by_name[raw_key]
    else:
        play_name = play_data.get("name")
        if play_name and play_name in universal_by_name:
            universal_play = universal_by_name[play_name]

    if isinstance(universal_play, dict):
        universal_id = universal_play.get("play_id") or universal_play.get("_id")
        if universal_id:
            return str(universal_id)

    return None


def merge_play_entry(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged.get(key) in (None, "", {}, []):
            merged[key] = value
    return merged


def migrate_plays_map(
    plays_map: dict[str, Any] | None,
    universal_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(plays_map, dict):
        return {}, []

    migrated: dict[str, Any] = {}
    warnings: list[str] = []

    for raw_key, raw_value in plays_map.items():
        if not isinstance(raw_value, dict):
            continue

        play_data = copy.deepcopy(raw_value)
        resolved_play_id = resolve_play_id(str(raw_key), play_data, universal_by_name)
        resolved_name = play_data.get("name") or (None if str(raw_key) == resolved_play_id else str(raw_key))

        if resolved_play_id:
            play_data["play_id"] = resolved_play_id
            target_key = resolved_play_id
        else:
            target_key = str(raw_key)
            warnings.append(f"unresolved play_id for key '{raw_key}'")

        if resolved_name:
            play_data["name"] = resolved_name

        if target_key in migrated:
            migrated[target_key] = merge_play_entry(migrated[target_key], play_data)
            warnings.append(f"duplicate play key collapsed into '{target_key}'")
        else:
            migrated[target_key] = play_data

    return migrated, warnings


def normalize_position_filters(
    raw_filters: dict[str, Any] | None,
    plays_by_id: dict[str, dict[str, Any]],
    plays_by_name: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {key: [] for key in POSITION_FILTER_KEYS}
    if not isinstance(raw_filters, dict):
        return normalized

    for filter_key in POSITION_FILTER_KEYS:
        raw_values = raw_filters.get(filter_key, []) or []
        resolved_values: list[str] = []
        for raw_value in raw_values:
            resolved_value = None
            if raw_value is None:
                continue
            raw_value = str(raw_value)
            if raw_value in plays_by_id:
                resolved_value = raw_value
            else:
                play_data = plays_by_name.get(raw_value)
                if isinstance(play_data, dict) and play_data.get("play_id"):
                    resolved_value = str(play_data["play_id"])
            if resolved_value and resolved_value not in resolved_values:
                resolved_values.append(resolved_value)
        normalized[filter_key] = resolved_values

    return normalized


def build_migrated_playbook_settings(
    existing_settings: dict[str, Any] | None,
    plays_map: dict[str, Any],
    universal_by_id: dict[str, dict[str, Any]],
    universal_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    existing_settings = existing_settings or {}
    team_by_id, team_by_name = build_play_lookups_from_team_plays(plays_map)
    plays_by_id, plays_by_name = merge_play_lookups(team_by_id, team_by_name, universal_by_id, universal_by_name)

    canonical = build_simplified_playbook_settings(existing_settings, plays_by_id, plays_by_name)
    legacy = build_legacy_playbook_settings_view(canonical, plays_by_id, plays_by_name)

    normalized_slots = normalize_slot_assignments_to_play_ids(
        existing_settings.get("slot_assignments", {}),
        plays_by_id,
        plays_by_name,
    )
    if not normalized_slots and legacy.get("slot_assignments"):
        normalized_slots = legacy.get("slot_assignments", {})

    normalized_motion_dropdowns = normalize_motion_dropdowns_to_play_ids(
        existing_settings.get("motion_dropdowns", {}),
        plays_by_id,
        plays_by_name,
    )

    normalized_position_filters = normalize_position_filters(
        existing_settings.get("position_filters", {}),
        plays_by_id,
        plays_by_name,
    )

    raw_meta = canonical.get("_meta", {}) or {}
    meta = {
        "user_saved": bool(raw_meta.get("user_saved", False)),
        "schema_version": max(2, int(raw_meta.get("schema_version", 2) or 2)),
    }

    migrated = {
        "motion": canonical.get("motion", {}),
        "set_plays": canonical.get("set_plays", {}),
        "fast_breaks": canonical.get("fast_breaks", {}),
        "zone_defense": canonical.get("zone_defense", {}),
        "man_defense": canonical.get("man_defense", {}),
        "pc_order": canonical.get("pc_order", {"offense": [], "defense": []}),
        "position_filters": normalized_position_filters,
        "even_distribution_all": bool(existing_settings.get("even_distribution_all", False)),
        "_meta": meta,
        # Transition compatibility keys:
        "set_play_inside": legacy.get("set_play_inside", {}),
        "set_play_attack": legacy.get("set_play_attack", {}),
        "set_play_outside": legacy.get("set_play_outside", {}),
        "fast_break": legacy.get("fast_break", canonical.get("fast_breaks", {})),
        "slot_assignments": normalized_slots,
        "motion_dropdowns": normalized_motion_dropdowns,
    }
    return migrated


def migrate_ftd_doc(
    doc: dict[str, Any],
    universal_by_id: dict[str, dict[str, Any]],
    universal_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    original_plays = doc.get("plays", {})
    migrated_plays, warnings = migrate_plays_map(original_plays, universal_by_name)

    migrated_playbook_settings = build_migrated_playbook_settings(
        doc.get("playbook_settings", {}),
        migrated_plays,
        universal_by_id,
        universal_by_name,
    )

    updates = {
        "plays": migrated_plays,
        "playbook_settings": migrated_playbook_settings,
    }
    return updates, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate FTD playbooks/plays to string-id keyed structure.")
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Target collection name (default: {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write the migration. Default is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of docs to inspect/write.",
    )
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.execute)
    db = connection.database
    ftd_collection = db[args.collection]
    plays_collection = db["plays"]

    universal_plays = list(plays_collection.find({}, {"name": 1}))
    universal_by_id, universal_by_name = build_play_lookups_from_universal_plays(universal_plays)

    query_cursor = ftd_collection.find({})
    if args.limit and args.limit > 0:
        query_cursor = query_cursor.limit(args.limit)

    inspected = 0
    changed = 0
    warnings_count = 0

    mode_label = "EXECUTE" if args.execute else "DRY RUN"
    print(f"\n=== FTD PLAYBOOK MIGRATION ({mode_label}) ===")
    print(f"Database:   {args.db}")
    print(f"Collection: {args.collection}")
    print(f"Universal plays loaded: {len(universal_plays)}")

    for doc in query_cursor:
        inspected += 1
        updates, warnings = migrate_ftd_doc(doc, universal_by_id, universal_by_name)
        warnings_count += len(warnings)

        current_plays = doc.get("plays", {}) if isinstance(doc.get("plays", {}), dict) else {}
        current_playbook_settings = doc.get("playbook_settings", {}) if isinstance(doc.get("playbook_settings", {}), dict) else {}
        needs_update = (
            updates["plays"] != current_plays or
            updates["playbook_settings"] != current_playbook_settings
        )

        if not needs_update:
            continue

        changed += 1
        doc_id = str(doc.get("_id"))
        team_id = str(doc.get("team_id"))
        print(f"\nFTD {doc_id} | team_id={team_id}")
        print(f"  plays: {len(current_plays)} -> {len(updates['plays'])}")
        print(f"  playbook keys: {sorted(list(updates['playbook_settings'].keys()))}")
        if warnings:
            for warning in warnings[:10]:
                print(f"  WARN: {warning}")
            if len(warnings) > 10:
                print(f"  WARN: ... {len(warnings) - 10} more")

        if args.execute:
            ftd_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": updates},
            )

    print("\n=== SUMMARY ===")
    print(f"Inspected: {inspected}")
    print(f"Changed:   {changed}")
    print(f"Warnings:  {warnings_count}")
    if not args.execute:
        print("No writes performed. Re-run with --execute to apply.")
    connection.close()


if __name__ == "__main__":
    main()
