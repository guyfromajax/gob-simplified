#!/usr/bin/env python3
"""
Script to remove the final step from all version 0 variants in Standard HCT and FCP skeletons.
This fixes the duplicate final steps caused by the "Finish Variant & Save" button auto-saving.
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for BackEnd imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target

def remove_final_step(db, collection_name, skeleton_name="Standard", *, apply=False):
    """Remove the final step from all version 0 variants in a skeleton."""
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
        
        if not steps or len(steps) <= 1:
            print(f"\n  ⚠️ {variant_name}: Version 0 has {len(steps)} step(s) - skipping (need at least 2 to remove last)")
            continue
        
        original_step_count = len(steps)
        
        # Remove the last step
        new_steps = steps[:-1]  # All steps except the last one
        
        print(f"\n  📍 {variant_name}: Removing final step (index {original_step_count - 1})")
        print(f"    Before: {original_step_count} steps")
        print(f"    After: {len(new_steps)} steps")
        
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
    print("🔧 Removing duplicate final steps from FCP and HCT skeletons...")
    connection = connect_migration_target(args.db, write=args.apply)
    
    # Remove duplicates from FCP skeletons
    remove_final_step(connection.database, "fcp_skeletons", "Standard", apply=args.apply)
    
    # Remove duplicates from HCT skeletons
    remove_final_step(connection.database, "hct_skeletons", "Standard", apply=args.apply)
    
    print("\n✅ All duplicate final steps removed!")
    print("🎯 You can now rebuild any skeletons that need different final steps")
    connection.close()
