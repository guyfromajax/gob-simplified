#!/usr/bin/env python3
"""
Script to copy the successful skeleton to the next available version 
for each variant (mid_play_change, contested, broken) in each play.

For each play:
- Gets the successful skeleton
- For each variant (mid_play_change, contested, broken):
  - Finds the highest existing version number
  - Adds 1 to get the next version number
  - Copies successful skeleton's steps to create the new version
  - Appends it to the variant's versions array
"""

import sys
import os
from pathlib import Path
import copy
import re

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection
from bson import ObjectId

def get_successful_steps(play):
    """
    Extract steps from successful skeleton.
    Handles both direct steps format and versions array format.
    
    Returns:
        list: Steps array from successful skeleton, or None if not found
    """
    skeletons = play.get("skeletons", {})
    successful = skeletons.get("successful")
    
    if not successful:
        return None
    
    # Check if successful has a versions array
    if "versions" in successful and isinstance(successful["versions"], list):
        # Get steps from the first version (v0 or v1, etc.)
        if len(successful["versions"]) > 0:
            first_version = successful["versions"][0]
            return first_version.get("steps")
        return None
    
    # Direct steps format
    if "steps" in successful:
        return successful.get("steps")
    
    return None

def get_highest_version_number(variant):
    """
    Find the highest version number in a variant's versions array.
    
    Args:
        variant: Variant dict (could have "versions" array or direct "steps")
    
    Returns:
        int: Highest version number found, or -1 if none found
    """
    if not variant:
        return -1
    
    # Check if variant has versions array
    if "versions" in variant and isinstance(variant["versions"], list):
        versions = variant["versions"]
        if not versions:
            return -1
        
        highest = -1
        for version_obj in versions:
            version_str = version_obj.get("version", "")
            # Extract number from "v0", "v1", "v2", etc.
            match = re.search(r'v(\d+)', version_str)
            if match:
                version_num = int(match.group(1))
                highest = max(highest, version_num)
        
        return highest
    
    # If variant has direct steps (old format), treat it as v0
    if "steps" in variant and variant.get("steps"):
        return 0
    
    return -1

def copy_successful_to_variants():
    """Copy successful skeleton to next available version for each variant in each play."""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Found {len(plays)} plays to process\n")
    
    total_updates = 0
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_id = play.get("_id")
        
        print(f"📝 Processing: {play_name}")
        
        # Get successful skeleton steps
        successful_steps = get_successful_steps(play)
        if not successful_steps:
            print(f"  ⚠️  No successful skeleton found, skipping")
            continue
        
        skeletons = play.get("skeletons", {})
        updated = False
        
        # Process each variant
        variants = ["mid_play_change", "contested", "broken"]
        for variant_name in variants:
            variant = skeletons.get(variant_name)
            if not variant:
                print(f"  ⚠️  {variant_name} not found, skipping")
                continue
            
            # Get highest version number
            highest_version = get_highest_version_number(variant)
            next_version_num = highest_version + 1
            next_version_str = f"v{next_version_num}"
            
            print(f"  🔍 {variant_name}: highest version = v{highest_version}, next = {next_version_str}")
            
            # Ensure variant has versions array structure
            if "versions" not in variant or not isinstance(variant["versions"], list):
                # Convert old format (direct steps) to versions array format
                existing_steps = variant.get("steps", [])
                variant["versions"] = []
                if existing_steps:
                    # Add existing steps as v0
                    variant["versions"].append({
                        "version": "v0",
                        "steps": existing_steps
                    })
                    print(f"    ✓ Converted old format to versions array (existing as v0)")
            
            # Create new version with copied steps
            new_version = {
                "version": next_version_str,
                "steps": copy.deepcopy(successful_steps)
            }
            
            # Append to versions array
            variant["versions"].append(new_version)
            print(f"    ✅ Added {next_version_str} with {len(successful_steps)} steps")
            updated = True
        
        # Update play in database if any changes were made
        if updated:
            plays_collection.update_one(
                {"_id": play_id},
                {"$set": {"skeletons": skeletons}}
            )
            print(f"  💾 Database updated for {play_name}")
            total_updates += 1
        else:
            print(f"  ⏭️  No updates needed for {play_name}")
        
        print()
    
    print(f"\n✅ Migration complete! Updated {total_updates} plays")
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    plays = list(plays_collection.find({}))
    for play in plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        print(f"\n📊 {play_name}:")
        for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
            variant = skeletons.get(variant_name)
            if variant:
                if "versions" in variant and isinstance(variant["versions"], list):
                    version_count = len(variant["versions"])
                    versions = [v.get("version", "?") for v in variant["versions"]]
                    print(f"  {variant_name}: {version_count} versions - {', '.join(versions)}")
                elif "steps" in variant:
                    print(f"  {variant_name}: direct steps format (old format)")
                else:
                    print(f"  {variant_name}: empty")
            else:
                print(f"  {variant_name}: not found")

if __name__ == "__main__":
    copy_successful_to_variants()

