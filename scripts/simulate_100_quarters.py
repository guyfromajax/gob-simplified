#!/usr/bin/env python3
"""
Simulate 100 quarters with two random teams and track turn statistics.
"""

import random
import statistics
import sys
import os
from io import StringIO

# Disable debug output for faster simulation
os.environ["DISABLE_DEBUG"] = "1"

# Suppress print statements during simulation
class SuppressOutput:
    def __init__(self):
        self.stdout = StringIO()
    
    def __enter__(self):
        self.original_stdout = sys.stdout
        sys.stdout = self.stdout
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        return False

from BackEnd.db import teams_collection
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter

def simulate_quarters(num_quarters=20):
    """Simulate specified number of quarters and track turn statistics."""
    
    # Get two random teams
    all_teams = list(teams_collection.find({}))
    if len(all_teams) < 2:
        print("❌ Error: Need at least 2 teams in the database")
        return
    
    selected_teams = random.sample(all_teams, 2)
    home_team_name = selected_teams[0]["name"]
    away_team_name = selected_teams[1]["name"]
    
    print(f"🏀 Simulating {num_quarters} quarters with:")
    print(f"   Home: {home_team_name}")
    print(f"   Away: {away_team_name}")
    print(f"   Starting simulation...\n")
    
    turns_per_quarter = []
    
    # Simulate quarters
    for q_num in range(1, num_quarters + 1):
        # Create a new game manager for each quarter (fresh state)
        gm = GameManager(home_team_name, away_team_name)
        gm.quarter = 1  # Always simulate as Q1 to get consistent behavior
        
        # Get initial turn count before simulation
        initial_turns = len(gm.turns)
        
        # Simulate the quarter (suppress verbose output)
        try:
            with SuppressOutput():
                simulate_quarter(gm)
            
            # Calculate number of turns in this quarter
            # simulate_quarter modifies gm.turns in place, so check the length after
            turns_in_quarter = len(gm.turns) - initial_turns
            turns_per_quarter.append(turns_in_quarter)
            
            if q_num % 5 == 0 or q_num == num_quarters:
                print(f"   ✅ Completed {q_num}/{num_quarters} quarters... (avg turns: {statistics.mean(turns_per_quarter):.1f})")
        except Exception as e:
            print(f"   ⚠️ Error in quarter {q_num}: {e}")
            # Continue with next quarter
            continue
    
    # Calculate statistics
    if not turns_per_quarter:
        print("❌ Error: No quarters completed successfully")
        return
    
    avg_turns = statistics.mean(turns_per_quarter)
    median_turns = statistics.median(turns_per_quarter)
    max_turns = max(turns_per_quarter)
    min_turns = min(turns_per_quarter)
    
    # Print results
    print(f"\n{'='*60}")
    print(f"📊 RESULTS: {num_quarters} Quarter Simulation")
    print(f"{'='*60}")
    print(f"Teams: {home_team_name} vs {away_team_name}")
    print(f"")
    print(f"Average turns per quarter: {avg_turns:.2f}")
    print(f"Median turns per quarter:  {median_turns:.2f}")
    print(f"Highest turns in a quarter: {max_turns}")
    print(f"Lowest turns in a quarter:  {min_turns}")
    print(f"{'='*60}")
    
    return {
        "average": avg_turns,
        "median": median_turns,
        "highest": max_turns,
        "lowest": min_turns,
        "turns_per_quarter": turns_per_quarter
    }

if __name__ == "__main__":
    import sys
    num_quarters = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    simulate_quarters(num_quarters)

