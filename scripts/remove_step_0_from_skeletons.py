#!/usr/bin/env python3
"""
Script to remove step 0 from all FCP and HCT skeleton variants.
Step 0 (inbound setup) is now handled by BASELINE_INBOUND turn.
Skeleton animations now start from old step 1 (new step 0).
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for BackEnd imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

def remove_step_0(db, collection_name, skeleton_name="Standard", *, apply=False):
    """Remove step 0 from all version 0 variants in a skeleton."""
    collection = db[collection_name]
    
    print(f"\n{'='*80}")
    print(f"Processing {collection_name.upper()} - {skeleton_name} skeleton")
    print(f"{'='*80}")
    
    # Find the skeleton document
    skeleton_doc = collection.find_one({"name": skeleton_name})
    
    if not skeleton_doc:
        print(f"❌ No skeleton found with name '{skeleton_name}'")
        return
    
    print(f"✅ Found skeleton: _id={skeleton_doc['_id']}")
    
    variants = skeleton_doc.get('variants', {})
    print(f"📊 Total variants: {len(variants)}")
    
    modified_variants = []
    
    for variant_name, variant_data in variants.items():
        versions = variant_data.get('versions', [])
        
        if not versions or len(versions) == 0:
            print(f"\n  ⚠️ {variant_name}: No versions - skipping")
            continue
        
        version_0 = versions[0]
        steps = version_0.get('steps', [])
        
        if not steps or len(steps) == 0:
            print(f"\n  ⚠️ {variant_name}: Version 0 has no steps - skipping")
            continue
        
        original_step_count = len(steps)
        
        # Show original step 0 before removal
        step_0 = steps[0]
        print(f"\n  📍 {variant_name}: Removing step 0 (inbound setup)")
        print(f"    Step 0 positions:")
        for pos, action in step_0.get('pos_actions', {}).items():
            print(f"      {pos}: location={action.get('location')}, action={action.get('action')}")
        
        # Remove step 0 (all steps except the first one)
        new_steps = steps[1:]
        
        # Adjust timestamps (subtract step 0's timestamp from all remaining steps)
        step_0_timestamp = steps[0].get('timestamp', 0)
        for step in new_steps:
            step['timestamp'] = step.get('timestamp', 0) - step_0_timestamp
        
        print(f"    Before: {original_step_count} steps")
        print(f"    After: {len(new_steps)} steps (timestamps adjusted)")
        
        # Update the version 0 steps in the variant
        variant_data['versions'][0]['steps'] = new_steps
        modified_variants.append(variant_name)
    
    if modified_variants:
        # Update the MongoDB document
        result = None
        if apply:
            result = collection.update_one(
                {"_id": skeleton_doc["_id"]},
                {"$set": {"variants": variants}}
            )
        
        print(f"\n{'='*80}")
        count = result.modified_count if result is not None else 0
        verb = "Updated" if apply else "Would update"
        print(f"✅ {verb} {collection_name}: {count if apply else 1} document(s)")
        print(f"📝 Modified {len(modified_variants)} variant(s):")
        for variant_name in modified_variants:
            print(f"  - {variant_name}")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"ℹ️ No variants needed modification")
        print(f"{'='*80}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run")
    args = parser.parse_args()
    print("🔧 Removing step 0 from FCP and HCT skeletons...")
    print("Step 0 (inbound setup) is now handled by BASELINE_INBOUND turn")
    connection = connect_migration_target(args.db, write=args.apply)
    
    # Remove step 0 from FCP skeletons
    remove_step_0(connection.database, "fcp_skeletons", "Standard", apply=args.apply)
    
    # Remove step 0 from HCT skeletons
    remove_step_0(connection.database, "hct_skeletons", "Standard", apply=args.apply)
    
    print("\n✅ All step 0s removed!")
    print("🎯 Skeletons now start from old step 1 (press break action)")
    connection.close()
