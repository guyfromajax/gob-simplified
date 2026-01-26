#!/usr/bin/env python3
"""
Script to create vertical inverse versions of FCP and HCT skeletons.

For each FCP/HCT skeleton:
- Reads each existing skeleton version (non-empty)
- Creates an inverse version by flipping "upper" ↔ "lower" in player locations
- Keeps all other locations unchanged (key, deep key, topLane, midLane, basketSpot, etc.)
- Keeps all actions and events the same
- Keeps opp boolean field unchanged
- Adds new versions with sequential numbers (v7, v8, v9, etc.)

Example:
- Skeleton has: base variant with v1-v6
- After script: base variant has v1-v12 (v7-v12 are inverses of v1-v6)
"""

import sys
import os
from pathlib import Path
import copy
import re

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import client
from bson import ObjectId


def get_staging_collection(collection_name: str):
    """Get collection from gob-staging database."""
    if not client:
        raise Exception("MongoDB client not available")
    staging_db = client["gob-staging"]
    return staging_db[collection_name]


# Positions that should NOT be inverted (stay the same)
UNCHANGED_POSITIONS = {
    "key", "deep key", "topLane", "midLane", "basketSpot",
    "opp key", "opp deep key", "opp topLane", "opp midLane", "opp basketSpot",
    "inbound_left", "inbound_right"
}


def flip_location(location):
    """
    Flip upper/lower in a location string, keeping opp prefix if present.
    
    Examples:
    - "upper midWing" → "lower midWing"
    - "opp lower midCorner" → "opp upper midCorner"
    - "key" → "key" (unchanged - in UNCHANGED_POSITIONS)
    - "opp key" → "opp key" (unchanged - in UNCHANGED_POSITIONS)
    
    Args:
        location: Location string
    
    Returns:
        str: Location with upper/lower flipped, or original if unchanged
    """
    if not location or not isinstance(location, str):
        return location
    
    # Check if this position should remain unchanged
    if location in UNCHANGED_POSITIONS:
        return location
    
    # Handle opp prefix
    has_opp = location.startswith("opp ")
    base_location = location[4:] if has_opp else location
    
    # Check if base location should remain unchanged
    if base_location in UNCHANGED_POSITIONS:
        return location
    
    # Flip upper to lower
    if "upper" in base_location.lower():
        # Replace "upper" with "lower" (case-insensitive, but preserve original case)
        if "upper" in base_location:
            flipped = base_location.replace("upper", "lower")
        elif "Upper" in base_location:
            flipped = base_location.replace("Upper", "Lower")
        elif "UPPER" in base_location:
            flipped = base_location.replace("UPPER", "LOWER")
        else:
            flipped = base_location
        
        return f"opp {flipped}" if has_opp else flipped
    
    # Flip lower to upper
    if "lower" in base_location.lower():
        # Replace "lower" with "upper" (case-insensitive, but preserve original case)
        if "lower" in base_location:
            flipped = base_location.replace("lower", "upper")
        elif "Lower" in base_location:
            flipped = base_location.replace("Lower", "Upper")
        elif "LOWER" in base_location:
            flipped = base_location.replace("LOWER", "UPPER")
        else:
            flipped = base_location
        
        return f"opp {flipped}" if has_opp else flipped
    
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
                if isinstance(action_info, dict) and "location" in action_info:
                    original_location = action_info["location"]
                    flipped_location = flip_location(original_location)
                    action_info["location"] = flipped_location
                    # Keep opp boolean field unchanged
        
        opposite_steps.append(opposite_step)
    
    return opposite_steps


def get_next_version_number(versions):
    """
    Get the next version number for adding a new version.
    
    Args:
        versions: List of version dictionaries
    
    Returns:
        int: Next version number (e.g., if v1-v6 exist, returns 7)
    """
    if not versions:
        return 1
    
    max_version = 0
    for version in versions:
        if not isinstance(version, dict):
            continue
        version_str = version.get("version", "")
        if version_str.startswith("v"):
            try:
                version_num = int(version_str[1:])
                max_version = max(max_version, version_num)
            except ValueError:
                continue
    
    return max_version + 1


def create_opposite_versions_for_skeleton(skeleton_doc, skeleton_type: str):
    """
    Create opposite versions for all variants in a skeleton.
    
    Args:
        skeleton_doc: Skeleton document from MongoDB
        skeleton_type: "FCP" or "HCT" for logging
    
    Returns:
        dict: Updated skeleton document with new inverse versions, or None if no changes
    """
    skeleton_name = skeleton_doc.get("name") or str(skeleton_doc.get("_id"))
    variants = skeleton_doc.get("variants", {})
    
    if not variants:
        print(f"  ⚠️  {skeleton_type} skeleton '{skeleton_name}': No variants found, skipping")
        return None
    
    updated_variants = {}
    changes_made = False
    total_new_versions = 0
    
    # Process each variant (base, shot, etc.)
    for variant_name, variant_data in variants.items():
        if not variant_data:
            updated_variants[variant_name] = variant_data
            continue
        
        versions = variant_data.get("versions", [])
        
        if not isinstance(versions, list) or len(versions) == 0:
            updated_variants[variant_name] = variant_data
            continue
        
        # Filter to only non-empty versions
        non_empty_versions = [
            v for v in versions 
            if isinstance(v, dict) and v.get("steps") and len(v.get("steps", [])) > 0
        ]
        
        if not non_empty_versions:
            updated_variants[variant_name] = variant_data
            continue
        
        # Get next version number
        next_version_num = get_next_version_number(versions)
        
        # Create inverse versions
        new_versions = []
        for original_version in non_empty_versions:
            original_steps = original_version.get("steps", [])
            if not original_steps:
                continue
            
            # Create inverse steps
            inverse_steps = create_opposite_steps(original_steps)
            
            # Create new version object
            new_version = {
                "version": f"v{next_version_num}",
                "steps": inverse_steps,
                "complete": original_version.get("complete", False)
            }
            
            new_versions.append(new_version)
            next_version_num += 1
        
        if new_versions:
            # Add new versions to existing versions
            updated_versions = versions + new_versions
            updated_variants[variant_name] = {
                **variant_data,
                "versions": updated_versions
            }
            changes_made = True
            total_new_versions += len(new_versions)
            print(f"    ✅ {variant_name}: Added {len(new_versions)} inverse versions (v{get_next_version_number(versions)}-v{next_version_num - 1})")
        else:
            updated_variants[variant_name] = variant_data
    
    if changes_made:
        updated_doc = skeleton_doc.copy()
        updated_doc["variants"] = updated_variants
        print(f"  📝 Total new versions added: {total_new_versions}")
        return updated_doc
    
    return None


def process_collection(collection_name: str, skeleton_type: str, dry_run: bool = True):
    """
    Process all skeletons in a collection.
    
    Args:
        collection_name: Name of the collection ("fcp_skeletons" or "hct_skeletons")
        skeleton_type: "FCP" or "HCT" for logging
        dry_run: If True, only show what would be changed (don't actually update)
    """
    collection = get_staging_collection(collection_name)
    
    print(f"\n{'='*60}")
    print(f"Creating Inverse Versions for {skeleton_type} Skeletons")
    print(f"{'='*60}")
    print(f"Collection: {collection_name}")
    print(f"Database: gob-staging")
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update database)'}")
    print(f"{'='*60}\n")
    
    # Find all skeletons
    skeletons = list(collection.find({}))
    
    if not skeletons:
        print(f"  ℹ️  No {skeleton_type} skeletons found in collection")
        return
    
    print(f"  Found {len(skeletons)} {skeleton_type} skeleton(s)\n")
    
    updated_count = 0
    skipped_count = 0
    
    for skeleton in skeletons:
        skeleton_id = skeleton.get("_id")
        skeleton_name = skeleton.get("name") or str(skeleton_id)
        
        print(f"  Processing: {skeleton_name} ({skeleton_id})")
        
        updated_doc = create_opposite_versions_for_skeleton(skeleton, skeleton_type)
        
        if updated_doc:
            if dry_run:
                print(f"    📝 Would update this skeleton with inverse versions")
            else:
                # Update in database
                try:
                    result = collection.update_one(
                        {"_id": skeleton_id},
                        {"$set": {"variants": updated_doc["variants"]}}
                    )
                    if result.modified_count > 0:
                        print(f"    ✅ Updated in database")
                        updated_count += 1
                    else:
                        print(f"    ⚠️  Update had no effect")
                except Exception as e:
                    print(f"    ❌ Error updating: {e}")
            print()
        else:
            print(f"    ⏭️  No changes needed (no non-empty versions found)")
            skipped_count += 1
            print()
    
    print(f"{'='*60}")
    print(f"Summary:")
    print(f"  Total skeletons: {len(skeletons)}")
    print(f"  {'Would update' if dry_run else 'Updated'}: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"{'='*60}\n")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create vertical inverse versions of FCP/HCT skeletons"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually update the database (default is dry-run)"
    )
    parser.add_argument(
        "--fcp-only",
        action="store_true",
        help="Only process FCP skeletons"
    )
    parser.add_argument(
        "--hct-only",
        action="store_true",
        help="Only process HCT skeletons"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.live
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made to the database")
        print("   Use --live flag to actually update the database\n")
    
    # Process FCP skeletons
    if not args.hct_only:
        process_collection("fcp_skeletons", "FCP", dry_run)
    
    # Process HCT skeletons
    if not args.fcp_only:
        process_collection("hct_skeletons", "HCT", dry_run)
    
    if dry_run:
        print("\n✅ Dry run complete. Review the output above.")
        print("   Run with --live flag to apply changes.\n")


if __name__ == "__main__":
    main()

