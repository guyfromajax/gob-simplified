"""
Add momentum field to all plays and defenses in the universal collections.

This script:
1. Adds `momentum: 0` to all plays in the universal `plays` collection that don't have it
2. Adds `momentum: 0` to all defenses in the universal `defenses` collection that don't have it

The momentum field lives at the same level as `effectiveness` and `cloaking`.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection, defenses_collection

def add_momentum_field():
    """Add momentum field to plays and defenses."""
    
    print("=" * 60)
    print("Adding momentum field to plays and defenses")
    print("=" * 60)
    
    # ============================================================
    # PLAYS COLLECTION
    # ============================================================
    print("\n📋 Processing PLAYS collection...")
    
    # Count total plays
    total_plays = plays_collection.count_documents({})
    print(f"  Total plays in collection: {total_plays}")
    
    # Add momentum field to plays that don't have it
    plays_missing_momentum = plays_collection.count_documents({"momentum": {"$exists": False}})
    if plays_missing_momentum > 0:
        result = plays_collection.update_many(
            {"momentum": {"$exists": False}},
            {"$set": {"momentum": 0}}
        )
        print(f"  ✅ Added 'momentum: 0' to {result.modified_count} play(s)")
    else:
        print(f"  ✓ All plays already have 'momentum' field")
    
    # Verify plays
    plays_with_momentum = plays_collection.count_documents({"momentum": {"$exists": True}})
    print(f"  📊 Verification: {plays_with_momentum}/{total_plays} plays have 'momentum' field")
    
    # ============================================================
    # DEFENSES COLLECTION
    # ============================================================
    print("\n🛡️  Processing DEFENSES collection...")
    
    # Count total defenses
    total_defenses = defenses_collection.count_documents({})
    print(f"  Total defenses in collection: {total_defenses}")
    
    # Add momentum field to defenses that don't have it
    defenses_missing_momentum = defenses_collection.count_documents({"momentum": {"$exists": False}})
    if defenses_missing_momentum > 0:
        result = defenses_collection.update_many(
            {"momentum": {"$exists": False}},
            {"$set": {"momentum": 0}}
        )
        print(f"  ✅ Added 'momentum: 0' to {result.modified_count} defense(s)")
    else:
        print(f"  ✓ All defenses already have 'momentum' field")
    
    # Verify defenses
    defenses_with_momentum = defenses_collection.count_documents({"momentum": {"$exists": True}})
    print(f"  📊 Verification: {defenses_with_momentum}/{total_defenses} defenses have 'momentum' field")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print("✅ Update complete!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Plays: {total_plays} total, {plays_with_momentum} with momentum field")
    print(f"  Defenses: {total_defenses} total, {defenses_with_momentum} with momentum field")
    
    # Show sample play and defense
    print("\n📋 Sample play (first play in collection):")
    sample_play = plays_collection.find_one({}, {"name": 1, "effectiveness": 1, "cloaking": 1, "momentum": 1})
    if sample_play:
        print(f"  Name: {sample_play.get('name', 'N/A')}")
        print(f"  Effectiveness: {sample_play.get('effectiveness', 'MISSING')}")
        print(f"  Cloaking: {sample_play.get('cloaking', 'MISSING')}")
        print(f"  Momentum: {sample_play.get('momentum', 'MISSING')}")
    
    print("\n🛡️  Sample defense (first defense in collection):")
    sample_defense = defenses_collection.find_one({}, {"name": 1, "effectiveness": 1, "cloaking": 1, "momentum": 1})
    if sample_defense:
        print(f"  Name: {sample_defense.get('name', 'N/A')}")
        print(f"  Effectiveness: {sample_defense.get('effectiveness', 'MISSING')}")
        print(f"  Cloaking: {sample_defense.get('cloaking', 'MISSING')}")
        print(f"  Momentum: {sample_defense.get('momentum', 'MISSING')}")

if __name__ == "__main__":
    add_momentum_field()

