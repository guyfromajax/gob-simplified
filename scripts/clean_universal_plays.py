"""
Clean universal plays collection by removing game_stats and season_stats.
Universal plays should only contain: _id, name, play_type, play_focus, skeletons
"""
from BackEnd.db import plays_collection

def clean_universal_plays():
    """Remove game_stats and season_stats from all plays in universal collection."""
    result = plays_collection.update_many(
        {},
        {
            "$unset": {
                "game_stats": "",
                "season_stats": ""
            }
        }
    )
    
    print(f"✅ Cleaned {result.modified_count} plays in universal collection")
    print(f"   Removed game_stats and season_stats fields")
    
    # Verify
    sample = plays_collection.find_one()
    if sample:
        print(f"\n📋 Sample play structure after cleanup:")
        print(f"   Fields: {list(sample.keys())}")
        print(f"   Name: {sample.get('name')}")
        print(f"   Has game_stats: {'game_stats' in sample}")
        print(f"   Has season_stats: {'season_stats' in sample}")

if __name__ == "__main__":
    clean_universal_plays()

