#!/usr/bin/env python3
"""Delete all franchise-owned documents from staging only.

Collections: franchises, franchise_team_data, franchise_players_data, and
franchise_recruits_data. Dry-run is the default; pass ``--yes`` to execute.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import STAGING_DB, ScriptDatabaseError, connect_script_database  # noqa: E402

COLLECTIONS = (
    "franchises",
    "franchise_team_data",
    "franchise_players_data",
    "franchise_recruits_data",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Perform the deletions.")
    args = parser.parse_args()
    connection = connect_script_database(
        target=STAGING_DB,
        access="write" if args.yes else "read",
        destructive=args.yes,
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    try:
        counts = {
            name: connection.database[name].count_documents({}) for name in COLLECTIONS
        }
        for name, count in counts.items():
            print(f"[PLAN] {STAGING_DB}.{name}: delete {count}")
        if not args.yes:
            print("[DRY RUN] No staging data changed.")
            return 0
        for name in COLLECTIONS:
            result = connection.database[name].delete_many({})
            print(f"[DONE] {name}: deleted={result.deleted_count}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
