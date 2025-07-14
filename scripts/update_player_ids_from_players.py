from BackEnd.db import teams_collection, players_collection

for team in teams_collection.find({}):
    name = team.get("name")
    player_cursor = players_collection.find({"team": name})
    player_ids = [p["_id"] for p in player_cursor]
    teams_collection.update_one(
        {"_id": team["_id"]},
        {"$set": {"player_ids": player_ids}}
    )
    print(f"✅ Updated {name} with {len(player_ids)} player_ids")
