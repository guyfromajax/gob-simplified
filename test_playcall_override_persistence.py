#!/usr/bin/env python3
"""
Test script to verify playcall overrides persist through turn transitions.

Tests 5 scenarios with 3 variations each (offense only, defense only, both).
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from BackEnd.models.game_manager import GameManager
from BackEnd.db import games_collection, teams_collection
import logging

# Set up logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
# Suppress most logs, but we'll check results directly

def create_test_game():
    """Create a test game with user team."""
    gm = GameManager(
        home_team_name="Test Home",
        away_team_name="Test Away",
        mode="single",
        user_team_side="home"
    )
    
    # Make home team the user team
    gm.home_team.is_user_team = True
    gm.away_team.is_user_team = False
    
    # Set initial possession to home (user team)
    gm.offense_team = gm.home_team
    gm.defense_team = gm.away_team
    
    return gm

def set_playcall_overrides(gm, offense_override=None, defense_override=None):
    """Set playcall overrides for the user team."""
    user_team = gm.home_team
    
    if offense_override:
        user_team.strategy_calls["offense_call"] = offense_override
        print(f"  ✅ Set offense override: {offense_override}")
    else:
        user_team.strategy_calls["offense_call"] = None
        print(f"  ⚪ No offense override")
    
    if defense_override:
        user_team.strategy_calls["defense_call"] = defense_override
        print(f"  ✅ Set defense override: {defense_override}")
    else:
        user_team.strategy_calls["defense_call"] = None
        print(f"  ⚪ No defense override")

def check_playcall_applied(gm, expected_offense=None, expected_defense=None, turn_description=""):
    """Check if the expected playcalls were applied."""
    calls = gm.turn_manager.set_playcalls()
    actual_offense = calls.get("offense")
    actual_defense = calls.get("defense")
    
    offense_match = (expected_offense is None) or (actual_offense == expected_offense)
    defense_match = (expected_defense is None) or (actual_defense == expected_defense)
    
    status = "✅ PASS" if (offense_match and defense_match) else "❌ FAIL"
    
    print(f"    {status} {turn_description}")
    if expected_offense:
        print(f"      Expected offense: {expected_offense}, Got: {actual_offense}")
    if expected_defense:
        print(f"      Expected defense: {expected_defense}, Got: {actual_defense}")
    
    if not offense_match or not defense_match:
        print(f"      ⚠️ MISMATCH DETECTED!")
    
    return offense_match and defense_match

def simulate_turn_with_result(gm, result_type, next_play_type=None, possession_flips=True):
    """Simulate a turn with a specific result."""
    # Set up the turn
    gm.game_state["offensive_state"] = "HCO"  # Default, will be overridden by next_play_type
    
    if next_play_type:
        gm.game_state["offensive_state"] = next_play_type
    
    # Create a mock turn result
    from BackEnd.models.turn_result import TurnResult
    result = TurnResult(
        result_type=result_type,
        offense_team=gm.offense_team,
        defense_team=gm.defense_team,
        next_play_type=next_play_type,
        possession_flips=possession_flips
    )
    
    # Handle possession flip if needed
    if possession_flips:
        gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    
    return result

def run_scenario_1(gm, offense_override, defense_override):
    """Scenario 1: BIP -> HCT (trap break) -> HCO (offense) -> SIP -> HCO (defense)"""
    print("\n  📋 Scenario 1: BIP -> HCT (trap break) -> HCO (offense) -> SIP -> HCO (defense)")
    
    # A. Set at BIP step
    set_playcall_overrides(gm, offense_override, defense_override)
    gm.game_state["offensive_state"] = "BASELINE_INBOUND"
    
    # B. HCT - trap break result
    print("  B. HCT (trap break)")
    gm.game_state["offensive_state"] = "HCT"
    # Simulate trap break - no HCO call here
    
    # C. HCO (offense override should be applied here) => Made shot, no foul
    print("  C. HCO (offense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    offense_expected = offense_override if offense_override else None
    defense_expected = None  # Defense team is not user team yet
    result_c = check_playcall_applied(gm, offense_expected, None, "HCO after HCT trap break")
    
    # D. SIP
    print("  D. SIP")
    gm.game_state["offensive_state"] = "SIDE_INBOUND"
    # No playcall check here
    
    # E. HCO (defense override should be applied here)
    print("  E. HCO (defense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    # After possession flip, user team is now on defense
    offense_expected = None  # Offense team is not user team
    defense_expected = defense_override if defense_override else None
    result_e = check_playcall_applied(gm, None, defense_expected, "HCO after SIP (user on defense)")
    
    return result_c and result_e

def run_scenario_2(gm, offense_override, defense_override):
    """Scenario 2: BIP -> HCT (dead ball turnover) -> SIP -> HCO (defense) -> Fast Break -> HCO (offense)"""
    print("\n  📋 Scenario 2: BIP -> HCT (dead ball) -> SIP -> HCO (defense) -> Fast Break -> HCO (offense)")
    
    # A. Set at BIP step
    set_playcall_overrides(gm, offense_override, defense_override)
    gm.game_state["offensive_state"] = "BASELINE_INBOUND"
    
    # B. HCT - dead ball turnover result
    print("  B. HCT (dead ball turnover)")
    gm.game_state["offensive_state"] = "HCT"
    # Possession flips
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    
    # C. SIP
    print("  C. SIP")
    gm.game_state["offensive_state"] = "SIDE_INBOUND"
    
    # D. HCO (defense override should be applied here) => Miss, DREB
    print("  D. HCO (defense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    # User team is on defense
    defense_expected = defense_override if defense_override else None
    result_d = check_playcall_applied(gm, None, defense_expected, "HCO after SIP (user on defense)")
    
    # E. Fast Break => Defensive Stop
    print("  E. Fast Break (defensive stop)")
    gm.game_state["offensive_state"] = "FAST_BREAK"
    # Possession flips back
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    
    # F. HCO (offensive override should be applied here)
    print("  F. HCO (offense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    # User team is back on offense
    offense_expected = offense_override if offense_override else None
    result_f = check_playcall_applied(gm, offense_expected, None, "HCO after Fast Break (user on offense)")
    
    return result_d and result_f

def run_scenario_3(gm, offense_override, defense_override):
    """Scenario 3: BIP -> HCO (offense) -> Free Throw -> BIP -> HCT -> HCO (defense)"""
    print("\n  📋 Scenario 3: BIP -> HCO (offense) -> Free Throw -> BIP -> HCT -> HCO (defense)")
    
    # A. Set at BIP step
    set_playcall_overrides(gm, offense_override, defense_override)
    gm.game_state["offensive_state"] = "BASELINE_INBOUND"
    
    # B. HCO (offense override should be applied here) => Made Shot, Defensive Foul
    print("  B. HCO (offense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    offense_expected = offense_override if offense_override else None
    result_b = check_playcall_applied(gm, offense_expected, None, "HCO after BIP (user on offense)")
    
    # C. Free Throw => Made Shot result
    print("  C. Free Throw")
    gm.game_state["offensive_state"] = "FREE_THROW"
    # Possession flips
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    
    # D. BIP
    print("  D. BIP")
    gm.game_state["offensive_state"] = "BASELINE_INBOUND"
    
    # E. HCT => Trap Break result
    print("  E. HCT (trap break)")
    gm.game_state["offensive_state"] = "HCT"
    
    # F. HCO (defensive override should be applied here)
    print("  F. HCO (defense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    # User team is on defense
    defense_expected = defense_override if defense_override else None
    result_f = check_playcall_applied(gm, None, defense_expected, "HCO after HCT (user on defense)")
    
    return result_b and result_f

def run_scenario_4(gm, offense_override, defense_override):
    """Scenario 4: HCT (user has ball) -> HCO (offense) -> HCO (defense)"""
    print("\n  📋 Scenario 4: HCT (user has ball) -> HCO (offense) -> HCO (defense)")
    
    # A. HCT (user team has the ball) => trap break result
    print("  A. HCT (trap break)")
    set_playcall_overrides(gm, offense_override, defense_override)
    gm.game_state["offensive_state"] = "HCT"
    gm.offense_team = gm.home_team  # User team on offense
    gm.defense_team = gm.away_team
    
    # B. HCO (offensive override should be applied here) => Missed shot, DREB
    print("  B. HCO (offense override expected)")
    gm.game_state["offensive_state"] = "HCO"
    offense_expected = offense_override if offense_override else None
    result_b = check_playcall_applied(gm, offense_expected, None, "HCO after HCT (user on offense)")
    
    # C. HCO (defensive override should be applied here)
    print("  C. HCO (defense override expected)")
    # Possession flips
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    gm.game_state["offensive_state"] = "HCO"
    # User team is now on defense
    defense_expected = defense_override if defense_override else None
    result_c = check_playcall_applied(gm, None, defense_expected, "HCO after DREB (user on defense)")
    
    return result_b and result_c

def run_scenario_5(gm, offense_override, defense_override):
    """Scenario 5: HCO -> Fast Break -> BIP -> FCP -> SIP -> HCO (offense) -> HCO (defense)"""
    print("\n  📋 Scenario 5: HCO -> Fast Break -> BIP -> FCP -> SIP -> HCO (offense) -> HCO (defense)")
    
    # A. HCO => missed shot, DREB result
    print("  A. HCO (missed shot, DREB)")
    set_playcall_overrides(gm, offense_override, defense_override)
    gm.game_state["offensive_state"] = "HCO"
    gm.offense_team = gm.home_team  # User team on offense
    gm.defense_team = gm.away_team
    
    # B. Fast Break => Shot Make result
    print("  B. Fast Break (shot make)")
    gm.game_state["offensive_state"] = "FAST_BREAK"
    # Possession flips
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    
    # C. BIP
    print("  C. BIP")
    gm.game_state["offensive_state"] = "BASELINE_INBOUND"
    
    # D. FCP => Defensive Foul Result
    print("  D. FCP (defensive foul)")
    gm.game_state["offensive_state"] = "FCP"
    
    # E. SIP
    print("  E. SIP")
    gm.game_state["offensive_state"] = "SIDE_INBOUND"
    
    # F. HCO (offensive override should be applied here) => Missed shot, DREB
    print("  F. HCO (offense override expected)")
    # Possession flips back
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    gm.game_state["offensive_state"] = "HCO"
    # User team is back on offense
    offense_expected = offense_override if offense_override else None
    result_f = check_playcall_applied(gm, offense_expected, None, "HCO after SIP (user on offense)")
    
    # G. HCO (defensive override should be applied here)
    print("  G. HCO (defense override expected)")
    # Possession flips
    gm.offense_team, gm.defense_team = gm.defense_team, gm.offense_team
    gm.game_state["offensive_state"] = "HCO"
    # User team is now on defense
    defense_expected = defense_override if defense_override else None
    result_g = check_playcall_applied(gm, None, defense_expected, "HCO after DREB (user on defense)")
    
    return result_f and result_g

def run_all_tests():
    """Run all test scenarios with all three override combinations."""
    print("="*80)
    print("PLAYCALL OVERRIDE PERSISTENCE TESTS")
    print("="*80)
    
    test_configs = [
        ("Offense Only", "3-2 Motion", None),
        ("Defense Only", None, "Zone"),
        ("Both Overrides", "5-0 Motion", "Man"),
    ]
    
    scenarios = [
        ("Scenario 1", run_scenario_1),
        ("Scenario 2", run_scenario_2),
        ("Scenario 3", run_scenario_3),
        ("Scenario 4", run_scenario_4),
        ("Scenario 5", run_scenario_5),
    ]
    
    results = {}
    
    for config_name, offense_override, defense_override in test_configs:
        print(f"\n{'='*80}")
        print(f"TEST CONFIGURATION: {config_name}")
        print(f"{'='*80}")
        
        scenario_results = {}
        
        for scenario_name, scenario_func in scenarios:
            print(f"\n{scenario_name} - {config_name}")
            print("-" * 80)
            
            # Create fresh game for each scenario
            gm = create_test_game()
            
            try:
                result = scenario_func(gm, offense_override, defense_override)
                scenario_results[scenario_name] = result
                print(f"  {'✅ PASSED' if result else '❌ FAILED'}")
            except Exception as e:
                print(f"  ❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                scenario_results[scenario_name] = False
        
        results[config_name] = scenario_results
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for config_name, scenario_results in results.items():
        print(f"\n{config_name}:")
        passed = sum(1 for r in scenario_results.values() if r)
        total = len(scenario_results)
        print(f"  {passed}/{total} scenarios passed")
        for scenario_name, result in scenario_results.items():
            status = "✅" if result else "❌"
            print(f"    {status} {scenario_name}")
    
    # Overall summary
    total_passed = sum(sum(1 for r in results[config].values() if r) for config in results)
    total_tests = sum(len(results[config]) for config in results)
    
    print(f"\n{'='*80}")
    print(f"OVERALL: {total_passed}/{total_tests} tests passed")
    print(f"{'='*80}")
    
    return total_passed == total_tests

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

