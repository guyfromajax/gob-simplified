#!/usr/bin/env python3
"""Create vanity or generated alpha access codes allocated to a creator.

Dry-run by default. Created codes have sent=true so the grant pool never
hands them out. max_uses defaults to 1.

Usage:
    PYTHONPATH=. venv/bin/python scripts/create_alpha_code.py --db gob-staging \\
        --code HOOPSGUY --allocated-to creator:hoopsguy
    PYTHONPATH=. venv/bin/python scripts/create_alpha_code.py --db gob-staging \\
        --generate 5 --allocated-to creator:hoopsguy --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target
from scripts.generate_alpha_otps import (
    build_alpha_otp_document,
    generate_otp_code,
)


MIN_CODE_LENGTH = 6


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _validate_code(code: str) -> str:
    normalized = _normalize_code(code)
    if len(normalized) < MIN_CODE_LENGTH:
        raise SystemExit(f"Code must be at least {MIN_CODE_LENGTH} characters: {code!r}")
    return normalized


def _insert_code(collection, *, code: str, allocated_to: str, max_uses: int, apply: bool) -> bool:
    now = datetime.now(timezone.utc)
    existing = collection.find_one({"otp_code": code})
    if existing:
        print(f"FAIL code already exists: {code}", file=sys.stderr)
        return False
    doc = build_alpha_otp_document(
        code,
        now=now,
        max_uses=max_uses,
        sent=True,
        allocated_to=allocated_to,
        allocated_at=now,
    )
    print(
        f"[PLAN] create {code} allocated_to={allocated_to} max_uses={max_uses} sent=true"
    )
    if not apply:
        return True
    collection.insert_one(doc)
    print(f"CREATED {code}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob", "gob-staging"])
    parser.add_argument("--code", help="Vanity code to create")
    parser.add_argument("--generate", type=int, metavar="N", help="Create N random codes")
    parser.add_argument("--allocated-to", required=True)
    parser.add_argument("--max-uses", type=int, default=1)
    parser.add_argument("--apply", action="store_true", help="Write (default: dry-run)")
    args = parser.parse_args()

    if bool(args.code) == bool(args.generate):
        print("Provide exactly one of --code or --generate N.", file=sys.stderr)
        return 2
    if args.max_uses < 1:
        print("--max-uses must be at least 1.", file=sys.stderr)
        return 2

    connection = connect_migration_target(args.db, write=args.apply)
    try:
        collection = connection.database["alpha_otps"]
        ok = True
        if args.code:
            code = _validate_code(args.code)
            ok = _insert_code(
                collection,
                code=code,
                allocated_to=args.allocated_to,
                max_uses=args.max_uses,
                apply=args.apply,
            )
        else:
            if args.generate < 1:
                print("--generate must be at least 1.", file=sys.stderr)
                return 2
            existing = {doc["otp_code"] for doc in collection.find({}, {"otp_code": 1})}
            created = []
            attempts = 0
            max_attempts = args.generate * 20
            while len(created) < args.generate and attempts < max_attempts:
                attempts += 1
                code = generate_otp_code()
                if code in existing:
                    continue
                existing.add(code)
                created.append(code)
            if len(created) < args.generate:
                print(
                    f"FAIL could only generate {len(created)} unique codes",
                    file=sys.stderr,
                )
                ok = False
            for code in created:
                if not _insert_code(
                    collection,
                    code=code,
                    allocated_to=args.allocated_to,
                    max_uses=args.max_uses,
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
