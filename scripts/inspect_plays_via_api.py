#!/usr/bin/env python3
"""
Script to pull all plays from MongoDB and save them to a file.
Tries direct MongoDB connection using BackEnd.db module.
"""

import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Fallback: Try to use BackEnd.db directly."""
    import sys
    import os
    from pathlib import Path
    
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    try:
        from BackEnd.db import plays_collection
        from bson import ObjectId
        
        print("🔍 Fetching all plays from MongoDB directly...")
        
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
            json.dump(plays_data, f, indent=2, default=str)
        
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
                    if isinstance(variant_data, dict):
                        if 'versions' in variant_data:
                            versions = variant_data.get('versions', {})
                            print(f"    {variant_name}: {len(versions)} versions ({list(versions.keys())})")
                        elif 'steps' in variant_data:
                            steps_count = len(variant_data.get('steps', []))
                            print(f"    {variant_name}: {steps_count} steps")
                        else:
                            print(f"    {variant_name}: {type(variant_data)} (no steps/versions)")
                    else:
                        print(f"    {variant_name}: {type(variant_data)}")
            else:
                print(f"  Skeletons: None")
            
            print()
            
    except ImportError as e:
        print(f"❌ Could not import BackEnd.db: {e}")
        print("💡 Suggestion: Make sure you're running this from the project root")
        print("   and that local MongoDB is configured in repo-root .env.local")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")

if __name__ == "__main__":
    main()
