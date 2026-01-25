#!/usr/bin/env python3
"""Check player ID matching between box_score and tournament.players"""

import sys
import json

API_URL = "https://gob-simplified-staging.up.railway.app"
tournament_id = "69765e76ddedbc5e0a126c1d"
game_id = "69765e7c8ac29c15aa48eb76"

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("Checking player ID matching...")
print()

# Get tournament players
tournament = fetch_json(f"{API_URL}/tournament/state?tournament_id={tournament_id}")
tournament_players = tournament.get("players", {})
print(f"Tournament players: {len(tournament_players)}")
tournament_player_ids = set(tournament_players.keys())
print(f"Sample tournament player IDs: {list(tournament_player_ids)[:5]}")
print()

# Get game box_score
game = fetch_json(f"{API_URL}/api/game/{game_id}")
box_score = game.get("box_score", {})

if not box_score:
    # Try nested structure
    home_team = game.get("home_team", {})
    away_team = game.get("away_team", {})
    if isinstance(home_team, dict) and "box_score" in home_team:
        box_score[home_team.get("name")] = home_team.get("box_score", {})
    if isinstance(away_team, dict) and "box_score" in away_team:
        box_score[away_team.get("name")] = away_team.get("box_score", {})

print(f"Box score teams: {list(box_score.keys())}")
print()

box_score_player_ids = set()
for team_name, team_box in box_score.items():
    if not isinstance(team_box, dict):
        continue
    for pos, player_data in team_box.items():
        if isinstance(player_data, dict):
            pid = player_data.get("playerId")
            if pid:
                box_score_player_ids.add(str(pid))

print(f"Box score player IDs: {len(box_score_player_ids)}")
print(f"Sample box_score player IDs: {list(box_score_player_ids)[:5]}")
print()

# Check matching
matching = tournament_player_ids & box_score_player_ids
missing = box_score_player_ids - tournament_player_ids

print(f"Matching IDs: {len(matching)}/{len(box_score_player_ids)}")
print(f"Missing in tournament: {len(missing)}")

if missing:
    print(f"\n⚠️  WARNING: {len(missing)} players from box_score are NOT in tournament.players!")
    print(f"Sample missing IDs: {list(missing)[:5]}")
    print("\nThis would prevent stats from being saved!")
else:
    print("\n✅ All box_score player IDs exist in tournament.players")

