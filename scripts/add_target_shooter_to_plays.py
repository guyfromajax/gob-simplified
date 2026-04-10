#!/usr/bin/env python3
"""
Backfill `target_shooter` on play documents in both `gob` and `gob-staging`.

Source of truth:
- docs/Playbooks_Rework/playbooks_summary.md

This script updates plays whose names appear in the summary table, which is
currently the set-play inventory. Non-summary plays, such as motion plays, are
left unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "docs" / "Playbooks_Rework" / "playbooks_summary.md"
TARGET_DBS = ("gob", "gob-staging")
VALID_SHOOTERS = {"PG", "SG", "SF", "PF", "C"}


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


def load_summary_mapping() -> dict[str, str]:
    if not SUMMARY_PATH.exists():
        raise RuntimeError(f"summary file not found: {SUMMARY_PATH}")

    mapping: dict[str, str] = {}
    for raw_line in SUMMARY_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        if line.startswith("Play Name |") or line.startswith("--- |"):
            continue
        if line.startswith("#") or line.startswith("Total set plays:"):
            continue

        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            continue

        play_name, target_shooter, _play_focus = parts
        if not play_name:
            continue
        if target_shooter not in VALID_SHOOTERS:
            raise RuntimeError(
                f"invalid target_shooter '{target_shooter}' for play '{play_name}' in {SUMMARY_PATH}"
            )
        mapping[play_name] = target_shooter

    if not mapping:
        raise RuntimeError(f"no play rows parsed from {SUMMARY_PATH}")
    return mapping


def validate_set_plays(collection, summary_mapping: dict[str, str], db_name: str) -> None:
    set_play_names = {
        (doc.get("name") or "").strip()
        for doc in collection.find({"play_type": "set_play"}, {"_id": 0, "name": 1})
    }
    set_play_names.discard("")

    missing_from_summary = sorted(set_play_names - set(summary_mapping))
    extra_in_summary = sorted(set(summary_mapping) - set_play_names)

    if missing_from_summary:
        raise RuntimeError(
            f"{db_name}.plays has set_play docs missing from summary: {', '.join(missing_from_summary)}"
        )
    if extra_in_summary:
        raise RuntimeError(
            f"summary has plays not found in {db_name}.plays set_play docs: {', '.join(extra_in_summary)}"
        )


def update_database(client: MongoClient, db_name: str, summary_mapping: dict[str, str]) -> tuple[int, int]:
    collection = client[db_name]["plays"]
    validate_set_plays(collection, summary_mapping, db_name)

    matched = 0
    modified = 0

    for play_name, target_shooter in sorted(summary_mapping.items()):
        result = collection.update_one(
            {"name": play_name},
            {"$set": {"target_shooter": target_shooter}},
        )
        matched += result.matched_count
        modified += result.modified_count

    return matched, modified


def main() -> int:
    summary_mapping = load_summary_mapping()
    uri = _load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    print(f"[plan] parsed {len(summary_mapping)} plays from {SUMMARY_PATH}")

    total_matched = 0
    total_modified = 0
    for db_name in TARGET_DBS:
        matched, modified = update_database(client, db_name, summary_mapping)
        total_matched += matched
        total_modified += modified
        print(f"[{db_name}.plays] matched={matched} modified={modified}")

    print(f"[done] total matched={total_matched} total modified={total_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
