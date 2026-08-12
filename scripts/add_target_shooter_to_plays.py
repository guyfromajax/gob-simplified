#!/usr/bin/env python3
"""
Backfill `target_shooter` on play documents in one explicit database.

Source of truth:
- docs/Playbooks_Rework/playbooks_summary.md

This script updates plays whose names appear in the summary table, which is
currently the set-play inventory. Non-summary plays, such as motion plays, are
left unchanged.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
SUMMARY_PATH = ROOT / "docs" / "Playbooks_Rework" / "playbooks_summary.md"
VALID_SHOOTERS = {"PG", "SG", "SF", "PF", "C"}


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


def update_database(collection, db_name: str, summary_mapping: dict[str, str], *, apply: bool) -> tuple[int, int]:
    validate_set_plays(collection, summary_mapping, db_name)

    matched = 0
    modified = 0

    for play_name, target_shooter in sorted(summary_mapping.items()):
        matched += collection.count_documents({"name": play_name}, limit=1)
        if apply:
            result = collection.update_one(
                {"name": play_name},
                {"$set": {"target_shooter": target_shooter}},
            )
            modified += result.modified_count

    return matched, modified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    summary_mapping = load_summary_mapping()
    connection = connect_migration_target(args.db, write=args.apply)

    print(f"[plan] parsed {len(summary_mapping)} plays from {SUMMARY_PATH}")

    total_matched, total_modified = update_database(
        connection.database["plays"], args.db, summary_mapping, apply=args.apply
    )
    print(f"[{args.db}.plays] matched={total_matched} modified={total_modified}")

    print(f"[done] total matched={total_matched} total modified={total_modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
