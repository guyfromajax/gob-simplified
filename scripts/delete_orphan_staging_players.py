#!/usr/bin/env python3
"""Delete staging players not referenced by any staging team's ``player_ids``.

Dry-run is the default; pass ``--yes`` to delete the computed IDs.
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
    parser.add_argument("--yes", action="store_true", help="Delete computed orphans.")
    args = parser.parse_args()
    connection = connect_script_database(
        target=STAGING_DB,
        access="write" if args.yes else "read",
        destructive=args.yes,
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    try:
        referenced = {
            str(player_id)
            for team in connection.database["teams"].find({}, {"player_ids": 1})
            for player_id in (team.get("player_ids") or [])
        }
        orphan_ids = [
            player["_id"]
            for player in connection.database["players"].find({}, {"_id": 1})
            if str(player["_id"]) not in referenced
        ]
        print(f"[PLAN] referenced={len(referenced)} orphan_players={len(orphan_ids)}")
        if not args.yes:
            print("[DRY RUN] No staging data changed.")
            return 0
        result = connection.database["players"].delete_many({"_id": {"$in": orphan_ids}})
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
