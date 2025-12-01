"""
Script to check if opp fields are present in FCP and HCT skeletons in MongoDB.

This will help verify where opp fields should be located in the document structure.
"""

import sys
import os
from pymongo import MongoClient
from bson import ObjectId
import json

# Add the parent directory to the sys.path to allow importing from BackEnd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection

def check_skeleton_opp_fields(skeleton, skeleton_type):
    """Check if opp fields exist in a skeleton and show their location."""
    print(f"\n{'='*60}")
    print(f"Checking {skeleton_type} skeleton: {skeleton.get('name', 'Unnamed')} (ID: {skeleton['_id']})")
    print(f"{'='*60}")
    
    variants = skeleton.get("variants", {})
    
    for variant_name, variant_data in variants.items():
        versions = variant_data.get("versions", [])
        
        if not versions:
            continue
            
        print(f"\n  Variant: {variant_name}")
        print(f"    Versions: {len(versions)}")
        
        for version_idx, version in enumerate(versions):
            steps = version.get("steps", [])
            
            if not steps:
                continue
                
            print(f"\n    Version {version_idx}:")
            print(f"      Steps: {len(steps)}")
            
            # Check first step for opp fields
            first_step = steps[0]
            pos_actions = first_step.get("pos_actions", {})
            
            print(f"\n      First step (timestamp: {first_step.get('timestamp', 'N/A')}):")
            for position in ["PG", "SG", "SF", "PF", "C"]:
                action = pos_actions.get(position)
                if action:
                    has_opp = "opp" in action
                    opp_value = action.get("opp", "N/A")
                    location = action.get("location", "N/A")
                    action_type = action.get("action", "N/A")
                    print(f"        {position}: location={location}, action={action_type}, opp={opp_value} {'✅' if has_opp else '❌ MISSING'}")

def check_all_skeletons():
    print("="*60)
    print("Checking FCP Skeletons")
    print("="*60)
    
    fcp_skeletons = list(fcp_skeletons_collection.find({}))
    print(f"Found {len(fcp_skeletons)} FCP skeletons")
    
    for skeleton in fcp_skeletons:
        check_skeleton_opp_fields(skeleton, "FCP")
    
    print("\n" + "="*60)
    print("Checking HCT Skeletons")
    print("="*60)
    
    hct_skeletons = list(hct_skeletons_collection.find({}))
    print(f"Found {len(hct_skeletons)} HCT skeletons")
    
    for skeleton in hct_skeletons:
        check_skeleton_opp_fields(skeleton, "HCT")
    
    print("\n" + "="*60)
    print("Document Structure Example")
    print("="*60)
    print("""
The opp field should be located at:
variants.{variant_name}.versions[{version_index}].steps[{step_index}].pos_actions.{position}.opp

Example path for PG in first step of hco variant, version 0:
variants.hco.versions[0].steps[0].pos_actions.PG.opp

Full document structure:
{
  "_id": ObjectId("..."),
  "name": "...",
  "variants": {
    "hco": {
      "versions": [
        {
          "steps": [
          {
            "timestamp": 0,
            "pos_actions": {
              "PG": {
                "location": "key",
                "action": "handle_ball",
                "opp": true  <-- HERE
              },
              "SG": {
                "location": "upper wing",
                "action": "stationary",
                "opp": false  <-- HERE
              },
              ...
            }
          }
        ]
      }
    }
  }
}
""")

if __name__ == "__main__":
    check_all_skeletons()

