#!/usr/bin/env python3
"""
Quick script to verify skeleton versions in MongoDB.
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

def verify_versions(plays_collection):
    """Check what versions exist for each variant in each play."""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Checking {len(plays)} plays in database\n")
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        print(f"📊 {play_name}:")
        
        for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
            variant = skeletons.get(variant_name)
            if variant:
                if "versions" in variant and isinstance(variant["versions"], list):
                    version_count = len(variant["versions"])
                    versions = [v.get("version", "?") for v in variant["versions"]]
                    print(f"  {variant_name}: {version_count} versions - {', '.join(versions)}")
                elif "steps" in variant:
                    steps_count = len(variant.get("steps", []))
                    print(f"  {variant_name}: direct steps format ({steps_count} steps)")
                else:
                    print(f"  {variant_name}: empty")
            else:
                print(f"  {variant_name}: not found")
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        verify_versions(connection.database.plays)
    finally:
        connection.close()
