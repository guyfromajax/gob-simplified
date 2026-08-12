#!/usr/bin/env python3
"""Additively upsert production teams into staging without deleting staging-only data.

Production is read-only and comes from process configuration with
``GOB_DB_ACCESS=read``. Staging resolves independently from repo-root ``.env.local``.
Dry-run is the default; pass ``--execute`` for staging writes.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform staging upserts.")
    args = parser.parse_args()
    pristine = dict(os.environ)

    source = connect_script_database(
        target=PRODUCTION_DB, access="read", pristine_env=pristine, repo_root=ROOT
    )
    target = connect_script_database(
        target=STAGING_DB,
        access="write" if args.execute else "read",
        pristine_env=pristine,
        repo_root=ROOT,
        force_local_staging=True,
    )
    try:
        docs = list(source.database["teams"].find({}))
        before = target.database["teams"].count_documents({})
        print(f"[PLAN] production teams={len(docs)}; staging teams={before}; deletes=0")
        if not args.execute:
            print("[DRY RUN] No staging data changed.")
            return 0

        upserted = matched = 0
        for doc in docs:
            player_id = doc.get("_id")
            if player_id is None:
                continue
            result = target.database["teams"].replace_one(
                {"_id": player_id}, doc, upsert=True
            )
            upserted += int(result.upserted_id is not None)
            matched += int(result.matched_count > 0)
        print(
            f"[DONE] upserted={upserted} updated={matched} "
            f"staging_total={target.database['teams'].count_documents({})}"
        )
        return 0
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
