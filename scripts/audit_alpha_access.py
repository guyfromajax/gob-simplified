#!/usr/bin/env python3
"""Read-only audit of alpha access collections for an explicit database.

Reports alpha_otps, access_code_requests, users-with-no-username, and a
cross-check of codes listed in _documentation_master/projects/creator_otps.md.

Usage:
    PYTHONPATH=. venv/bin/python scripts/audit_alpha_access.py --db gob
    PYTHONPATH=. venv/bin/python scripts/audit_alpha_access.py --db gob-staging
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

CREATOR_OTPS_PATH = ROOT / "_documentation_master" / "projects" / "creator_otps.md"


def _truthy_label(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return f"other:{type(value).__name__}={value!r}"


def _load_creator_otp_codes(path: Path) -> list[str]:
    if not path.exists():
        return []
    codes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("Source:") or line.startswith("Generated:"):
            continue
        codes.append(line)
    return codes


def _print_counter(title: str, counter: Counter[str], *, indent: str = "  ") -> None:
    print(f"{title}")
    if not counter:
        print(f"{indent}(none)")
        return
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        print(f"{indent}{key}: {count}")


def audit_alpha_otps(database) -> None:
    collection = database["alpha_otps"]
    total = collection.count_documents({})
    print("=" * 72)
    print("1. alpha_otps")
    print("=" * 72)
    print(f"Total documents: {total}")

    used_sent: Counter[str] = Counter()
    field_presence: Counter[str] = Counter()
    used_false_sent_false = 0
    used_ne_true_sent_ne_true = 0
    missing_used = 0
    missing_sent = 0
    missing_otp_code = 0

    for doc in collection.find({}):
        for key in doc.keys():
            field_presence[key] += 1
        used = doc.get("used", "__missing__")
        sent = doc.get("sent", "__missing__")
        if "used" not in doc:
            missing_used += 1
        if "sent" not in doc:
            missing_sent += 1
        if not doc.get("otp_code"):
            missing_otp_code += 1
        used_label = "missing" if used == "__missing__" else _truthy_label(used)
        sent_label = "missing" if sent == "__missing__" else _truthy_label(sent)
        used_sent[f"used={used_label}, sent={sent_label}"] += 1
        if used is False and sent is False:
            used_false_sent_false += 1
        if used is not True and sent is not True:
            used_ne_true_sent_ne_true += 1

    print()
    _print_counter("Counts by (used, sent):", used_sent)
    print()
    print(f"used:false AND sent:false (exact booleans): {used_false_sent_false}")
    print(f"used != true AND sent != true (includes missing): {used_ne_true_sent_ne_true}")
    print(f"Missing used field: {missing_used}")
    print(f"Missing sent field: {missing_sent}")
    print(f"Missing/empty otp_code: {missing_otp_code}")
    print()
    print("Distinct field names and document counts that have each:")
    for key, count in sorted(field_presence.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key}: {count}/{total}")


def audit_access_code_requests(database) -> None:
    requests = database["access_code_requests"]
    users = database["users"]
    total = requests.count_documents({})
    print()
    print("=" * 72)
    print("2. access_code_requests")
    print("=" * 72)
    print(f"Total documents: {total}")

    status_counts: Counter[str] = Counter()
    email_counts: Counter[str] = Counter()
    field_presence: Counter[str] = Counter()
    missing_email = 0

    for doc in requests.find({}):
        for key in doc.keys():
            field_presence[key] += 1
        status = doc.get("status")
        status_counts["missing" if status is None and "status" not in doc else str(status)] += 1
        raw_email = doc.get("email")
        if not isinstance(raw_email, str) or not raw_email.strip():
            missing_email += 1
            continue
        email_counts[raw_email.strip().lower()] += 1

    print()
    _print_counter("Counts by status:", status_counts)
    distinct_emails = len(email_counts)
    emails_with_multiple = {email: count for email, count in email_counts.items() if count > 1}
    print()
    print(f"Distinct emails: {distinct_emails}")
    print(f"Emails with >1 document: {len(emails_with_multiple)}")
    print(f"Documents with missing/empty email: {missing_email}")
    if emails_with_multiple:
        print("  Repeat counts:")
        for count in sorted(set(emails_with_multiple.values()), reverse=True):
            n = sum(1 for value in emails_with_multiple.values() if value == count)
            print(f"    {count} docs: {n} email(s)")

    registered = 0
    never_registered = 0
    for email in email_counts:
        if users.find_one({"email": email}):
            registered += 1
        else:
            never_registered += 1

    print()
    print(f"Distinct request emails with a matching users doc: {registered}")
    print(f"Distinct request emails with NO matching users doc: {never_registered}")
    print()
    print("Distinct field names and document counts that have each:")
    for key, count in sorted(field_presence.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {key}: {count}/{total}")


def audit_users_username(database) -> None:
    users = database["users"]
    total = users.count_documents({})
    missing = users.count_documents({"username": {"$exists": False}})
    # MongoDB {username: null} also matches missing fields; use $type to isolate explicit nulls.
    explicit_null = users.count_documents({"username": {"$type": "null"}})
    empty = users.count_documents({"username": ""})
    print()
    print("=" * 72)
    print("3. users (username)")
    print("=" * 72)
    print(f"Total users: {total}")
    print(f"username field missing: {missing}")
    print(f"username is explicit null: {explicit_null}")
    print(f"username is empty string: {empty}")
    print(f"username null OR missing: {missing + explicit_null}")


def audit_creator_otps_crosscheck(database, db_name: str) -> None:
    codes = _load_creator_otp_codes(CREATOR_OTPS_PATH)
    print()
    print("=" * 72)
    print("4. creator_otps.md cross-check")
    print("=" * 72)
    print(f"File: {CREATOR_OTPS_PATH}")
    print(f"Codes listed in file: {len(codes)}")
    duplicate_file_codes = len(codes) - len(set(codes))
    if duplicate_file_codes:
        print(f"WARNING: duplicate codes in file: {duplicate_file_codes}")

    collection = database["alpha_otps"]
    found = 0
    missing = 0
    state_counts: Counter[str] = Counter()
    missing_codes: list[str] = []

    for code in codes:
        doc = collection.find_one({"otp_code": code})
        if not doc:
            missing += 1
            missing_codes.append(code)
            state_counts["NOT_FOUND"] += 1
            continue
        found += 1
        used = doc.get("used", "__missing__")
        sent = doc.get("sent", "__missing__")
        used_label = "missing" if used == "__missing__" else _truthy_label(used)
        sent_label = "missing" if sent == "__missing__" else _truthy_label(sent)
        state_counts[f"used={used_label}, sent={sent_label}"] += 1

    print(f"Exist on {db_name}: {found}")
    print(f"Not found on {db_name}: {missing}")
    print()
    _print_counter(f"State of listed codes on {db_name}:", state_counts)
    if missing_codes:
        print()
        print(f"Codes listed in file but missing from {db_name}: {len(missing_codes)}")
        print("(codes omitted from this printout; re-run locally if you need the list)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob", "gob-staging"])
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=False)
    try:
        print(f"Alpha access audit (read-only): {args.db}")
        audit_alpha_otps(connection.database)
        audit_access_code_requests(connection.database)
        audit_users_username(connection.database)
        audit_creator_otps_crosscheck(connection.database, args.db)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
