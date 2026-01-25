#!/usr/bin/env python3
"""Quick script to check if game document exists and has box_score"""

import sys
import json
from urllib.parse import urlencode

API_URL = "https://gob-simplified-staging.up.railway.app"
game_id = "69765e7c8ac29c15aa48eb76"

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

print(f"Checking game document: {game_id}")
print(f"API: {API_URL}/api/game/{game_id}")
print()

game = fetch_json(f"{API_URL}/api/game/{game_id}")

if "error" in game:
    print(f"❌ Error: {game['error']}")
else:
    print("✅ Game document found")
    print(f"   Quarter: {game.get('quarter', 'N/A')}")
    print(f"   Is Final: {game.get('is_final', 'N/A')}")
    print(f"   Has box_score: {'box_score' in game}")
    
    box_score = game.get("box_score", {})
    if box_score:
        print(f"   Teams in box_score: {list(box_score.keys())}")
        for team_name, team_box in box_score.items():
            player_count = len(team_box) if isinstance(team_box, dict) else 0
            print(f"      {team_name}: {player_count} players")
            if player_count > 0:
                # Check first player for stats
                first_pos = list(team_box.keys())[0]
                first_player = team_box[first_pos]
                if isinstance(first_player, dict):
                    pts = first_player.get("PTS", 0)
                    fgm = first_player.get("FGM", 0)
                    print(f"         Sample player stats: PTS={pts}, FGM={fgm}")
    else:
        print("   ⚠️  No box_score in game document!")

