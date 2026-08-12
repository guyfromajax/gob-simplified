#!/usr/bin/env python3
"""Set one existing user's role to admin on one explicit database target.

Dry-run is the default. Staging uses repo-root ``.env.local``. Production requires
process configuration and matching ``GOB_DB_ACCESS`` authorization.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import ScriptDatabaseError, connect_script_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="Persist role=admin.")
    args = parser.parse_args()
    email = args.email.strip().lower()
    connection = connect_script_database(
        target=args.db,
        access="write" if args.apply else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    try:
        users = connection.database["users"]
        user = users.find_one({"email": email}, {"_id": 1, "email": 1, "role": 1})
        if not user:
            print(f"No user found with email {email!r} in {args.db}.", file=sys.stderr)
            return 1
        print(f"[PLAN] {args.db} user_id={user['_id']} role={user.get('role')!r} -> 'admin'")
        if not args.apply:
            print("[DRY RUN] No data changed.")
            return 0
        result = users.update_one(
            {"_id": user["_id"], "email": email},
            {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}},
        )
        if result.matched_count != 1:
            raise RuntimeError("User changed between preview and update")
        print(f"[DONE] role=admin set for user_id={user['_id']} in {args.db}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
