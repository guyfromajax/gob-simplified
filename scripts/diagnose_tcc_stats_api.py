#!/usr/bin/env python3
"""
API-based diagnostic script to check TCC stats population issue

This script queries the backend API endpoints to check:
1. If stats are saved in tournament document
2. If players have stats in tournament
3. If team stats aggregator returns data

Usage:
    python3 scripts/diagnose_tcc_stats_api.py [tournament_id] [api_url]
    
If tournament_id is not provided, it will list all tournaments.
Default API URL: http://localhost:8000 (or set API_URL env var)
"""

import os
import sys
import json
from urllib.parse import urlencode

# Default API URL
API_URL = os.getenv("API_URL", "http://localhost:8000")

def fetch_json(url):
    """Fetch JSON from API endpoint"""
    try:
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None

def get_tournament_id(api_url):
    """Get tournament ID from command line"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    print("❌ Tournament ID required as first argument")
    print("Usage: python3 scripts/diagnose_tcc_stats_api.py <tournament_id> [api_url]")
    print(f"Example: python3 scripts/diagnose_tcc_stats_api.py 697646b0662eab0b435d1567 {api_url}")
    return None

def diagnose_tournament(tournament_id, api_url):
    """Diagnose stats population for a tournament via API"""
    print("\n" + "="*70)
    print(f"DIAGNOSING TOURNAMENT VIA API: {tournament_id}")
    print(f"API URL: {api_url}")
    print("="*70 + "\n")
    
    if not tournament_id:
        print("❌ No tournament ID provided")
        return
    
    # Step 1: Get tournament state
    print("📋 Step 1: Fetching tournament state...")
    state_url = f"{api_url}/tournament/state?tournament_id={tournament_id}"
    print(f"   URL: {state_url}")
    tournament = fetch_json(state_url)
    
    if not tournament:
        print("   ❌ Failed to fetch tournament state")
        return
    
    print(f"   ✅ Tournament found: {tournament.get('name', 'Unnamed')}")
    print(f"   Current round: {tournament.get('current_round', 'N/A')}")
    print()
    
    # Step 2: Check players object
    players = tournament.get("players", {})
    print(f"👥 Step 2: Checking players in tournament...")
    print(f"   Found {len(players)} players in tournament document")
    
    if not players:
        print("   ❌ ERROR: No players object in tournament document!")
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
        print()
    
    # Step 3: Check team stats aggregator
    print("📊 Step 3: Testing team stats aggregator (Stats tab)...")
    team_stats_url = f"{api_url}/tournament/team-stats?tournament_id={tournament_id}"
    print(f"   URL: {team_stats_url}")
    team_stats_response = fetch_json(team_stats_url)
    
    if not team_stats_response:
        print("   ❌ Failed to fetch team stats")
        return
    
    teams = team_stats_response.get("teams", [])
    print(f"   Found {len(teams)} teams in aggregated stats")
    
    teams_with_stats = 0
    for team in teams:
        stats = team.get("stats", {})
        has_nonzero = any(
            isinstance(v, (int, float)) and v > 0 
            for k, v in stats.items() 
            if k not in ["W", "L", "PF", "PA"]  # W/L/PF/PA might be 0
        )
        if has_nonzero:
            teams_with_stats += 1
            print(f"   Team '{team['team']}' stats:")
            print(f"      PTS: {stats.get('PTS', 0)}")
            print(f"      FGM: {stats.get('FGM', 0)}")
            print(f"      FGA: {stats.get('FGA', 0)}")
            print(f"      3PTM: {stats.get('3PTM', 0)}")
            print(f"      3PTA: {stats.get('3PTA', 0)}")
            print(f"      REB: {stats.get('REB', 0)}")
    
    print()
    
    # Step 4: Check applied_games
    applied_games = tournament.get("applied_games", [])
    print(f"🎮 Step 4: Checking applied_games...")
    print(f"   Applied games: {len(applied_games)}")
    if applied_games:
        print(f"   Sample game IDs: {[str(g) for g in applied_games[:3]]}")
    else:
        print("   ⚠️  WARNING: No games in applied_games - finalize_game() may not have been called!")
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
    if teams_with_stats == 0:
        issues.append("❌ No teams with non-zero aggregated stats")
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
    
    print()


if __name__ == "__main__":
    # Get API URL from command line or env
    if len(sys.argv) > 2:
        API_URL = sys.argv[2]
    elif os.getenv("API_URL"):
        API_URL = os.getenv("API_URL")
    
    tournament_id = get_tournament_id(API_URL)
    diagnose_tournament(tournament_id, API_URL)

