#!/usr/bin/env python3
"""Provision or tear down the league-convergence scratch database.

Reads reference collections from production and writes only the explicitly named
``gob-s11-league-convergence`` scratch database. Production requires process-level
``GOB_DB_ACCESS=read``. Destructive scratch operations require its exact name through
``--confirm-db``.
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
    ScriptDatabaseError,
    connect_production_cluster_scratch_database,
    connect_script_database,
)

SCRATCH_DB = "gob-s11-league-convergence"
REFERENCE = (
    "players", "teams", "plays", "defenses", "fcp_skeletons",
    "hct_skeletons", "recruit_sets",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drop", action="store_true", help="Drop the scratch DB entirely.")
    parser.add_argument("--force-reclone", action="store_true", help="Replace populated scratch collections.")
    parser.add_argument("--confirm-db", help=f"Required as '--confirm-db {SCRATCH_DB}' for destructive actions.")
    args = parser.parse_args()
    pristine = dict(os.environ)
    destructive = args.drop or args.force_reclone
    scratch = connect_production_cluster_scratch_database(
        target=SCRATCH_DB,
        access="write",
        destructive=destructive,
        confirm_db=args.confirm_db,
        pristine_env=pristine,
    )
    source = None
    try:
        if args.drop:
            scratch.client.drop_database(SCRATCH_DB)
            print(f"[DONE] dropped {SCRATCH_DB}")
            return 0

        source = connect_script_database(
            target=PRODUCTION_DB,
            access="read",
            pristine_env=pristine,
            repo_root=ROOT,
        )
        for name in REFERENCE:
            source_count = source.database[name].count_documents({})
            target_count = scratch.database[name].count_documents({})
            if not source_count:
                raise ScriptDatabaseError(f"Refusing to clone empty production collection {name}")
            if target_count and not args.force_reclone:
                print(f"[SKIP] {name}: scratch={target_count}, production={source_count}")
                continue
            docs = list(source.database[name].find({}))
            if target_count:
                scratch.database[name].delete_many({})
            scratch.database[name].insert_many(docs, ordered=True)
            final_count = scratch.database[name].count_documents({})
            if final_count != source_count:
                raise RuntimeError(
                    f"Count verification failed for {name}: expected={source_count} actual={final_count}"
                )
            print(f"[DONE] {name}: cloned={final_count}")
        return 0
    finally:
        if source is not None:
            source.close()
        scratch.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        raise SystemExit(2)
