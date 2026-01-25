#!/usr/bin/env python3
"""Check if box_score has per-player stats"""

import sys
import json

API_URL = "https://gob-simplified-staging.up.railway.app"
game_id = "69765e7c8ac29c15aa48eb76"

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("Checking per-player stats in box_score...")
print()

game = fetch_json(f"{API_URL}/api/game/{game_id}")
box_score = game.get("box_score", {})

if not box_score:
    home_team = game.get("home_team", {})
    away_team = game.get("away_team", {})
    if isinstance(home_team, dict) and "box_score" in home_team:
        box_score[home_team.get("name")] = home_team.get("box_score", {})
    if isinstance(away_team, dict) and "box_score" in away_team:
        box_score[away_team.get("name")] = away_team.get("box_score", {})

players_with_stats = 0
players_with_nonzero = 0

for team_name, team_box in box_score.items():
    print(f"Team: {team_name}")
    if not isinstance(team_box, dict):
        continue
    
    for pos, player_data in team_box.items():
        if not isinstance(player_data, dict):
            continue
        
        pid = player_data.get("playerId")
        name = player_data.get("name", "Unknown")
        pts = player_data.get("PTS", 0)
        fgm = player_data.get("FGM", 0)
        tpm = player_data.get("3PTM", 0) or player_data.get("TPM", 0)
        
        if pts > 0 or fgm > 0 or tpm > 0:
            players_with_nonzero += 1
            if players_with_nonzero <= 5:
                print(f"   {name} ({pos}): PTS={pts}, FGM={fgm}, 3PTM={tpm}")
        
        if pts > 0 or fgm > 0:
            players_with_stats += 1

print()
print(f"Players with stats: {players_with_stats}")
print(f"Players with non-zero stats: {players_with_nonzero}")

if players_with_nonzero == 0:
    print("\n⚠️  WARNING: All player stats in box_score are zero!")
    print("   This would cause inc_doc to be empty in finalize_game()")

