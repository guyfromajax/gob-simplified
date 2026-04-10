#!/usr/bin/env python3
"""
Migrate set-play skeleton position keys in gob-staging.

Changes:
- Universal plays in gob-staging.plays:
  - For play_type == "set_play", rewrite HCO skeleton positions from
    PG/SG/SF/PF/C to:
      - target_shooter
      - pos1
      - pos2
      - pos3
      - pos4
  - Applies to all set-play variants and all versions within each variant.
  - Rewrites both step.pos_actions keys and event position references because
    the engine reads event fields today.

- Team-specific play copies in gob-staging:
  - Backfill target_shooter onto copied play objects in:
    - franchise_team_data.plays
    - tournaments.teams.{team_id}.plays
    - games.teams.{team_id}.plays

This script intentionally touches gob-staging only.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
DB_NAME = "gob-staging"
CANONICAL_POSITIONS = ("PG", "SG", "SF", "PF", "C")
SET_PLAY_VARIANTS = ("successful", "mid_play_change", "contested", "broken")
EVENT_POSITION_FIELDS = ("by", "for", "from", "to")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_mongo_uri() -> str:
    _load_env_file(ROOT / ".env.local")
    _load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment/.env files")
    return uri


def build_position_alias_map(target_shooter: str) -> dict[str, str]:
    if target_shooter not in CANONICAL_POSITIONS:
        raise ValueError(f"invalid target_shooter: {target_shooter}")

    remaining = [pos for pos in CANONICAL_POSITIONS if pos != target_shooter]
    alias_map = {target_shooter: "target_shooter"}
    for index, position in enumerate(remaining, start=1):
        alias_map[position] = f"pos{index}"
    return alias_map


def remap_event_positions(event: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
    updated = copy.deepcopy(event)
    for field in EVENT_POSITION_FIELDS:
        value = updated.get(field)
        if value in alias_map:
            updated[field] = alias_map[value]
    return updated


def remap_steps(steps: list[dict[str, Any]], alias_map: dict[str, str]) -> list[dict[str, Any]]:
    updated_steps: list[dict[str, Any]] = []

    for step in steps:
        updated_step = copy.deepcopy(step)
        pos_actions = updated_step.get("pos_actions") or {}
        remapped_pos_actions: dict[str, Any] = {}

        for position, action_info in pos_actions.items():
            remapped_position = alias_map.get(position, position)
            remapped_pos_actions[remapped_position] = action_info

        updated_step["pos_actions"] = remapped_pos_actions

        events = updated_step.get("events")
        if isinstance(events, list):
            updated_step["events"] = [
                remap_event_positions(event, alias_map) if isinstance(event, dict) else event
                for event in events
            ]

        updated_steps.append(updated_step)

    return updated_steps


def migrate_skeleton_variant(variant: dict[str, Any], alias_map: dict[str, str]) -> tuple[dict[str, Any], bool]:
    updated_variant = copy.deepcopy(variant)
    changed = False

    if isinstance(updated_variant.get("versions"), list):
        new_versions = []
        for version in updated_variant["versions"]:
            if not isinstance(version, dict):
                new_versions.append(version)
                continue
            updated_version = copy.deepcopy(version)
            steps = updated_version.get("steps")
            if isinstance(steps, list) and steps:
                remapped = remap_steps(steps, alias_map)
                if remapped != steps:
                    updated_version["steps"] = remapped
                    changed = True
            new_versions.append(updated_version)
        updated_variant["versions"] = new_versions
        return updated_variant, changed

    steps = updated_variant.get("steps")
    if isinstance(steps, list) and steps:
        remapped = remap_steps(steps, alias_map)
        if remapped != steps:
            updated_variant["steps"] = remapped
            changed = True

    return updated_variant, changed


def migrate_universal_play(play_doc: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if play_doc.get("play_type") != "set_play":
        return None, "skip_non_set_play"

    target_shooter = play_doc.get("target_shooter")
    if target_shooter not in CANONICAL_POSITIONS:
        raise RuntimeError(
            f"play '{play_doc.get('name', '<unknown>')}' missing valid target_shooter"
        )

    alias_map = build_position_alias_map(target_shooter)
    skeletons = copy.deepcopy(play_doc.get("skeletons") or {})
    changed = False

    for variant_name in SET_PLAY_VARIANTS:
        variant = skeletons.get(variant_name)
        if not isinstance(variant, dict):
            continue
        migrated_variant, variant_changed = migrate_skeleton_variant(variant, alias_map)
        if variant_changed:
            skeletons[variant_name] = migrated_variant
            changed = True

    if not changed:
        return None, "no_change"

    return {"skeletons": skeletons}, "updated"


def migrate_universal_plays(db) -> dict[str, int]:
    plays = db["plays"]
    stats = {"updated": 0, "no_change": 0, "skip_non_set_play": 0}

    for play in plays.find({}, {"name": 1, "play_type": 1, "target_shooter": 1, "skeletons": 1}):
        update_doc, status = migrate_universal_play(play)
        stats[status] = stats.get(status, 0) + 1
        if update_doc:
            plays.update_one({"_id": play["_id"]}, {"$set": update_doc})

    return stats


def backfill_target_shooter_into_plays_map(plays_map: dict[str, Any], target_map: dict[str, str]) -> tuple[dict[str, Any], bool]:
    updated_map = copy.deepcopy(plays_map)
    changed = False

    for play_name, play_data in updated_map.items():
        if not isinstance(play_data, dict):
            continue
        target_shooter = target_map.get(play_name)
        if not target_shooter:
            continue
        if play_data.get("target_shooter") != target_shooter:
            play_data["target_shooter"] = target_shooter
            changed = True

    return updated_map, changed


def backfill_franchise_team_data(db, target_map: dict[str, str]) -> tuple[int, int]:
    collection = db["franchise_team_data"]
    matched = 0
    modified = 0

    for doc in collection.find({}, {"plays": 1}):
        plays_map = doc.get("plays")
        if not isinstance(plays_map, dict):
            continue
        matched += 1
        updated_map, changed = backfill_target_shooter_into_plays_map(plays_map, target_map)
        if changed:
            collection.update_one({"_id": doc["_id"]}, {"$set": {"plays": updated_map}})
            modified += 1

    return matched, modified


def backfill_nested_team_plays(db, collection_name: str, target_map: dict[str, str]) -> tuple[int, int]:
    collection = db[collection_name]
    matched = 0
    modified = 0

    for doc in collection.find({}, {"teams": 1}):
        teams = doc.get("teams")
        if not isinstance(teams, dict):
            continue

        matched += 1
        updated_teams = copy.deepcopy(teams)
        changed = False

        for team_id, team_obj in updated_teams.items():
            if not isinstance(team_obj, dict):
                continue
            plays_map = team_obj.get("plays")
            if not isinstance(plays_map, dict):
                continue
            updated_map, plays_changed = backfill_target_shooter_into_plays_map(plays_map, target_map)
            if plays_changed:
                team_obj["plays"] = updated_map
                changed = True
                updated_teams[team_id] = team_obj

        if changed:
            collection.update_one({"_id": doc["_id"]}, {"$set": {"teams": updated_teams}})
            modified += 1

    return matched, modified


def main() -> int:
    uri = _load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    universal_stats = migrate_universal_plays(db)
    print(
        f"[{DB_NAME}.plays] updated={universal_stats['updated']} "
        f"no_change={universal_stats['no_change']} "
        f"skip_non_set_play={universal_stats['skip_non_set_play']}"
    )

    target_map = {
        doc["name"]: doc["target_shooter"]
        for doc in db["plays"].find(
            {"play_type": "set_play", "target_shooter": {"$in": list(CANONICAL_POSITIONS)}},
            {"_id": 0, "name": 1, "target_shooter": 1},
        )
    }
    print(f"[{DB_NAME}.plays] loaded target_shooter map for {len(target_map)} set plays")

    ftd_matched, ftd_modified = backfill_franchise_team_data(db, target_map)
    print(f"[{DB_NAME}.franchise_team_data] matched={ftd_matched} modified={ftd_modified}")

    tournaments_matched, tournaments_modified = backfill_nested_team_plays(db, "tournaments", target_map)
    print(f"[{DB_NAME}.tournaments] matched={tournaments_matched} modified={tournaments_modified}")

    games_matched, games_modified = backfill_nested_team_plays(db, "games", target_map)
    print(f"[{DB_NAME}.games] matched={games_matched} modified={games_modified}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
