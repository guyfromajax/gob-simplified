#!/usr/bin/env python3
"""
FTE v2 Migration Script — adds tutorial_state machinery to existing users.

What it does:
  1. For users missing fte_v2_complete, sets fte_v2_complete=False.
  2. For users missing tutorial_state, initializes it to the team_select step.
  3. For users with at least one franchise record (any document in the
     franchises collection where user_id matches their _id), sets
     fte_v2_complete=True (grandfathering — they will NOT see the new
     tutorial on next login).

Safety guarantees (all enforced by this script):
  - DEFAULT IS DRY-RUN. Pass --apply to actually write.
  - DEFAULT TARGET IS STAGING (gob-staging). Pass --db production to switch.
  - PRODUCTION WRITES require an additional --confirm-production-write flag.
  - IDEMPOTENT. Re-running has no destructive effect:
      * Step 1 / 2 use narrow queries that only match users missing the field.
      * A user mid-tutorial (has tutorial_state set, even partially) is not
        touched by Step 1 — their progress is preserved.
      * Step 3 unconditionally sets fte_v2_complete=True for franchise owners;
        same-value writes are a no-op.
  - NEVER UNSETS OR DELETES anything. Only $set operations on the two new
    fields. Existing fields (fte, username, account_settings, etc.) are not
    touched.

Usage:
  # Default: dry-run against staging (safe to run anytime — no writes)
  python scripts/migrate_fte_v2.py

  # Apply against staging
  python scripts/migrate_fte_v2.py --apply

  # Dry-run against production
  python scripts/migrate_fte_v2.py --db production

  # Apply against production (requires explicit confirmation)
  python scripts/migrate_fte_v2.py --apply --db production --confirm-production-write
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bson import ObjectId
from scripts.db_migration_cli import connect_migration_target


DB_NAME_STAGING = "gob-staging"
DB_NAME_PRODUCTION = "gob"


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the database. Without this flag, runs in dry-run mode (default).",
    )
    p.add_argument(
        "--db",
        choices=["staging", "production"],
        default="staging",
        help="Which database to target. Defaults to staging.",
    )
    p.add_argument(
        "--confirm-production-write",
        action="store_true",
        help="Required confirmation when --apply is used with --db production.",
    )
    return p.parse_args()


def get_mongo_client():
    raise RuntimeError("Use connect_migration_target with an explicit target")


def get_db_name(target: str) -> str:
    return DB_NAME_PRODUCTION if target == "production" else DB_NAME_STAGING


def _initial_tutorial_state(now: datetime) -> dict:
    return {
        "step": "team_select",
        "team_pick": None,
        "started_at": now,
        "completed_at": None,
    }


def step1_set_fte_v2_complete_false(users_collection, dry_run: bool) -> int:
    """Set fte_v2_complete=False for any user missing the field."""
    query = {"fte_v2_complete": {"$exists": False}}
    candidates = users_collection.count_documents(query)
    total_users = users_collection.count_documents({})
    print("Step 1: Set fte_v2_complete=False for users missing the field")
    print(f"  Total users:                          {total_users}")
    print(f"  Users missing fte_v2_complete:        {candidates}")
    if dry_run:
        print("  [DRY-RUN] Would set fte_v2_complete=False on those users.")
        return 0
    result = users_collection.update_many(query, {"$set": {"fte_v2_complete": False}})
    print(f"  Matched:  {result.matched_count}")
    print(f"  Modified: {result.modified_count}")
    return result.modified_count


def step2_initialize_tutorial_state(users_collection, dry_run: bool, now: datetime) -> int:
    """Initialize tutorial_state for any user missing it. Users mid-tutorial are skipped."""
    query = {"tutorial_state": {"$exists": False}}
    candidates = users_collection.count_documents(query)
    print("Step 2: Initialize tutorial_state for users missing the field")
    print(f"  Users missing tutorial_state:         {candidates}")
    if dry_run:
        print("  [DRY-RUN] Would set tutorial_state = {step: team_select, ...} on those users.")
        return 0
    result = users_collection.update_many(
        query,
        {"$set": {"tutorial_state": _initial_tutorial_state(now)}},
    )
    print(f"  Matched:  {result.matched_count}")
    print(f"  Modified: {result.modified_count}")
    return result.modified_count


def step3_grandfather_franchise_owners(users_collection, franchises_collection, dry_run: bool) -> int:
    """Set fte_v2_complete=True for users who own at least one franchise."""
    owner_ids_raw = list(franchises_collection.distinct("user_id"))
    object_ids = []
    for oid in owner_ids_raw:
        if oid is None:
            continue
        try:
            object_ids.append(ObjectId(str(oid)))
        except Exception:
            continue

    print("Step 3: Grandfather franchise owners (set fte_v2_complete=True)")
    print(f"  Distinct franchise owner user_ids:    {len(object_ids)}")

    if not object_ids:
        print("  No franchise owners found. Nothing to do.")
        return 0

    query = {"_id": {"$in": object_ids}}
    matching_users = users_collection.count_documents(query)
    print(f"  Matching user docs:                   {matching_users}")

    if dry_run:
        print("  [DRY-RUN] Would set fte_v2_complete=True on those users.")
        return 0

    result = users_collection.update_many(query, {"$set": {"fte_v2_complete": True}})
    print(f"  Matched:  {result.matched_count}")
    print(f"  Modified: {result.modified_count}")
    return result.modified_count


def print_summary(users_collection):
    total = users_collection.count_documents({})
    with_field = users_collection.count_documents({"fte_v2_complete": {"$exists": True}})
    grandfathered = users_collection.count_documents({"fte_v2_complete": True})
    will_see_tutorial = users_collection.count_documents({"fte_v2_complete": False})
    legacy = users_collection.count_documents({"fte_v2_complete": {"$exists": False}})
    with_tutorial_state = users_collection.count_documents({"tutorial_state": {"$exists": True}})
    print("Summary after run:")
    print(f"  Total users:                          {total}")
    print(f"  Have fte_v2_complete field:           {with_field}")
    print(f"    fte_v2_complete = True (grandfath): {grandfathered}")
    print(f"    fte_v2_complete = False (will see): {will_see_tutorial}")
    print(f"    Still missing field (anomaly):      {legacy}")
    print(f"  Have tutorial_state field:            {with_tutorial_state}")


def main():
    args = parse_args()
    dry_run = not args.apply
    db_name = get_db_name(args.db)

    if args.apply and args.db == "production" and not args.confirm_production_write:
        print(
            "ERROR: Refusing to write to production without --confirm-production-write.",
            file=sys.stderr,
        )
        sys.exit(2)

    mode = "DRY-RUN" if dry_run else "APPLY"
    print("=" * 60)
    print(f"  FTE v2 Migration — Mode: {mode} — Database: {db_name}")
    print("=" * 60)
    print()

    connection = connect_migration_target(args.db, write=args.apply)
    db = connection.database
    users = db["users"]
    franchises = db["franchises"]

    now = datetime.now(timezone.utc)

    step1_set_fte_v2_complete_false(users, dry_run)
    print()
    step2_initialize_tutorial_state(users, dry_run, now)
    print()
    step3_grandfather_franchise_owners(users, franchises, dry_run)
    print()
    print_summary(users)
    print()
    if dry_run:
        print("Done (dry-run). Re-run with --apply to actually write.")
    else:
        print(f"Done. Wrote to: {db_name}")


if __name__ == "__main__":
    main()
