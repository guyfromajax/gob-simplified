
import os
import json
from uuid import uuid4
from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player

# Load all JSON files in /teams directory
directory = "./teams"
for filename in os.listdir(directory):
    if not filename.endswith(".json") or filename.startswith("."):
        continue

    path = os.path.join(directory, filename)
    with open(path, "r") as f:
        team_data = json.load(f)

    team_name = team_data["name"]

    # Insert team ONLY if it doesn't already exist
    existing_team = teams_collection.find_one({"name": team_name})
    if existing_team:
        print(f"⚠️ Team '{team_name}' already exists. Skipping.")
        continue

    player_docs = []
    player_ids = []

    for raw_player in team_data["players"]:
        player_obj = Player(raw_player)
        player_id = str(uuid4())
        player_data = {
            "_id": player_id,
            "first_name": player_obj.first_name,
            "last_name": player_obj.last_name,
            "team": player_obj.team,
            "attributes": player_obj.attributes,
            "stats": player_obj.stats,
            "metadata": player_obj.metadata
        }
        player_ids.append(player_id)
        player_docs.append(player_data)

    # Insert team with player_ids
    teams_collection.insert_one({
        "name": team_name,
        "player_ids": player_ids
    })

    # Insert all players
    players_collection.insert_many(player_docs)
    print(f"✅ Inserted team: {team_name} with {len(player_docs)} players")

print("🎉 All teams and players loaded successfully.")
