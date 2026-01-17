# scripts/update_staging_position_ratings.py
# Recalculates position ratings for all players in gob-staging database
# Position ratings are calculated from player attributes and height

import os
import sys

# Set database name to gob-staging BEFORE importing db module
os.environ["MONGO_DB_NAME"] = "gob-staging"

# Make BackEnd importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import players_collection, DB_NAME
from BackEnd.utils.position_ratings import compute_position_ratings

# Verify we're using the staging database
if "staging" not in DB_NAME.lower():
    raise SystemExit(f"❌ ERROR: Script is configured for 'gob-staging' database, but DB_NAME is '{DB_NAME}'. "
                     f"Please ensure MONGO_DB_NAME is set to 'gob-staging'.")

print(f"📊 Using database: {DB_NAME}")
print(f"🔄 Recalculating position ratings from updated attributes...\n")

scanned = updated = 0

# Pull minimal fields; compute_position_ratings reads what it needs
for doc in players_collection.find({}, {"team": 1, "first_name": 1, "last_name": 1, "attributes": 1, "height": 1}):
    scanned += 1
    ratings = compute_position_ratings(doc)  # returns dict with PG/SG/SF/PF/C, ints 1..100

    res = players_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"position_ratings": ratings}}
    )

    name = f"{doc.get('first_name','?')} {doc.get('last_name','?')}"
    team = doc.get("team", "?")
    if res.modified_count:
        updated += 1
        print(f"✅ UPDATED: {team} — {name} -> {ratings}")
    else:
        print(f"✓ OK: {team} — {name} (no change)")

print(f"\n{'='*80}")
print(f"📊 SUMMARY")
print(f"{'='*80}")
print(f"Database: {DB_NAME}")
print(f"Players scanned: {scanned}")
print(f"Position ratings updated: {updated}")
print(f"Players with no changes: {scanned - updated}")
print(f"{'='*80}\n")

