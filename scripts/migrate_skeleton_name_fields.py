"""
Migration script to update skeleton name fields:
1. Change "field" key to "name" in FCP skeletons
2. Add "name": "Standard" to HCT skeletons that don't have a "name" key
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection

def migrate_skeleton_name_fields():
    """Migrate skeleton name fields"""
    
    # Part 1: Migrate FCP skeletons - change "field" to "name"
    print("=" * 60)
    print("Part 1: Migrating FCP skeletons (field → name)")
    print("=" * 60)
    
    fcp_skeletons = list(fcp_skeletons_collection.find({}))
    print(f"Found {len(fcp_skeletons)} FCP skeletons to check")
    
    fcp_updated = 0
    for skeleton in fcp_skeletons:
        skeleton_id = skeleton.get("_id")
        has_field = "field" in skeleton
        has_name = "name" in skeleton
        
        if has_field:
            field_value = skeleton["field"]
            print(f"\n📝 Migrating FCP skeleton: {skeleton_id}")
            print(f"  Current 'field' value: {field_value}")
            
            # Update: set name from field, then remove field
            update_op = {
                "$set": {"name": field_value},
                "$unset": {"field": ""}
            }
            fcp_skeletons_collection.update_one(
                {"_id": skeleton_id},
                update_op
            )
            print(f"  ✅ Changed 'field' → 'name' with value: {field_value}")
            fcp_updated += 1
        elif has_name:
            print(f"⏭️  Skipping FCP skeleton {skeleton_id} (already has 'name', no 'field' to migrate)")
        else:
            print(f"⚠️  Warning: FCP skeleton {skeleton_id} has neither 'field' nor 'name'")
    
    print(f"\n✅ FCP migration complete! Updated {fcp_updated} skeleton(s)")
    
    # Part 2: Add "name": "Standard" to HCT skeletons without "name"
    print("\n" + "=" * 60)
    print("Part 2: Adding 'name' to HCT skeletons without it")
    print("=" * 60)
    
    hct_skeletons = list(hct_skeletons_collection.find({}))
    print(f"Found {len(hct_skeletons)} HCT skeletons to check")
    
    hct_updated = 0
    for skeleton in hct_skeletons:
        skeleton_id = skeleton.get("_id")
        has_name = "name" in skeleton
        
        if not has_name:
            print(f"\n📝 Updating HCT skeleton: {skeleton_id}")
            hct_skeletons_collection.update_one(
                {"_id": skeleton_id},
                {"$set": {"name": "Standard"}}
            )
            print(f"  ✅ Added 'name': 'Standard'")
            hct_updated += 1
        else:
            print(f"⏭️  Skipping HCT skeleton {skeleton_id} (already has 'name': {skeleton.get('name')})")
    
    print(f"\n✅ HCT migration complete! Updated {hct_updated} skeleton(s)")
    
    # Verify migration
    print("\n" + "=" * 60)
    print("🔍 Verifying migration...")
    print("=" * 60)
    
    print("\nFCP Skeletons:")
    fcp_skeletons = list(fcp_skeletons_collection.find({}))
    for skeleton in fcp_skeletons:
        skeleton_id = str(skeleton.get("_id"))
        name = skeleton.get("name", "❌ MISSING")
        has_field = "field" in skeleton
        status = "✅" if name != "❌ MISSING" and not has_field else "❌"
        print(f"  {status} {skeleton_id}: name='{name}', has_field={has_field}")
    
    print("\nHCT Skeletons:")
    hct_skeletons = list(hct_skeletons_collection.find({}))
    for skeleton in hct_skeletons:
        skeleton_id = str(skeleton.get("_id"))
        name = skeleton.get("name", "❌ MISSING")
        status = "✅" if name != "❌ MISSING" else "❌"
        print(f"  {status} {skeleton_id}: name='{name}'")
    
    print("\n✅ Migration verification complete!")

if __name__ == "__main__":
    migrate_skeleton_name_fields()

