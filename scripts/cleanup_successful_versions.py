#!/usr/bin/env python3
"""
Cleanup script to reduce successful variant to only 2 versions:
- v0: Original skeleton
- v1: Opposite of v0 (flipped upper/lower)

Removes all other versions (v2-v13) that were created by previous scripts.
"""

import sys
import os
from pathlib import Path
import copy

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection
from bson import ObjectId

def flip_location(location):
    """
    Flip upper/lower in a location string.
    
    Args:
        location: Location string
    
    Returns:
        str: Location with upper/lower flipped, or original if no upper/lower
    """
    if not location or not isinstance(location, str):
        return location
    
    # Flip upper to lower
    if "upper" in location.lower():
        if "upper" in location:
            location = location.replace("upper", "lower")
        elif "Upper" in location:
            location = location.replace("Upper", "Lower")
        elif "UPPER" in location:
            location = location.replace("UPPER", "LOWER")
        return location
    
    # Flip lower to upper
    if "lower" in location.lower():
        if "lower" in location:
            location = location.replace("lower", "upper")
        elif "Lower" in location:
            location = location.replace("Lower", "Upper")
        elif "LOWER" in location:
            location = location.replace("LOWER", "UPPER")
        return location
    
    # No upper/lower found, return unchanged
    return location

def create_opposite_steps(steps):
    """
    Create opposite version of steps by flipping upper/lower in locations.
    
    Args:
        steps: List of step dictionaries
    
    Returns:
        list: New steps with locations flipped
    """
    opposite_steps = []
    
    for step in steps:
        opposite_step = copy.deepcopy(step)
        
        # Flip locations in pos_actions
        if "pos_actions" in opposite_step:
            for position, action_info in opposite_step["pos_actions"].items():
                if "location" in action_info:
                    original_location = action_info["location"]
                    flipped_location = flip_location(original_location)
                    action_info["location"] = flipped_location
        
        opposite_steps.append(opposite_step)
    
    return opposite_steps

def cleanup_successful_versions():
    """Clean up successful variants to only have v0 (original) and v1 (opposite)."""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Found {len(plays)} plays to process\n")
    
    total_updates = 0
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_id = play.get("_id")
        
        # Skip Motion plays
        play_type = play.get("play_type", "")
        if play_type == "motion":
            print(f"⏭️  Skipping: {play_name} (Motion play)")
            print()
            continue
        
        print(f"📝 Processing: {play_name}")
        
        skeletons = play.get("skeletons", {})
        successful = skeletons.get("successful")
        
        if not successful:
            print(f"  ⚠️  No successful skeleton found, skipping")
            print()
            continue
        
        # Check if in versions array format
        if "versions" not in successful or not isinstance(successful["versions"], list):
            print(f"  ⚠️  Successful not in versions array format, skipping")
            print()
            continue
        
        existing_versions = successful["versions"]
        
        # Find v0 (original)
        v0_version = None
        for version in existing_versions:
            if version.get("version") == "v0":
                v0_version = version
                break
        
        if not v0_version or not v0_version.get("steps"):
            print(f"  ⚠️  No v0 found or v0 is empty, skipping")
            print()
            continue
        
        v0_steps = v0_version.get("steps", [])
        print(f"  ✅ Found v0 with {len(v0_steps)} steps")
        
        # Create opposite from v0
        v1_steps = create_opposite_steps(v0_steps)
        print(f"  ✅ Created v1 (opposite of v0) with {len(v1_steps)} steps")
        
        # Replace versions array with only v0 and v1
        skeletons["successful"] = {
            "versions": [
                {
                    "version": "v0",
                    "steps": v0_steps
                },
                {
                    "version": "v1",
                    "steps": v1_steps
                }
            ]
        }
        
        removed_count = len(existing_versions) - 2
        print(f"  🗑️  Removed {removed_count} extra versions (kept v0 and v1)")
        
        # Update play in database
        plays_collection.update_one(
            {"_id": play_id},
            {"$set": {"skeletons": skeletons}}
        )
        print(f"  💾 Database updated for {play_name}")
        total_updates += 1
        print()
    
    print(f"\n✅ Cleanup complete! Updated {total_updates} plays")
    
    # Verify cleanup
    print("\n🔍 Verifying cleanup...")
    plays = list(plays_collection.find({}))
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_type = play.get("play_type", "")
        
        if play_type == "motion":
            continue
        
        skeletons = play.get("skeletons", {})
        successful = skeletons.get("successful")
        
        if successful and "versions" in successful:
            versions = successful.get("versions", [])
            version_count = len(versions)
            non_empty = [v for v in versions if v.get("steps") and len(v.get("steps", [])) > 0]
            version_names = [v.get("version", "?") for v in non_empty]
            
            if version_count == 2 and set(version_names) == {"v0", "v1"}:
                print(f"  ✅ {play_name}: {version_count} versions - {', '.join(version_names)}")
            else:
                print(f"  ⚠️  {play_name}: {version_count} versions - {', '.join(version_names)}")

if __name__ == "__main__":
    cleanup_successful_versions()

