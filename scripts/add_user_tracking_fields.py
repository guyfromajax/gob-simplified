#!/usr/bin/env python3
"""
Backfill the `record` and `archetypes` tracking sub-documents onto every user.

Context:
  The User Archetype System (see _documentation_master/projects/User_Archetype_System.md)
  adds per-user career tracking: a `record` block (wins / losses / total_games /
  win_rate / discount_wins / discount_losses) and an `archetypes` block (the 18
  coaching archetypes + a derived `total`). New signups are born with these
  fields; this script backfills existing user documents.

  Shape is defined ONCE in BackEnd/utils/user_tracking.py and imported here, so
  the backfill can never drift from signup defaults or the per-game commit.

Safety guarantees (same as backfill_persona_intro_step.py):
  - DEFAULT IS DRY-RUN. Pass --apply to actually write.
  - DEFAULT TARGET IS STAGING (gob-staging). Pass --db production to switch.
  - PRODUCTION WRITES require an additional --confirm-production-write flag.
  - IDEMPOTENT and NON-CLOBBERING. `record` and `archetypes` are each set only
    where the field is MISSING ($exists:false), so re-running is a no-op and a
    user who already has accumulated counts is never reset to zero.
  - NEVER UNSETS OR DELETES anything. Only $set on absent fields.

Usage:
  python scripts/add_user_tracking_fields.py                                      # dry-run, staging
  python scripts/add_user_tracking_fields.py --apply                              # apply, staging
  python scripts/add_user_tracking_fields.py --db production                      # dry-run, production
  python scripts/add_user_tracking_fields.py --apply --db production --confirm-production-write
"""

import argparse
import importlib.util
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

try:
    from dotenv import load_dotenv
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient


# Load the schema helper as a standalone leaf module (avoids dragging in the
# heavy BackEnd.utils package __init__ chain just to read default shapes).
def _load_user_tracking():
    path = os.path.join(REPO_ROOT, "BackEnd", "utils", "user_tracking.py")
    spec = importlib.util.spec_from_file_location("user_tracking", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


user_tracking = _load_user_tracking()
default_record = user_tracking.default_record
default_archetypes = user_tracking.default_archetypes


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
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("ERROR: MONGO_URI not set in environment or .env file.", file=sys.stderr)
        sys.exit(1)
    return MongoClient(mongo_uri)


def get_db_name(target: str) -> str:
    return DB_NAME_PRODUCTION if target == "production" else DB_NAME_STAGING


MISSING_RECORD = {"record": {"$exists": False}}
MISSING_ARCHETYPES = {"archetypes": {"$exists": False}}


def print_pre_summary(users):
    total = users.count_documents({})
    missing_record = users.count_documents(MISSING_RECORD)
    missing_archetypes = users.count_documents(MISSING_ARCHETYPES)
    fully_tracked = users.count_documents(
        {"record": {"$exists": True}, "archetypes": {"$exists": True}}
    )
    print("Before:")
    print(f"  Total users:               {total}")
    print(f"  Already fully tracked:     {fully_tracked}")
    print(f"  Missing `record`:          {missing_record}")
    print(f"  Missing `archetypes`:      {missing_archetypes}")
    return missing_record, missing_archetypes


def apply_backfill(users, dry_run: bool):
    if dry_run:
        print("[DRY-RUN] Would $set default `record` on users missing it.")
        print("[DRY-RUN] Would $set default `archetypes` on users missing it.")
        return
    rec = users.update_many(MISSING_RECORD, {"$set": {"record": default_record()}})
    print(f"`record`     -> Matched: {rec.matched_count}  Modified: {rec.modified_count}")
    arc = users.update_many(MISSING_ARCHETYPES, {"$set": {"archetypes": default_archetypes()}})
    print(f"`archetypes` -> Matched: {arc.matched_count}  Modified: {arc.modified_count}")


def print_post_summary(users):
    missing_record = users.count_documents(MISSING_RECORD)
    missing_archetypes = users.count_documents(MISSING_ARCHETYPES)
    print("After:")
    print(f"  Missing `record`:          {missing_record}  (should be 0)")
    print(f"  Missing `archetypes`:      {missing_archetypes}  (should be 0)")


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
    print("=" * 64)
    print(f"  Backfill user tracking fields — Mode: {mode} — Database: {db_name}")
    print("=" * 64)
    print()

    client = get_mongo_client()
    db = client[db_name]
    users = db["users"]

    missing_record, missing_archetypes = print_pre_summary(users)
    print()

    if missing_record == 0 and missing_archetypes == 0:
        print("Every user already has both tracking blocks. Nothing to do.")
        print()
        print("Done (dry-run)." if dry_run else "Done.")
        return

    apply_backfill(users, dry_run)
    print()

    if not dry_run:
        print_post_summary(users)
        print()
        print("Done.")
    else:
        print("Done (dry-run). Re-run with --apply to actually write.")


if __name__ == "__main__":
    main()
