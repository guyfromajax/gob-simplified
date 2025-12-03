#!/usr/bin/env python3
"""
Script to check for duplicate final steps in FCP and HCT skeleton variants.
Pulls version 0 of all variants from Standard skeletons and compares the last two steps.
"""

import sys
import os

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

def get_db():
    """Get MongoDB database connection."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return client["gob"]

def steps_are_identical(step1, step2):
    """Compare two steps to see if they're identical."""
    if not step1 or not step2:
        return False
    
    pos_actions1 = step1.get('pos_actions', {})
    pos_actions2 = step2.get('pos_actions', {})
    
    # Check if same positions exist
    if set(pos_actions1.keys()) != set(pos_actions2.keys()):
        return False
    
    # Compare each position's data
    for pos in pos_actions1.keys():
        action1 = pos_actions1[pos]
        action2 = pos_actions2[pos]
        
        # Compare location, action, and opp (ignore has_ball since it's always False in DB)
        if (action1.get('location') != action2.get('location') or
            action1.get('action') != action2.get('action') or
            action1.get('opp') != action2.get('opp')):
            return False
    
    return True

def check_skeleton(collection_name, skeleton_name="Standard"):
    """Check a skeleton for duplicate final steps in all variants."""
    db = get_db()
    collection = db[collection_name]
    
    print(f"\n{'='*80}")
    print(f"Checking {collection_name.upper()} - {skeleton_name} skeleton")
    print(f"{'='*80}")
    
    # Find the skeleton document
    skeleton_doc = collection.find_one({"name": skeleton_name})
    
    if not skeleton_doc:
        print(f"❌ No skeleton found with name '{skeleton_name}'")
        return
    
    print(f"✅ Found skeleton: _id={skeleton_doc['_id']}")
    
    variants = skeleton_doc.get('variants', {})
    print(f"📊 Total variants: {len(variants)}")
    
    duplicates_found = []
    
    for variant_name, variant_data in variants.items():
        versions = variant_data.get('versions', [])
        
        if not versions or len(versions) == 0:
            print(f"\n  ⚠️ {variant_name}: No versions")
            continue
        
        version_0 = versions[0]
        steps = version_0.get('steps', [])
        
        if not steps or len(steps) == 0:
            print(f"\n  ⚠️ {variant_name}: Version 0 has no steps")
            continue
        
        print(f"\n  📍 {variant_name}: Version 0 has {len(steps)} steps")
        
        # Check if last two steps are identical
        if len(steps) >= 2:
            last_step = steps[-1]
            second_to_last = steps[-2]
            
            if steps_are_identical(last_step, second_to_last):
                print(f"    ❌ DUPLICATE DETECTED: Last 2 steps are identical!")
                duplicates_found.append(variant_name)
                
                # Show the duplicate steps
                print(f"\n    Second-to-last step (index {len(steps)-2}):")
                for pos, action in second_to_last.get('pos_actions', {}).items():
                    print(f"      {pos}: location={action.get('location')}, action={action.get('action')}, opp={action.get('opp')}")
                
                print(f"\n    Last step (index {len(steps)-1}):")
                for pos, action in last_step.get('pos_actions', {}).items():
                    print(f"      {pos}: location={action.get('location')}, action={action.get('action')}, opp={action.get('opp')}")
            else:
                print(f"    ✅ No duplicate - last 2 steps are different")
        else:
            print(f"    ℹ️ Only {len(steps)} step(s) - cannot check for duplicates")
    
    if duplicates_found:
        print(f"\n{'='*80}")
        print(f"🚨 SUMMARY: {len(duplicates_found)} variant(s) with duplicate final steps:")
        for variant_name in duplicates_found:
            print(f"  - {variant_name}")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"✅ SUMMARY: No duplicate final steps found")
        print(f"{'='*80}")

if __name__ == "__main__":
    print("🔍 Checking FCP and HCT skeletons for duplicate final steps...")
    
    # Check FCP skeletons
    check_skeleton("fcp_skeletons", "Standard")
    
    # Check HCT skeletons
    check_skeleton("hct_skeletons", "Standard")
    
    print("\n✅ Analysis complete!")

