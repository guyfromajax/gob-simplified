import os
from dotenv import load_dotenv

# 👇 Load .env file
load_dotenv()

# 👇 Import the already-configured collection
from BackEnd.db import teams_collection  # or wherever it's defined

def update_team_ids():
    for team in teams_collection.find():
        name = team["name"]
        team_id = name.upper().replace(" ", "_")

        teams_collection.update_one(
            {"_id": team["_id"]},
            {"$set": {"team_id": team_id}}
        )
        print(f"✅ Updated team_id for {name} → {team_id}")

if __name__ == "__main__":
    update_team_ids()
