#!/usr/bin/env python3
"""
Script to pull and display version 0 of STEAL skeletons for FCP and HCT.
"""

import sys
import os

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient
from dotenv import load_dotenv
import json

load_dotenv()

def get_db():
    """Get MongoDB database connection."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return client["gob"]

def check_steal_skeleton(collection_name, skeleton_name="Standard"):
    """Display STEAL skeleton structure."""
    db = get_db()
    collection = db[collection_name]
    
    print(f"\n{'='*80}")
    print(f"{collection_name.upper()} - {skeleton_name} - STEAL variant")
    print(f"{'='*80}")
    
    # Find the skeleton document
    skeleton_doc = collection.find_one({"name": skeleton_name})
    
    if not skeleton_doc:
        print(f"❌ No skeleton found with name '{skeleton_name}'")
        return
    
    print(f"✅ Found skeleton: _id={skeleton_doc['_id']}")
    
    variants = skeleton_doc.get('variants', {})
    steal_variant = variants.get('steal')
    
    if not steal_variant:
        print(f"❌ No 'steal' variant found")
        return
    
    versions = steal_variant.get('versions', [])
    if not versions or len(versions) == 0:
        print(f"❌ No versions in steal variant")
        return
    
    version_0 = versions[0]
    steps = version_0.get('steps', [])
    
    if not steps:
        print(f"❌ No steps in version 0")
        return
    
    print(f"\n📊 STEAL variant - Version 0 has {len(steps)} steps")
    print(f"\n{'='*80}")
    
    for step_idx, step in enumerate(steps):
        print(f"\n📍 STEP {step_idx} (timestamp: {step.get('timestamp', 0)}ms):")
        pos_actions = step.get('pos_actions', {})
        
        for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            if pos in pos_actions:
                action_data = pos_actions[pos]
                location = action_data.get('location', 'N/A')
                action = action_data.get('action', 'N/A')
                has_ball = action_data.get('has_ball', False)
                opp = action_data.get('opp', False)
                
                print(f"  {pos}: location={location:20s} action={action:12s} has_ball={has_ball!s:5s} opp={opp!s:5s}")
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS:")
    print(f"  - Total steps: {len(steps)}")
    print(f"  - Final step index: {len(steps) - 1}")
    
    # Check if last two steps are identical
    if len(steps) >= 2:
        last = steps[-1]
        second_last = steps[-2]
        
        same = True
        for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            last_action = last.get('pos_actions', {}).get(pos, {})
            second_action = second_last.get('pos_actions', {}).get(pos, {})
            
            if (last_action.get('location') != second_action.get('location') or
                last_action.get('action') != second_action.get('action') or
                last_action.get('opp') != second_action.get('opp')):
                same = False
                break
        
        if same:
            print(f"  ❌ WARNING: Last 2 steps are IDENTICAL (duplicate detected)")
        else:
            print(f"  ✅ Last 2 steps are different")
    
    # Check if any step has a 'receive' or 'steal' action
    has_receive = False
    has_steal_action = False
    for step in steps:
        for pos, action_data in step.get('pos_actions', {}).items():
            if action_data.get('action') == 'receive':
                has_receive = True
            if action_data.get('action') == 'steal':
                has_steal_action = True
    
    print(f"  - Contains 'receive' action: {has_receive}")
    print(f"  - Contains 'steal' action: {has_steal_action}")
    print(f"  - Expected: Skeleton should end BEFORE steal (no receive in final step)")
    print(f"{'='*80}")

if __name__ == "__main__":
    print("🔍 Checking STEAL skeletons for FCP and HCT...")
    
    check_steal_skeleton("fcp_skeletons", "Standard")
    check_steal_skeleton("hct_skeletons", "Standard")
    
    print("\n✅ Analysis complete!")

