#!/usr/bin/env python3
"""
Script to create opposite versions (v1) for motion plays' base_loop skeletons
by flipping upper/lower locations.

For each motion play:
- Gets the v0 version from base_loop.versions
- Creates v1 by flipping upper/lower in all locations
- Appends v1 to the versions array
- Result: Each motion play has 2 versions (v0 = original, v1 = opposite)
"""

import sys
import os
from pathlib import Path
import copy
import logging

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

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

def create_motion_opposite_versions():
    """
    Creates opposite versions (v1) for all motion plays' base_loop skeletons.
    """
    logging.info("🔍 Finding motion plays to process...")
    
    # Find all motion plays
    motion_plays = list(plays_collection.find({"play_type": "motion"}))
    logging.info(f"📋 Found {len(motion_plays)} motion plays\n")
    
    total_updates = 0
    
    for play in motion_plays:
        play_id = play.get("_id")
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        base_loop = skeletons.get("base_loop")
        if not base_loop:
            logging.warning(f"⏭️  Skipping: {play_name} (No base_loop skeleton)")
            continue
        
        # Check if in versions array format
        if "versions" not in base_loop or not isinstance(base_loop["versions"], list):
            logging.warning(f"⏭️  Skipping: {play_name} (base_loop not in versions array format - run convert_motion_base_loop_to_versions.py first)")
            continue
        
        versions = base_loop["versions"]
        
        # Check if v1 already exists
        has_v1 = any(v.get("version") == "v1" for v in versions)
        if has_v1:
            logging.info(f"⏭️  Skipping: {play_name} (v1 already exists)")
            continue
        
        # Get v0 steps
        v0_version = None
        for v in versions:
            if v.get("version") == "v0" and v.get("steps"):
                v0_version = v
                break
        
        if not v0_version:
            logging.warning(f"⏭️  Skipping: {play_name} (No v0 version found)")
            continue
        
        v0_steps = v0_version.get("steps", [])
        if not v0_steps:
            logging.warning(f"⏭️  Skipping: {play_name} (v0 has no steps)")
            continue
        
        logging.info(f"📝 Processing: {play_name}")
        
        # Create v1 with opposite steps
        v1_steps = create_opposite_steps(v0_steps)
        
        # Add v1 to versions array
        versions.append({
            "version": "v1",
            "steps": v1_steps
        })
        
        # Update play in database
        plays_collection.update_one(
            {"_id": play_id},
            {"$set": {"skeletons": skeletons}}
        )
        
        logging.info(f"  ✅ Created v1 with {len(v1_steps)} steps (opposite of v0)")
        logging.info(f"  💾 Database updated for {play_name}")
        total_updates += 1
        logging.info("")  # Newline for readability
    
    logging.info(f"✅ Migration complete! Updated {total_updates} motion plays")
    
    # Verification step
    logging.info("\n🔍 Verifying migration...")
    motion_plays = list(plays_collection.find({"play_type": "motion"}))
    for play in motion_plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        base_loop = skeletons.get("base_loop", {})
        
        if "versions" in base_loop and isinstance(base_loop["versions"], list):
            versions = base_loop["versions"]
            non_empty_versions = [v for v in versions if v.get("steps") and len(v.get("steps", [])) > 0]
            version_strs = [v.get("version", "N/A") for v in non_empty_versions]
            logging.info(f"  ✅ {play_name}: {len(versions)} versions ({len(non_empty_versions)} non-empty) - {', '.join(version_strs)}")
        else:
            logging.warning(f"  ❌ {play_name}: base_loop not in versions array format")

if __name__ == "__main__":
    create_motion_opposite_versions()

