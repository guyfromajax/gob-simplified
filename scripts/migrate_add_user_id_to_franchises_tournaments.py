#!/usr/bin/env python3
"""
Migration: Add user_id to franchises and tournaments that lack it.

Documents without user_id are now denied access (403). This script backfills
user_id so existing data remains accessible.

USAGE:
    # Dry run - show what would be updated
    python scripts/migrate_add_user_id_to_franchises_tournaments.py

    # Assign all orphan docs to a specific user
    python scripts/migrate_add_user_id_to_franchises_tournaments.py --user-id <user_object_id> --execute

    # Use first user in DB as fallback (for single-user staging)
    python scripts/migrate_add_user_id_to_franchises_tournaments.py --use-first-user --execute

NOTE: For documents we cannot associate with a user, they remain inaccessible.
Use --user-id to assign all orphans to one user (e.g. staging admin).
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import (
    client,
    DB_NAME,
    franchises_collection,
    tournaments_collection,
    users_collection,
)


def migrate(dry_run: bool = True, user_id: str | None = None, use_first_user: bool = False):
    db = client[DB_NAME]

    if not user_id and use_first_user:
        first_user = users_collection.find_one({}, {"_id": 1})
        if first_user:
            user_id = str(first_user["_id"])
            print(f"Using first user in DB: {user_id}")
        else:
            print("No users found. Cannot use --use-first-user.")
            return

    if not user_id:
        print("Provide --user-id or --use-first-user")
        return

    print("=" * 80)
    print("MIGRATION: Add user_id to franchises and tournaments")
    print("=" * 80)
    print(f"Database: {DB_NAME}")
    print(f"Target user_id: {user_id}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE'}")
    print("=" * 80)

    # Franchises without user_id (missing or null)
    franchise_query = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]}
    franchise_count = franchises_collection.count_documents(franchise_query)
    print(f"\nFranchises missing user_id: {franchise_count}")

    # Tournaments without user_id (missing or null)
    tournament_query = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]}
    tournament_count = tournaments_collection.count_documents(tournament_query)
    print(f"Tournaments missing user_id: {tournament_count}")

    if franchise_count == 0 and tournament_count == 0:
        print("\nNothing to migrate.")
        return

    if not dry_run:
        if franchise_count > 0:
            result = franchises_collection.update_many(
                franchise_query, {"$set": {"user_id": user_id}}
            )
            print(f"\nUpdated {result.modified_count} franchises")
        if tournament_count > 0:
            result = tournaments_collection.update_many(
                tournament_query, {"$set": {"user_id": user_id}}
            )
            print(f"Updated {result.modified_count} tournaments")
    else:
        print("\n[DRY RUN] No changes made. Use --execute to apply.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Apply migration")
    parser.add_argument("--user-id", type=str, help="User ObjectId to assign to orphan docs")
    parser.add_argument(
        "--use-first-user",
        action="store_true",
        help="Use first user in users collection (for single-user staging)",
    )
    args = parser.parse_args()

    if args.execute and not args.user_id and not args.use_first_user:
        print("Error: --execute requires --user-id or --use-first-user")
        sys.exit(1)

    try:
        migrate(
            dry_run=not args.execute,
            user_id=args.user_id,
            use_first_user=args.use_first_user,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
