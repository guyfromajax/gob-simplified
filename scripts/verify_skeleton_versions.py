#!/usr/bin/env python3
"""
Quick script to verify skeleton versions in MongoDB.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import plays_collection

def verify_versions():
    """Check what versions exist for each variant in each play."""
    
    plays = list(plays_collection.find({}))
    print(f"🔍 Checking {len(plays)} plays in database\n")
    
    for play in plays:
        play_name = play.get("name", "Unknown")
        skeletons = play.get("skeletons", {})
        
        print(f"📊 {play_name}:")
        
        for variant_name in ["successful", "mid_play_change", "contested", "broken"]:
            variant = skeletons.get(variant_name)
            if variant:
                if "versions" in variant and isinstance(variant["versions"], list):
                    version_count = len(variant["versions"])
                    versions = [v.get("version", "?") for v in variant["versions"]]
                    print(f"  {variant_name}: {version_count} versions - {', '.join(versions)}")
                elif "steps" in variant:
                    steps_count = len(variant.get("steps", []))
                    print(f"  {variant_name}: direct steps format ({steps_count} steps)")
                else:
                    print(f"  {variant_name}: empty")
            else:
                print(f"  {variant_name}: not found")
        print()

if __name__ == "__main__":
    verify_versions()

