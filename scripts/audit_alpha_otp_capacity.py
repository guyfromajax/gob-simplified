#!/usr/bin/env python3
"""Read-only count of alpha access-code capacity for an explicit database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target


def audit_alpha_otp_capacity(database) -> dict[str, int]:
    collection = database["alpha_otps"]
    total = collection.count_documents({})
    used = collection.count_documents({"used": True})
    unused = collection.count_documents({"used": {"$ne": True}})
    available = collection.count_documents(
        {"used": {"$ne": True}, "sent": {"$ne": True}}
    )
    sent_unused = collection.count_documents(
        {"used": {"$ne": True}, "sent": True}
    )
    return {
        "total": total,
        "used": used,
        "unused": unused,
        "available": available,
        "sent_unused": sent_unused,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=False)
    try:
        counts = audit_alpha_otp_capacity(connection.database)
    finally:
        connection.close()

    print(f"Alpha OTP capacity: {args.db}")
    print(f"Total documents: {counts['total']}")
    print(f"Used codes: {counts['used']}")
    print(f"Unused codes (used != true): {counts['unused']}")
    print(f"Available to issue (unused and not sent): {counts['available']}")
    print(f"Already sent but not yet redeemed: {counts['sent_unused']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
