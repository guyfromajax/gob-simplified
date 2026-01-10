#!/usr/bin/env python3
"""
Clone Reference Data to Staging Database

This script copies reference/static collections from the 'gob' database to 'gob-staging'.
Reference collections (needed for the app to function):
- players (team rosters)
- teams (team info, colors, etc.)
- plays (offensive plays)
- defenses (defensive plays)
- fcp_skeletons (animation skeletons)
- hct_skeletons (animation skeletons)

This does NOT copy:
- games (game documents - staging should start fresh)
- tournaments (tournament documents - staging should start fresh)
- franchises (franchise documents - staging should start fresh)
- training_sessions (training logs - staging should start fresh)
- franchise_state (deprecated - not needed)

Usage:
    python scripts/clone_reference_data_to_staging.py
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables
load_dotenv()

# Get connection strings
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ MONGO_URI not found in environment variables")
    print("   Set MONGO_URI in .env file or export it")
    sys.exit(1)

# Reference collections to clone (static/reference data)
REFERENCE_COLLECTIONS = [
    "players",
    "teams", 
    "plays",
    "defenses",
    "fcp_skeletons",
    "hct_skeletons"
]

# Collections to skip (game/tournament/franchise specific data - start fresh)
SKIP_COLLECTIONS = [
    "games",
    "tournaments",
    "franchises",
    "training_sessions",
    "franchise_state"
]

def clone_collection(source_db, dest_db, collection_name):
    """Clone a collection from source to destination database."""
    source_collection = source_db[collection_name]
    dest_collection = dest_db[collection_name]
    
    # Count existing documents
    source_count = source_collection.count_documents({})
    dest_count = dest_collection.count_documents({})
    
    print(f"\n📋 Cloning collection: {collection_name}")
    print(f"   Source ({source_db.name}): {source_count} documents")
    print(f"   Destination ({dest_db.name}): {dest_count} documents (will be overwritten)")
    
    if source_count == 0:
        print(f"   ⚠️  WARNING: Source collection is empty - skipping")
        return {"cloned": 0, "skipped": 0, "error": "Source empty"}
    
    # Clear destination collection (start fresh)
    if dest_count > 0:
        result = dest_collection.delete_many({})
        print(f"   🗑️  Cleared {result.deleted_count} existing documents from destination")
    
    # Clone all documents
    try:
        documents = list(source_collection.find({}))
        if documents:
            dest_collection.insert_many(documents)
            print(f"   ✅ Cloned {len(documents)} documents successfully")
            return {"cloned": len(documents), "skipped": 0, "error": None}
        else:
            print(f"   ⚠️  WARNING: No documents to clone")
            return {"cloned": 0, "skipped": 0, "error": "No documents"}
    except Exception as e:
        print(f"   ❌ ERROR cloning collection: {str(e)}")
        return {"cloned": 0, "skipped": 0, "error": str(e)}

def main():
    print("=" * 60)
    print("Clone Reference Data to Staging Database")
    print("=" * 60)
    print()
    print("This script will:")
    print("  ✅ Clone reference collections from 'gob' → 'gob-staging':")
    for col in REFERENCE_COLLECTIONS:
        print(f"     - {col}")
    print("  ❌ Skip game-specific collections (will start fresh):")
    for col in SKIP_COLLECTIONS:
        print(f"     - {col}")
    print()
    
    # Confirm
    response = input("Continue? (yes/no): ").strip().lower()
    if response != "yes":
        print("❌ Cancelled")
        sys.exit(0)
    
    print()
    print("🔗 Connecting to MongoDB...")
    
    try:
        # Connect to MongoDB (using same cluster, different database names)
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        
        # Access source and destination databases
        source_db = client["gob"]
        dest_db = client["gob-staging"]
        
        # Verify source database exists and has data
        print(f"📊 Source database: {source_db.name}")
        print(f"📊 Destination database: {dest_db.name} (will be created if needed)")
        print()
        
        # Check which collections exist in source
        source_collections = source_db.list_collection_names()
        print(f"📋 Collections found in source: {len(source_collections)}")
        for col in source_collections:
            count = source_db[col].count_documents({})
            status = "✅ Will clone" if col in REFERENCE_COLLECTIONS else "⏸️  Will skip" if col in SKIP_COLLECTIONS else "❓ Unknown (will skip)"
            print(f"   {col:20} - {count:4} documents - {status}")
        print()
        
        # Clone each reference collection
        results = {}
        total_cloned = 0
        errors = []
        
        for collection_name in REFERENCE_COLLECTIONS:
            if collection_name in source_collections:
                result = clone_collection(source_db, dest_db, collection_name)
                results[collection_name] = result
                total_cloned += result["cloned"]
                if result["error"]:
                    errors.append(f"{collection_name}: {result['error']}")
            else:
                print(f"\n⚠️  WARNING: Collection '{collection_name}' not found in source database - skipping")
                results[collection_name] = {"cloned": 0, "skipped": 0, "error": "Collection not found"}
                errors.append(f"{collection_name}: Collection not found")
        
        # Summary
        print()
        print("=" * 60)
        print("CLONING SUMMARY")
        print("=" * 60)
        print(f"✅ Successfully cloned: {total_cloned} documents across {len([r for r in results.values() if r['cloned'] > 0])} collections")
        print(f"❌ Errors: {len(errors)}")
        
        if errors:
            print("\nErrors encountered:")
            for error in errors:
                print(f"   - {error}")
        
        print()
        print("📋 Next steps:")
        print("1. Update Railway staging MONGO_URI to point to gob-staging database")
        print("   Format: mongodb+srv://user:pass@cluster.mongodb.net/gob-staging?retryWrites=true&w=majority")
        print("2. Or set MONGO_DB_NAME=gob-staging in Railway environment variables")
        print("3. Redeploy staging backend to use new database")
        print("4. Test staging backend connects to gob-staging database")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

