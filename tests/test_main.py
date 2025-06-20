
import pytest
from BackEnd.main import build_box_score_from_player_stats
from BackEnd.models.player import Player

mock_data = {
    "first_name": "Test",
    "last_name": "Player",
    "team": "Lancaster",
    "SC": 80, "SH": 70, "ID": 60, "OD": 60,
    "PS": 70, "BH": 80, "RB": 60, "ST": 55,
    "AG": 75, "FT": 80, "ND": 65, "IQ": 90,
    "CH": 80, "EM": 0, "MO": 0
}

def test_box_score_contains_correct_player_name():
    player = Player(mock_data)
    game_state = {
        "players": {
            "Lancaster": {
                "PG": player
            }
        }
    }

    box_score = build_box_score_from_player_stats(game_state)
    assert "Lancaster" in box_score
    assert "Test Player" in box_score["Lancaster"]
    assert isinstance(box_score["Lancaster"]["Test Player"], dict)

def test_box_score_stats_match_player_game_stats():
    player = Player(mock_data)
    player.record_stat("AST", 3)
    player.record_stat("FGM", 2)
    player.record_stat("3PTM", 1)
    player.record_stat("FTM", 2)

    game_state = {
        "players": {
            "Lancaster": {
                "PG": player
            }
        }
    }

    box_score = build_box_score_from_player_stats(game_state)
    stats = box_score["Lancaster"]["Test Player"]
    assert stats["AST"] == 3
    assert stats["FGM"] == 2
    assert stats["3PTM"] == 1
    assert stats["FTM"] == 2
    assert stats["PTS"] == (2 * 2) + 1 + 2
