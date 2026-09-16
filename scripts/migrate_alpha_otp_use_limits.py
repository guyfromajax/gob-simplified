#!/usr/bin/env python3
"""Backfill max_uses / use_count / redemptions / active on alpha_otps.

Dry-run by default. Re-running is a no-op on documents that already have the
new fields.

Usage:
    PYTHONPATH=. venv/bin/python scripts/migrate_alpha_otp_use_limits.py --db gob-staging
    PYTHONPATH=. venv/bin/python scripts/migrate_alpha_otp_use_limits.py --db gob-staging --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

COLLECTION = "alpha_otps"


def _needs_backfill(doc: dict) -> bool:
    return any(
        field not in doc
        for field in (
            "max_uses",
            "use_count",
            "redemptions",
            "allocated_to",
            "allocated_at",
            "active",
        )
    )


def _backfill_fields(doc: dict) -> dict:
    used = doc.get("used") is True
    fields: dict = {}
    if "max_uses" not in doc:
        fields["max_uses"] = 1
    if "use_count" not in doc:
        fields["use_count"] = 1 if used else 0
    if "active" not in doc:
        fields["active"] = True
    if "allocated_to" not in doc:
        fields["allocated_to"] = None
    if "allocated_at" not in doc:
        fields["allocated_at"] = None
    if "redemptions" not in doc:
        email = doc.get("used_by_email")
        used_at = doc.get("used_at")
        if used and isinstance(email, str) and email.strip():
            fields["redemptions"] = [{"email": email.strip().lower(), "used_at": used_at}]
        else:
            fields["redemptions"] = []
    return fields


def migrate(collection, *, apply: bool) -> int:
    pending = 0
    updated = 0
    now = datetime.now(timezone.utc)
    for doc in collection.find({}):
        if not _needs_backfill(doc):
            continue
        pending += 1
        fields = _backfill_fields(doc)
        fields["migrated_use_limits_at"] = now
        if not apply:
            continue
        result = collection.update_one(
            {"_id": doc["_id"]},
            {"$set": fields},
        )
        if result.modified_count == 1:
            updated += 1
    return pending if not apply else updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob", "gob-staging"])
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    try:
        collection = connection.database[COLLECTION]
        total = collection.count_documents({})
        missing = {
            field: collection.count_documents({field: {"$exists": False}})
            for field in ("max_uses", "use_count", "redemptions", "allocated_to", "allocated_at", "active")
        }
        print(f"Target: {args.db}.{COLLECTION}")
        print(f"Total documents: {total}")
        for field, count in missing.items():
            print(f"Missing {field}: {count}")
        count = migrate(collection, apply=args.apply)
        if args.apply:
            remaining = collection.count_documents(
                {
                    "$or": [
                        {"max_uses": {"$exists": False}},
                        {"use_count": {"$exists": False}},
                    ]
                }
            )
            print(f"Updated {count} documents")
            print(f"Still missing use_count or max_uses: {remaining}")
        else:
            print(f"Would update {count} documents")
            print("Dry-run only. Re-run with --apply to update documents.")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
