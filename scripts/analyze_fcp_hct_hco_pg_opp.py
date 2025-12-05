#!/usr/bin/env python3
"""
Analyze FCP and HCT HCO variant skeletons to diagnose PG opp field issue.

The issue: When FCP/HCT breaks to HCO, the final step shows PG receiving a pass
on the wrong side of the court (opp side when it should be offense side).

This script:
1. Pulls HCT and FCP skeletons (HCO variant, version 0) from MongoDB
2. Analyzes the opp field for PG in each step
3. Traces through apply_opposite_side_logic to see how coords are calculated
4. Compares with animator.py logic to identify discrepancies
"""

import sys
import os
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

# Import after setting up path
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.engine.phase_resolution import apply_opposite_side_logic

def analyze_skeleton_steps(skeleton_data, skeleton_type, variant_name="hco"):
    """Analyze each step of a skeleton to check PG opp field and coordinate calculations."""
    print(f"\n{'='*80}")
    print(f"Analyzing {skeleton_type.upper()} skeleton - {variant_name.upper()} variant")
    print(f"{'='*80}\n")
    
    if not skeleton_data or "steps" not in skeleton_data:
        print(f"❌ No steps found in skeleton")
        return
    
    steps = skeleton_data["steps"]
    print(f"Total steps: {len(steps)}\n")
    
    # Analyze each step
    for step_idx, step in enumerate(steps):
        timestamp = step.get("timestamp", 0)
        pos_actions = step.get("pos_actions", {})
        
        print(f"--- Step {step_idx} (timestamp: {timestamp}) ---")
        
        # Check PG specifically
        pg_action = pos_actions.get("PG")
        if pg_action:
            location = pg_action.get("location") or pg_action.get("spot", "N/A")
            opp = pg_action.get("opp", False)
            has_ball = pg_action.get("has_ball", False)
            coords = pg_action.get("coords")
            
            # Get expected coords from location
            expected_coords = HCO_STRING_SPOTS.get(location, None)
            
            print(f"  PG:")
            print(f"    location: {location}")
            print(f"    opp: {opp}")
            print(f"    has_ball: {has_ball}")
            print(f"    coords in skeleton: {coords}")
            print(f"    expected coords from location: {expected_coords}")
            
            # Check if this is the final step
            is_final = step_idx == len(steps) - 1
            if is_final:
                print(f"    ⚠️ FINAL STEP - PG should be on offense side (opp=False)")
                if opp:
                    print(f"    ❌ PROBLEM: opp=True in final step!")
                else:
                    print(f"    ✅ opp=False (correct)")
            
            # Check all positions for context
            print(f"  All positions in step:")
            for pos, action in pos_actions.items():
                pos_opp = action.get("opp", False)
                pos_has_ball = action.get("has_ball", False)
                pos_location = action.get("location") or action.get("spot", "N/A")
                print(f"    {pos}: opp={pos_opp}, has_ball={pos_has_ball}, location={pos_location}")
        
        print()
    
    # Now simulate apply_opposite_side_logic for both home and away offense
    print(f"\n{'='*80}")
    print("Simulating apply_opposite_side_logic()")
    print(f"{'='*80}\n")
    
    for is_away_offense in [False, True]:
        offense_side = "AWAY" if is_away_offense else "HOME"
        print(f"\n--- {offense_side} team on offense ---")
        
        # Apply the logic
        modified_skeleton = apply_opposite_side_logic(skeleton_data.copy(), is_away_offense)
        
        # Check final step PG
        if modified_skeleton and "steps" in modified_skeleton:
            final_step = modified_skeleton["steps"][-1]
            final_pg = final_step.get("pos_actions", {}).get("PG")
            
            if final_pg:
                # Get original from first step for comparison
                original_step = skeleton_data["steps"][-1]
                original_pg = original_step.get("pos_actions", {}).get("PG", {})
                original_location = original_pg.get("location") or original_pg.get("spot", "N/A")
                original_opp = original_pg.get("opp", False)
                final_coords = final_pg.get("coords")
                final_location = final_pg.get("location") or final_pg.get("spot", "N/A")
                final_opp = final_pg.get("opp", False)
                
                print(f"  Final step PG:")
                print(f"    Original: location={original_location}, opp={original_opp}")
                print(f"    After apply_opposite_side_logic: coords={final_coords}, location={final_location}, opp={final_opp}")
                
                # Check if coords are on wrong side
                if final_coords:
                    x = final_coords.get("x", 50)
                    # For home offense, offense side is x > 50, defense side is x < 50
                    # For away offense, offense side is x < 50, defense side is x > 50
                    if is_away_offense:
                        is_on_offense_side = x < 50
                        expected_side = "offense side (x < 50)"
                    else:
                        is_on_offense_side = x > 50
                        expected_side = "offense side (x > 50)"
                    
                    print(f"    x={x}, on offense side: {is_on_offense_side} (expected: {expected_side})")
                    
                    if not is_on_offense_side:
                        print(f"    ❌ PROBLEM: PG is on defense side when should be on offense side!")
                    else:
                        print(f"    ✅ PG is on correct side")

def get_skeleton_from_db(collection_name, skeleton_name="Standard", variant_name="hco", version_idx=0):
    """Get a specific skeleton from MongoDB."""
    db = get_db()
    collection = db[collection_name]
    skeleton_doc = collection.find_one({"name": skeleton_name})
    
    if not skeleton_doc:
        print(f"❌ Skeleton '{skeleton_name}' not found")
        return None
    
    variants = skeleton_doc.get("variants", {})
    variant_data = variants.get(variant_name)
    
    if not variant_data:
        print(f"❌ Variant '{variant_name}' not found")
        return None
    
    versions = variant_data.get("versions", [])
    
    if version_idx >= len(versions):
        print(f"❌ Version {version_idx} not found (only {len(versions)} versions)")
        return None
    
    version = versions[version_idx]
    steps = version.get("steps", [])
    
    if not steps:
        print(f"❌ Version {version_idx} has no steps")
        return None
    
    return {"steps": steps}

def main():
    print("="*80)
    print("FCP/HCT HCO Variant PG opp Field Analysis")
    print("="*80)
    
    # Get FCP skeleton
    print("\n📦 Fetching FCP skeleton...")
    fcp_skeleton = get_skeleton_from_db(
        "fcp_skeletons",
        skeleton_name="Standard",
        variant_name="hco",
        version_idx=0
    )
    
    if fcp_skeleton:
        analyze_skeleton_steps(fcp_skeleton, "FCP", "hco")
    else:
        print("❌ Failed to fetch FCP skeleton")
    
    # Get HCT skeleton
    print("\n📦 Fetching HCT skeleton...")
    hct_skeleton = get_skeleton_from_db(
        "hct_skeletons",
        skeleton_name="Standard",
        variant_name="hco",
        version_idx=0
    )
    
    if hct_skeleton:
        analyze_skeleton_steps(hct_skeleton, "HCT", "hco")
    else:
        print("❌ Failed to fetch HCT skeleton")
    
    print("\n" + "="*80)
    print("Analysis complete")
    print("="*80)

if __name__ == "__main__":
    main()

