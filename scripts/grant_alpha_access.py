#!/usr/bin/env python3
"""Grant a pool alpha access code to one or more emails, or list pending requests.

Dry-run by default. --apply claims a pool code, sends the welcome email, and
marks the queue document granted.

Usage:
    PYTHONPATH=. venv/bin/python scripts/grant_alpha_access.py --db gob-staging --list-pending
    PYTHONPATH=. venv/bin/python scripts/grant_alpha_access.py --db gob-staging --email a@x.com
    PYTHONPATH=. venv/bin/python scripts/grant_alpha_access.py --db gob-staging --email a@x.com --apply --granted-by jamie
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.utils.alpha_access_email import send_alpha_welcome_email
from BackEnd.utils.alpha_otp_service import (
    claim_otp_for_email,
    count_available_otps,
    release_otp_claim,
)
from scripts.db_migration_cli import connect_migration_target


def _list_pending(database) -> int:
    requests = database["alpha_access_requests"]
    docs = list(requests.find({"status": "pending"}).sort("first_requested_at", 1))
    print(f"Pending requests: {len(docs)}")
    for doc in docs:
        print(
            f"  {doc.get('email')}  source={doc.get('source')!r}  "
            f"request_count={doc.get('request_count')}  "
            f"first={doc.get('first_requested_at')}  last={doc.get('last_requested_at')}"
        )
    return 0


def _grant_one(*, database, email: str, granted_by: str, apply: bool) -> bool:
    otps = database["alpha_otps"]
    requests = database["alpha_access_requests"]
    existing = requests.find_one({"email": email})
    if existing and existing.get("status") == "registered":
        print(f"SKIP {email}: already registered")
        return False
    if existing and existing.get("status") == "granted" and existing.get("otp_code"):
        print(f"SKIP {email}: already granted code {existing.get('otp_code')}")
        return False

    available = count_available_otps(otps)
    print(f"[PLAN] {email}: claim 1 pool code (available={available}) granted_by={granted_by}")
    if not apply:
        return True
    if available < 1:
        print(f"FAIL {email}: no pool codes available", file=sys.stderr)
        return False

    otp_code = claim_otp_for_email(email, collection=otps)
    if not otp_code:
        print(f"FAIL {email}: pool empty at claim time", file=sys.stderr)
        return False

    sent = send_alpha_welcome_email(email, otp_code)
    if not sent:
        release_otp_claim(otp_code, collection=otps)
        print(f"FAIL {email}: welcome email failed; code released", file=sys.stderr)
        return False

    now = datetime.now(timezone.utc)
    update = {
        "$set": {
            "status": "granted",
            "otp_code": otp_code,
            "granted_at": now,
            "granted_by": granted_by,
        },
        "$setOnInsert": {
            "email": email,
            "first_requested_at": now,
            "last_requested_at": now,
            "request_count": 1,
            "source": "manual",
        },
    }
    requests.update_one({"email": email}, update, upsert=True)
    print(f"GRANTED {email} code={otp_code}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob", "gob-staging"])
    parser.add_argument("--email", action="append", default=[], help="Repeatable. Email to grant.")
    parser.add_argument("--granted-by", default="jamie")
    parser.add_argument("--list-pending", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write and send (default: dry-run)")
    args = parser.parse_args()

    if args.list_pending:
        connection = connect_migration_target(args.db, write=False)
        try:
            return _list_pending(connection.database)
        finally:
            connection.close()

    emails = [email.strip().lower() for email in args.email if email and email.strip()]
    if not emails:
        print("Provide --email at least once, or use --list-pending.", file=sys.stderr)
        return 2

    connection = connect_migration_target(args.db, write=args.apply)
    try:
        if not args.apply:
            print(f"[DRY RUN] {args.db} pool available={count_available_otps(connection.database['alpha_otps'])}")
        ok = True
        for email in emails:
            if not _grant_one(
                database=connection.database,
                email=email,
                granted_by=args.granted_by,
                apply=args.apply,
            ):
                ok = False
        if not args.apply:
            print("[DRY RUN] No data changed.")
        return 0 if ok else 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
