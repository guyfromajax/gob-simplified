#!/usr/bin/env python3
"""
Script to remove the final step from all version 0 variants in Standard HCT and FCP skeletons.
This fixes the duplicate final steps caused by the "Finish Variant & Save" button auto-saving.
"""

import sys
import os

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_db():
    """Get MongoDB database connection."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return client["gob"]

def remove_final_step(collection_name, skeleton_name="Standard"):
    """Remove the final step from all version 0 variants in a skeleton."""
    db = get_db()
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
        result = collection.update_one(
            {"_id": skeleton_doc["_id"]},
            {"$set": {"variants": variants}}
        )
        
        print(f"\n{'='*80}")
        print(f"✅ Updated {collection_name}: {result.modified_count} document(s) modified")
        print(f"📝 Modified {len(modified_variants)} variant(s):")
        for variant_name in modified_variants:
            print(f"  - {variant_name}")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"ℹ️ No variants needed modification")
        print(f"{'='*80}")

if __name__ == "__main__":
    print("🔧 Removing duplicate final steps from FCP and HCT skeletons...")
    print("\n⚠️ WARNING: This will modify the MongoDB database!")
    
    # Check for --confirm flag
    if "--confirm" not in sys.argv:
        print("\n❌ Please run with --confirm flag to proceed:")
        print("   python3 scripts/remove_duplicate_final_steps.py --confirm")
        sys.exit(1)
    
    print("\n✅ Proceeding with removal...")
    
    # Remove duplicates from FCP skeletons
    remove_final_step("fcp_skeletons", "Standard")
    
    # Remove duplicates from HCT skeletons
    remove_final_step("hct_skeletons", "Standard")
    
    print("\n✅ All duplicate final steps removed!")
    print("🎯 You can now rebuild any skeletons that need different final steps")

