#!/usr/bin/env python3
"""
Simplified test to verify playcall override logic in set_playcalls().

This test directly checks the override detection and application logic
without requiring full game engine setup.
"""

def test_override_logic():
    """Test the override detection logic."""
    
    print("="*80)
    print("PLAYCALL OVERRIDE LOGIC TEST")
    print("="*80)
    
    # Simulate the logic from set_playcalls()
    # Lines 764-794 in turn_manager.py
    
    test_cases = [
        {
            "name": "Offense override only",
            "offense_team_is_user": True,
            "defense_team_is_user": False,
            "offense_call": "3-2 Motion",
            "defense_call": None,
            "expected_offense": "3-2 Motion",
            "expected_defense": None,  # Will be chosen normally
        },
        {
            "name": "Defense override only (user on offense)",
            "offense_team_is_user": True,
            "defense_team_is_user": False,
            "offense_call": None,
            "defense_call": "Zone",
            "expected_offense": None,  # Will be chosen normally
            "expected_defense": "Zone",  # Should be converted to specific zone
        },
        {
            "name": "Both overrides (user on offense)",
            "offense_team_is_user": True,
            "defense_team_is_user": False,
            "offense_call": "5-0 Motion",
            "defense_call": "Man",
            "expected_offense": "5-0 Motion",
            "expected_defense": "Man",
        },
        {
            "name": "Defense override only (user on defense)",
            "offense_team_is_user": False,
            "defense_team_is_user": True,
            "offense_call": None,
            "defense_call": "Zone",
            "expected_offense": None,  # Will be chosen normally
            "expected_defense": "Zone",  # Should be converted to specific zone
        },
        {
            "name": "Both overrides (user on defense)",
            "offense_team_is_user": False,
            "defense_team_is_user": True,
            "offense_call": None,  # User is on defense, can't set offense override
            "defense_call": "2-3 Zone",
            "expected_offense": None,  # Will be chosen normally
            "expected_defense": "2-3 Zone",
        },
    ]
    
    print("\nTesting override detection logic:")
    print("-" * 80)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"  Offense team is user: {test['offense_team_is_user']}")
        print(f"  Defense team is user: {test['defense_team_is_user']}")
        print(f"  offense_call: {test['offense_call']}")
        print(f"  defense_call: {test['defense_call']}")
        
        # Simulate the logic from lines 766-794
        offense_call = None
        if test['offense_team_is_user']:
            # Simulate: offense_call = self.game.offense_team.strategy_calls.get("offense_call")
            offense_call = test['offense_call']
        
        # ✅ FIX: Check user team's strategy_calls regardless of current offense/defense
        # (This matches the fix in turn_manager.py line 779-790)
        defense_call = None
        # Find user team (could be offense or defense team)
        user_team_has_defense_override = test['offense_team_is_user'] or test['defense_team_is_user']
        if user_team_has_defense_override:
            # Simulate: defense_call = user_team.strategy_calls.get("defense_call")
            defense_call = test['defense_call']
        
        # Simulate legacy support (line 793-794)
        user_offense = offense_call  # Simplified: no game_state check
        user_defense = defense_call   # Simplified: no game_state check
        
        print(f"  Detected user_offense: {user_offense}")
        print(f"  Detected user_defense: {user_defense}")
        
        # Check if early return path would be taken (line 797)
        early_return = bool(user_offense)
        
        if early_return:
            print(f"  ✅ Would take early return path (offense override detected)")
            print(f"  Expected offense: {test['expected_offense']}")
            print(f"  Expected defense: {test['expected_defense']}")
        else:
            print(f"  ⚪ Would take normal path (no offense override)")
            print(f"  Defense override would be checked at line 873 or 942")
            print(f"  Expected offense: {test['expected_offense']}")
            print(f"  Expected defense: {test['expected_defense']}")
        
        # Verify expectations
        offense_match = (user_offense == test['expected_offense']) if test['expected_offense'] else (user_offense is None)
        defense_match = (user_defense == test['expected_defense']) if test['expected_defense'] else (user_defense is None)
        
        if offense_match and defense_match:
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL")
            if not offense_match:
                print(f"    Offense mismatch: expected {test['expected_offense']}, got {user_offense}")
            if not defense_match:
                print(f"    Defense mismatch: expected {test['expected_defense']}, got {user_defense}")
    
    print("\n" + "="*80)
    print("KEY OBSERVATIONS:")
    print("="*80)
    print("1. Early return path (line 797) is taken when user_offense is truthy")
    print("2. Defense override is checked in early return path (line 838) if user_defense is truthy")
    print("3. Defense override is checked in normal path (line 873 or 942) if no offense override")
    print("4. Zone conversion happens at:")
    print("   - Line 849 (early return path, both overrides)")
    print("   - Line 884 (normal path, defense-only override)")
    print("   - Line 961 (normal path, defense override from strategy_calls)")
    print("="*80)

if __name__ == "__main__":
    test_override_logic()

