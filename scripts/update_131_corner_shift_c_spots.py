#!/usr/bin/env python3
"""
Update 1-3-1 Zone corner-shift C coverage in one explicit database.

For docs with name "1-3-1 Zone":
  zone_definitions.lower_corner_shift.C →
    ["lower lowPost", "lower midBaseline", "lower corner"] (+ any other existing spots)
  zone_definitions.upper_corner_shift.C →
    ["upper lowPost", "upper midBaseline", "upper corner"] (+ any other existing spots)

Idempotent: does not duplicate spots. Required spots are ordered first; any
extra existing spots are preserved after them in original relative order.

Usage:
  .venv/bin/python scripts/update_131_corner_shift_c_spots.py --dry-run
  .venv/bin/python scripts/update_131_corner_shift_c_spots.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
DEFENSE_NAME = "1-3-1 Zone"

LOWER_C_REQUIRED = ("lower lowPost", "lower midBaseline", "lower corner")
UPPER_C_REQUIRED = ("upper lowPost", "upper midBaseline", "upper corner")


def merge_c_spots(existing: Any, required: tuple[str, ...]) -> list[str]:
    """Required spots first (ordered), then any other existing spots; no dupes."""
    prior = [str(s) for s in (existing or []) if s is not None and str(s).strip()]
    out: list[str] = []
    for spot in required:
        if spot not in out:
            out.append(spot)
    for spot in prior:
        if spot not in out:
            out.append(spot)
    return out


def _update_db(database, db_name: str, *, apply: bool) -> int:
    coll = database["defenses"]
    docs = list(coll.find({"name": DEFENSE_NAME}))
    if not docs:
        print(f"[{db_name}] No defenses doc with name={DEFENSE_NAME!r}")
        return 0

    modified = 0
    for doc in docs:
        doc_id = doc.get("_id")
        defense_id = doc.get("defense_id")
        zone_defs = dict(doc.get("zone_definitions") or {})
        if not zone_defs:
            print(f"[{db_name}] {defense_id}: missing zone_definitions — skip")
            continue

        lower = dict(zone_defs.get("lower_corner_shift") or {})
        upper = dict(zone_defs.get("upper_corner_shift") or {})
        if "C" not in lower and "lower_corner_shift" not in zone_defs:
            print(f"[{db_name}] {defense_id}: missing lower_corner_shift — skip")
            continue
        if "C" not in upper and "upper_corner_shift" not in zone_defs:
            print(f"[{db_name}] {defense_id}: missing upper_corner_shift — skip")
            continue

        old_lower_c = list(lower.get("C") or [])
        old_upper_c = list(upper.get("C") or [])
        new_lower_c = merge_c_spots(old_lower_c, LOWER_C_REQUIRED)
        new_upper_c = merge_c_spots(old_upper_c, UPPER_C_REQUIRED)

        print(f"[{db_name}] {defense_id} (_id={doc_id})")
        print(f"  lower_corner_shift.C: {old_lower_c} → {new_lower_c}")
        print(f"  upper_corner_shift.C: {old_upper_c} → {new_upper_c}")

        if old_lower_c == new_lower_c and old_upper_c == new_upper_c:
            print("  (already up to date)")
            continue

        if not apply:
            print("  (dry-run — not written)")
            continue

        lower["C"] = new_lower_c
        upper["C"] = new_upper_c
        zone_defs["lower_corner_shift"] = lower
        zone_defs["upper_corner_shift"] = upper
        result = coll.update_one(
            {"_id": doc_id},
            {"$set": {"zone_definitions": zone_defs}},
        )
        if result.modified_count:
            modified += 1
            print("  ✅ updated")
        else:
            print("  ⚠️ matched but modified_count=0")
    return modified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="Apply updates")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    apply = bool(args.apply)
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Target DB: {args.db}")
    print(f"Filter: name == {DEFENSE_NAME!r}\n")

    total = _update_db(connection.database, args.db, apply=apply)

    print(f"\nDone. Documents modified: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
