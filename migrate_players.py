
import os
import json
from uuid import uuid4
from BackEnd.db import teams_collection, players_collection
from BackEnd.models.player import Player

# 🧹 Step 1: Clear the players collection
# players_collection.delete_many({})
# print("🧹 Cleared existing players from database.")

# ✅ Step 2: Loop through each team in the teams collection
teams = teams_collection.find({})
for team in teams:
    team_name = team.get("name", "Unnamed Team")
    player_data_list = team.get("players", [])
    
    if not player_data_list:
        print(f"⚠️ No embedded player data found for team '{team_name}'. Skipping...")
        continue

    player_docs = []

    # 🔁 Step 3: For each player, generate a valid Player object and collect it
    for p_data in player_data_list:
        try:
            player_obj = Player(p_data)
            player_docs.append({
                "_id": str(uuid4()),
                "first_name": player_obj.first_name,
                "last_name": player_obj.last_name,
                "name": player_obj.name,
                "team": player_obj.team,
                "attributes": player_obj.attributes,
                "stats": player_obj.stats,
                "metadata": player_obj.metadata
            })
        except Exception as e:
            print(f"❌ Error creating player from team '{team_name}': {e}")

    if player_docs:
        players_collection.insert_many(player_docs)
        print(f"✅ Migrated {len(player_docs)} players from team '{team_name}'")

print("🎉 All players successfully migrated.")
