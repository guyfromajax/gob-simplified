from BackEnd.db import teams_collection, players_collection

for team_doc in teams_collection.find({}):
    team_name = team_doc["name"]
    players = players_collection.find({"team": team_name})
    player_ids = [p["_id"] for p in players]
    
    result = teams_collection.update_one(
        {"_id": team_doc["_id"]},
        {"$set": {"player_ids": player_ids}}
    )

    print(f"Updated {team_name} with {len(player_ids)} player_ids.")
