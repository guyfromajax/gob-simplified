#!/usr/bin/env python3
"""Maintain and additively publish canonical defense catalog definitions.

Documents are keyed by stable ``defense_id``. Definition fields are synchronized;
``game_stats`` and ``season_stats`` are initialized for new documents but preserved on
existing production documents. Missing baseline fields can also be repaired on one
explicit target without changing existing values. Dry-run is the default.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import PRODUCTION_DB, STAGING_DB, ScriptDatabaseError, connect_script_database
from scripts.publish_universal_data import _validate_backup_root, _write_backup

PRESERVED_COUNTER_FIELDS = ("game_stats", "season_stats")
BASELINE_DEFAULTS = {"effectiveness": 0, "momentum": 0, "cloaking": 0}


def _by_defense_id(docs: list[dict[str, Any]], *, source: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for doc in docs:
        defense_id = str(doc.get("defense_id") or "").strip()
        if not defense_id:
            raise ScriptDatabaseError(f"{source} contains a defense without defense_id")
        if defense_id in result:
            raise ScriptDatabaseError(f"{source} contains duplicate defense_id {defense_id!r}")
        result[defense_id] = doc
    return result


def _definition_fields(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in doc.items()
        if key not in {"_id", *PRESERVED_COUNTER_FIELDS}
    }


def publish_definitions(source_collection, destination_collection, *, apply: bool) -> dict[str, int]:
    source_docs = list(source_collection.find({}))
    if not source_docs:
        raise ScriptDatabaseError("Refusing to publish an empty staging defenses collection")
    source = _by_defense_id(source_docs, source="staging defenses")
    destination = _by_defense_id(list(destination_collection.find({})), source="production defenses")
    counts = {"insert": 0, "update": 0, "unchanged": 0}

    for defense_id, source_doc in sorted(source.items()):
        existing = destination.get(defense_id)
        definitions = _definition_fields(source_doc)
        if existing is None:
            counts["insert"] += 1
        elif all(existing.get(key) == value for key, value in definitions.items()):
            counts["unchanged"] += 1
        else:
            counts["update"] += 1

        if not apply:
            continue
        set_on_insert = {
            key: source_doc.get(key, {}) for key in PRESERVED_COUNTER_FIELDS
        }
        destination_collection.update_one(
            {"defense_id": defense_id},
            {"$set": definitions, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    return counts


def repair_missing_baselines(collection, *, apply: bool) -> dict[str, int]:
    """Add only absent catalog baselines; never overwrite an existing value."""
    counts = {field: 0 for field in BASELINE_DEFAULTS}
    counts["documents"] = 0
    for doc in collection.find({}, {field: 1 for field in BASELINE_DEFAULTS}):
        missing = {
            field: default
            for field, default in BASELINE_DEFAULTS.items()
            if field not in doc
        }
        if not missing:
            continue
        counts["documents"] += 1
        for field in missing:
            counts[field] += 1
        if apply:
            collection.update_one({"_id": doc["_id"]}, {"$set": missing})
    return counts


def _backup_collection(connection, backup_dir: Path | None, *, label: str) -> Path:
    backup_root = _validate_backup_root(backup_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = backup_root / f"{connection.target}-before-{label}-{stamp}"
    run_dir.mkdir(mode=0o700)
    return _write_backup(run_dir, "defenses", list(connection.database["defenses"].find({})))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"], help="Explicit target")
    parser.add_argument(
        "--repair-missing-baselines",
        action="store_true",
        help="Backfill only absent effectiveness/momentum/cloaking fields on --db",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-db")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()

    pristine = dict(os.environ)
    if args.repair_missing_baselines:
        target = connect_script_database(
            target=args.db,
            access="write" if args.apply else "read",
            destructive=args.apply and args.db == PRODUCTION_DB,
            confirm_db=args.confirm_db,
            pristine_env=pristine,
            repo_root=ROOT,
        )
        try:
            if args.apply:
                backup = _backup_collection(target, args.backup_dir, label="defense-baseline-repair")
                print(f"[BACKUP] defenses: {backup}")
            counts = repair_missing_baselines(target.database["defenses"], apply=args.apply)
            mode = "REPAIRED" if args.apply else "DRY RUN"
            print(
                f"[{mode}] documents={counts['documents']} effectiveness={counts['effectiveness']} "
                f"momentum={counts['momentum']} cloaking={counts['cloaking']}"
            )
            return 0
        finally:
            target.close()

    if args.db != PRODUCTION_DB:
        raise ScriptDatabaseError(
            "Publishing copies staging to production; use --db gob, or select "
            "--repair-missing-baselines for a one-target repair"
        )
    staging = connect_script_database(
        target=STAGING_DB, access="read", pristine_env=pristine,
        repo_root=ROOT, force_local_staging=True,
    )
    production = connect_script_database(
        target=PRODUCTION_DB, access="write" if args.apply else "read",
        destructive=args.apply, confirm_db=args.confirm_db,
        pristine_env=pristine, repo_root=ROOT,
    )
    try:
        if args.apply:
            backup = _backup_collection(production, args.backup_dir, label="defense-publish")
            print(f"[BACKUP] defenses: {backup}")

        counts = publish_definitions(
            staging.database["defenses"], production.database["defenses"], apply=args.apply
        )
        mode = "PUBLISHED" if args.apply else "DRY RUN"
        print(f"[{mode}] insert={counts['insert']} update={counts['update']} unchanged={counts['unchanged']}")
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
