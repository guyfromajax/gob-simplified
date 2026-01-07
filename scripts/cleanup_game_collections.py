#!/usr/bin/env python3
"""
Cleanup Game-Specific Collections

This script safely deletes all entries from game-specific collections:
- tournaments
- franchises  
- games

These collections are game-specific (not universal) and can be safely cleared
to remove outdated data structures. The collections themselves are kept.

WARNING: This will delete ALL tournament, franchise, and game data!
Only run this if you want to start fresh.
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("❌ MONGO_URI not found in environment variables")
    print("   Set MONGO_URI in .env file or export it")
    exit(1)

# Connect to MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client["gob"]  # Your database name
    
    print("🔗 Connected to MongoDB")
    print(f"📊 Database: {db.name}")
    print()
    
    # Collections to clean
    collections_to_clean = {
        "tournaments": "Tournament mode documents",
        "franchises": "Franchise mode documents", 
        "games": "Single Game mode documents"
    }
    
    # Show current counts
    print("📈 Current collection counts:")
    for collection_name, description in collections_to_clean.items():
        count = db[collection_name].count_documents({})
        print(f"   {collection_name:15} - {count:4} documents ({description})")
    print()
    
    # Confirm deletion
    total_docs = sum(db[coll].count_documents({}) for coll in collections_to_clean.keys())
    if total_docs == 0:
        print("✅ All collections are already empty. Nothing to delete.")
        exit(0)
    
    print(f"⚠️  WARNING: This will delete {total_docs} documents across 3 collections!")
    print()
    response = input("Type 'DELETE' to confirm: ")
    
    if response != "DELETE":
        print("❌ Deletion cancelled")
        exit(0)
    
    print()
    print("🗑️  Deleting documents...")
    
    # Delete all documents from each collection
    deleted_counts = {}
    for collection_name in collections_to_clean.keys():
        result = db[collection_name].delete_many({})
        deleted_counts[collection_name] = result.deleted_count
        print(f"   ✅ {collection_name:15} - Deleted {result.deleted_count} documents")
    
    print()
    print("✅ Cleanup complete!")
    print()
    print("📊 Final collection counts:")
    for collection_name in collections_to_clean.keys():
        count = db[collection_name].count_documents({})
        print(f"   {collection_name:15} - {count:4} documents")
    
    print()
    print("✅ Collections are now empty and ready for fresh data")
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

