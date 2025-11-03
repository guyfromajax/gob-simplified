"""
Migration script to update play skeletons structure:
1. Rename "standard" → "successful" 
2. Add empty placeholders for: mid_play_change, contested, broken
"""

from BackEnd.db import plays_collection

def migrate_play_skeletons():
    """Migrate all plays to new skeleton structure"""
    
    plays = list(plays_collection.find({}))
    print(f"Found {len(plays)} plays to migrate")
    
    for play in plays:
        play_name = play.get("name")
        skeletons = play.get("skeletons", {})
        
        # Check if migration needed
        if "standard" in skeletons and "successful" not in skeletons:
            print(f"\n📝 Migrating: {play_name}")
            
            # Step 1: Rename standard → successful
            skeletons["successful"] = skeletons.pop("standard")
            print(f"  ✓ Renamed 'standard' → 'successful'")
            
            # Step 2: Add empty placeholders for other variants
            empty_skeleton = {"steps": []}
            
            if "mid_play_change" not in skeletons:
                skeletons["mid_play_change"] = empty_skeleton.copy()
                print(f"  ✓ Added 'mid_play_change' placeholder")
            
            if "contested" not in skeletons:
                skeletons["contested"] = empty_skeleton.copy()
                print(f"  ✓ Added 'contested' placeholder")
            
            if "broken" not in skeletons:
                skeletons["broken"] = empty_skeleton.copy()
                print(f"  ✓ Added 'broken' placeholder")
            
            # Step 3: Update in database
            plays_collection.update_one(
                {"_id": play["_id"]},
                {"$set": {"skeletons": skeletons}}
            )
            print(f"  ✅ Database updated")
        
        elif "successful" in skeletons:
            print(f"⏭️  Skipping: {play_name} (already migrated)")
        else:
            print(f"⚠️  Warning: {play_name} has no 'standard' or 'successful' skeleton")
    
    print("\n✅ Migration complete!")
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    plays = list(plays_collection.find({}))
    for play in plays:
        skeletons = play.get("skeletons", {})
        has_all = all(k in skeletons for k in ["successful", "mid_play_change", "contested", "broken"])
        status = "✅" if has_all else "❌"
        print(f"{status} {play['name']}: {list(skeletons.keys())}")

if __name__ == "__main__":
    migrate_play_skeletons()

