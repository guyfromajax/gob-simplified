#!/usr/bin/env python3
"""Delete every staging tournament; this command cannot target production.

Dry-run is the default. Pass ``--yes`` to open a destructive staging write connection
and perform the deletion.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import STAGING_DB, ScriptDatabaseError, connect_script_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Perform the deletion.")
    args = parser.parse_args()
    connection = connect_script_database(
        target=STAGING_DB,
        access="write" if args.yes else "read",
        destructive=args.yes,
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    try:
        collection = connection.database["tournaments"]
        count = collection.count_documents({})
        print(f"[PLAN] delete {count} document(s) from {STAGING_DB}.tournaments")
        if not args.yes:
            print("[DRY RUN] No staging data changed.")
            return 0
        result = collection.delete_many({})
        print(f"[DONE] deleted={result.deleted_count}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
