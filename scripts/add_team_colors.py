from BackEnd.db import teams_collection

# Define your team color mappings
team_colors = {
    "BENTLEY-TRUMAN": {
        "primary_color": "#4066b2",
        "secondary_color": "#9b9b9b"
    },
    "LANCASTER": {
        "primary_color": "#d24a1b",
        "secondary_color": "#cccccc"
    },
    "FOUR_CORNERS": {
        "primary_color": "#c0976a",
        "secondary_color": "#00954b"
    },
    "OCEAN_CITY": {
        "primary_color": "#2a2168",
        "secondary_color": "#00a89d"
    },
    "MORRISTOWN": {
        "primary_color": "#ec1d28",
        "secondary_color": "#cccccc"
    },
    "LITTLE_YORK": {
        "primary_color": "#65308e",
        "secondary_color": "#f6af38"
    },
    "XAVIEN": {
        "primary_color": "#016837",
        "secondary_color": "#999999"
    },
    "SOUTH_LANCASTER": {
        "primary_color": "#7c2b24",
        "secondary_color": "#e39649"
    }
}

# Loop through and update each team in Mongo
for team_id, colors in team_colors.items():
    result = teams_collection.update_one(
        {"team_id": team_id},
        {"$set": colors}
    )
    print(f"✅ Updated {team_id} → matched: {result.matched_count}, modified: {result.modified_count}")
