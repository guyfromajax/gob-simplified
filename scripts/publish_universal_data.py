#!/usr/bin/env python3
"""Publish explicitly selected universal collections from staging to production.

Production credentials and ``GOB_DB_ACCESS`` must be supplied by the invoking
process. Staging is independently resolved from repo-root ``.env.local``. Dry-run is
the default. An apply run requires an external backup directory and typed production
database confirmation.

Examples:
  GOB_DB_ACCESS=read ... python scripts/publish_universal_data.py --collection recruit_sets
  GOB_DB_ACCESS=write ... python scripts/publish_universal_data.py \
      --collection recruit_sets --apply --confirm-db gob --backup-dir /secure/backups

Each selected collection is backed up locally, copied into a temporary production
collection, compared exactly, and atomically renamed over the destination. Selecting
one collection never publishes another.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any

from bson import json_util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import (  # noqa: E402
    PRODUCTION_DB,
    STAGING_DB,
    ScriptDatabaseError,
    connect_script_database,
)


PUBLISHABLE_COLLECTIONS = (
    "recruit_sets",
    "teams",
    "players",
    "fcp_skeletons",
    "hct_skeletons",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection",
        action="append",
        choices=PUBLISHABLE_COLLECTIONS,
        required=True,
        dest="collections",
        help="Collection to publish; repeat for another explicit collection.",
    )
    parser.add_argument("--apply", action="store_true", help="Perform the publication.")
    parser.add_argument("--confirm-db", help="Required as '--confirm-db gob' when applying.")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Existing or creatable directory outside the repository for production backups.",
    )
    return parser.parse_args()


def _docs_by_id(collection) -> dict[Any, dict[str, Any]]:
    return {doc["_id"]: doc for doc in collection.find({})}


def _validate_backup_root(path: Path | None) -> Path:
    if path is None:
        raise ScriptDatabaseError("--backup-dir is required when --apply is used")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise ScriptDatabaseError("Production backups must be stored outside the repository")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    return resolved


def _write_backup(directory: Path, name: str, docs: list[dict[str, Any]]) -> Path:
    path = directory / f"{name}.json"
    path.write_text(json_util.dumps(docs, indent=2), encoding="utf-8")
    path.chmod(0o600)
    return path


def main() -> int:
    args = _parse_args()
    pristine_env = dict(os.environ)
    access = "write" if args.apply else "read"
    backup_run_dir: Path | None = None
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_run_dir = _validate_backup_root(args.backup_dir) / f"gob-before-publish-{stamp}"
        backup_run_dir.mkdir(mode=0o700)

    staging = connect_script_database(
        target=STAGING_DB,
        access="read",
        pristine_env=pristine_env,
        repo_root=ROOT,
        force_local_staging=True,
    )
    production = connect_script_database(
        target=PRODUCTION_DB,
        access=access,
        destructive=args.apply,
        confirm_db=args.confirm_db,
        pristine_env=pristine_env,
        repo_root=ROOT,
    )
    try:
        selected = list(dict.fromkeys(args.collections))
        plans: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
        for name in selected:
            source_docs = list(staging.database[name].find({}))
            destination_docs = list(production.database[name].find({}))
            if not source_docs:
                raise ScriptDatabaseError(
                    f"Refusing to publish empty source collection {STAGING_DB}.{name}"
                )
            plans[name] = (source_docs, destination_docs)
            print(
                f"[PLAN] {name}: {STAGING_DB}={len(source_docs)} docs -> "
                f"{PRODUCTION_DB}={len(destination_docs)} docs"
            )

        if not args.apply:
            print("[DRY RUN] No production data changed.")
            return 0

        assert backup_run_dir is not None
        for name, (source_docs, destination_docs) in plans.items():
            backup_path = _write_backup(backup_run_dir, name, destination_docs)
            print(f"[BACKUP] {name}: {backup_path}")

            temp_name = f"{name}__publish_tmp"
            temp = production.database[temp_name]
            temp.drop()
            try:
                temp.insert_many(source_docs, ordered=True)
                expected = {doc["_id"]: doc for doc in source_docs}
                if _docs_by_id(temp) != expected:
                    raise RuntimeError(f"Exact verification failed for temporary {name} copy")
                temp.rename(name, dropTarget=True)
                if _docs_by_id(production.database[name]) != expected:
                    raise RuntimeError(f"Post-rename exact verification failed for {name}")
            except Exception:
                # The destination is untouched until rename succeeds.
                if temp_name in production.database.list_collection_names():
                    temp.drop()
                raise
            print(f"[PUBLISHED] {name}: {len(source_docs)} exact documents verified")
        return 0
    finally:
        staging.close()
        production.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
