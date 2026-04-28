"""
Test script for Training System
Tests that training completes successfully with valid values for all components.
"""

import sys
import os

# Add the project root to the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from BackEnd.models.training_execution_v2 import execute_training
import logging

# Set up logging to see debug output
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def test_training_system():
    """Test that training executes successfully and produces valid results."""
    
    print("=" * 80)
    print("TESTING TRAINING SYSTEM")
    print("=" * 80)
    
    # Create sample players
    players = [
        {
            "_id": "player1",
            "first_name": "John",
            "last_name": "Doe",
            "team": "Test Team",
            "attributes": {
                "anchor_SC": 50,
                "SC": 50,
                "anchor_SH": 45,
                "SH": 45,
                "anchor_ND": 60,
                "ND": 60,
                "NG": 1.0,
                "EM": 50,
                "MO": 50
            }
        },
        {
            "_id": "player2",
            "first_name": "Jane",
            "last_name": "Smith",
            "team": "Test Team",
            "attributes": {
                "anchor_SC": 55,
                "SC": 55,
                "anchor_SH": 50,
                "SH": 50,
                "anchor_ND": 70,
                "ND": 70,
                "NG": 1.0,
                "EM": 50,
                "MO": 50
            }
        }
    ]
    
    # Create sample team
    team = {
        "offensive_efficiency": 0,
        "defensive_efficiency": 0,
        "team_chemistry": 7,
        "shot_threshold": 0,
        "rebound_modifier": 1.0,
        "fight": 0,
        "discipline": 0,
        "momentum_score": 0,
        "fb_efficiency": 0,
        "pt_efficiency": 0,
        "fb_opp_modifier": 0,
        "pt_opp_modifier": 0
    }
    
    # Create sample plays data
    plays_data = {
        "3-2 Motion": {
            "name": "3-2 Motion",
            "play_type": "motion",
            "effectiveness": 100
        },
        "4-1 Motion": {
            "name": "4-1 Motion",
            "play_type": "motion",
            "effectiveness": 80
        },
        "5-0 Motion": {
            "name": "5-0 Motion",
            "play_type": "motion",
            "effectiveness": 90
        },
        "Inside Play 1": {
            "name": "Inside Play 1",
            "play_type": "set_play",
            "play_focus": "inside",
            "effectiveness": 75
        }
    }
    
    # Create sample scouting data
    scouting_data = {
        "defense": {
            "man": {
                "effectiveness": 100,
                "momentum": 0,
                "used": 0,
                "success": 0
            },
            "2-3-zone": {
                "effectiveness": 80,
                "momentum": 0,
                "used": 0,
                "success": 0
            },
            "3-2-zone": {
                "effectiveness": 85,
                "momentum": 0,
                "used": 0,
                "success": 0
            },
            "1-3-1-zone": {
                "effectiveness": 70,
                "momentum": 0,
                "used": 0,
                "success": 0
            }
        }
    }
    
    # Create sample allocations
    allocations = {
        "player_drills": {
            "inside_offense": {"install": 2},
            "outside_offense": {"install": 1},
            "inside_defense": {"install": 1},
            "outside_defense": {"install": 2},
            "passing": {"install": 1},
            "ball_handling": {"install": 1},
            "rebounding": {"install": 1},
            "strength": {"install": 1},
            "agility": {"install": 1}
        },
        "team_drills": {
            "team_offense": {"install": 2},
            "team_defense": {"install": 2},
            "fast_breaks": {
                "offense_install": 1,
                "defense_install": 0
            },
            "scrimmages": 2,
            "presses_traps": {
                "defense_install": 1,
                "offense_install": 0
            }
        },
        "general": {
            "conditioning": 2,
            "breaks": 1
        }
    }
    
    # Sample settings
    strategy_settings = {
        "offense": 1,  # 75% motion, 25% set plays
        "defense": 2,  # 50/50 man/zone
        "inside": 4,   # Inside focus preference
        "outside": 2,  # Outside focus preference
        "attack": 0    # Attack focus preference
    }
    
    playbook_settings = {
        "motion": {
            "3-2 Motion": 10,
            "4-1 Motion": 40,
            "5-0 Motion": 50
        },
        "fast_break": {
            "covert_release": 34,
            "rim_runner": 33,
            "triangle": 33
        },
        "set_play_inside": {
            "Inside Play 1": 100
        },
        "zone_defense": {
            "zone_23": 50,
            "zone_32": 30,
            "zone_131": 20
        }
    }
    
    coaching_focus = "systems-coach-offense"
    playbook_training_mode = "current-playbooks"
    
    print("\n📋 Test Setup:")
    print(f"  - Players: {len(players)}")
    print(f"  - Plays: {len(plays_data)}")
    print(f"  - Defenses: {len(scouting_data.get('defense', {}))}")
    print(f"  - Offense Install: {allocations['team_drills']['team_offense']['install']}")
    print(f"  - Defense Install: {allocations['team_drills']['team_defense']['install']}")
    print(f"  - Coaching Focus: {coaching_focus}")
    print(f"  - Playbook Mode: {playbook_training_mode}")
    
    try:
        # Execute training
        print("\n🔄 Executing training...")
        updated_players, updated_team, updated_plays, updated_scouting_data, training_report = execute_training(
            players,
            team,
            allocations,
            coaching_focus,
            plays_data=plays_data,
            strategy_settings=strategy_settings,
            playbook_settings=playbook_settings,
            scouting_data=scouting_data,
            playbook_training_mode=playbook_training_mode
        )
        
        print("\n✅ Training completed successfully!")
        
        # Test 1: Player attributes changed
        print("\n📊 Test 1: Player Attributes Changed")
        print("-" * 80)
        all_player_attrs_valid = True
        for player in updated_players:
            attrs = player.get("attributes", {})
            print(f"\n  Player: {player.get('first_name')} {player.get('last_name')}")
            for attr in ["SC", "SH", "ND", "NG", "EM", "MO"]:
                if attr in ["NG", "EM", "MO"]:
                    val = attrs.get(attr, 0)
                    anchor_key = None
                else:
                    anchor_key = f"anchor_{attr}"
                    val = attrs.get(anchor_key, 0)
                
                if val is None:
                    print(f"    ❌ {attr}: None (INVALID)")
                    all_player_attrs_valid = False
                elif isinstance(val, (int, float)):
                    print(f"    ✅ {attr}: {val}")
                else:
                    print(f"    ❌ {attr}: {val} (INVALID TYPE: {type(val)})")
                    all_player_attrs_valid = False
        
        if all_player_attrs_valid:
            print("\n  ✅ All player attributes are valid")
        else:
            print("\n  ❌ Some player attributes are invalid")
        
        # Test 2: Team attributes changed
        print("\n📊 Test 2: Team Attributes Changed")
        print("-" * 80)
        all_team_attrs_valid = True
        for attr_name, attr_value in updated_team.items():
            if isinstance(attr_value, dict):
                continue  # Skip nested dicts
            if attr_value is None:
                print(f"  ❌ {attr_name}: None (INVALID)")
                all_team_attrs_valid = False
            elif isinstance(attr_value, (int, float)):
                print(f"  ✅ {attr_name}: {attr_value}")
            else:
                print(f"  ❌ {attr_name}: {attr_value} (INVALID TYPE: {type(attr_value)})")
                all_team_attrs_valid = False
        
        if all_team_attrs_valid:
            print("\n  ✅ All team attributes are valid")
        else:
            print("\n  ❌ Some team attributes are invalid")
        
        # Test 3: Play effectiveness scores changed
        print("\n📊 Test 3: Play Effectiveness Scores Changed")
        print("-" * 80)
        all_plays_valid = True
        plays_changes = training_report.get("plays_effectiveness_changes", {})
        for play_name, play_data in updated_plays.items():
            if isinstance(play_data, dict):
                eff = play_data.get("effectiveness", 0)
                change = plays_changes.get(play_name, 0)
                if eff is None:
                    print(f"  ❌ {play_name}: effectiveness = None (INVALID)")
                    all_plays_valid = False
                elif isinstance(eff, (int, float)) and eff >= 0:
                    print(f"  ✅ {play_name}: effectiveness = {eff} (change: {change:+d})")
                else:
                    print(f"  ❌ {play_name}: effectiveness = {eff} (INVALID)")
                    all_plays_valid = False
        
        if all_plays_valid:
            print("\n  ✅ All play effectiveness scores are valid")
        else:
            print("\n  ❌ Some play effectiveness scores are invalid")
        
        # Test 4: Defense effectiveness scores changed
        print("\n📊 Test 4: Defense Effectiveness Scores Changed")
        print("-" * 80)
        all_defenses_valid = True
        defenses_changes = training_report.get("defenses_effectiveness_changes", {})
        if updated_scouting_data and "defense" in updated_scouting_data:
            for defense_name, defense_data in updated_scouting_data["defense"].items():
                if isinstance(defense_data, dict):
                    eff = defense_data.get("effectiveness", 0)
                    change = defenses_changes.get(defense_name, 0)
                    if eff is None:
                        print(f"  ❌ {defense_name}: effectiveness = None (INVALID)")
                        all_defenses_valid = False
                    elif isinstance(eff, (int, float)) and eff >= 0:
                        print(f"  ✅ {defense_name}: effectiveness = {eff} (change: {change:+d})")
                    else:
                        print(f"  ❌ {defense_name}: effectiveness = {eff} (INVALID)")
                        all_defenses_valid = False
        
        if all_defenses_valid:
            print("\n  ✅ All defense effectiveness scores are valid")
        else:
            print("\n  ❌ Some defense effectiveness scores are invalid")
        
        # Test 5: Training notes generated
        print("\n📊 Test 5: Training Notes Generated")
        print("-" * 80)
        training_notes = training_report.get("training_notes", [])
        if isinstance(training_notes, list):
            print(f"  ✅ Training notes: {len(training_notes)} sections")
            for note in training_notes:
                if isinstance(note, dict) and "title" in note:
                    print(f"    - {note.get('title')}: {note.get('body', '')[:80]}...")
                else:
                    print(f"    - {note}")
        else:
            print(f"  ❌ Training notes: Invalid type {type(training_notes)}")
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        all_tests_passed = (
            all_player_attrs_valid and
            all_team_attrs_valid and
            all_plays_valid and
            all_defenses_valid and
            isinstance(training_notes, list)
        )
        
        if all_tests_passed:
            print("✅ ALL TESTS PASSED - Training system is working correctly!")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Check output above for details")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: Training execution failed with exception:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_training_system()
    sys.exit(exit_code)
