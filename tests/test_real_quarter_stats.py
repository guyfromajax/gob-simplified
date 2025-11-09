"""
Test with REAL quarter simulation (not turn-by-turn mode).
This will actually play turns and generate real stats.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.main import simulate_quarter
from BackEnd.models.game_manager import GameManager


def test_real_quarter_stats():
    """Test with actual quarter simulation to get real stats."""
    print("\n" + "="*80)
    print("TEST: Real Quarter Simulation with Stats")
    print("="*80)
    
    # Create a new game
    print("\n1. Creating GameManager...")
    gm = GameManager("Bentley-Truman", "Morristown", mode="single")
    game_id = "test_game_real"
    gm.game_id = game_id
    
    # Simulate Q1 WITHOUT turn-by-turn mode (full simulation)
    print("\n2. Simulating Quarter 1 (FULL SIMULATION - NOT turn-by-turn)...")
    simulate_quarter(gm, turn_by_turn_mode=False)  # Full simulation
    
    # Capture Q1 end state
    q1_home_score = gm.score.get(gm.home_team.name, 0)
    q1_away_score = gm.score.get(gm.away_team.name, 0)
    q1_home_fouls = gm.home_team.team_fouls
    q1_away_fouls = gm.away_team.team_fouls
    
    # Get a sample player's stats
    sample_player = list(gm.home_team.lineup.values())[0]
    q1_player_pts = sample_player.stats.get("game", {}).get("PTS", 0)
    q1_player_fgm = sample_player.stats.get("game", {}).get("FGM", 0)
    
    # Get team totals
    q1_home_totals = gm.team_totals.get(gm.home_team.name, {})
    q1_away_totals = gm.team_totals.get(gm.away_team.name, {})
    
    print(f"\n   ✅ Q1 COMPLETED - Final State:")
    print(f"   - Home Score: {q1_home_score}")
    print(f"   - Away Score: {q1_away_score}")
    print(f"   - Home Fouls: {q1_home_fouls}")
    print(f"   - Away Fouls: {q1_away_fouls}")
    print(f"   - Sample Player ({sample_player.name}): {q1_player_pts} PTS, {q1_player_fgm} FGM")
    print(f"   - Home Team Totals PTS: {q1_home_totals.get('PTS', 0)}")
    print(f"   - Away Team Totals PTS: {q1_away_totals.get('PTS', 0)}")
    
    # Verify Q1 generated real stats
    if q1_home_score == 0 and q1_away_score == 0:
        print("\n   ⚠️ WARNING: Both teams scored 0 (unusual but possible)")
    
    # Now simulate Q2 (this is what happens in the real game)
    print("\n3. Advancing to Quarter 2...")
    gm.quarter = 2
    
    # In turn-by-turn mode, Q2 starts with just initialization
    print("   (Using turn-by-turn mode for Q2, as the real game does)")
    simulate_quarter(gm, turn_by_turn_mode=True, start_with_inbound=True)
    
    # Check Q2 state IMMEDIATELY after initialization (before any turns)
    q2_home_score = gm.score.get(gm.home_team.name, 0)
    q2_away_score = gm.score.get(gm.away_team.name, 0)
    q2_home_fouls = gm.home_team.team_fouls
    q2_away_fouls = gm.away_team.team_fouls
    q2_player_pts = sample_player.stats.get("game", {}).get("PTS", 0)
    q2_player_fgm = sample_player.stats.get("game", {}).get("FGM", 0)
    
    print(f"\n   Q2 INITIALIZED - State:")
    print(f"   - Home Score: {q2_home_score}")
    print(f"   - Away Score: {q2_away_score}")
    print(f"   - Home Fouls: {q2_home_fouls}")
    print(f"   - Away Fouls: {q2_away_fouls}")
    print(f"   - Sample Player ({sample_player.name}): {q2_player_pts} PTS, {q2_player_fgm} FGM")
    
    # Verify stats persisted
    print("\n4. Verifying Stats Persistence...")
    
    errors = []
    
    # Team scores should persist (Q2 score == Q1 score at start of Q2)
    if q2_home_score != q1_home_score:
        errors.append(f"❌ Home score changed: {q1_home_score} → {q2_home_score} (should be equal)")
    else:
        print(f"   ✅ Home score persisted: {q1_home_score} → {q2_home_score}")
    
    if q2_away_score != q1_away_score:
        errors.append(f"❌ Away score changed: {q1_away_score} → {q2_away_score} (should be equal)")
    else:
        print(f"   ✅ Away score persisted: {q1_away_score} → {q2_away_score}")
    
    # Team fouls should reset to 0 at start of each quarter
    if q2_home_fouls != 0:
        errors.append(f"❌ Home fouls NOT reset: {q2_home_fouls} (expected 0)")
    else:
        print(f"   ✅ Home fouls reset to 0: {q1_home_fouls} → {q2_home_fouls}")
    
    if q2_away_fouls != 0:
        errors.append(f"❌ Away fouls NOT reset: {q2_away_fouls} (expected 0)")
    else:
        print(f"   ✅ Away fouls reset to 0: {q1_away_fouls} → {q2_away_fouls}")
    
    # Player stats should persist
    if q2_player_pts != q1_player_pts:
        errors.append(f"❌ Player PTS changed: {q1_player_pts} → {q2_player_pts} (should be equal)")
    else:
        print(f"   ✅ Player PTS persisted: {q1_player_pts} → {q2_player_pts}")
    
    if q2_player_fgm != q1_player_fgm:
        errors.append(f"❌ Player FGM changed: {q1_player_fgm} → {q2_player_fgm} (should be equal)")
    else:
        print(f"   ✅ Player FGM persisted: {q1_player_fgm} → {q2_player_fgm}")
    
    # Team totals should persist
    q2_home_totals = gm.team_totals.get(gm.home_team.name, {})
    if q2_home_totals.get('PTS', 0) != q1_home_totals.get('PTS', 0):
        errors.append(f"❌ Team totals PTS changed: {q1_home_totals.get('PTS', 0)} → {q2_home_totals.get('PTS', 0)}")
    else:
        print(f"   ✅ Team totals PTS persisted: {q1_home_totals.get('PTS', 0)} → {q2_home_totals.get('PTS', 0)}")
    
    # Print results
    print("\n" + "="*80)
    if errors:
        print("❌ TEST FAILED")
        print("="*80)
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("✅ TEST PASSED - All stats persisted correctly from Q1 to Q2!")
        print("="*80)
        return True


if __name__ == "__main__":
    print("\n🧪 Running REAL Quarter Simulation Test...\n")
    
    passed = test_real_quarter_stats()
    
    if passed:
        print("\n🎉 TEST PASSED!")
        sys.exit(0)
    else:
        print("\n💥 TEST FAILED")
        sys.exit(1)

