#!/usr/bin/env python3
"""
Alpha Data Wipe Script

Wipes test/dev data before alpha launch while preserving universal reference data.

WHAT IT WIPES (user-generated data):
- games
- tournaments
- franchises
- users
- franchise_players_data
- franchise_team_data
- franchise_recruits_data
- alpha_otps (optional - preserves by default for tracking)

WHAT IT PRESERVES (universal reference data):
- teams (8 team definitions)
- players (player roster)
- plays (offensive plays)
- defenses (defensive schemes)
- fcp_skeletons (fast break skeletons)
- hct_skeletons (half-court skeletons)

USAGE:
    python scripts/wipe_alpha_data.py                    # DRY RUN (shows what would be deleted)
    python scripts/wipe_alpha_data.py --execute          # ACTUALLY WIPES DATA
    python scripts/wipe_alpha_data.py --execute --wipe-otps  # Also wipes alpha_otps

SAFETY:
- Requires explicit --execute flag to actually delete
- Asks for confirmation before each collection wipe
- Provides collection counts before/after
- Logs all operations

WARNING: This is destructive. Test in staging first.
"""

import sys
import os
from typing import List

# Add parent directory to path so we can import BackEnd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import client, DB_NAME


WIPE_COLLECTIONS = [
    "games",
    "tournaments", 
    "franchises",
    "users",
    "franchise_players_data",
    "franchise_team_data",
    "franchise_recruits_data",
]

PRESERVE_COLLECTIONS = [
    "teams",
    "players",
    "plays",
    "defenses",
    "fcp_skeletons",
    "hct_skeletons",
]

OPTIONAL_WIPE_COLLECTIONS = [
    "alpha_otps",  # Only wipe if --wipe-otps flag provided
]


def confirm(prompt: str) -> bool:
    """Ask user for yes/no confirmation."""
    while True:
        response = input(f"{prompt} (yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            return True
        if response in ["no", "n"]:
            return False
        print("Please answer 'yes' or 'no'")


def wipe_alpha_data(dry_run: bool = True, wipe_otps: bool = False):
    """
    Wipe alpha data from MongoDB.
    
    Args:
        dry_run: If True, only show what would be deleted (don't actually delete)
        wipe_otps: If True, also wipe alpha_otps collection
    """
    db = client[DB_NAME]
    
    print("=" * 80)
    print("ALPHA DATA WIPE SCRIPT")
    print("=" * 80)
    print(f"Database: {DB_NAME}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete data)'}")
    print(f"Wipe OTPs: {'YES' if wipe_otps else 'NO (preserved)'}")
    print("=" * 80)
    print()
    
    # Determine which collections to wipe
    collections_to_wipe = WIPE_COLLECTIONS.copy()
    if wipe_otps:
        collections_to_wipe.extend(OPTIONAL_WIPE_COLLECTIONS)
    
    # Show current state
    print("📊 CURRENT STATE:")
    print()
    print("Collections TO BE WIPED:")
    for coll_name in collections_to_wipe:
        count = db[coll_name].count_documents({})
        print(f"  - {coll_name}: {count:,} documents")
    
    print()
    print("Collections TO BE PRESERVED:")
    for coll_name in PRESERVE_COLLECTIONS:
        count = db[coll_name].count_documents({})
        print(f"  - {coll_name}: {count:,} documents")
    
    if not wipe_otps and "alpha_otps" in db.list_collection_names():
        count = db["alpha_otps"].count_documents({})
        used_count = db["alpha_otps"].count_documents({"used": True})
        print(f"  - alpha_otps: {count:,} documents ({used_count} used, {count - used_count} available)")
    
    print()
    print("=" * 80)
    
    if dry_run:
        print("✅ DRY RUN COMPLETE - No data was deleted")
        print()
        print("To actually wipe data, run:")
        print("  python scripts/wipe_alpha_data.py --execute")
        if not wipe_otps:
            print("  python scripts/wipe_alpha_data.py --execute --wipe-otps  # Also wipe OTPs")
        return
    
    # EXECUTE mode - confirm before proceeding
    print("⚠️  WARNING: You are about to DELETE data from the database!")
    print()
    if not confirm(f"Are you sure you want to wipe {len(collections_to_wipe)} collections from '{DB_NAME}'?"):
        print("❌ Wipe cancelled")
        return
    
    print()
    print("🗑️  WIPING DATA...")
    print()
    
    # Wipe each collection
    for coll_name in collections_to_wipe:
        count_before = db[coll_name].count_documents({})
        if count_before == 0:
            print(f"  ⏭️  {coll_name}: already empty, skipping")
            continue
        
        print(f"  🗑️  {coll_name}: {count_before:,} documents → ", end="", flush=True)
        result = db[coll_name].delete_many({})
        count_after = db[coll_name].count_documents({})
        print(f"deleted {result.deleted_count:,}, remaining: {count_after:,}")
    
    print()
    print("=" * 80)
    print("✅ WIPE COMPLETE")
    print()
    print("📊 FINAL STATE:")
    for coll_name in collections_to_wipe:
        count = db[coll_name].count_documents({})
        status = "✅" if count == 0 else "⚠️"
        print(f"  {status} {coll_name}: {count:,} documents")
    
    print()
    print("PRESERVED COLLECTIONS:")
    for coll_name in PRESERVE_COLLECTIONS:
        count = db[coll_name].count_documents({})
        print(f"  ✅ {coll_name}: {count:,} documents (preserved)")
    
    if not wipe_otps and "alpha_otps" in db.list_collection_names():
        count = db["alpha_otps"].count_documents({})
        used_count = db["alpha_otps"].count_documents({"used": True})
        print(f"  ✅ alpha_otps: {count:,} documents ({used_count} used, {count - used_count} available) (preserved)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Wipe alpha data from MongoDB")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually wipe data (default is dry-run mode)"
    )
    parser.add_argument(
        "--wipe-otps",
        action="store_true",
        help="Also wipe alpha_otps collection (default: preserve for tracking)"
    )
    
    args = parser.parse_args()
    
    try:
        wipe_alpha_data(dry_run=not args.execute, wipe_otps=args.wipe_otps)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
