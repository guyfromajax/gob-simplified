#!/usr/bin/env python3
"""
Script to analyze FCP and HCT HCO skeletons for PG opp value issue.
The final step has PG with opp=False, but animates on wrong side (as if opp=True).
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

def analyze_hco_skeleton(collection_name, skeleton_name="Standard"):
    """Analyze HCO variant skeleton for PG opp values."""
    db = get_db()
    collection = db[collection_name]
    
    print(f"\n{'='*80}")
    print(f"{collection_name.upper()} - {skeleton_name} - HCO variant")
    print(f"{'='*80}")
    
    # Find the skeleton document
    skeleton_doc = collection.find_one({"name": skeleton_name})
    
    if not skeleton_doc:
        print(f"❌ No skeleton found with name '{skeleton_name}'")
        return
    
    variants = skeleton_doc.get('variants', {})
    hco_variant = variants.get('hco')
    
    if not hco_variant:
        print(f"❌ No 'hco' variant found")
        return
    
    versions = hco_variant.get('versions', [])
    if not versions or len(versions) == 0:
        print(f"❌ No versions in hco variant")
        return
    
    version_0 = versions[0]
    steps = version_0.get('steps', [])
    
    if not steps:
        print(f"❌ No steps in version 0")
        return
    
    print(f"\n📊 HCO variant - Version 0 has {len(steps)} steps")
    print(f"\n{'='*80}")
    print(f"PG opp VALUE PROGRESSION:")
    print(f"{'='*80}")
    
    pg_opp_values = []
    
    for step_idx, step in enumerate(steps):
        pos_actions = step.get('pos_actions', {})
        pg_action = pos_actions.get('PG')
        
        if pg_action:
            location = pg_action.get('location', 'N/A')
            action = pg_action.get('action', 'N/A')
            opp = pg_action.get('opp', False)
            coords = pg_action.get('coords', 'N/A')
            
            pg_opp_values.append(opp)
            
            marker = ""
            if step_idx == len(steps) - 1:
                marker = " ← FINAL STEP (ISSUE HERE)"
            elif step_idx > 0 and opp != pg_opp_values[step_idx - 1]:
                marker = f" ← OPP CHANGED from {pg_opp_values[step_idx - 1]} to {opp}"
            
            print(f"\nSTEP {step_idx}: PG opp={opp!s:5s} location={location:20s} action={action:12s}{marker}")
            if coords != 'N/A':
                print(f"         coords={coords}")
        else:
            print(f"\nSTEP {step_idx}: PG not in this step")
    
    # Analysis
    print(f"\n{'='*80}")
    print(f"ANALYSIS:")
    print(f"{'='*80}")
    
    # Check if opp changes
    opp_changes = []
    for i in range(1, len(pg_opp_values)):
        if pg_opp_values[i] != pg_opp_values[i-1]:
            opp_changes.append(f"  Step {i-1} ({pg_opp_values[i-1]}) → Step {i} ({pg_opp_values[i]})")
    
    if opp_changes:
        print(f"\n🔍 PG opp VALUE CHANGES DETECTED:")
        for change in opp_changes:
            print(change)
    else:
        print(f"\n✅ PG opp value is CONSISTENT across all steps (always {pg_opp_values[0] if pg_opp_values else 'N/A'})")
    
    # Check final step
    if pg_opp_values:
        final_opp = pg_opp_values[-1]
        print(f"\n📍 FINAL STEP PG opp={final_opp}")
        if final_opp:
            print(f"   ⚠️ UNEXPECTED: Final step has opp=True (should be False for receiving on offensive side)")
        else:
            print(f"   ✅ EXPECTED: Final step has opp=False (receiving on offensive side)")
            print(f"   ❌ BUG: Animates on WRONG side despite opp=False!")
    
    # Show all steps details
    print(f"\n{'='*80}")
    print(f"FULL SKELETON STRUCTURE:")
    print(f"{'='*80}")
    
    for step_idx, step in enumerate(steps):
        print(f"\nSTEP {step_idx} (timestamp: {step.get('timestamp', 0)}ms):")
        pos_actions = step.get('pos_actions', {})
        
        for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            if pos in pos_actions:
                action_data = pos_actions[pos]
                location = action_data.get('location', 'N/A')
                action = action_data.get('action', 'N/A')
                opp = action_data.get('opp', False)
                coords = action_data.get('coords', 'N/A')
                
                opp_marker = " ← OPP!" if opp else ""
                print(f"  {pos}: location={location:20s} action={action:12s} opp={opp!s:5s}{opp_marker}")

if __name__ == "__main__":
    print("🔍 Analyzing HCO skeletons for PG opp value issue...")
    
    analyze_hco_skeleton("fcp_skeletons", "Standard")
    analyze_hco_skeleton("hct_skeletons", "Standard")
    
    print("\n✅ Analysis complete!")

