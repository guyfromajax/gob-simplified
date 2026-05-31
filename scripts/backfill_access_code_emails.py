#!/usr/bin/env python3
"""
Backfill welcome emails for pending access_code_requests (production).

Usage:
  PYTHONPATH=. python scripts/backfill_access_code_emails.py --dry-run
  PYTHONPATH=. python scripts/backfill_access_code_emails.py --execute
  PYTHONPATH=. python scripts/backfill_access_code_emails.py --execute --db production --confirm-production-write
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
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

from pymongo import MongoClient, ReturnDocument

from BackEnd.utils.alpha_access_email import send_alpha_welcome_email

DB_NAME_STAGING = "gob-staging"
DB_NAME_PRODUCTION = "gob"
REQUESTS = "access_code_requests"
USERS = "users"
OTPS = "alpha_otps"


def _count_available(db) -> int:
    return db[OTPS].count_documents({"used": False, "sent": False})


def _claim_otp(db, email: str) -> str | None:
    now = datetime.now(timezone.utc)
    doc = db[OTPS].find_one_and_update(
        {"used": False, "sent": False},
        {"$set": {"sent": True, "sent_to_email": email, "sent_at": now}},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )
    return doc.get("otp_code") if doc else None


def _release_otp(db, otp_code: str) -> None:
    db[OTPS].update_one(
        {"otp_code": otp_code, "sent": True, "used": False},
        {"$set": {"sent": False, "sent_to_email": None, "sent_at": None}},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Print planned actions only")
    group.add_argument("--execute", action="store_true", help="Send emails and update DB")
    parser.add_argument(
        "--db",
        choices=["staging", "production"],
        default="production",
        help="Target database (default: production)",
    )
    parser.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required with --execute --db production",
    )
    return parser.parse_args()


def _dedupe_requests(docs: list[dict]) -> list[dict]:
    by_email: dict[str, list[dict]] = defaultdict(list)
    for doc in docs:
        email = (doc.get("email") or "").lower().strip()
        if email:
            by_email[email].append(doc)
    winners: list[dict] = []
    for email, rows in by_email.items():
        rows.sort(key=lambda d: d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))
        winners.append(rows[0])
    winners.sort(key=lambda d: d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))
    return winners


def main() -> int:
    args = parse_args()
    db_name = DB_NAME_STAGING if args.db == "staging" else DB_NAME_PRODUCTION
    if args.execute and args.db == "production" and not args.confirm_production_write:
        print("Refusing production execute without --confirm-production-write")
        return 1

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set")
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    requests = db[REQUESTS]
    users = db[USERS]

    pending = list(requests.find({"status": "pending"}).sort("created_at", 1))
    deduped = _dedupe_requests(pending)
    available = _count_available(db) if args.execute else None

    print(f"Target: {db_name}")
    print(f"Pending requests: {len(pending)}")
    print(f"After de-dupe (oldest per email): {len(deduped)}")
    if args.execute:
        print(f"Available OTPs: {available}")

    send_queue = 0
    for doc in deduped:
        email = doc["email"].lower().strip()
        if users.find_one({"email": email}, {"_id": 1}):
            print(f"SKIP already_registered  {email}")
            if args.execute:
                requests.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "skipped", "skip_reason": "already_registered"}},
                )
            continue

        if args.dry_run:
            send_queue += 1
            print(f"SEND  {email}  (request_id={doc['_id']})")
            continue

        if _count_available(db) == 0:
            print(f"STOP no_otp_capacity  {email}")
            break

        otp_code = _claim_otp(db, email)
        if not otp_code:
            print(f"STOP claim_failed  {email}")
            break

        sent = send_alpha_welcome_email(email, otp_code)
        now = datetime.now(timezone.utc)
        if not sent:
            _release_otp(db, otp_code)
            requests.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "otp_code": otp_code}},
            )
            print(f"FAIL send  {email}")
            continue

        requests.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "sent", "otp_code": otp_code, "sent_at": now}},
        )
        send_queue += 1
        print(f"SENT  {email}  otp={otp_code}")

    if args.dry_run:
        print(f"Would send: {send_queue}")
    else:
        print(f"Sent: {send_queue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
