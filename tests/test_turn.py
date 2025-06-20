
import pytest
from BackEnd.models.player import Player
from BackEnd.main import assign_roles, resolve_turn
from BackEnd.constants import POSITION_LIST

# Utility: Create mock Player
def mock_player(first, last, team="Lancaster"):
    base = {
        "first_name": first,
        "last_name": last,
        "team": team,
        "SC": 80, "SH": 80, "ID": 60, "OD": 60,
        "PS": 70, "BH": 70, "RB": 50, "ST": 55,
        "AG": 75, "FT": 80, "ND": 65, "IQ": 90,
        "CH": 85, "EM": 0, "MO": 0
    }
    return Player(base)

# Setup basic game state
def build_mock_game_state():
    return {
        "players": {
            "Lancaster": {pos: mock_player(pos, "L") for pos in POSITION_LIST},
            "Bentley-Truman": {pos: mock_player(pos, "B", "Bentley-Truman") for pos in POSITION_LIST}
        },
        "offense_team": "Lancaster",
        "defense_team": "Bentley-Truman",
        "offensive_state": "HALF_COURT",
        "offense_playcall": "Base",
        "defense_playcall": "Man",
        "tempo": "normal",
        "aggression": "normal",
        "clock": 600,
        "possession": "Lancaster",
        "current_playcall": "Base",
        "defense_playcall": "Man",
        "score": {"Lancaster": 0, "Bentley-Truman": 0},
        "game_log": [],
        "playcall_weights": {
            "Lancaster": {"Base": 1.0},
            "Bentley-Truman": {"Base": 1.0}
        },
        "strategy_calls": {
            "Lancaster": {
                "offense_playcall": "Base",
                "defense_playcall": "Man",
                "tempo_call": "normal",
                "aggression_call": "normal"
            },
            "Bentley-Truman": {
                "offense_playcall": "Base",
                "defense_playcall": "Man",
                "tempo_call": "normal",
                "aggression_call": "normal"
            }
        },
        "strategy_settings": {
            "Lancaster": {
                "defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "half_court_trap": 2, "full_court_press": 2},
            "Bentley-Truman": {
                "defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "half_court_trap": 2, "full_court_press": 2} 
        },
        "playcall_tracker": {
            "Lancaster": {"Base": 0},
            "Bentley-Truman": {"Base": 0}
        },
        "defense_playcall_tracker": {
            "Lancaster": {"Man": 0, "Zone": 0},
            "Bentley-Truman": {"Man": 0, "Zone": 0}
        },
        "scouting_data": {
            "Lancaster": {
                "offense": {
                    "Fast_Break_Entries": 0, 
                    "Fast_Break_Success": 0, 
                    "Playcalls": {
                        "Base": {"used": 0,"success": 0}, 
                        "Freelance": {"used": 0,"success": 0}, 
                        "Inside": {"used": 0,"success": 0}, 
                        "Attack": {"used": 0,"success": 0}, 
                        "Outside": {"used": 0,"success": 0}, 
                        "Set": {"used": 0,"success": 0}}},
                "defense": {
                    "Man": {"used": 0,"success": 0}, 
                    "Zone": {"used": 0,"success": 0}, 
                    "vs_Fast_Break": {"used": 0,"success": 0}}
            },
            "Bentley-Truman": {
                "offense": {
                    "Fast_Break_Entries": 0, 
                    "Fast_Break_Success": 0, 
                    "Playcalls": {"Base": {"used": 0,"success": 0}, "Freelance": {"used": 0,"success": 0}, "Inside": {"used": 0,"success": 0}, "Attack": {"used": 0,"success": 0}, "Outside": {"used": 0,"success": 0}, "Set": {"used": 0,"success": 0}}},
                "defense": {
                    "Man": {"used": 0,"success": 0}, 
                    "Zone": {"used": 0,"success": 0}, 
                    "vs_Fast_Break": {"used": 0,"success": 0}}
            }
        },
        "quarter": 1,
        "points_by_quarter": {
            "Lancaster": [0, 0, 0, 0],
            "Bentley-Truman": [0, 0, 0, 0]
        },
        "team_fouls": {
            "Lancaster": 0,
            "Bentley-Truman": 0
        },
        "free_throws": 0,
        "free_throws_remaining": 0,
        "last_ball_handler": None,
        "bonus_active": False,
        "team_attributes": {
            "Lancaster": {
                "shot_threshold": 150,
                "ft_shot_threshold": 150,
                "turnover_threshold": -250,
                "foul_threshold": 40,
                "rebound_modifier": 0.8,
                "momentum_score": 0,
                "momentum_delta": 0,
                "offensive_efficienty": 0,
                "offensive_adjust": 0,
                "o_tendency_reads": 0,
                "d_tendency_reads": 0,
                "team_chemistry": 0
            },
            "Bentley-Truman": {
                "shot_threshold": 150,
                "ft_shot_threshold": 150,
                "turnover_threshold": -250,
                "foul_threshold": 40,
                "rebound_modifier": 0.8,
                "momentum_score": 0,
                "momentum_delta": 0,
                "offensive_efficienty": 0,
                "offensive_adjust": 0,
                "o_tendency_reads": 0,
                "d_tendency_reads": 0,
                "team_chemistry": 0
            }}
    }

def test_assign_roles_outputs_player_objects():
    game_state = build_mock_game_state()
    roles = assign_roles(game_state, "Base")

    assert roles["shooter"] is not None
    assert roles["screener"] is not None
    assert roles["ball_handler"] is not None
    assert hasattr(roles["shooter"], "record_stat")

def test_turn_returns_valid_result():
    game_state = build_mock_game_state()
    result = resolve_turn(game_state)

    assert result['result_type'] in {"SHOT", "TURNOVER", "FOUL", "HCO", "MISS", "BLOCK", "MAKE"}
