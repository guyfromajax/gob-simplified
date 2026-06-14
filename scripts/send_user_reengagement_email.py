#!/usr/bin/env python3
"""
Send a one-time re-engagement ("come back and play") email to existing users.

Suppresses: recent alpha-code recipients, unsubscribes, and anyone already sent
this campaign (idempotent re-runs).

Usage:
  PYTHONPATH=. python scripts/send_user_reengagement_email.py --dry-run
  PYTHONPATH=. python scripts/send_user_reengagement_email.py --execute --db production --confirm-production-write
  PYTHONPATH=. python scripts/send_user_reengagement_email.py --execute --limit 100   # batch under Resend free-tier cap
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv

    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass

DEFAULT_CAMPAIGN = "2026-06-revisit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Print planned actions only")
    group.add_argument("--execute", action="store_true", help="Send emails and record sends")
    parser.add_argument("--db", choices=["staging", "production"], default="production")
    parser.add_argument("--confirm-production-write", action="store_true")
    parser.add_argument("--campaign", default=DEFAULT_CAMPAIGN, help="Campaign id (suppression key)")
    parser.add_argument("--recent-days", type=int, default=7, help="Suppress alpha sends within N days")
    parser.add_argument("--limit", type=int, default=0, help="Max sends this run (0 = no limit)")
    parser.add_argument(
        "--only",
        default="",
        help="Restrict to a single exact email (for test sends); still respects suppression",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.execute and args.db == "production" and not args.confirm_production_write:
        print("Refusing production execute without --confirm-production-write")
        return 1

    # The DB name is selected here and exported BEFORE importing BackEnd.db so the
    # suppression/email helpers resolve to the intended database.
    os.environ["MONGO_DB_NAME"] = "gob-staging" if args.db == "staging" else "gob"
    if not os.environ.get("MONGO_URI"):
        print("MONGO_URI not set")
        return 1

    from BackEnd.db import db
    from BackEnd.utils.email_suppression import (
        campaign_sent_email_set,
        normalize_email,
        recent_alpha_send_email_set,
        record_campaign_send,
        unsubscribed_email_set,
    )
    from BackEnd.utils.reengagement_email import send_reengagement_email, _mailing_address

    users = db["users"]
    all_emails = sorted({normalize_email(u.get("email", "")) for u in users.find({}, {"email": 1}) if u.get("email")})

    suppress_recent = recent_alpha_send_email_set(days=args.recent_days)
    suppress_unsub = unsubscribed_email_set()
    suppress_campaign = campaign_sent_email_set(args.campaign)

    recipients = [
        e for e in all_emails
        if e not in suppress_recent and e not in suppress_unsub and e not in suppress_campaign
    ]

    if args.only:
        only = normalize_email(args.only)
        if only not in all_emails:
            print(f"--only {only}: not an existing user with email; nothing to send")
            return 1
        if only not in recipients:
            print(f"--only {only}: suppressed (recent alpha / unsubscribed / already sent); nothing to send")
            return 0
        recipients = [only]
        print(f"--only filter: restricting to {only}")

    print(f"Target: {os.environ['MONGO_DB_NAME']}  campaign={args.campaign}")
    print(f"Users with email: {len(all_emails)}")
    print(f"Suppressed — recent alpha ({args.recent_days}d): {len(suppress_recent & set(all_emails))}"
          f" | unsubscribed: {len(suppress_unsub & set(all_emails))}"
          f" | already sent campaign: {len(suppress_campaign & set(all_emails))}")
    print(f"Eligible recipients: {len(recipients)}")

    if args.execute and not _mailing_address().strip():
        print("Refusing execute: no mailing address configured (CAN-SPAM requires a physical address)")
        return 1

    if args.limit and len(recipients) > args.limit:
        print(f"NOTE: limiting to {args.limit} of {len(recipients)} this run ({len(recipients) - args.limit} deferred)")
        recipients = recipients[: args.limit]

    sent = 0
    for email in recipients:
        if args.dry_run:
            print(f"SEND  {email}")
            sent += 1
            continue
        ok = send_reengagement_email(email)
        if ok:
            record_campaign_send(email, args.campaign)
            sent += 1
            print(f"SENT  {email}")
        else:
            print(f"FAIL  {email}")

    print(f"{'Would send' if args.dry_run else 'Sent'}: {sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
