"""
Tests for Q2, Q3, and Q4 quarter starts with BASELINE_INBOUND turns.

Verifies:
- Correct possession based on opening tip winner
- BASELINE_INBOUND turn structure (not opening tip)
- Proper SS&S fields (offense_team_id, current_turn, next_turn)
- Possession pattern: Q2/Q3 = loser, Q4 = winner
"""
import pytest
from BackEnd.models.game_manager import GameManager
from BackEnd.main import simulate_quarter
from bson import ObjectId


@pytest.fixture
def game_manager():
    """Create a fresh GameManager instance with teams loaded from database"""
    gm = GameManager("Four Corners", "Morristown")
    
    # Set default strategy settings to avoid KeyError
    default_strategy = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2}
    gm.home_team.strategy_settings = default_strategy.copy()
    gm.away_team.strategy_settings = default_strategy.copy()
    
    return gm


def test_q2_starts_with_baseline_inbound(game_manager):
    """Test that Q2 starts with BASELINE_INBOUND turn (not opening tip)"""
    game_id = str(ObjectId())
    
    # Simulate Q1 to get opening tip winner
    simulate_quarter(game_manager, game_id=game_id)
    opening_tip_winner = game_manager.game_state["opening_tip_winner"]
    q1_turn_count = len(game_manager.turns)
    
    # Simulate Q2
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q2 has turns
    q2_turns = game_manager.turns[q1_turn_count:]
    assert len(q2_turns) > 0, "Q2 should have turns"
    
    # First Q2 turn should be BASELINE_INBOUND
    first_q2_turn = q2_turns[0]
    assert first_q2_turn["result_type"] == "BASELINE_INBOUND", \
        f"Q2 should start with BASELINE_INBOUND, got {first_q2_turn.get('result_type')}"
    
    # Verify no opening tip in Q2
    q2_opening_tips = [t for t in q2_turns if t.get("result_type") == "OPENING_TIP"]
    assert len(q2_opening_tips) == 0, "Q2 should NOT have an opening tip"
    
    print(f"✅ Q2 starts with BASELINE_INBOUND (no opening tip)")


def test_q2_possession_loser_gets_ball(game_manager):
    """Test that Q2 gives possession to team that did NOT win opening tip"""
    game_id = str(ObjectId())
    
    # Simulate Q1 to get opening tip winner
    simulate_quarter(game_manager, game_id=game_id)
    opening_tip_winner = game_manager.game_state["opening_tip_winner"]
    q1_turn_count = len(game_manager.turns)
    
    # Determine expected offense team (loser)
    if opening_tip_winner == "home":
        expected_offense_team = game_manager.away_team
        expected_offense_name = game_manager.away_team.name
    else:
        expected_offense_team = game_manager.home_team
        expected_offense_name = game_manager.home_team.name
    
    # Simulate Q2
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q2 BASELINE_INBOUND has correct offense team
    q2_turns = game_manager.turns[q1_turn_count:]
    first_q2_turn = q2_turns[0]
    
    assert first_q2_turn["result_type"] == "BASELINE_INBOUND", "Q2 should start with BASELINE_INBOUND"
    assert "offense_team_id" in first_q2_turn, "BASELINE_INBOUND should have offense_team_id"
    assert first_q2_turn["offense_team_id"] == expected_offense_team.team_id, \
        f"Q2 offense should be {expected_offense_name} (loser), got {first_q2_turn.get('offense_team_id')}"
    
    # Note: We don't check game_manager.offense_team after full simulation because
    # possession changes multiple times during the quarter. We only verify the
    # BASELINE_INBOUND turn has the correct starting offense team.
    
    print(f"✅ Q2: {expected_offense_name} (loser) gets possession via BASELINE_INBOUND")


def test_q2_baseline_inbound_structure(game_manager):
    """Test that Q2 BASELINE_INBOUND has proper SS&S structure"""
    game_id = str(ObjectId())
    
    # Simulate Q1
    simulate_quarter(game_manager, game_id=game_id)
    q1_turn_count = len(game_manager.turns)
    
    # Simulate Q2
    simulate_quarter(game_manager, game_id=game_id)
    
    # Get Q2 BASELINE_INBOUND turn
    q2_turns = game_manager.turns[q1_turn_count:]
    bip_turn = q2_turns[0]
    
    # Verify SS&S fields
    assert bip_turn["result_type"] == "BASELINE_INBOUND", "Should be BASELINE_INBOUND"
    assert "offense_team_id" in bip_turn, "Should have offense_team_id"
    assert "current_turn" in bip_turn, "Should have current_turn"
    assert bip_turn["current_turn"] == "BASELINE_INBOUND", "current_turn should be BASELINE_INBOUND"
    assert "next_turn" in bip_turn, "Should have next_turn"
    assert "next_play_type" in bip_turn, "Should have next_play_type"
    assert "quarter" in bip_turn, "Should have quarter"
    assert bip_turn["quarter"] == 2, "Quarter should be 2"
    
    # Verify required fields for frontend
    assert "oDestinations" in bip_turn, "Should have oDestinations"
    assert "dDestinations" in bip_turn, "Should have dDestinations"
    assert "ball_spot" in bip_turn, "Should have ball_spot"
    assert "text" in bip_turn, "Should have text"
    assert "time_elapsed" in bip_turn, "Should have time_elapsed"
    
    print(f"✅ Q2 BASELINE_INBOUND has proper SS&S structure")


def test_q3_starts_with_baseline_inbound(game_manager):
    """Test that Q3 starts with BASELINE_INBOUND turn (not opening tip)"""
    game_id = str(ObjectId())
    
    # Simulate Q1 and Q2
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    q1_q2_turn_count = len(game_manager.turns)
    
    # Simulate Q3
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q3 has turns
    q3_turns = game_manager.turns[q1_q2_turn_count:]
    assert len(q3_turns) > 0, "Q3 should have turns"
    
    # First Q3 turn should be BASELINE_INBOUND
    first_q3_turn = q3_turns[0]
    assert first_q3_turn["result_type"] == "BASELINE_INBOUND", \
        f"Q3 should start with BASELINE_INBOUND, got {first_q3_turn.get('result_type')}"
    
    # Verify no opening tip in Q3
    q3_opening_tips = [t for t in q3_turns if t.get("result_type") == "OPENING_TIP"]
    assert len(q3_opening_tips) == 0, "Q3 should NOT have an opening tip"
    
    print(f"✅ Q3 starts with BASELINE_INBOUND (no opening tip)")


def test_q3_possession_loser_gets_ball(game_manager):
    """Test that Q3 gives possession to team that did NOT win opening tip"""
    game_id = str(ObjectId())
    
    # Simulate Q1 to get opening tip winner
    simulate_quarter(game_manager, game_id=game_id)
    opening_tip_winner = game_manager.game_state["opening_tip_winner"]
    simulate_quarter(game_manager, game_id=game_id)  # Q2
    q1_q2_turn_count = len(game_manager.turns)
    
    # Determine expected offense team (loser)
    if opening_tip_winner == "home":
        expected_offense_team = game_manager.away_team
        expected_offense_name = game_manager.away_team.name
    else:
        expected_offense_team = game_manager.home_team
        expected_offense_name = game_manager.home_team.name
    
    # Simulate Q3
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q3 BASELINE_INBOUND has correct offense team
    q3_turns = game_manager.turns[q1_q2_turn_count:]
    first_q3_turn = q3_turns[0]
    
    assert first_q3_turn["result_type"] == "BASELINE_INBOUND", "Q3 should start with BASELINE_INBOUND"
    assert "offense_team_id" in first_q3_turn, "BASELINE_INBOUND should have offense_team_id"
    assert first_q3_turn["offense_team_id"] == expected_offense_team.team_id, \
        f"Q3 offense should be {expected_offense_name} (loser), got {first_q3_turn.get('offense_team_id')}"
    
    # Note: We don't check game_manager.offense_team after full simulation because
    # possession changes multiple times during the quarter. We only verify the
    # BASELINE_INBOUND turn has the correct starting offense team.
    
    print(f"✅ Q3: {expected_offense_name} (loser) gets possession via BASELINE_INBOUND")


def test_q3_baseline_inbound_structure(game_manager):
    """Test that Q3 BASELINE_INBOUND has proper SS&S structure"""
    game_id = str(ObjectId())
    
    # Simulate Q1 and Q2
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    q1_q2_turn_count = len(game_manager.turns)
    
    # Simulate Q3
    simulate_quarter(game_manager, game_id=game_id)
    
    # Get Q3 BASELINE_INBOUND turn
    q3_turns = game_manager.turns[q1_q2_turn_count:]
    bip_turn = q3_turns[0]
    
    # Verify SS&S fields
    assert bip_turn["result_type"] == "BASELINE_INBOUND", "Should be BASELINE_INBOUND"
    assert "offense_team_id" in bip_turn, "Should have offense_team_id"
    assert "current_turn" in bip_turn, "Should have current_turn"
    assert bip_turn["current_turn"] == "BASELINE_INBOUND", "current_turn should be BASELINE_INBOUND"
    assert "next_turn" in bip_turn, "Should have next_turn"
    assert "next_play_type" in bip_turn, "Should have next_play_type"
    assert "quarter" in bip_turn, "Should have quarter"
    assert bip_turn["quarter"] == 3, "Quarter should be 3"
    
    print(f"✅ Q3 BASELINE_INBOUND has proper SS&S structure")


def test_q4_starts_with_baseline_inbound(game_manager):
    """Test that Q4 starts with BASELINE_INBOUND turn (not opening tip)"""
    game_id = str(ObjectId())
    
    # Simulate Q1, Q2, Q3
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    q1_q2_q3_turn_count = len(game_manager.turns)
    
    # Simulate Q4
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q4 has turns
    q4_turns = game_manager.turns[q1_q2_q3_turn_count:]
    assert len(q4_turns) > 0, "Q4 should have turns"
    
    # First Q4 turn should be BASELINE_INBOUND
    first_q4_turn = q4_turns[0]
    assert first_q4_turn["result_type"] == "BASELINE_INBOUND", \
        f"Q4 should start with BASELINE_INBOUND, got {first_q4_turn.get('result_type')}"
    
    # Verify no opening tip in Q4
    q4_opening_tips = [t for t in q4_turns if t.get("result_type") == "OPENING_TIP"]
    assert len(q4_opening_tips) == 0, "Q4 should NOT have an opening tip"
    
    print(f"✅ Q4 starts with BASELINE_INBOUND (no opening tip)")


def test_q4_possession_winner_gets_ball(game_manager):
    """Test that Q4 gives possession to opening tip winner"""
    game_id = str(ObjectId())
    
    # Simulate Q1 to get opening tip winner
    simulate_quarter(game_manager, game_id=game_id)
    opening_tip_winner = game_manager.game_state["opening_tip_winner"]
    simulate_quarter(game_manager, game_id=game_id)  # Q2
    simulate_quarter(game_manager, game_id=game_id)  # Q3
    q1_q2_q3_turn_count = len(game_manager.turns)
    
    # Determine expected offense team (winner)
    if opening_tip_winner == "home":
        expected_offense_team = game_manager.home_team
        expected_offense_name = game_manager.home_team.name
    else:
        expected_offense_team = game_manager.away_team
        expected_offense_name = game_manager.away_team.name
    
    # Simulate Q4
    simulate_quarter(game_manager, game_id=game_id)
    
    # Verify Q4 BASELINE_INBOUND has correct offense team
    q4_turns = game_manager.turns[q1_q2_q3_turn_count:]
    first_q4_turn = q4_turns[0]
    
    assert first_q4_turn["result_type"] == "BASELINE_INBOUND", "Q4 should start with BASELINE_INBOUND"
    assert "offense_team_id" in first_q4_turn, "BASELINE_INBOUND should have offense_team_id"
    assert first_q4_turn["offense_team_id"] == expected_offense_team.team_id, \
        f"Q4 offense should be {expected_offense_name} (winner), got {first_q4_turn.get('offense_team_id')}"
    
    # Note: We don't check game_manager.offense_team after full simulation because
    # possession changes multiple times during the quarter. We only verify the
    # BASELINE_INBOUND turn has the correct starting offense team.
    
    print(f"✅ Q4: {expected_offense_name} (winner) gets possession via BASELINE_INBOUND")


def test_q4_baseline_inbound_structure(game_manager):
    """Test that Q4 BASELINE_INBOUND has proper SS&S structure"""
    game_id = str(ObjectId())
    
    # Simulate Q1, Q2, Q3
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    simulate_quarter(game_manager, game_id=game_id)
    q1_q2_q3_turn_count = len(game_manager.turns)
    
    # Simulate Q4
    simulate_quarter(game_manager, game_id=game_id)
    
    # Get Q4 BASELINE_INBOUND turn
    q4_turns = game_manager.turns[q1_q2_q3_turn_count:]
    bip_turn = q4_turns[0]
    
    # Verify SS&S fields
    assert bip_turn["result_type"] == "BASELINE_INBOUND", "Should be BASELINE_INBOUND"
    assert "offense_team_id" in bip_turn, "Should have offense_team_id"
    assert "current_turn" in bip_turn, "Should have current_turn"
    assert bip_turn["current_turn"] == "BASELINE_INBOUND", "current_turn should be BASELINE_INBOUND"
    assert "next_turn" in bip_turn, "Should have next_turn"
    assert "next_play_type" in bip_turn, "Should have next_play_type"
    assert "quarter" in bip_turn, "Should have quarter"
    assert bip_turn["quarter"] == 4, "Quarter should be 4"
    
    print(f"✅ Q4 BASELINE_INBOUND has proper SS&S structure")


def test_all_quarters_possession_pattern(game_manager):
    """Test the complete possession pattern across all quarters"""
    game_id = str(ObjectId())
    
    # Simulate Q1
    simulate_quarter(game_manager, game_id=game_id)
    opening_tip_winner = game_manager.game_state["opening_tip_winner"]
    q1_turn_count = len(game_manager.turns)
    
    # Determine expected teams
    if opening_tip_winner == "home":
        winner_team = game_manager.home_team
        loser_team = game_manager.away_team
    else:
        winner_team = game_manager.away_team
        loser_team = game_manager.home_team
    
    # Simulate Q2
    simulate_quarter(game_manager, game_id=game_id)
    q2_turns = game_manager.turns[q1_turn_count:]
    q2_bip = q2_turns[0]
    assert q2_bip["offense_team_id"] == loser_team.team_id, "Q2 should be loser"
    q1_q2_turn_count = len(game_manager.turns)
    
    # Simulate Q3
    simulate_quarter(game_manager, game_id=game_id)
    q3_turns = game_manager.turns[q1_q2_turn_count:]
    q3_bip = q3_turns[0]
    assert q3_bip["offense_team_id"] == loser_team.team_id, "Q3 should be loser"
    q1_q2_q3_turn_count = len(game_manager.turns)
    
    # Simulate Q4
    simulate_quarter(game_manager, game_id=game_id)
    q4_turns = game_manager.turns[q1_q2_q3_turn_count:]
    q4_bip = q4_turns[0]
    assert q4_bip["offense_team_id"] == winner_team.team_id, "Q4 should be winner"
    
    # Verify only 1 opening tip total
    all_opening_tips = [t for t in game_manager.turns if t.get("result_type") == "OPENING_TIP"]
    assert len(all_opening_tips) == 1, f"Should have exactly 1 opening tip, found {len(all_opening_tips)}"
    
    print(f"✅ Complete possession pattern verified:")
    print(f"   Q1: {winner_team.name} (opening tip winner)")
    print(f"   Q2: {loser_team.name} (loser via BASELINE_INBOUND)")
    print(f"   Q3: {loser_team.name} (loser via BASELINE_INBOUND)")
    print(f"   Q4: {winner_team.name} (winner via BASELINE_INBOUND)")

