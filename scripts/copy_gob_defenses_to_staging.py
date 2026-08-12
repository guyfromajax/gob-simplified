#!/usr/bin/env python3
"""Replace staging defenses with an exact, verified copy of production defenses.

Production is read-only and requires process-level ``GOB_DB_ACCESS=read``. Staging
resolves independently from repo-root ``.env.local``. Dry-run is the default.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)

COLLECTION = "defenses"
TEMP_COLLECTION = "defenses__copy_from_gob_tmp"


def _docs_by_id(collection) -> dict[Any, dict[str, Any]]:
    return {doc["_id"]: doc for doc in collection.find({})}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Replace staging defenses.")
    args = parser.parse_args()
    pristine = dict(os.environ)
    source = connect_script_database(
        target=PRODUCTION_DB, access="read", pristine_env=pristine, repo_root=ROOT
    )
    target = connect_script_database(
        target=STAGING_DB,
        access="write" if args.execute else "read",
        destructive=args.execute,
        pristine_env=pristine,
        repo_root=ROOT,
        force_local_staging=True,
    )
    try:
        source_docs = list(source.database[COLLECTION].find({}))
        if not source_docs:
            raise ScriptDatabaseError(f"Refusing to copy empty {PRODUCTION_DB}.{COLLECTION}")
        before = target.database[COLLECTION].count_documents({})
        print(f"[PLAN] production={len(source_docs)} docs; staging={before} docs")
        if not args.execute:
            print("[DRY RUN] No staging data changed.")
            return 0

        temp = target.database[TEMP_COLLECTION]
        temp.drop()
        try:
            temp.insert_many(source_docs, ordered=True)
            expected = {doc["_id"]: doc for doc in source_docs}
            if _docs_by_id(temp) != expected:
                raise RuntimeError("Temporary defenses verification failed")
            temp.rename(COLLECTION, dropTarget=True)
            if _docs_by_id(target.database[COLLECTION]) != expected:
                raise RuntimeError("Post-rename defenses verification failed")
        except Exception:
            if TEMP_COLLECTION in target.database.list_collection_names():
                temp.drop()
            raise
        print(f"[DONE] copied and verified {len(source_docs)} defense documents")
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
