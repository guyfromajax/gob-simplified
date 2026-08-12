#!/usr/bin/env python3
"""
Reset FTE v2 status for every user → force everyone through the tutorial.

Context (Coach):
  We're removing the "grandfathering" introduced by migrate_fte_v2.py (which
  set fte_v2_complete=True for franchise owners so they'd skip the new
  tutorial). Going forward we want every user to walk the FTE v2 funnel,
  including users who already completed it. There is no DB flag
  distinguishing originally-grandfathered users from users who actually
  completed the tutorial, so this script targets ALL users.

What it does (when --apply):
  For every user document:
    - fte_v2_complete                  → False
    - tutorial_state.step              → "persona_intro"
    - tutorial_state.team_pick         → None
    - tutorial_state.completed_at      → None
  Leaves tutorial_state.started_at intact (preserves the user's original
  signup timestamp; their first-time experience already happened, this is
  a re-tour).

Side effects to know about (already flagged in the PR description):
  - Every user gets force-routed into the tutorial on next page load
    (authBarInit.routeToTutorial fires whenever fte_v2_complete === false).
  - Franchises / tournaments / past data are untouched — full access
    restored once the user completes the tutorial.
  - Idempotent: re-running just sets the same values; no destructive
    history-loss.

Safety guarantees (same as migrate_fte_v2.py):
  - DEFAULT IS DRY-RUN. Pass --apply to actually write.
  - DEFAULT TARGET IS STAGING (gob-staging). Pass --db production to switch.
  - PRODUCTION WRITES require an additional --confirm-production-write flag.
  - NEVER UNSETS OR DELETES anything; only $set on the four fields above.

Usage:
  python scripts/reset_fte_v2_for_all.py                                                  # dry-run, staging
  python scripts/reset_fte_v2_for_all.py --apply                                          # apply, staging
  python scripts/reset_fte_v2_for_all.py --db production                                  # dry-run, production
  python scripts/reset_fte_v2_for_all.py --apply --db production --confirm-production-write
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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


# The set of fields we'll overwrite on every user. Intentionally narrow —
# we don't touch usernames, account settings, franchises, etc.
RESET_FIELDS = {
    "fte_v2_complete": False,
    "tutorial_state.step": "persona_intro",
    "tutorial_state.team_pick": None,
    "tutorial_state.completed_at": None,
}


def print_pre_summary(users):
    total = users.count_documents({})
    completed = users.count_documents({"fte_v2_complete": True})
    incomplete = users.count_documents({"fte_v2_complete": False})
    missing = users.count_documents({"fte_v2_complete": {"$exists": False}})
    step_persona = users.count_documents({"tutorial_state.step": "persona_intro"})
    step_team_select = users.count_documents({"tutorial_state.step": "team_select"})
    print("Before:")
    print(f"  Total users:                          {total}")
    print(f"  fte_v2_complete = True:               {completed}")
    print(f"  fte_v2_complete = False:              {incomplete}")
    print(f"  fte_v2_complete missing (anomaly):    {missing}")
    print(f"  tutorial_state.step = persona_intro:  {step_persona}")
    print(f"  tutorial_state.step = team_select:    {step_team_select}")


def apply_reset(users, dry_run: bool):
    if dry_run:
        print("[DRY-RUN] Would set on EVERY user:")
        for k, v in RESET_FIELDS.items():
            print(f"            {k} = {v!r}")
        return 0
    result = users.update_many({}, {"$set": RESET_FIELDS})
    print(f"Matched:  {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    return result.modified_count


def print_post_summary(users):
    total = users.count_documents({})
    completed = users.count_documents({"fte_v2_complete": True})
    step_persona = users.count_documents({"tutorial_state.step": "persona_intro"})
    print("After:")
    print(f"  Total users:                          {total}")
    print(f"  fte_v2_complete = True:               {completed}  (should be 0)")
    print(f"  tutorial_state.step = persona_intro:  {step_persona}  (should equal total)")


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
    print(f"  Reset FTE v2 status for all users — Mode: {mode} — Database: {db_name}")
    print("=" * 64)
    print()

    connection = connect_migration_target(args.db, write=args.apply)
    db = connection.database
    users = db["users"]

    print_pre_summary(users)
    print()
    apply_reset(users, dry_run)
    print()

    if not dry_run:
        print_post_summary(users)
        print()
        print("Done.")
    else:
        print("Done (dry-run). Re-run with --apply to actually write.")


if __name__ == "__main__":
    main()
