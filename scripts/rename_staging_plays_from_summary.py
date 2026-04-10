#!/usr/bin/env python3
"""
Rename universal play docs in gob-staging.plays using the mapping embedded in
docs/Playbooks_Rework/playbooks_summary.md.

Expected markdown row format:
Old Play Name | Target Shooter | play_focus (New Play Name)

Only rows with a parenthesized rename in the third column are applied.
This script updates gob-staging.plays only.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


# Force staging before importing BackEnd.db
os.environ["MONGO_DB_NAME"] = "gob-staging"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import DB_NAME, plays_collection  # noqa: E402


SUMMARY_PATH = Path(__file__).resolve().parents[1] / "docs" / "Playbooks_Rework" / "playbooks_summary.md"
ROW_RE = re.compile(r"^(?P<old>[^|]+)\|(?P<shooter>[^|]+)\|(?P<focus>.+)$")
NEW_NAME_RE = re.compile(r"\((?P<new>[^()]+)\)\s*$")


def parse_rename_map(summary_path: Path) -> dict[str, str]:
    rename_map: dict[str, str] = {}

    for raw_line in summary_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("---") or line.startswith("Play Name") or line.startswith("Total "):
            continue

        match = ROW_RE.match(line)
        if not match:
            continue

        old_name = match.group("old").strip()
        focus_col = match.group("focus").strip()
        new_match = NEW_NAME_RE.search(focus_col)
        if not new_match:
            continue

        new_name = new_match.group("new").strip()
        rename_map[old_name] = new_name

    return rename_map


def main() -> None:
    if "staging" not in DB_NAME.lower():
        raise SystemExit(f"ERROR: Expected gob-staging, got DB_NAME={DB_NAME!r}")

    if not SUMMARY_PATH.exists():
        raise SystemExit(f"ERROR: Summary file not found: {SUMMARY_PATH}")

    rename_map = parse_rename_map(SUMMARY_PATH)
    if not rename_map:
        raise SystemExit("ERROR: No rename pairs found in playbooks_summary.md")

    print(f"Using database: {DB_NAME}")
    print(f"Summary file: {SUMMARY_PATH}")
    print(f"Rename pairs found: {len(rename_map)}")

    duplicate_targets = {}
    for old_name, new_name in rename_map.items():
        duplicate_targets.setdefault(new_name, []).append(old_name)
    collisions = {new: olds for new, olds in duplicate_targets.items() if len(olds) > 1}
    if collisions:
        raise SystemExit(f"ERROR: Multiple old names map to the same new name: {collisions}")

    matched = 0
    modified = 0
    unchanged = 0
    missing: list[str] = []

    for old_name, new_name in rename_map.items():
        play_doc = plays_collection.find_one({"name": old_name}, {"_id": 1, "name": 1})
        if not play_doc:
            missing.append(old_name)
            print(f"MISSING: {old_name}")
            continue

        matched += 1

        if old_name == new_name:
            unchanged += 1
            print(f"UNCHANGED: {old_name}")
            continue

        conflict = plays_collection.find_one({"name": new_name}, {"_id": 1, "name": 1})
        if conflict and conflict["_id"] != play_doc["_id"]:
            raise SystemExit(
                f"ERROR: Cannot rename {old_name!r} to {new_name!r} because another play already uses that name."
            )

        result = plays_collection.update_one({"_id": play_doc["_id"]}, {"$set": {"name": new_name}})
        if result.modified_count:
            modified += 1
            print(f"RENAMED: {old_name} -> {new_name}")
        else:
            unchanged += 1
            print(f"NO CHANGE: {old_name} -> {new_name}")

    print("\nSummary")
    print(f"Matched: {matched}")
    print(f"Modified: {modified}")
    print(f"Unchanged: {unchanged}")
    print(f"Missing: {len(missing)}")
    if missing:
        print("Missing names:")
        for name in missing:
            print(f" - {name}")


if __name__ == "__main__":
    main()
