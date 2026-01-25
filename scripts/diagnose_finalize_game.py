#!/usr/bin/env python3
"""Diagnose why finalize_game() isn't saving stats"""

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

print("Diagnosing finalize_game() issue...")
print()

game = fetch_json(f"{API_URL}/api/game/{game_id}")

print("Game document structure:")
print(f"  Has 'box_score' at top level: {'box_score' in game}")
print(f"  Has 'home_team': {'home_team' in game}")
print(f"  Has 'away_team': {'away_team' in game}")
print()

# Check top-level box_score
if "box_score" in game:
    box_score = game["box_score"]
    print(f"Top-level box_score: {list(box_score.keys())}")
    if box_score:
        team_name = list(box_score.keys())[0]
        team_box = box_score[team_name]
        if isinstance(team_box, dict):
            print(f"  Sample team '{team_name}': {len(team_box)} players")
            sample_pos = list(team_box.keys())[0]
            sample_player = team_box[sample_pos]
            if isinstance(sample_player, dict):
                print(f"  Sample player at '{sample_pos}':")
                print(f"    playerId: {sample_player.get('playerId')}")
                print(f"    PTS: {sample_player.get('PTS')}")
                print(f"    FGM: {sample_player.get('FGM')}")
                print(f"    3PTM: {sample_player.get('3PTM')}")
else:
    print("No top-level box_score found")
    print()

# Check nested box_score
home_team = game.get("home_team", {})
away_team = game.get("away_team", {})

if isinstance(home_team, dict) and "box_score" in home_team:
    print(f"Nested home_team.box_score: {list(home_team.get('box_score', {}).keys())[:5]}")
if isinstance(away_team, dict) and "box_score" in away_team:
    print(f"Nested away_team.box_score: {list(away_team.get('box_score', {}).keys())[:5]}")

print()
print("Simulating finalize_game() extraction logic...")

# Simulate the extraction logic from finalize_game()
box_score_extracted = game.get("box_score", {})
if not box_score_extracted:
    if isinstance(home_team, dict) and "box_score" in home_team:
        home_team_name = home_team.get("name")
        if home_team_name:
            box_score_extracted[home_team_name] = home_team.get("box_score", {})
    if isinstance(away_team, dict) and "box_score" in away_team:
        away_team_name = away_team.get("name")
        if away_team_name:
            box_score_extracted[away_team_name] = away_team.get("box_score", {})

print(f"Extracted box_score: {list(box_score_extracted.keys())}")

if box_score_extracted:
    total_players = 0
    players_with_stats = 0
    
    for team_name, team_box in box_score_extracted.items():
        if not isinstance(team_box, dict):
            continue
        
        for pos, player_data in team_box.items():
            if not isinstance(player_data, dict):
                continue
            
            total_players += 1
            pid = player_data.get("playerId")
            if not pid:
                continue
            
            # Simulate _clean_stat_block
            cleaned_stats = {}
            for stat, val in player_data.items():
                if stat == "name":
                    continue
                if isinstance(val, (int, float)) and val >= 0:
                    cleaned_stats[stat] = val
            
            if cleaned_stats:
                players_with_stats += 1
                if players_with_stats <= 3:
                    print(f"  {player_data.get('name', 'Unknown')} ({pos}): {len(cleaned_stats)} stats")
                    print(f"    Sample: PTS={cleaned_stats.get('PTS', 0)}, FGM={cleaned_stats.get('FGM', 0)}")
    
    print()
    print(f"Total players processed: {total_players}")
    print(f"Players with stats: {players_with_stats}")
    
    if players_with_stats == 0:
        print("\n⚠️  WARNING: No players have stats after cleaning!")
        print("   This would cause inc_doc to be empty in finalize_game()")
    else:
        print(f"\n✅ {players_with_stats} players have stats - inc_doc should have {players_with_stats * len(cleaned_stats)} increments")

