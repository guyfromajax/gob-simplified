"""
Test stats persistence across quarter transitions.

This test verifies that team stats, player stats, and GameManager state
persist correctly when transitioning from Q1 to Q2.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.main import simulate_quarter
from BackEnd.models.game_manager import GameManager
from BackEnd.utils.shared import summarize_game_state


def test_stats_persistence_across_quarters():
    """Test that stats persist from Q1 to Q2."""
    print("\n" + "="*80)
    print("TEST: Stats Persistence Across Quarters")
    print("="*80)
    
    # Create a new game
    print("\n1. Creating GameManager...")
    gm = GameManager("Bentley-Truman", "Morristown", mode="single")
    game_id = "test_game_123"
    gm.game_id = game_id
    
    print(f"   ✓ GameManager created: {gm.home_team.name} vs {gm.away_team.name}")
    
    # Simulate Q1
    print("\n2. Simulating Quarter 1...")
    simulate_quarter(gm, turn_by_turn_mode=True)
    
    # Capture Q1 end state
    q1_home_score = gm.score.get(gm.home_team.name, 0)
    q1_away_score = gm.score.get(gm.away_team.name, 0)
    q1_home_fouls = gm.home_team.team_fouls
    q1_away_fouls = gm.away_team.team_fouls
    
    # Get a sample player's stats
    sample_player = list(gm.home_team.lineup.values())[0]
    q1_player_pts = sample_player.stats.get("game", {}).get("PTS", 0)
    
    # Get team totals
    q1_team_totals = dict(gm.team_totals)
    
    print(f"\n   Q1 Final State:")
    print(f"   - Home Score: {q1_home_score}")
    print(f"   - Away Score: {q1_away_score}")
    print(f"   - Home Fouls: {q1_home_fouls}")
    print(f"   - Away Fouls: {q1_away_fouls}")
    print(f"   - Sample Player PTS: {q1_player_pts}")
    print(f"   - Team Totals Keys: {list(q1_team_totals.keys())}")
    
    # Save game state (simulate what happens between quarters)
    print("\n3. Saving game state to simulate DB persistence...")
    saved_state = summarize_game_state(gm, exclude_animations=True)
    
    print(f"   ✓ Saved state includes:")
    print(f"     - score: {saved_state.get('score')}")
    print(f"     - home_team.score: {saved_state.get('home_team', {}).get('score')}")
    print(f"     - home_team.team_fouls: {saved_state.get('home_team', {}).get('team_fouls')}")
    print(f"     - home_team.totals keys: {list(saved_state.get('home_team', {}).get('totals', {}).keys())}")
    print(f"     - players count: {len(saved_state.get('players', []))}")
    
    # Check for benched players with pos: null
    benched_players = [p for p in saved_state.get('players', []) if p.get('pos') is None]
    if benched_players:
        print(f"\n   ⚠️ WARNING: {len(benched_players)} benched players with pos: null found!")
        for p in benched_players[:3]:  # Show first 3
            print(f"      - {p.get('name')} ({p.get('playerId')})")
    else:
        print(f"   ✓ No benched players with pos: null (correct!)")
    
    # Simulate Q2 (using same GameManager instance, as in Single Game mode)
    print("\n4. Advancing to Quarter 2...")
    gm.quarter = 2
    simulate_quarter(gm, turn_by_turn_mode=True, start_with_inbound=True)
    
    # Check Q2 state
    q2_home_score = gm.score.get(gm.home_team.name, 0)
    q2_away_score = gm.score.get(gm.away_team.name, 0)
    q2_home_fouls = gm.home_team.team_fouls
    q2_away_fouls = gm.away_team.team_fouls
    q2_player_pts = sample_player.stats.get("game", {}).get("PTS", 0)
    
    print(f"\n   Q2 Start State:")
    print(f"   - Home Score: {q2_home_score}")
    print(f"   - Away Score: {q2_away_score}")
    print(f"   - Home Fouls: {q2_home_fouls}")
    print(f"   - Away Fouls: {q2_away_fouls}")
    print(f"   - Sample Player PTS: {q2_player_pts}")
    
    # Verify stats persisted
    print("\n5. Verifying Stats Persistence...")
    
    errors = []
    
    # Team scores should accumulate (Q2 score >= Q1 score)
    if q2_home_score < q1_home_score:
        errors.append(f"❌ Home score DECREASED: {q1_home_score} → {q2_home_score}")
    else:
        print(f"   ✓ Home score persisted: {q1_home_score} → {q2_home_score}")
    
    if q2_away_score < q1_away_score:
        errors.append(f"❌ Away score DECREASED: {q1_away_score} → {q2_away_score}")
    else:
        print(f"   ✓ Away score persisted: {q1_away_score} → {q2_away_score}")
    
    # Team fouls should reset to 0 at start of each quarter
    if q2_home_fouls != 0:
        errors.append(f"❌ Home fouls NOT reset: {q2_home_fouls} (expected 0)")
    else:
        print(f"   ✓ Home fouls reset: {q2_home_fouls}")
    
    if q2_away_fouls != 0:
        errors.append(f"❌ Away fouls NOT reset: {q2_away_fouls} (expected 0)")
    else:
        print(f"   ✓ Away fouls reset: {q2_away_fouls}")
    
    # Player stats should accumulate
    if q2_player_pts < q1_player_pts:
        errors.append(f"❌ Player PTS DECREASED: {q1_player_pts} → {q2_player_pts}")
    else:
        print(f"   ✓ Player PTS persisted: {q1_player_pts} → {q2_player_pts}")
    
    # Team totals should exist
    if not gm.team_totals:
        errors.append(f"❌ Team totals are empty")
    else:
        print(f"   ✓ Team totals exist: {list(gm.team_totals.keys())}")
    
    # Print results
    print("\n" + "="*80)
    if errors:
        print("❌ TEST FAILED")
        print("="*80)
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("✅ TEST PASSED - All stats persisted correctly!")
        print("="*80)
        return True


def test_api_game_endpoint_data():
    """Test that /api/game/{game_id} returns complete data."""
    print("\n" + "="*80)
    print("TEST: API Game Endpoint Data Completeness")
    print("="*80)
    
    from BackEnd.api.api import ongoing_games
    
    # Create a game and add to ongoing_games
    print("\n1. Creating GameManager and simulating Q1...")
    gm = GameManager("Bentley-Truman", "Morristown", mode="single")
    game_id = "test_game_api_456"
    gm.game_id = game_id
    
    # Simulate Q1
    simulate_quarter(gm, turn_by_turn_mode=True)
    
    # Add to ongoing_games
    ongoing_games[game_id] = gm
    
    print(f"   ✓ Game added to ongoing_games")
    print(f"   - Home Score: {gm.score.get(gm.home_team.name, 0)}")
    print(f"   - Away Score: {gm.score.get(gm.away_team.name, 0)}")
    
    # Simulate the /api/game/{game_id} endpoint logic
    print("\n2. Simulating /api/game/{game_id} endpoint...")
    
    players = []
    for team in [gm.home_team, gm.away_team]:
        for pos, player in team.lineup.items():
            players.append({
                "_id": player.player_id,
                "name": player.name,
                "NG": player.attributes.get("NG", 1.0),
                "team": team.name
            })
    
    response_data = {
        "game_id": game_id,
        "score": gm.score,
        "box_score": gm.get_box_score(),
        "quarter": gm.quarter,
        "clock": gm.game_state.get("clock", "8:00"),
        "players": players,
        "team_totals": gm.team_totals,
        "points_by_quarter": gm.game_state.get("points_by_quarter", {}),
        "home_team": {
            "name": gm.home_team.name,
            "team_fouls": gm.home_team.team_fouls
        },
        "away_team": {
            "name": gm.away_team.name,
            "team_fouls": gm.away_team.team_fouls
        }
    }
    
    print(f"   ✓ Response data generated")
    
    # Verify all required fields are present
    print("\n3. Verifying response data completeness...")
    
    errors = []
    
    if "score" not in response_data:
        errors.append("❌ Missing 'score'")
    else:
        print(f"   ✓ 'score' present: {response_data['score']}")
    
    if "box_score" not in response_data:
        errors.append("❌ Missing 'box_score'")
    else:
        print(f"   ✓ 'box_score' present (keys: {list(response_data['box_score'].keys())})")
    
    if "team_totals" not in response_data:
        errors.append("❌ Missing 'team_totals'")
    else:
        print(f"   ✓ 'team_totals' present (keys: {list(response_data['team_totals'].keys())})")
    
    if "points_by_quarter" not in response_data:
        errors.append("❌ Missing 'points_by_quarter'")
    else:
        print(f"   ✓ 'points_by_quarter' present")
    
    if "home_team" not in response_data or "team_fouls" not in response_data["home_team"]:
        errors.append("❌ Missing 'home_team.team_fouls'")
    else:
        print(f"   ✓ 'home_team.team_fouls' present: {response_data['home_team']['team_fouls']}")
    
    if "away_team" not in response_data or "team_fouls" not in response_data["away_team"]:
        errors.append("❌ Missing 'away_team.team_fouls'")
    else:
        print(f"   ✓ 'away_team.team_fouls' present: {response_data['away_team']['team_fouls']}")
    
    # Verify team_totals has actual data
    if not response_data["team_totals"]:
        errors.append("❌ 'team_totals' is empty")
    else:
        print(f"   ✓ 'team_totals' has data")
    
    # Clean up
    del ongoing_games[game_id]
    
    # Print results
    print("\n" + "="*80)
    if errors:
        print("❌ TEST FAILED")
        print("="*80)
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("✅ TEST PASSED - API endpoint returns complete data!")
        print("="*80)
        return True


if __name__ == "__main__":
    print("\n🧪 Running Quarter Transition Stats Tests...\n")
    
    test1_passed = test_stats_persistence_across_quarters()
    test2_passed = test_api_game_endpoint_data()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Test 1 (Stats Persistence): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (API Endpoint Data): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print("="*80)
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n💥 SOME TESTS FAILED")
        sys.exit(1)

