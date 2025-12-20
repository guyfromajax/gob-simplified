"""
Add effectiveness and cloaking fields to all plays and defenses.

This script:
1. Adds `effectiveness: 0` and `cloaking: 0` to all plays in the universal `plays` collection that don't have them
2. Adds `cloaking: 0` to all defenses in the universal `defenses` collection that don't have it
3. Adds `effectiveness: 0` to defenses that don't have it (safety check, though user says all have it)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection, defenses_collection

def add_effectiveness_cloaking_fields():
    """Add effectiveness and cloaking fields to plays and defenses."""
    
    print("=" * 60)
    print("Adding effectiveness and cloaking fields to plays and defenses")
    print("=" * 60)
    
    # ============================================================
    # PLAYS COLLECTION
    # ============================================================
    print("\n📋 Processing PLAYS collection...")
    
    # Count total plays
    total_plays = plays_collection.count_documents({})
    print(f"  Total plays in collection: {total_plays}")
    
    # Add effectiveness field to plays that don't have it
    plays_missing_effectiveness = plays_collection.count_documents({"effectiveness": {"$exists": False}})
    if plays_missing_effectiveness > 0:
        result = plays_collection.update_many(
            {"effectiveness": {"$exists": False}},
            {"$set": {"effectiveness": 0}}
        )
        print(f"  ✅ Added 'effectiveness: 0' to {result.modified_count} play(s)")
    else:
        print(f"  ✓ All plays already have 'effectiveness' field")
    
    # Add cloaking field to plays that don't have it
    plays_missing_cloaking = plays_collection.count_documents({"cloaking": {"$exists": False}})
    if plays_missing_cloaking > 0:
        result = plays_collection.update_many(
            {"cloaking": {"$exists": False}},
            {"$set": {"cloaking": 0}}
        )
        print(f"  ✅ Added 'cloaking: 0' to {result.modified_count} play(s)")
    else:
        print(f"  ✓ All plays already have 'cloaking' field")
    
    # Verify plays
    plays_with_both = plays_collection.count_documents({
        "effectiveness": {"$exists": True},
        "cloaking": {"$exists": True}
    })
    print(f"  📊 Verification: {plays_with_both}/{total_plays} plays have both fields")
    
    # ============================================================
    # DEFENSES COLLECTION
    # ============================================================
    print("\n🛡️  Processing DEFENSES collection...")
    
    # Count total defenses
    total_defenses = defenses_collection.count_documents({})
    print(f"  Total defenses in collection: {total_defenses}")
    
    # Add effectiveness field to defenses that don't have it (safety check)
    defenses_missing_effectiveness = defenses_collection.count_documents({"effectiveness": {"$exists": False}})
    if defenses_missing_effectiveness > 0:
        result = defenses_collection.update_many(
            {"effectiveness": {"$exists": False}},
            {"$set": {"effectiveness": 0}}
        )
        print(f"  ✅ Added 'effectiveness: 0' to {result.modified_count} defense(s)")
    else:
        print(f"  ✓ All defenses already have 'effectiveness' field")
    
    # Add cloaking field to defenses that don't have it
    defenses_missing_cloaking = defenses_collection.count_documents({"cloaking": {"$exists": False}})
    if defenses_missing_cloaking > 0:
        result = defenses_collection.update_many(
            {"cloaking": {"$exists": False}},
            {"$set": {"cloaking": 0}}
        )
        print(f"  ✅ Added 'cloaking: 0' to {result.modified_count} defense(s)")
    else:
        print(f"  ✓ All defenses already have 'cloaking' field")
    
    # Verify defenses
    defenses_with_both = defenses_collection.count_documents({
        "effectiveness": {"$exists": True},
        "cloaking": {"$exists": True}
    })
    print(f"  📊 Verification: {defenses_with_both}/{total_defenses} defenses have both fields")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print("✅ Update complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Plays: {total_plays} total, {plays_with_both} with both fields")
    print(f"  Defenses: {total_defenses} total, {defenses_with_both} with both fields")
    
    # Show sample play and defense
    print("\n📋 Sample play (first play in collection):")
    sample_play = plays_collection.find_one({}, {"name": 1, "effectiveness": 1, "cloaking": 1})
    if sample_play:
        print(f"  Name: {sample_play.get('name', 'N/A')}")
        print(f"  Effectiveness: {sample_play.get('effectiveness', 'MISSING')}")
        print(f"  Cloaking: {sample_play.get('cloaking', 'MISSING')}")
    
    print("\n🛡️  Sample defense (first defense in collection):")
    sample_defense = defenses_collection.find_one({}, {"name": 1, "effectiveness": 1, "cloaking": 1})
    if sample_defense:
        print(f"  Name: {sample_defense.get('name', 'N/A')}")
        print(f"  Effectiveness: {sample_defense.get('effectiveness', 'MISSING')}")
        print(f"  Cloaking: {sample_defense.get('cloaking', 'MISSING')}")

if __name__ == "__main__":
    add_effectiveness_cloaking_fields()

