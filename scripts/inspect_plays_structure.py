#!/usr/bin/env python3
"""
Script to pull all plays from MongoDB and save them to a file for inspection.
This helps understand the current play structure before brainstorming motion offense changes.
"""

import sys
import argparse
import json
from pathlib import Path

from bson import ObjectId

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "current_plays_structure.json")
    args = parser.parse_args()
    print("🔍 Fetching all plays from MongoDB...")
    connection = connect_migration_target(args.db, write=False)
    try:
        plays = list(connection.database["plays"].find({}))
    finally:
        connection.close()
    
    print(f"✅ Found {len(plays)} plays")
    
    # Convert to JSON-serializable format
    plays_data = []
    for play in plays:
        play_dict = {}
        for key, value in play.items():
            if isinstance(value, ObjectId):
                play_dict[key] = str(value)
            else:
                play_dict[key] = value
        plays_data.append(play_dict)
    
    # Save to file
    output_file = args.output
    with open(output_file, 'w') as f:
        json.dump(plays_data, f, indent=2, default=json_serial)
    
    print(f"💾 Saved to: {output_file}")
    
    # Print summary
    print("\n📊 Play Summary:")
    print("-" * 60)
    for play in plays_data:
        print(f"Name: {play.get('name', 'N/A')}")
        print(f"  Type: {play.get('play_type', 'N/A')}")
        print(f"  Focus: {play.get('play_focus', 'N/A')}")
        
        # Check skeleton structure
        skeletons = play.get('skeletons', {})
        if skeletons:
            print(f"  Skeletons: {list(skeletons.keys())}")
            # Check if variants have versions
            for variant_name, variant_data in skeletons.items():
                if isinstance(variant_data, dict) and 'versions' in variant_data:
                    versions = variant_data.get('versions', {})
                    print(f"    {variant_name}: {len(versions)} versions ({list(versions.keys())})")
                elif isinstance(variant_data, dict) and 'steps' in variant_data:
                    steps_count = len(variant_data.get('steps', []))
                    print(f"    {variant_name}: {steps_count} steps")
                else:
                    print(f"    {variant_name}: {type(variant_data)}")
        else:
            print(f"  Skeletons: None")
        
        print()

if __name__ == "__main__":
    main()
