# scripts/update_player_position_ratings.py
# Adds a {"PG":..,"SG":..,"SF":..,"PF":..,"C":..} dict to each player doc as position_ratings

import os, sys
from pathlib import Path

# Make BackEnd importable (same pattern as your other scripts)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.db import players_collection  # uses your existing DB wiring
from BackEnd.utils.position_ratings import compute_position_ratings  # built earlier

scanned = updated = 0

# Pull minimal fields just for logs; compute_position_ratings reads what it needs
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
        print(f"SET: {team} — {name} -> {ratings}")
    else:
        print(f"OK:  {team} — {name} (no change)")

print("\n— done —")
print(f"players scanned: {scanned}   updated: {updated}")
