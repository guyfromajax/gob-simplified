from BackEnd.db import teams_collection

# Mascot mapping
MASCOTS = {
    "Bentley-Truman": "Sterling Knights",
    "Lancaster": "Johnnies",
    "Four Corners": "Harvest",
    "Ocean City": "Admirals",
    "Morristown": "Pirates",
    "Little York": "Minute Men",
    "Xavien": "Elm Trees",
    "South Lancaster": "Bulldogs"
}

def add_mascots():
    """Add mascot field to teams in universal teams collection."""
    for team_name, mascot in MASCOTS.items():
        result = teams_collection.update_one(
            {"name": team_name},
            {"$set": {"mascot": mascot}}
        )
        if result.modified_count > 0:
            print(f"✅ Added mascot '{mascot}' to {team_name}")
        elif result.matched_count > 0:
            print(f"ℹ️  {team_name} already has mascot")
        else:
            print(f"⚠️  Team {team_name} not found in database")

if __name__ == "__main__":
    add_mascots()

