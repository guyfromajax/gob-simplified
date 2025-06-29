import pytest
from BackEnd.models.player import Player
from BackEnd.constants import ALL_ATTRS

mock_data = {
    "first_name": "Ervin",
    "last_name": "Miller",
    "team": "Lancaster",
    "SC": 80, "SH": 75, "ID": 60, "OD": 70,
    "PS": 85, "BH": 90, "RB": 55, "ST": 50,
    "AG": 88, "FT": 77, "ND": 68, "IQ": 92,
    "CH": 81, "EM": 0, "MO": 0
}


def test_get_name():
    p = Player(mock_data)
    assert p.get_name() == "Ervin Miller"


def test_record_stat_increments_correctly():
    p = Player(mock_data)
    p.record_stat("AST")
    assert p.stats["game"]["AST"] == 1


def test_pts_updates_on_made_shot():
    p = Player(mock_data)
    p.record_stat("FGM")
    p.record_stat("3PTM")
    p.record_stat("FTM")
    assert p.stats["game"]["PTS"] == (2 * 1) + 1 + 1


def test_decay_energy_scales_attributes():
    p = Player(mock_data)
    initial_SC = p.attributes["SC"]
    p.decay_energy(0.2)
    assert p.attributes["NG"] < 1.0
    assert p.attributes["SC"] < initial_SC


def test_recharge_energy_increases_NG():
    p = Player(mock_data)
    p.decay_energy(0.5)
    before = p.attributes["NG"]
    p.recharge_energy(0.3)
    after = p.attributes["NG"]
    assert after > before


def test_reset_energy_restores_attributes():
    p = Player(mock_data)
    p.decay_energy(0.3)
    p.reset_energy()
    for attr in ALL_ATTRS:
        assert p.attributes[attr] == mock_data[attr]

# tests/test_player.py

def test_player_initialization_from_nested_attributes():
    mock_doc = {
        "first_name": "Test",
        "last_name": "Player",
        "team": "Lancaster",
        "attributes": {
            "SC": 5,
            "SH": 4,
            "ID": 3,
            "OD": 2,
            "PS": 1,
            "BH": 6,
            "RB": 5,
            "ST": 4,
            "AG": 3,
            "FT": 2,
            "ND": 1,
            "IQ": 7,
            "CH": 8,
            "EM": 9,
            "MO": 10,
            "NG": 1.2
        }
    }

    player = Player(mock_doc)

    assert player.SC == 5
    assert player.SH == 4
    assert player.ID == 3
    assert player.OD == 2
    assert player.PS == 1
    assert player.BH == 6
    assert player.RB == 5
    assert player.ST == 4
    assert player.AG == 3
    assert player.FT == 2
    assert player.ND == 1
    assert player.IQ == 7
    assert player.CH == 8
    assert player.EM == 9
    assert player.MO == 10
    assert abs(player.NG - 1.2) < 0.001

