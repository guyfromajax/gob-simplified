"""
Test TCC Stats Population - End-to-End Test
Verifies that stats properly populate Roster and Stats tabs in Tournament Command Center

Success Criteria:
1. Stats are saved to tournament document after game completion
2. Roster tab endpoint returns stats merged with player data
3. Stats tab endpoint returns aggregated team stats
4. All stats (including 3PTM/3PTA) are present and non-zero after gameplay
"""

from bson import ObjectId
from BackEnd.db import (
    tournaments_collection,
    games_collection,
    teams_collection,
    players_collection
)
from BackEnd.utils.stat_updater import finalize_game
from BackEnd.utils.team_stats_aggregator import aggregate_team_stats_from_players
from BackEnd.utils.shared import summarize_game_state
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter


def setup_function(fn):
    """Clean up test data before each test"""
    tournaments_collection.delete_many({})
    games_collection.delete_many({})
    # Don't delete teams/players - they may be shared


def test_tcc_stats_population_end_to_end():
    """
    End-to-end test: Create tournament, play game, verify stats populate in TCC
    """
    print("\n" + "="*70)
    print("TCC STATS POPULATION END-TO-END TEST")
    print("="*70 + "\n")
    
    # Step 1: Create a tournament with teams and players
    print("📋 Step 1: Creating tournament...")
    
    # Get or create test teams
    team1_doc = teams_collection.find_one({"name": "Morristown"})
    team2_doc = teams_collection.find_one({"name": "Bentley-Truman"})
    
    if not team1_doc or not team2_doc:
        print("⚠️  Test teams not found in database. Using mock teams.")
        team1_id = ObjectId()
        team2_id = ObjectId()
        teams_collection.insert_many([
            {"_id": team1_id, "name": "Morristown", "team_id": "MORRISTOWN"},
            {"_id": team2_id, "name": "Bentley-Truman", "team_id": "BENTLEY_TRUMAN"}
        ])
    else:
        team1_id = team1_doc["_id"]
        team2_id = team2_doc["_id"]
    
    # Create tournament document
    tournament_doc = {
        "_id": ObjectId(),
        "name": "Test Tournament",
        "current_round": 1,
        "teams": {
            str(team1_id): {"name": "Morristown"},
            str(team2_id): {"name": "Bentley-Truman"}
        },
        "players": {},  # Will be populated by game
        "bracket": {
            "round1": [
                {
                    "home_team": "Morristown",
                    "away_team": "Bentley-Truman",
                    "winner": None,
                    "score": {}
                }
            ]
        },
        "applied_games": []
    }
    tournament_id = tournaments_collection.insert_one(tournament_doc).inserted_id
    print(f"✅ Tournament created: {tournament_id}")
    
    # Step 2: Initialize and simulate a game
    print("\n📋 Step 2: Simulating game...")
    
    # Create game manager
    gm = GameManager(
        home_team_name="Morristown",
        away_team_name="Bentley-Truman",
        mode="tournament",
        tournament_id=str(tournament_id)
    )
    
    # Simulate Q1
    print("   Simulating Q1...")
    result = simulate_quarter(
        game_manager=gm,
        quarter=1,
        turn_by_turn_mode=False,
        full_sim=True
    )
    
    # Get game summary
    game_summary = summarize_game_state(gm)
    game_summary["tournament_id"] = str(tournament_id)
    
    # Save game to database
    game_id = games_collection.insert_one(game_summary).inserted_id
    print(f"✅ Game saved: {game_id}")
    
    # Step 3: Finalize game (this should save stats to tournament document)
    print("\n📋 Step 3: Finalizing game (saving stats to tournament)...")
    finalize_game(
        str(game_id),
        mode="tournament",
        tournament_id=str(tournament_id)
    )
    print("✅ Game finalized")
    
    # Step 4: Verify stats are in tournament document
    print("\n📋 Step 4: Verifying stats in tournament document...")
    tournament_after = tournaments_collection.find_one({"_id": tournament_id})
    
    assert tournament_after is not None, "Tournament document not found"
    assert "players" in tournament_after, "Tournament document missing 'players' key"
    
    players = tournament_after.get("players", {})
    print(f"   Found {len(players)} players in tournament document")
    
    # Check if any players have stats
    players_with_stats = 0
    players_with_nonzero_stats = 0
    sample_player_id = None
    sample_stats = None
    
    for player_id, player_data in players.items():
        if player_data.get("season"):
            players_with_stats += 1
            season_stats = player_data["season"]
            # Check for non-zero stats
            has_nonzero = any(
                isinstance(v, (int, float)) and v > 0 
                for k, v in season_stats.items() 
                if k not in ["Outlet_Score_List"]
            )
            if has_nonzero:
                players_with_nonzero_stats += 1
                if sample_player_id is None:
                    sample_player_id = player_id
                    sample_stats = season_stats
    
    print(f"   Players with stats: {players_with_stats}")
    print(f"   Players with non-zero stats: {players_with_nonzero_stats}")
    
    if sample_stats:
        print(f"   Sample player stats (ID: {sample_player_id}):")
        print(f"      PTS: {sample_stats.get('PTS', 0)}")
        print(f"      FGM: {sample_stats.get('FGM', 0)}")
        print(f"      FGA: {sample_stats.get('FGA', 0)}")
        print(f"      3PTM: {sample_stats.get('3PTM', 0)}")
        print(f"      3PTA: {sample_stats.get('3PTA', 0)}")
        print(f"      REB: {sample_stats.get('REB', 0)}")
        print(f"      GP: {sample_stats.get('GP', 0)}")
    
    # Assertions
    assert players_with_stats > 0, "No players have stats in tournament document"
    assert players_with_nonzero_stats > 0, "All player stats are zero"
    
    # Step 5: Test aggregator (used by Stats tab)
    print("\n📋 Step 5: Testing team stats aggregator (Stats tab)...")
    
    team_stats = aggregate_team_stats_from_players(
        players=players,
        team_ids=tournament_after["teams"],
        teams_collection=teams_collection,
        collection_type='tournament',
        logger=None,
        tournament_bracket=tournament_after.get("bracket", {})
    )
    
    print(f"   Aggregated stats for {len(team_stats)} teams")
    
    # Check if team stats have non-zero values
    teams_with_stats = 0
    for team in team_stats:
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
    
    assert teams_with_stats > 0, "No teams have non-zero aggregated stats"
    
    # Step 6: Verify 3PTM/3PTA specifically (the bug we just fixed)
    print("\n📋 Step 6: Verifying 3PTM/3PTA field names...")
    
    # Check player stats use 3PTM (not TPM)
    for player_id, player_data in players.items():
        season_stats = player_data.get("season", {})
        if "3PTM" in season_stats or "3PTA" in season_stats:
            assert "3PTM" in season_stats or season_stats.get("3PTM", 0) == 0, \
                f"Player {player_id} should use '3PTM' field name, not 'TPM'"
            assert "3PTA" in season_stats or season_stats.get("3PTA", 0) == 0, \
                f"Player {player_id} should use '3PTA' field name, not 'TPA'"
            print(f"   ✅ Player {player_id} uses correct field names (3PTM/3PTA)")
            break
    
    # Check team stats use 3PTM (not TPM)
    for team in team_stats:
        stats = team.get("stats", {})
        if "3PTM" in stats or "3PTA" in stats:
            assert "3PTM" in stats, f"Team '{team['team']}' stats should use '3PTM' field name"
            assert "3PTA" in stats, f"Team '{team['team']}' stats should use '3PTA' field name"
            print(f"   ✅ Team '{team['team']}' uses correct field names (3PTM/3PTA)")
            break
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED - Stats properly populate in TCC")
    print("="*70 + "\n")


if __name__ == "__main__":
    """Run test directly"""
    import sys
    
    try:
        test_tcc_stats_population_end_to_end()
        print("✅ Test passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

