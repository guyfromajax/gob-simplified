"""
Migration Script: Convert Plays to Multi-Version Structure

Converts existing play skeletons from single structure to version arrays.

Before:
{
  "mid_play_change": {
    "steps": [...],
    "complete": true
  }
}

After:
{
  "mid_play_change": {
    "versions": [
      {"version": "v1", "steps": [...]},
      {"version": "v2", "steps": []},
      {"version": "v3", "steps": []},
      {"version": "v4", "steps": []},
      {"version": "v5", "steps": []},
      {"version": "v6", "steps": []}
    ]
  }
}

Note: "successful" variant keeps single structure (no versions)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection


def migrate_play_to_versions(play):
    """
    Migrate a single play to version structure.
    
    Args:
        play: Play document from MongoDB
        
    Returns:
        dict: Updated skeletons with version arrays
    """
    play_name = play.get("name")
    skeletons = play.get("skeletons", {})
    
    if not skeletons:
        print(f"  ⚠️  {play_name}: No skeletons found, skipping")
        return None
    
    updated_skeletons = {}
    changes_made = False
    
    # Process each variant
    for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
        variant_data = skeletons.get(variant_name, {})
        
        if not variant_data:
            # Create empty variant
            if variant_name == "successful":
                updated_skeletons[variant_name] = {"steps": [], "complete": False}
            else:
                updated_skeletons[variant_name] = {
                    "versions": [
                        {"version": f"v{i}", "steps": []} for i in range(1, 7)
                    ]
                }
            continue
        
        if variant_name == "successful":
            # Successful variant keeps single structure (no versions)
            updated_skeletons[variant_name] = variant_data
        else:
            # Check if already has versions
            if "versions" in variant_data:
                print(f"    ✓ {variant_name}: Already has versions")
                updated_skeletons[variant_name] = variant_data
            else:
                # Convert to version array
                existing_steps = variant_data.get("steps", [])
                
                # Create v1 with existing steps, v2-v6 empty
                updated_skeletons[variant_name] = {
                    "versions": [
                        {"version": "v1", "steps": existing_steps},
                        {"version": "v2", "steps": []},
                        {"version": "v3", "steps": []},
                        {"version": "v4", "steps": []},
                        {"version": "v5", "steps": []},
                        {"version": "v6", "steps": []}
                    ]
                }
                
                step_count = len(existing_steps)
                print(f"    ✓ {variant_name}: Migrated {step_count} steps to v1, added v2-v6 placeholders")
                changes_made = True
    
    return updated_skeletons if changes_made else None


def migrate_all_plays():
    """Migrate all plays in the collection."""
    print("=" * 70)
    print("MIGRATING PLAYS TO MULTI-VERSION STRUCTURE")
    print("=" * 70)
    
    plays = list(plays_collection.find({}))
    print(f"\nFound {len(plays)} plays to check\n")
    
    migrated_count = 0
    skipped_count = 0
    
    for play in plays:
        play_id = play.get("_id")
        play_name = play.get("name")
        
        print(f"Processing: {play_name}")
        
        updated_skeletons = migrate_play_to_versions(play)
        
        if updated_skeletons:
            # Update in database
            plays_collection.update_one(
                {"_id": play_id},
                {"$set": {"skeletons": updated_skeletons}}
            )
            print(f"  ✅ Updated in database\n")
            migrated_count += 1
        else:
            print(f"  ⏭️  No changes needed\n")
            skipped_count += 1
    
    print("=" * 70)
    print(f"MIGRATION COMPLETE")
    print("=" * 70)
    print(f"  Migrated: {migrated_count} plays")
    print(f"  Skipped: {skipped_count} plays (already up-to-date)")
    print(f"  Total: {len(plays)} plays")
    
    # Verify migration
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    plays = list(plays_collection.find({}))
    for play in plays:
        play_name = play.get("name")
        skeletons = play.get("skeletons", {})
        
        print(f"\n{play_name}:")
        
        for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
            variant_data = skeletons.get(variant_name, {})
            
            if variant_name == "successful":
                step_count = len(variant_data.get("steps", []))
                complete = variant_data.get("complete", False)
                print(f"  {variant_name}: {step_count} steps, complete={complete}")
            else:
                if "versions" in variant_data:
                    versions = variant_data["versions"]
                    version_summary = []
                    for v in versions:
                        v_name = v.get("version")
                        v_steps = len(v.get("steps", []))
                        if v_steps > 0:
                            version_summary.append(f"{v_name}({v_steps})")
                    
                    if version_summary:
                        print(f"  {variant_name}: {len(versions)} versions - {', '.join(version_summary)}")
                    else:
                        print(f"  {variant_name}: {len(versions)} versions (all empty)")
                else:
                    print(f"  {variant_name}: ❌ MISSING VERSIONS!")


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will modify play documents in MongoDB")
    print("Make sure you have a backup if needed.\n")
    
    response = input("Continue with migration? (yes/no): ")
    
    if response.lower() in ["yes", "y"]:
        migrate_all_plays()
    else:
        print("Migration cancelled.")

