"""
Script to add 'opp' fields to existing FCP and HCT skeletons in MongoDB.

For FCP/HCT skeletons:
- Ball handlers (usually PG, sometimes SG) should have opp=True (they break the press on defensive side)
- Outlet players (SF, PF, C) should have opp=False (they stay on offensive side)

This script will:
1. Find all FCP and HCT skeletons
2. For each skeleton, check each step
3. Add opp=True to PG and SG positions (ball handlers)
4. Add opp=False to SF, PF, C positions (outlet players)
5. Save updated skeletons back to database
"""

import sys
import os
from pymongo import MongoClient
from bson import ObjectId
import logging

# Add the parent directory to the sys.path to allow importing from BackEnd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def add_opp_fields_to_skeleton(skeleton, skeleton_type):
    """
    Add opp fields to a skeleton document.
    
    Logic:
    - PG and SG: opp=True (ball handlers breaking press)
    - SF, PF, C: opp=False (outlet players)
    """
    updated = False
    variants = skeleton.get("variants", {})
    
    for variant_name, variant_data in variants.items():
        versions = variant_data.get("versions", [])
        
        for version_idx, version in enumerate(versions):
            steps = version.get("steps", [])
            
            for step_idx, step in enumerate(steps):
                pos_actions = step.get("pos_actions", {})
                
                for position, action_data in pos_actions.items():
                    # Skip if opp field already exists
                    if "opp" in action_data:
                        continue
                    
                    # Add opp field based on position
                    if position in ["PG", "SG"]:
                        # Ball handlers - should be on opposite side
                        action_data["opp"] = True
                        updated = True
                        logging.info(f"  Added opp=True to {position} in {variant_name} version {version_idx} step {step_idx}")
                    elif position in ["SF", "PF", "C"]:
                        # Outlet players - stay on offensive side
                        action_data["opp"] = False
                        updated = True
                        logging.info(f"  Added opp=False to {position} in {variant_name} version {version_idx} step {step_idx}")
    
    return updated

def migrate_skeletons():
    logging.info("============================================================")
    logging.info("Adding 'opp' fields to FCP and HCT skeletons")
    logging.info("============================================================")
    
    # FCP Skeletons
    logging.info("\n📝 Processing FCP skeletons...")
    fcp_skeletons = list(fcp_skeletons_collection.find({}))
    logging.info(f"Found {len(fcp_skeletons)} FCP skeletons")
    
    updated_fcp_count = 0
    for skeleton in fcp_skeletons:
        skeleton_id = str(skeleton["_id"])
        logging.info(f"\n🔍 Processing FCP skeleton: {skeleton_id} ({skeleton.get('name', 'Unnamed')})")
        
        if add_opp_fields_to_skeleton(skeleton, "FCP"):
            fcp_skeletons_collection.update_one(
                {"_id": ObjectId(skeleton_id)},
                {"$set": {"variants": skeleton["variants"]}}
            )
            logging.info(f"  ✅ Updated FCP skeleton: {skeleton_id}")
            updated_fcp_count += 1
        else:
            logging.info(f"  ⏭️  No changes needed for FCP skeleton: {skeleton_id}")
    
    logging.info(f"\n✅ FCP migration complete! Updated {updated_fcp_count} skeleton(s)")
    
    # HCT Skeletons
    logging.info("\n📝 Processing HCT skeletons...")
    hct_skeletons = list(hct_skeletons_collection.find({}))
    logging.info(f"Found {len(hct_skeletons)} HCT skeletons")
    
    updated_hct_count = 0
    for skeleton in hct_skeletons:
        skeleton_id = str(skeleton["_id"])
        logging.info(f"\n🔍 Processing HCT skeleton: {skeleton_id} ({skeleton.get('name', 'Unnamed')})")
        
        if add_opp_fields_to_skeleton(skeleton, "HCT"):
            hct_skeletons_collection.update_one(
                {"_id": ObjectId(skeleton_id)},
                {"$set": {"variants": skeleton["variants"]}}
            )
            logging.info(f"  ✅ Updated HCT skeleton: {skeleton_id}")
            updated_hct_count += 1
        else:
            logging.info(f"  ⏭️  No changes needed for HCT skeleton: {skeleton_id}")
    
    logging.info(f"\n✅ HCT migration complete! Updated {updated_hct_count} skeleton(s)")
    
    logging.info("\n============================================================")
    logging.info("🔍 Verifying migration...")
    logging.info("============================================================")
    
    # Verify FCP
    logging.info("\nFCP Skeletons:")
    for skeleton in fcp_skeletons_collection.find({}):
        opp_count = 0
        total_positions = 0
        for variant_name, variant_data in skeleton.get("variants", {}).items():
            for version in variant_data.get("versions", []):
                for step in version.get("steps", []):
                    for pos, action in step.get("pos_actions", {}).items():
                        total_positions += 1
                        if action.get("opp") is not None:
                            opp_count += 1
        status = "✅" if opp_count == total_positions and total_positions > 0 else "❌"
        logging.info(f"  {status} {str(skeleton['_id'])}: {opp_count}/{total_positions} positions have opp field")
    
    # Verify HCT
    logging.info("\nHCT Skeletons:")
    for skeleton in hct_skeletons_collection.find({}):
        opp_count = 0
        total_positions = 0
        for variant_name, variant_data in skeleton.get("variants", {}).items():
            for version in variant_data.get("versions", []):
                for step in version.get("steps", []):
                    for pos, action in step.get("pos_actions", {}).items():
                        total_positions += 1
                        if action.get("opp") is not None:
                            opp_count += 1
        status = "✅" if opp_count == total_positions and total_positions > 0 else "❌"
        logging.info(f"  {status} {str(skeleton['_id'])}: {opp_count}/{total_positions} positions have opp field")
    
    logging.info("\n✅ Migration verification complete!")

if __name__ == "__main__":
    migrate_skeletons()

