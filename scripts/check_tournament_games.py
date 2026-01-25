#!/usr/bin/env python3
"""Check for completed games in tournament"""

import sys
import json

API_URL = "https://gob-simplified-staging.up.railway.app"
tournament_id = "69765e76ddedbc5e0a126c1d"

def fetch_json(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

print(f"Checking tournament: {tournament_id}")
print()

# Get tournament state to see bracket
state = fetch_json(f"{API_URL}/tournament/state?tournament_id={tournament_id}")
if "error" in state:
    print(f"❌ Error: {state['error']}")
    sys.exit(1)

bracket = state.get("bracket", {})
print(f"Tournament rounds: {list(bracket.keys())}")

# Check round1 for completed games
round1 = bracket.get("round1", [])
print(f"\nRound 1 matches: {len(round1)}")

completed = 0
for i, match in enumerate(round1):
    winner = match.get("winner")
    score = match.get("score", {})
    game_id = match.get("game_id")
    
    if winner:
        completed += 1
        print(f"  Match {i+1}: {match.get('home_team')} vs {match.get('away_team')}")
        print(f"    Winner: {winner}")
        print(f"    Score: {score}")
        print(f"    Game ID: {game_id}")
        
        if game_id:
            # Check if game is final
            game = fetch_json(f"{API_URL}/api/game/{game_id}")
            if "error" not in game:
                is_final = game.get("is_final", False)
                quarter = game.get("quarter", "?")
                print(f"    Game quarter: {quarter}, is_final: {is_final}")
                
                if not is_final:
                    print(f"    ⚠️  WARNING: Game is not marked as final!")

print(f"\nCompleted matches: {completed}/{len(round1)}")

