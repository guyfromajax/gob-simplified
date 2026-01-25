#!/usr/bin/env python3
"""
Diagnostic script to check TCC stats population issue

This script queries the database to check:
1. If stats are saved in tournament document
2. If finalize_game was called (check applied_games)
3. If box_score exists in game documents
4. Player ID matching between roster and tournament

Usage:
    python3 scripts/diagnose_tcc_stats.py [tournament_id]
    
If tournament_id is not provided, it will list all tournaments and let you choose.
"""

import os
import sys

# Add BackEnd to path to use existing imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Now import from BackEnd (which has bson/pymongo)
from BackEnd.db import tournaments_collection, games_collection
from bson import ObjectId

print("🔗 Using BackEnd database connection")
print()


def get_tournament_id():
    """Get tournament ID from command line or prompt user"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    # List all tournaments
    tournaments = list(tournaments_collection.find({}, {"name": 1, "current_round": 1, "created_at": 1}).sort("created_at", -1).limit(10))
    
    if not tournaments:
        print("❌ No tournaments found in database")
        sys.exit(1)
    
    print("📋 Available tournaments:")
    for i, t in enumerate(tournaments):
        name = t.get("name", "Unnamed")
        round_num = t.get("current_round", "?")
        print(f"   {i+1}. {name} (Round {round_num}) - ID: {t['_id']}")
    
    print()
    choice = input("Enter tournament number (1-10) or paste tournament ID: ").strip()
    
    # Try to parse as number
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(tournaments):
            return str(tournaments[idx]["_id"])
    except ValueError:
        pass
    
    # Assume it's an ID
    return choice


def diagnose_tournament(tournament_id):
    """Diagnose stats population for a tournament"""
    print("\n" + "="*70)
    print(f"DIAGNOSING TOURNAMENT: {tournament_id}")
    print("="*70 + "\n")
    
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        print(f"❌ Invalid tournament ID: {tournament_id}")
        return
    
    # Get tournament document
    tournament = tournaments_collection.find_one({"_id": tid})
    if not tournament:
        print(f"❌ Tournament not found: {tournament_id}")
        return
    
    print(f"✅ Tournament found: {tournament.get('name', 'Unnamed')}")
    print(f"   Current round: {tournament.get('current_round', 'N/A')}")
    print()
    
    # Check applied_games
    applied_games = tournament.get("applied_games", [])
    print(f"📋 Applied Games: {len(applied_games)} games")
    if applied_games:
        print(f"   Sample game IDs: {[str(g) for g in applied_games[:3]]}")
    else:
        print("   ⚠️  WARNING: No games in applied_games - finalize_game() may not have been called!")
    print()
    
    # Check players object
    players = tournament.get("players", {})
    print(f"👥 Players in tournament: {len(players)} players")
    
    if not players:
        print("   ❌ ERROR: No players object in tournament document!")
        print("   This means stats cannot be saved or retrieved.")
        return
    
    # Check for players with stats
    players_with_stats = 0
    players_with_nonzero_stats = 0
    players_with_3ptm = 0
    
    sample_player = None
    sample_stats = None
    
    for player_id, player_data in players.items():
        season_stats = player_data.get("season", {})
        if season_stats:
            players_with_stats += 1
            
            # Check for non-zero stats
            has_nonzero = any(
                isinstance(v, (int, float)) and v > 0 
                for k, v in season_stats.items() 
                if k not in ["Outlet_Score_List"]
            )
            
            if has_nonzero:
                players_with_nonzero_stats += 1
                if sample_player is None:
                    sample_player = player_id
                    sample_stats = season_stats
            
            # Check for 3PTM specifically
            if "3PTM" in season_stats and season_stats["3PTM"] > 0:
                players_with_3ptm += 1
    
    print(f"   Players with stats: {players_with_stats}")
    print(f"   Players with non-zero stats: {players_with_nonzero_stats}")
    print(f"   Players with 3PTM > 0: {players_with_3ptm}")
    print()
    
    if sample_stats:
        print(f"📊 Sample player stats (ID: {sample_player[:8]}...):")
        print(f"   PTS: {sample_stats.get('PTS', 0)}")
        print(f"   FGM: {sample_stats.get('FGM', 0)}")
        print(f"   FGA: {sample_stats.get('FGA', 0)}")
        print(f"   3PTM: {sample_stats.get('3PTM', 0)}")
        print(f"   3PTA: {sample_stats.get('3PTA', 0)}")
        print(f"   REB: {sample_stats.get('REB', 0)}")
        print(f"   GP: {sample_stats.get('GP', 0)}")
        print()
        
        # Check field names
        if "TPM" in sample_stats:
            print("   ⚠️  WARNING: Found 'TPM' field (should be '3PTM')")
        if "TPA" in sample_stats:
            print("   ⚠️  WARNING: Found 'TPA' field (should be '3PTA')")
    else:
        print("   ⚠️  WARNING: No players with non-zero stats found!")
        print("   This suggests stats were not saved or all stats are zero.")
        print()
    
    # Check game documents
    print("🎮 Checking game documents...")
    games = list(games_collection.find(
        {"tournament_id": tournament_id},
        {"_id": 1, "quarter": 1, "is_final": 1, "box_score": 1}
    ).limit(5))
    
    print(f"   Found {len(games)} games with tournament_id={tournament_id}")
    
    games_with_box_score = 0
    games_with_empty_box_score = 0
    
    for game in games:
        box_score = game.get("box_score", {})
        if box_score:
            games_with_box_score += 1
            # Check if box_score has actual data
            has_data = False
            for team_name, team_box in box_score.items():
                if team_box and isinstance(team_box, dict):
                    for pos, player_data in team_box.items():
                        if isinstance(player_data, dict) and player_data.get("PTS", 0) > 0:
                            has_data = True
                            break
                    if has_data:
                        break
            if not has_data:
                games_with_empty_box_score += 1
        else:
            games_with_empty_box_score += 1
    
    print(f"   Games with box_score: {games_with_box_score}")
    print(f"   Games with empty/missing box_score: {games_with_empty_box_score}")
    
    if games_with_empty_box_score > 0:
        print("   ⚠️  WARNING: Some games have empty or missing box_score!")
        print("   This would prevent finalize_game() from saving stats.")
    print()
    
    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    
    issues = []
    if len(applied_games) == 0:
        issues.append("❌ No games in applied_games - finalize_game() may not have been called")
    if players_with_nonzero_stats == 0:
        issues.append("❌ No players with non-zero stats - stats may not have been saved")
    if games_with_empty_box_score > 0:
        issues.append(f"⚠️  {games_with_empty_box_score} games have empty box_score")
    if players_with_3ptm == 0 and players_with_nonzero_stats > 0:
        issues.append("⚠️  3PTM stats are all zero (may be normal if no 3-pointers made)")
    
    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ No obvious issues found!")
        print("   Stats appear to be saved correctly in tournament document.")
        print("   If TCC tabs are still not showing stats, check:")
        print("   1. Player ID matching between roster and tournament document")
        print("   2. Frontend merge logic in loadRoster()")
        print("   3. Aggregator logic in team_stats_aggregator.py")
    
    print()


if __name__ == "__main__":
    tournament_id = get_tournament_id()
    diagnose_tournament(tournament_id)

