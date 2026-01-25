#!/usr/bin/env python3
"""Check box_score in completed game documents"""

import sys
import json

API_URL = "https://gob-simplified-staging.up.railway.app"
game_ids = ["69765e7c8ac29c15aa48eb76", "69765faeddedbc5e0a126c1e", "69765fb2ddedbc5e0a126c1f"]

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("Checking box_score in completed games...")
print()

for game_id in game_ids:
    print(f"Game: {game_id}")
    game = fetch_json(f"{API_URL}/api/game/{game_id}")
    
    if "error" in game:
        print(f"   ❌ Error: {game['error']}")
        continue
    
    print(f"   Quarter: {game.get('quarter', 'N/A')}")
    print(f"   Is Final: {game.get('is_final', 'N/A')}")
    
    box_score = game.get("box_score", {})
    if not box_score:
        print(f"   ❌ No box_score!")
        continue
    
    print(f"   Teams: {list(box_score.keys())}")
    
    total_pts = 0
    total_fgm = 0
    total_3ptm = 0
    
    for team_name, team_box in box_score.items():
        if not isinstance(team_box, dict):
            continue
        
        team_pts = 0
        team_fgm = 0
        team_3ptm = 0
        
        for pos, player_data in team_box.items():
            if isinstance(player_data, dict):
                pts = player_data.get("PTS", 0)
                fgm = player_data.get("FGM", 0)
                tpm = player_data.get("3PTM", 0) or player_data.get("TPM", 0)
                
                team_pts += pts
                team_fgm += fgm
                team_3ptm += tpm
        
        total_pts += team_pts
        total_fgm += team_fgm
        total_3ptm += team_3ptm
        
        print(f"      {team_name}: PTS={team_pts}, FGM={team_fgm}, 3PTM={team_3ptm}")
    
    print(f"   Total: PTS={total_pts}, FGM={total_fgm}, 3PTM={total_3ptm}")
    
    if total_pts == 0:
        print(f"   ⚠️  WARNING: All stats are zero in box_score!")
    print()

