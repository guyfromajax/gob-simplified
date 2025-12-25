#!/usr/bin/env python3
"""
Script to convert motion plays' base_loop skeleton from direct steps format
to versions array format (migrating existing steps to v0).

For each motion play:
- If base_loop is in direct steps format, convert to:
  {"versions": [{"version": "v0", "steps": original_steps}]}
- If already in versions array format, skip
"""

import sys
import os
from pathlib import Path
import logging

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection
from bson import ObjectId

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def convert_base_loop_to_versions():
    """
    Converts base_loop skeleton from direct steps format to versions array format.
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
        
        # Check if already in versions array format
        if "versions" in base_loop and isinstance(base_loop["versions"], list):
            logging.info(f"⏭️  Skipping: {play_name} (Already in versions array format)")
            continue
        
        # Check if has direct steps format
        if "steps" not in base_loop or not base_loop.get("steps"):
            logging.warning(f"⏭️  Skipping: {play_name} (No steps in base_loop)")
            continue
        
        logging.info(f"📝 Processing: {play_name}")
        existing_steps = base_loop.get("steps", [])
        
        # Convert to versions array format
        skeletons["base_loop"] = {
            "versions": [
                {"version": "v0", "steps": existing_steps}
            ]
        }
        
        # Update play in database
        plays_collection.update_one(
            {"_id": play_id},
            {"$set": {"skeletons": skeletons}}
        )
        
        logging.info(f"  ✅ Migrated {len(existing_steps)} steps to v0")
        logging.info(f"  💾 Database updated for {play_name}")
        total_updates += 1
        logging.info("")  # Newline for readability
    
    logging.info(f"✅ Conversion complete! Updated {total_updates} motion plays")
    
    # Verification step
    logging.info("\n🔍 Verifying conversion...")
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
    convert_base_loop_to_versions()

