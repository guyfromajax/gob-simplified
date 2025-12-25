#!/usr/bin/env python3
"""
Script to convert successful variant to versions array format and create multiple versions.

For each play:
1. Converts successful from direct steps format to versions array format
   - Existing steps become v0
2. Creates additional versions (v1, v2, v3, etc.) by copying v0's steps
   - Number of versions to create can be configured
"""

import sys
import os
from pathlib import Path
import copy

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection
from bson import ObjectId

def convert_successful_to_versions(play, num_versions=7):
    """
    Convert successful variant to versions array format and create multiple versions.
    
    Args:
        play: Play document from MongoDB
        num_versions: Number of versions to create (default: 7, so v0-v6)
    
    Returns:
        tuple: (updated_skeletons_dict, bool_changed)
    """
    play_name = play.get("name", "Unknown")
    skeletons = play.get("skeletons", {})
    successful = skeletons.get("successful")
    
    if not successful:
        print(f"  ⚠️  No successful skeleton found, skipping")
        return None, False
    
    # Check if already in versions format
    if "versions" in successful and isinstance(successful["versions"], list):
        existing_versions = successful["versions"]
        existing_count = len([v for v in existing_versions if v.get("steps") and len(v.get("steps", [])) > 0])
        print(f"  ℹ️  Already in versions format with {existing_count} non-empty versions")
        
        # Check if we need to add more versions
        highest_version_num = -1
        for version_obj in existing_versions:
            version_str = version_obj.get("version", "")
            import re
            match = re.search(r'v(\d+)', version_str)
            if match:
                version_num = int(match.group(1))
                highest_version_num = max(highest_version_num, version_num)
        
        if highest_version_num >= num_versions - 1:
            print(f"  ⏭️  Already has enough versions (up to v{highest_version_num}), skipping")
            return None, False
        
        # Get v0 steps (or first non-empty version)
        v0_steps = None
        for version_obj in existing_versions:
            steps = version_obj.get("steps", [])
            if steps and len(steps) > 0:
                v0_steps = steps
                break
        
        if not v0_steps:
            print(f"  ⚠️  No non-empty versions found to copy, skipping")
            return None, False
        
        # Add additional versions
        updated_versions = copy.deepcopy(existing_versions)
        next_version_num = highest_version_num + 1
        
        while next_version_num < num_versions:
            new_version = {
                "version": f"v{next_version_num}",
                "steps": copy.deepcopy(v0_steps)
            }
            updated_versions.append(new_version)
            print(f"    ✅ Added v{next_version_num} with {len(v0_steps)} steps")
            next_version_num += 1
        
        skeletons["successful"] = {"versions": updated_versions}
        return skeletons, True
    
    # Convert from direct steps format to versions array
    if "steps" in successful:
        existing_steps = successful.get("steps", [])
        if not existing_steps or len(existing_steps) == 0:
            print(f"  ⚠️  Successful skeleton has no steps, skipping")
            return None, False
        
        print(f"  🔄 Converting from direct steps format to versions array")
        print(f"    ✓ Migrating {len(existing_steps)} steps to v0")
        
        # Create versions array starting with v0
        versions = []
        versions.append({
            "version": "v0",
            "steps": copy.deepcopy(existing_steps)
        })
        
        # Create additional versions (v1, v2, v3, etc.) by copying v0
        for i in range(1, num_versions):
            versions.append({
                "version": f"v{i}",
                "steps": copy.deepcopy(existing_steps)
            })
            print(f"    ✅ Created v{i} with {len(existing_steps)} steps")
        
        skeletons["successful"] = {"versions": versions}
        return skeletons, True
    
    print(f"  ⚠️  Successful skeleton has unexpected format, skipping")
    return None, False

def create_successful_versions(num_versions=7):
    """
    Convert successful variants to versions array format and create multiple versions.
    
    Args:
        num_versions: Number of versions to create (default: 7, so v0-v6)
    """
    plays = list(plays_collection.find({}))
    print(f"🔍 Found {len(plays)} plays to process\n")
    print(f"📋 Creating {num_versions} versions (v0-v{num_versions-1}) for successful variant\n")
    
    total_updates = 0
    skipped = 0
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_id = play.get("_id")
        
        # Skip Motion plays (they use base_loop, not successful)
        play_type = play.get("play_type", "")
        if play_type == "motion":
            print(f"⏭️  Skipping: {play_name} (Motion play - uses base_loop, not successful)")
            skipped += 1
            print()
            continue
        
        print(f"📝 Processing: {play_name}")
        
        updated_skeletons, changed = convert_successful_to_versions(play, num_versions)
        
        if changed and updated_skeletons:
            # Update play in database
            plays_collection.update_one(
                {"_id": play_id},
                {"$set": {"skeletons": updated_skeletons}}
            )
            print(f"  💾 Database updated for {play_name}")
            total_updates += 1
        else:
            print(f"  ⏭️  No updates needed for {play_name}")
            skipped += 1
        
        print()
    
    print(f"\n✅ Migration complete!")
    print(f"  Updated: {total_updates} plays")
    print(f"  Skipped: {skipped} plays")
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    plays = list(plays_collection.find({}))
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_type = play.get("play_type", "")
        
        # Skip Motion plays in verification
        if play_type == "motion":
            continue
        
        skeletons = play.get("skeletons", {})
        successful = skeletons.get("successful")
        
        if successful:
            if "versions" in successful and isinstance(successful["versions"], list):
                version_count = len(successful["versions"])
                non_empty_count = len([v for v in successful["versions"] if v.get("steps") and len(v.get("steps", [])) > 0])
                versions = [v.get("version", "?") for v in successful["versions"]]
                print(f"  ✅ {play_name}: {version_count} versions ({non_empty_count} non-empty) - {', '.join(versions)}")
            elif "steps" in successful:
                steps_count = len(successful.get("steps", []))
                print(f"  ⚠️  {play_name}: Still in direct steps format ({steps_count} steps)")
            else:
                print(f"  ❌ {play_name}: Unexpected format")
        else:
            print(f"  ❌ {play_name}: No successful skeleton found")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert successful variant to versions array and create multiple versions")
    parser.add_argument("--num-versions", type=int, default=7, help="Number of versions to create (default: 7, so v0-v6)")
    args = parser.parse_args()
    
    create_successful_versions(num_versions=args.num_versions)

