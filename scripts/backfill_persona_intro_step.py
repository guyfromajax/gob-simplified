#!/usr/bin/env python3
"""
Backfill the persona_intro step onto non-grandfathered tutorial users.

Context:
  The original FTE v2 migration (2026-05-27, scripts/migrate_fte_v2.py)
  initialized every non-franchise user with tutorial_state.step = "team_select".
  On 2026-05-29 we prepended a new screen, persona_intro, to the funnel.
  New signups after that date default to step="persona_intro" at signup,
  but the users already migrated to "team_select" never saw the new screen
  on their next login — routeToTutorial sent them straight to team-select.

  This script bumps those still-at-the-starting-line users back one step so
  they see the persona screen too. ONLY targets users who haven't made any
  progress yet (team_pick is null AND step is the initial "team_select").
  Anyone who actually advanced past team_select (picked a team, set a
  username, started the tip-off, etc.) is left alone — they're mid-flow
  and bouncing them backward would be a regression.

Safety guarantees (same as migrate_fte_v2.py):
  - DEFAULT IS DRY-RUN. Pass --apply to actually write.
  - DEFAULT TARGET IS STAGING (gob-staging). Pass --db production to switch.
  - PRODUCTION WRITES require an additional --confirm-production-write flag.
  - IDEMPOTENT. Re-running has no destructive effect — the query won't match
    after the first apply, and even mid-tutorial users are filtered out by
    the team_pick: null + step: "team_select" conjunction.
  - NEVER UNSETS OR DELETES anything. Only one $set on tutorial_state.step.

Usage:
  python scripts/backfill_persona_intro_step.py                                      # dry-run, staging
  python scripts/backfill_persona_intro_step.py --apply                              # apply, staging
  python scripts/backfill_persona_intro_step.py --db production                      # dry-run, production
  python scripts/backfill_persona_intro_step.py --apply --db production --confirm-production-write
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient


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


# Strict eligibility filter:
#   - fte_v2_complete is False (not grandfathered)
#   - tutorial_state.step is exactly "team_select" (haven't advanced)
#   - tutorial_state.team_pick is null/missing (haven't picked a team)
# A user who's advanced AT ALL — picked a team, set a username, opened
# the situation card — is excluded by design. Bouncing those users back
# to persona_intro would be a forward-only-step violation and a UX regression.
ELIGIBLE_FILTER = {
    "fte_v2_complete": False,
    "tutorial_state.step": "team_select",
    "$or": [
        {"tutorial_state.team_pick": None},
        {"tutorial_state.team_pick": {"$exists": False}},
    ],
}


def print_pre_summary(users):
    total = users.count_documents({})
    grandfathered = users.count_documents({"fte_v2_complete": True})
    incomplete = users.count_documents({"fte_v2_complete": False})
    at_team_select = users.count_documents({"tutorial_state.step": "team_select"})
    at_persona = users.count_documents({"tutorial_state.step": "persona_intro"})
    eligible = users.count_documents(ELIGIBLE_FILTER)
    print("Before:")
    print(f"  Total users:                          {total}")
    print(f"  Grandfathered (fte_v2_complete=True): {grandfathered}")
    print(f"  Tutorial-incomplete (=False):         {incomplete}")
    print(f"    of which step=persona_intro:        {at_persona}")
    print(f"    of which step=team_select:          {at_team_select}")
    print(f"  Eligible to backfill (haven't picked a team yet): {eligible}")
    return eligible


def apply_backfill(users, dry_run: bool) -> int:
    if dry_run:
        print("[DRY-RUN] Would set tutorial_state.step = 'persona_intro' on eligible users.")
        return 0
    result = users.update_many(
        ELIGIBLE_FILTER,
        {"$set": {"tutorial_state.step": "persona_intro"}},
    )
    print(f"Matched:  {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    return result.modified_count


def print_post_summary(users):
    at_persona = users.count_documents({"tutorial_state.step": "persona_intro"})
    at_team_select = users.count_documents({"tutorial_state.step": "team_select"})
    eligible_remaining = users.count_documents(ELIGIBLE_FILTER)
    print("After:")
    print(f"  step=persona_intro:                   {at_persona}")
    print(f"  step=team_select:                     {at_team_select}")
    print(f"  Eligible-but-still-team_select:       {eligible_remaining}  (should be 0)")


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
    print(f"  Backfill persona_intro step — Mode: {mode} — Database: {db_name}")
    print("=" * 64)
    print()

    client = get_mongo_client()
    db = client[db_name]
    users = db["users"]

    eligible = print_pre_summary(users)
    print()

    if eligible == 0:
        print("No eligible users to backfill. Nothing to do.")
        print()
        if dry_run:
            print("Done (dry-run).")
        else:
            print("Done.")
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
