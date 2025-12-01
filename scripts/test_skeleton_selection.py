"""
Test script to verify FCP and HCT skeleton selection from MongoDB.
Tests that only non-empty versions are selected for random choice.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection
from BackEnd.engine.phase_resolution import get_fcp_skeleton, get_hct_skeleton

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def test_skeleton_selection():
    """Test skeleton selection for FCP and HCT"""
    
    print("=" * 60)
    print("Testing FCP Skeleton Selection")
    print("=" * 60)
    
    # Test all FCP result types
    fcp_result_types = ["O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"]
    
    for result_type in fcp_result_types:
        print(f"\n📋 Testing FCP skeleton for result_type: {result_type}")
        try:
            skeleton = get_fcp_skeleton(result_type, game_context=None)
            if skeleton and skeleton.get("steps"):
                print(f"  ✅ Successfully retrieved skeleton with {len(skeleton['steps'])} steps")
            else:
                print(f"  ⚠️  Retrieved skeleton but it has no steps (fell back to hardcoded)")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Testing HCT Skeleton Selection")
    print("=" * 60)
    
    # Test all HCT result types
    hct_result_types = ["O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"]
    
    for result_type in hct_result_types:
        print(f"\n📋 Testing HCT skeleton for result_type: {result_type}")
        try:
            skeleton = get_hct_skeleton(result_type, game_context=None)
            if skeleton and skeleton.get("steps"):
                print(f"  ✅ Successfully retrieved skeleton with {len(skeleton['steps'])} steps")
            else:
                print(f"  ⚠️  Retrieved skeleton but it has no steps (fell back to hardcoded)")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Database Structure Verification")
    print("=" * 60)
    
    # Check FCP skeleton structure
    print("\n📊 FCP Skeleton Structure:")
    fcp_skeleton = fcp_skeletons_collection.find_one({})
    if fcp_skeleton:
        print(f"  Name: {fcp_skeleton.get('name', 'N/A')}")
        variants = fcp_skeleton.get("variants", {})
        print(f"  Variants: {list(variants.keys())}")
        for variant_name, variant_data in variants.items():
            versions = variant_data.get("versions", [])
            non_empty = sum(1 for v in versions if v.get("steps") and len(v.get("steps", [])) > 0)
            print(f"    {variant_name}: {non_empty}/{len(versions)} versions have steps")
    else:
        print("  ⚠️  No FCP skeleton found in database")
    
    # Check HCT skeleton structure
    print("\n📊 HCT Skeleton Structure:")
    hct_skeleton = hct_skeletons_collection.find_one({})
    if hct_skeleton:
        print(f"  Name: {hct_skeleton.get('name', 'N/A')}")
        variants = hct_skeleton.get("variants", {})
        print(f"  Variants: {list(variants.keys())}")
        for variant_name, variant_data in variants.items():
            versions = variant_data.get("versions", [])
            non_empty = sum(1 for v in versions if v.get("steps") and len(v.get("steps", [])) > 0)
            print(f"    {variant_name}: {non_empty}/{len(versions)} versions have steps")
    else:
        print("  ⚠️  No HCT skeleton found in database")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    test_skeleton_selection()

