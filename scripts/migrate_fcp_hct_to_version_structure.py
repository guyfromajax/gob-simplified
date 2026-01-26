"""
Migration Script: Add Version Fields to FCP/HCT Skeletons

Adds version fields (v1, v2, etc.) to existing FCP and HCT skeleton versions arrays
to match the offensive plays structure.

Before:
{
  "variants": {
    "base": {
      "versions": [
        {"steps": [...]},
        {"steps": [...]}
      ]
    }
  }
}

After:
{
  "variants": {
    "base": {
      "versions": [
        {"version": "v1", "steps": [...]},
        {"version": "v2", "steps": [...]}
      ]
    }
  }
}

Note: Only updates skeletons in gob-staging database (where builders save).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import client
from bson import ObjectId


def get_staging_collection(collection_name: str):
    """Get collection from gob-staging database."""
    if not client:
        raise Exception("MongoDB client not available")
    staging_db = client["gob-staging"]
    return staging_db[collection_name]


def migrate_skeleton_versions(skeleton_doc, skeleton_type: str):
    """
    Add version fields to a skeleton's variants.
    
    Args:
        skeleton_doc: Skeleton document from MongoDB
        skeleton_type: "FCP" or "HCT" for logging
        
    Returns:
        dict: Updated skeleton document, or None if no changes needed
    """
    skeleton_name = skeleton_doc.get("name") or skeleton_doc.get("_id")
    variants = skeleton_doc.get("variants", {})
    
    if not variants:
        print(f"  ⚠️  {skeleton_type} skeleton '{skeleton_name}': No variants found, skipping")
        return None
    
    updated_variants = {}
    changes_made = False
    
    # Process each variant (base, shot)
    for variant_name, variant_data in variants.items():
        if not variant_data:
            continue
            
        versions = variant_data.get("versions", [])
        
        # Skip if no versions array
        if not isinstance(versions, list) or len(versions) == 0:
            continue
        
        # Check if versions already have version fields
        has_version_fields = all(
            isinstance(v, dict) and "version" in v 
            for v in versions if v
        )
        
        if has_version_fields:
            # Already migrated, skip
            updated_variants[variant_name] = variant_data
            continue
        
        # Add version fields based on array index
        updated_versions = []
        for idx, version_data in enumerate(versions):
            if not isinstance(version_data, dict):
                continue
                
            # Create updated version with version field
            updated_version = version_data.copy()
            updated_version["version"] = f"v{idx + 1}"  # v1, v2, v3, etc.
            updated_versions.append(updated_version)
        
        if updated_versions:
            updated_variants[variant_name] = {
                **variant_data,
                "versions": updated_versions
            }
            changes_made = True
            print(f"    ✅ {variant_name}: Added version fields to {len(updated_versions)} versions")
        else:
            updated_variants[variant_name] = variant_data
    
    if changes_made:
        updated_doc = skeleton_doc.copy()
        updated_doc["variants"] = updated_variants
        return updated_doc
    
    return None


def migrate_collection(collection_name: str, skeleton_type: str, dry_run: bool = True):
    """
    Migrate all skeletons in a collection.
    
    Args:
        collection_name: Name of the collection ("fcp_skeletons" or "hct_skeletons")
        skeleton_type: "FCP" or "HCT" for logging
        dry_run: If True, only show what would be changed (don't actually update)
    """
    collection = get_staging_collection(collection_name)
    
    print(f"\n{'='*60}")
    print(f"Migrating {skeleton_type} Skeletons")
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
        
        updated_doc = migrate_skeleton_versions(skeleton, skeleton_type)
        
        if updated_doc:
            if dry_run:
                print(f"    📝 Would update this skeleton")
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
            print(f"    ⏭️  No changes needed (already has version fields or no versions)")
            skipped_count += 1
            print()
    
    print(f"{'='*60}")
    print(f"Summary:")
    print(f"  Total skeletons: {len(skeletons)}")
    print(f"  {'Would update' if dry_run else 'Updated'}: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"{'='*60}\n")


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Add version fields to FCP/HCT skeletons to match offensive plays structure"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually update the database (default is dry-run)"
    )
    parser.add_argument(
        "--fcp-only",
        action="store_true",
        help="Only migrate FCP skeletons"
    )
    parser.add_argument(
        "--hct-only",
        action="store_true",
        help="Only migrate HCT skeletons"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.live
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made to the database")
        print("   Use --live flag to actually update the database\n")
    
    # Migrate FCP skeletons
    if not args.hct_only:
        migrate_collection("fcp_skeletons", "FCP", dry_run)
    
    # Migrate HCT skeletons
    if not args.fcp_only:
        migrate_collection("hct_skeletons", "HCT", dry_run)
    
    if dry_run:
        print("\n✅ Dry run complete. Review the output above.")
        print("   Run with --live flag to apply changes.\n")


if __name__ == "__main__":
    main()

