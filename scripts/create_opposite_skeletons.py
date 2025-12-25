#!/usr/bin/env python3
"""
Script to create opposite versions of skeletons by flipping upper/lower locations.

For each play:
- Reads each existing skeleton version (non-empty)
- Creates an opposite version by flipping "upper" ↔ "lower" in player locations
- Keeps all other locations unchanged (key, deep key, topLane, midLane, basketSpot, etc.)
- Keeps all actions and events the same

Example:
- Play has: 1 successful, 2 mid_play_change, 2 contested, 4 broken
- After script: 2 successful, 4 mid_play_change, 4 contested, 8 broken
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

def flip_location(location):
    """
    Flip upper/lower in a location string.
    
    Examples:
    - "upper midWing" → "lower midWing"
    - "lower midCorner" → "upper midCorner"
    - "key" → "key" (unchanged)
    - "deep key" → "deep key" (unchanged)
    
    Args:
        location: Location string
    
    Returns:
        str: Location with upper/lower flipped, or original if no upper/lower
    """
    if not location or not isinstance(location, str):
        return location
    
    # Flip upper to lower
    if "upper" in location.lower():
        # Replace "upper" with "lower" (case-insensitive, but preserve original case)
        if "upper" in location:
            location = location.replace("upper", "lower")
        elif "Upper" in location:
            location = location.replace("Upper", "Lower")
        elif "UPPER" in location:
            location = location.replace("UPPER", "LOWER")
        return location
    
    # Flip lower to upper
    if "lower" in location.lower():
        # Replace "lower" with "upper" (case-insensitive, but preserve original case)
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

def create_opposite_skeletons():
    """Create opposite versions for all existing skeleton versions."""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Found {len(plays)} plays to process\n")
    
    total_updates = 0
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        play_id = play.get("_id")
        
        # Skip Motion plays (they use base_loop, not the variants we're processing)
        play_type = play.get("play_type", "")
        if play_type == "motion":
            print(f"⏭️  Skipping: {play_name} (Motion play - uses base_loop)")
            print()
            continue
        
        print(f"📝 Processing: {play_name}")
        
        skeletons = play.get("skeletons", {})
        updated = False
        
        # Process each variant
        variants = ["successful", "mid_play_change", "contested", "broken"]
        for variant_name in variants:
            variant = skeletons.get(variant_name)
            if not variant:
                continue
            
            # Get existing versions
            existing_versions = []
            if "versions" in variant and isinstance(variant["versions"], list):
                existing_versions = variant["versions"]
            elif "steps" in variant and variant.get("steps"):
                # Old format - convert to versions array with v0
                existing_versions = [{
                    "version": "v0",
                    "steps": variant.get("steps", [])
                }]
                variant["versions"] = existing_versions
                print(f"  🔄 {variant_name}: Converted old format to versions array")
            
            if not existing_versions:
                continue
            
            # Find non-empty versions to create opposites for
            non_empty_versions = [v for v in existing_versions if v.get("steps") and len(v.get("steps", [])) > 0]
            
            if not non_empty_versions:
                print(f"  ⚠️  {variant_name}: No non-empty versions found, skipping")
                continue
            
            # Get highest version number
            highest_version = get_highest_version_number(variant)
            next_version_num = highest_version + 1
            
            print(f"  🔍 {variant_name}: Found {len(non_empty_versions)} non-empty versions, highest = v{highest_version}")
            
            # Create opposite for each non-empty version
            opposites_created = 0
            for original_version in non_empty_versions:
                original_steps = original_version.get("steps", [])
                if not original_steps:
                    continue
                
                # Create opposite steps
                opposite_steps = create_opposite_steps(original_steps)
                
                # Create new version
                new_version = {
                    "version": f"v{next_version_num}",
                    "steps": opposite_steps
                }
                
                # Append to versions array
                variant["versions"].append(new_version)
                print(f"    ✅ Created v{next_version_num} (opposite of {original_version.get('version', '?')}) with {len(opposite_steps)} steps")
                next_version_num += 1
                opposites_created += 1
            
            if opposites_created > 0:
                updated = True
                print(f"    📊 {variant_name}: Now has {len(variant['versions'])} total versions ({opposites_created} opposites added)")
        
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
        play_type = play.get("play_type", "")
        
        # Skip Motion plays in verification
        if play_type == "motion":
            continue
        
        skeletons = play.get("skeletons", {})
        
        print(f"\n📊 {play_name}:")
        for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
            variant = skeletons.get(variant_name)
            if variant:
                if "versions" in variant and isinstance(variant["versions"], list):
                    total_versions = len(variant["versions"])
                    non_empty_versions = [v for v in variant["versions"] if v.get("steps") and len(v.get("steps", [])) > 0]
                    non_empty_count = len(non_empty_versions)
                    versions = [v.get("version", "?") for v in non_empty_versions]
                    print(f"  {variant_name}: {total_versions} total versions ({non_empty_count} non-empty) - {', '.join(versions)}")
                elif "steps" in variant:
                    steps_count = len(variant.get("steps", []))
                    print(f"  {variant_name}: direct steps format ({steps_count} steps)")
                else:
                    print(f"  {variant_name}: empty")
            else:
                print(f"  {variant_name}: not found")

if __name__ == "__main__":
    create_opposite_skeletons()

