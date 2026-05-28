#!/usr/bin/env python3
"""
Fix contested v1/v8 step 7 on Double Screen Three - Wing in gob and gob-staging.

Step 7 incorrectly re-passed to target_shooter at low post after the wing pass.
Changes:
  - target_shooter: receive -> handle_ball (location unchanged)
  - pos2: pass -> stationary (location unchanged)

Run from repo root:
  PYTHONPATH=. venv/bin/python scripts/fix_double_screen_three_wing_contested_step7.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
PLAY_NAME = "Double Screen Three - Wing"
TARGET_DBS = ("gob", "gob-staging")
TARGET_VERSIONS = ("v1", "v8")
STEP_INDEX = 7


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


def _step7_actions(play: dict, version: str) -> dict | None:
    versions = (
        (play.get("skeletons") or {})
        .get("contested", {})
        .get("versions")
        or []
    )
    for entry in versions:
        if entry.get("version") != version:
            continue
        steps = entry.get("steps") or []
        if len(steps) <= STEP_INDEX:
            return None
        pa = (steps[STEP_INDEX].get("pos_actions") or {})
        return {
            "target_shooter": dict(pa.get("target_shooter") or {}),
            "pos2": dict(pa.get("pos2") or {}),
        }
    return None


def _needs_update(actions: dict | None) -> bool:
    if not actions:
        return False
    ts = actions.get("target_shooter") or {}
    pos2 = actions.get("pos2") or {}
    return ts.get("action") == "receive" and pos2.get("action") == "pass"


def update_database(client: MongoClient, db_name: str) -> tuple[int, int]:
    collection = client[db_name]["plays"]
    play = collection.find_one({"name": PLAY_NAME})
    if not play:
        print(f"[{db_name}] play not found: {PLAY_NAME!r}")
        return 0, 0

    matched = 0
    modified = 0

    for version in TARGET_VERSIONS:
        before = _step7_actions(play, version)
        if before is None:
            print(f"[{db_name}] {version}: step 7 missing — skipped")
            continue
        if not _needs_update(before):
            print(
                f"[{db_name}] {version}: already fixed or unexpected shape — skipped "
                f"(target_shooter={before['target_shooter'].get('action')!r}, "
                f"pos2={before['pos2'].get('action')!r})"
            )
            continue

        result = collection.update_one(
            {"name": PLAY_NAME, "skeletons.contested.versions.version": version},
            {
                "$set": {
                    f"skeletons.contested.versions.$.steps.{STEP_INDEX}.pos_actions.target_shooter.action": "handle_ball",
                    f"skeletons.contested.versions.$.steps.{STEP_INDEX}.pos_actions.pos2.action": "stationary",
                }
            },
        )
        matched += result.matched_count
        modified += result.modified_count

        after_play = collection.find_one({"name": PLAY_NAME})
        after = _step7_actions(after_play, version)
        print(
            f"[{db_name}] {version}: updated step 7 "
            f"target_shooter {before['target_shooter'].get('action')}@{before['target_shooter'].get('location')} "
            f"-> {after['target_shooter'].get('action')}@{after['target_shooter'].get('location')}; "
            f"pos2 {before['pos2'].get('action')}@{before['pos2'].get('location')} "
            f"-> {after['pos2'].get('action')}@{after['pos2'].get('location')}"
        )

    return matched, modified


def main() -> int:
    uri = _load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    total_matched = 0
    total_modified = 0
    for db_name in TARGET_DBS:
        matched, modified = update_database(client, db_name)
        total_matched += matched
        total_modified += modified

    print(f"[done] matched={total_matched} modified={total_modified}")
    return 0 if total_modified > 0 or total_matched > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
