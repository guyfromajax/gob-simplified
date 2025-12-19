#!/usr/bin/env python3
"""
Script to simulate 10 full games and track HCO turn statistics.

This script:
1. Simulates 10 full games using the actual game engine code
2. Tracks all HCO turns and their results
3. Provides cumulative statistics for HCO outcomes
"""

import sys
import os

# Add parent directory to path to import BackEnd modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.models.game_manager import GameManager
from BackEnd.utils.db_utils import build_lineup_from_mongo
from BackEnd.db import teams_collection
from BackEnd.main import simulate_quarter
import logging

# Disable verbose logging for cleaner output
logging.basicConfig(level=logging.ERROR)

def load_team_attributes_from_universal(team_name):
    """Load team attributes from the universal teams collection."""
    team_doc = teams_collection.find_one({"name": team_name})
    if not team_doc:
        return None
    
    attrs = {}
    for key in ["shot_threshold", "turnover_modifier", "foul_modifier",
               "rebound_modifier", "momentum_score", "offensive_efficiency",
               "team_chemistry", "defensive_efficiency", "fb_efficiency",
               "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier"]:
        if key in team_doc:
            attrs[key] = team_doc[key]
    
    return attrs if attrs else None

def run_hco_statistics_test():
    """Simulate 10 full games and track HCO turn statistics."""
    
    # Load team attributes from database (matching prototype behavior)
    print("🏀 Loading team data from database...")
    home_attrs = load_team_attributes_from_universal("Morristown")
    away_attrs = load_team_attributes_from_universal("Four Corners")
    
    if home_attrs:
        print(f"   ✅ Loaded Morristown attributes: {len(home_attrs)} attributes")
    else:
        print(f"   ⚠️  No attributes found for Morristown, using random defaults")
    
    if away_attrs:
        print(f"   ✅ Loaded Four Corners attributes: {len(away_attrs)} attributes")
    else:
        print(f"   ⚠️  No attributes found for Four Corners, using random defaults")
    
    # Initialize statistics tracking
    stats = {
        "HCO Results": {
            "Shot Attempt": 0,
            "O_FOUL": 0,
            "D_FOUL (non-shooting)": 0,
            "DEAD_BALL_TURNOVER": 0,
            "STEAL": 0
        },
        "Shot Attempts": 0,
        "Shooting Fouls": 0,
        "Fouls + Made Shots (AND-1)": 0,
        "Total HCO Turns": 0,
        "Total Games": 0,
        "Total Turns": 0
    }
    
    print("\n🎯 Simulating 20 full games...")
    print("=" * 60)
    
    # Simulate 20 full games
    for game_num in range(1, 21):
        print(f"\n📊 Game {game_num}/10...")
        
        # Initialize game with Morristown and Four Corners, using loaded attributes
        gm = GameManager(
            "Morristown", 
            "Four Corners", 
            mode="single",
            home_team_attributes=home_attrs,
            away_team_attributes=away_attrs
        )
        
        # Set initial lineups (autoset)
        gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
        gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)
        
        # Execute opening tip
        gm.setup_opening_tip()
        
        # Simulate all 4 quarters
        for quarter in range(1, 5):
            gm.quarter = quarter
            
            # Store turns before this quarter
            turns_before = len(gm.turns)
            
            # Simulate the quarter
            simulate_quarter(
                gm,
                home_lineup_ids=None,  # Use autoset lineups
                away_lineup_ids=None,  # Use autoset lineups
                game_id=None,
                start_with_inbound=False,
                starting_possession=None,
                turn_by_turn_mode=False,
                resume_from_timeout=False
            )
            
            # Process turns from this quarter
            turns_this_quarter = gm.turns[turns_before:]
            
            for turn in turns_this_quarter:
                stats["Total Turns"] += 1
                
                # Check if this was an HCO turn
                current_turn = turn.get("current_turn", "")
                
                if current_turn == "HCO":
                    stats["Total HCO Turns"] += 1
                    
                    # Track HCO result type
                    result_type = turn.get("result_type", "")
                    
                    # Track HCO outcomes
                    if result_type in ["MAKE", "MISS"]:
                        # Shot attempt
                        stats["HCO Results"]["Shot Attempt"] += 1
                        stats["Shot Attempts"] += 1
                        
                        # Shooting foul detected if:
                        # 1. next_play_type is FREE_THROW (indicates shooting foul)
                        # 2. next_turn is FREE_THROW (copied from next_play_type in turn_manager)
                        # 3. free_throws_remaining > 0 (stored in turn dict for shooting fouls)
                        # 4. has_and_one is True (explicit AND-1 flag)
                        # 5. foul_player_id is present (shooting foul indicator)
                        next_play_type = turn.get("next_play_type", "")
                        next_turn = turn.get("next_turn", "")
                        free_throws_remaining = turn.get("free_throws_remaining", 0)
                        has_and_one = turn.get("has_and_one", False)
                        foul_player_id = turn.get("foul_player_id")
                        foul_team = turn.get("foul_team", "")
                        
                        is_shooting_foul = (
                            next_play_type == "FREE_THROW" or 
                            next_turn == "FREE_THROW" or
                            free_throws_remaining > 0 or 
                            has_and_one or
                            (foul_player_id and foul_team == "DEFENSE")
                        )
                        
                        if is_shooting_foul:
                            stats["Shooting Fouls"] += 1
                            if result_type == "MAKE":
                                # AND-1: Made shot + foul
                                stats["Fouls + Made Shots (AND-1)"] += 1
                                # Debug: Print first few AND-1 instances with full turn data
                                if stats["Fouls + Made Shots (AND-1)"] <= 5:
                                    print(f"   🎯 AND-1 DETECTED #{stats['Fouls + Made Shots (AND-1)']}:")
                                    print(f"      result_type={result_type}, next_play_type={next_play_type}, next_turn={next_turn}")
                                    print(f"      has_and_one={has_and_one}, free_throws_remaining={free_throws_remaining}")
                                    print(f"      foul_player_id={foul_player_id}, foul_team={foul_team}")
                                    print(f"      Turn keys: {list(turn.keys())}")
                        
                        # Debug: Check for made shots that might have shooting fouls
                        if result_type == "MAKE" and stats["Fouls + Made Shots (AND-1)"] < 5:
                            # Check if next turn is FREE_THROW (shooting foul indicator)
                            next_turn_check = turn.get("next_turn", "")
                            if next_turn_check == "FREE_THROW" and not is_shooting_foul:
                                print(f"   ⚠️  MISSED AND-1: result_type={result_type}, next_turn={next_turn_check}")
                                print(f"      next_play_type={next_play_type}, has_and_one={has_and_one}")
                                print(f"      foul_player_id={foul_player_id}, foul_team={foul_team}")
                                print(f"      Turn keys: {list(turn.keys())}")
                    
                    elif result_type == "FOUL":
                        # Foul result - check foul_team to determine O_FOUL vs D_FOUL
                        foul_team = turn.get("foul_team") or gm.game_state.get("foul_team")
                        next_play_type = turn.get("next_play_type", "")
                        free_throws_remaining = turn.get("free_throws_remaining", 0)
                
                        if foul_team == "OFFENSE":
                            stats["HCO Results"]["O_FOUL"] += 1
                        elif foul_team == "DEFENSE":
                            # Check if it's a shooting foul (next_play_type would be FREE_THROW)
                            if next_play_type == "FREE_THROW" or free_throws_remaining > 0:
                                # Shooting foul - also counts as shot attempt
                                stats["Shooting Fouls"] += 1
                                stats["HCO Results"]["Shot Attempt"] += 1
                                stats["Shot Attempts"] += 1
                            else:
                                # Non-shooting foul
                                stats["HCO Results"]["D_FOUL (non-shooting)"] += 1
                        else:
                            # Fallback: check if it's a shooting foul
                            if next_play_type == "FREE_THROW" or free_throws_remaining > 0:
                                # Likely a shooting foul
                                stats["Shooting Fouls"] += 1
                                stats["HCO Results"]["Shot Attempt"] += 1
                                stats["Shot Attempts"] += 1
                            else:
                                # Non-shooting foul (default to defensive)
                                stats["HCO Results"]["D_FOUL (non-shooting)"] += 1
                    
                    elif result_type == "DEAD_BALL_TURNOVER" or result_type == "DEAD BALL":
                        stats["HCO Results"]["DEAD_BALL_TURNOVER"] += 1
                    
                    elif result_type == "TURNOVER":
                        # Check if this is a steal or dead ball turnover
                        # Steals have stealer_id or stealer, dead ball turnovers have turnover_player
                        if turn.get("stealer_id") or turn.get("stealer") or turn.get("stealer_name"):
                            # This is a steal
                            stats["HCO Results"]["STEAL"] += 1
                        elif turn.get("turnover_player") or turn.get("turnover_player_id"):
                            # This is a dead ball turnover
                            stats["HCO Results"]["DEAD_BALL_TURNOVER"] += 1
                        else:
                            # Check text for clues
                            text = turn.get("text", "").lower()
                            if "steal" in text or "steals" in text or "jumps the pass" in text:
                                stats["HCO Results"]["STEAL"] += 1
                            else:
                                # Default to dead ball turnover if unclear
                                stats["HCO Results"]["DEAD_BALL_TURNOVER"] += 1
                    
                    elif result_type == "STEAL":
                        stats["HCO Results"]["STEAL"] += 1
        
        stats["Total Games"] += 1
        if game_num % 10 == 0:
            print(f"   Game {game_num} complete: {stats['Total HCO Turns']} HCO turns so far")
    
    # Print final statistics
    print("\n" + "=" * 60)
    print("📊 CUMULATIVE STATISTICS (200 HCO Turns)")
    print("=" * 60)
    
    print("\n🎯 HCO Results Breakdown:")
    total_hco_results = sum(stats["HCO Results"].values())
    for result_type, count in stats["HCO Results"].items():
        percentage = (count / total_hco_results * 100) if total_hco_results > 0 else 0
        print(f"   {result_type:30s}: {count:4d} ({percentage:5.2f}%)")
    
    print(f"\n   Total HCO Results: {total_hco_results}")
    
    print("\n🏀 Shot Attempts:")
    print(f"   Total Shot Attempts: {stats['Shot Attempts']}")
    
    print("\n🚨 Foul Statistics:")
    print(f"   Shooting Fouls: {stats['Shooting Fouls']}")
    print(f"   Fouls + Made Shots (AND-1): {stats['Fouls + Made Shots (AND-1)']}")
    
    print(f"\n📈 Total Statistics:")
    print(f"   Total Turns Processed: {stats['Total Turns']}")
    print(f"   Total HCO Turns: {stats['Total HCO Turns']}")
    print(f"   Total Games Simulated: {stats['Total Games']}")
    print(f"   HCO Turns per Game: {stats['Total HCO Turns'] / stats['Total Games']:.1f}" if stats['Total Games'] > 0 else "   HCO Turns per Game: N/A")
    
    # Calculate percentages for HCO results
    print("\n📊 HCO Results Percentages:")
    if total_hco_results > 0:
        for result_type, count in stats["HCO Results"].items():
            percentage = (count / total_hco_results * 100)
            print(f"   {result_type:30s}: {percentage:5.2f}%")
    
    # Calculate shot attempt percentage
    if stats["Total Turns"] > 0:
        shot_percentage = (stats["Shot Attempts"] / stats["Total Turns"] * 100)
        print(f"\n   Shot Attempt Rate: {shot_percentage:.2f}% of all turns")
    
    # Calculate shooting foul rate
    if stats["Shot Attempts"] > 0:
        shooting_foul_rate = (stats["Shooting Fouls"] / stats["Shot Attempts"] * 100)
        print(f"   Shooting Foul Rate: {shooting_foul_rate:.2f}% of shot attempts")
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    run_hco_statistics_test()

