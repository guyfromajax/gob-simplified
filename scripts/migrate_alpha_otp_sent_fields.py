#!/usr/bin/env python3
"""
Add sent / sent_to_email / sent_at fields to alpha_otps documents missing them.

Usage:
  PYTHONPATH=. python scripts/migrate_alpha_otp_sent_fields.py
  PYTHONPATH=. python scripts/migrate_alpha_otp_sent_fields.py --apply
  PYTHONPATH=. python scripts/migrate_alpha_otp_sent_fields.py --apply --db production --confirm-production-write
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv

    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

DB_NAME_STAGING = "gob-staging"
DB_NAME_PRODUCTION = "gob"
COLLECTION = "alpha_otps"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--db",
        choices=["staging", "production"],
        default="staging",
        help="Target database (default: staging)",
    )
    parser.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required with --apply --db production",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_name = DB_NAME_STAGING if args.db == "staging" else DB_NAME_PRODUCTION
    if args.apply and args.db == "production" and not args.confirm_production_write:
        print("Refusing production write without --confirm-production-write")
        return 1

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set")
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    collection = client[db_name][COLLECTION]

    missing_sent = collection.count_documents({"sent": {"$exists": False}})
    missing_sent_to = collection.count_documents({"sent_to_email": {"$exists": False}})
    missing_sent_at = collection.count_documents({"sent_at": {"$exists": False}})

    print(f"Target: {db_name}.{COLLECTION}")
    print(f"Missing sent: {missing_sent}")
    print(f"Missing sent_to_email: {missing_sent_to}")
    print(f"Missing sent_at: {missing_sent_at}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to update documents.")
        return 0

    now = datetime.now(timezone.utc)
    result = collection.update_many(
        {"sent": {"$exists": False}},
        {"$set": {"sent": False, "sent_to_email": None, "sent_at": None, "migrated_sent_fields_at": now}},
    )
    print(f"Updated {result.modified_count} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
