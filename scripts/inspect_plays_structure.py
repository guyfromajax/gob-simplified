#!/usr/bin/env python3
"""
Script to pull all plays from MongoDB and save them to a file for inspection.
This helps understand the current play structure before brainstorming motion offense changes.
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path for BackEnd imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

def get_db():
    """Get MongoDB database connection."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return client["gob"]

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def main():
    print("🔍 Fetching all plays from MongoDB...")
    
    db = get_db()
    plays_collection = db["plays"]
    
    # Get all plays
    plays = list(plays_collection.find({}))
    
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
    output_file = Path(__file__).parent.parent / "docs" / "current_plays_structure.json"
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

