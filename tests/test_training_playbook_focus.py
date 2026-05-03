"""Custom Training Playbook: CMD distribution restricted to training_playbook_focus ids."""

import copy

from BackEnd.models.training_execution_v2 import (
    _apply_defense_training,
    _apply_offense_play_training,
)


def _plays_three():
    return {
        "k1": {
            "play_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
            "play_type": "motion",
            "motion_focus": "balanced",
            "effectiveness": 10,
            "name": "Motion One",
        },
        "k2": {
            "play_id": "bbbbbbbbbbbbbbbbbbbbbbbb",
            "play_type": "motion",
            "motion_focus": "inside",
            "effectiveness": 20,
            "name": "Motion Two",
        },
        "k3": {
            "play_id": "cccccccccccccccccccccccc",
            "play_type": "set_play",
            "play_focus": "inside",
            "target_shooter": "PG",
            "effectiveness": 30,
            "name": "Set One",
        },
    }


def test_custom_offense_cmd_even_split_selected_plays_only():
    plays = _plays_three()
    before = {k: plays[k]["effectiveness"] for k in plays}
    focus = {"offense": ["aaaaaaaaaaaaaaaaaaaaaaaa", "cccccccccccccccccccccccc"], "defense": []}

    out = _apply_offense_play_training(
        copy.deepcopy(plays),
        100,
        "custom",
        {},
        {},
        training_playbook_focus=focus,
    )

    assert out["k1"]["effectiveness"] == before["k1"] + 50
    assert out["k3"]["effectiveness"] == before["k3"] + 50
    assert out["k2"]["effectiveness"] == before["k2"]


def test_custom_offense_single_play_gets_all_points():
    plays = _plays_three()
    before = {k: plays[k]["effectiveness"] for k in plays}
    focus = {"offense": ["bbbbbbbbbbbbbbbbbbbbbbbb"], "defense": []}

    out = _apply_offense_play_training(
        copy.deepcopy(plays),
        100,
        "custom",
        {},
        {},
        training_playbook_focus=focus,
    )

    assert out["k2"]["effectiveness"] == before["k2"] + 100
    assert out["k1"]["effectiveness"] == before["k1"]
    assert out["k3"]["effectiveness"] == before["k3"]


def test_custom_defense_cmd_maps_row_ids_and_splits_evenly():
    scouting = {
        "defense": {
            "man": {"effectiveness": 0, "momentum": 0},
            "2-3-zone": {"effectiveness": 0, "momentum": 0},
            "3-2-zone": {"effectiveness": 99, "momentum": 0},
            "1-3-1-zone": {"effectiveness": 0, "momentum": 0},
        }
    }
    focus = {"offense": [], "defense": ["man_normal", "zone_23"]}

    out = _apply_defense_training(
        copy.deepcopy(scouting),
        101,
        "custom",
        {},
        {},
        training_playbook_focus=focus,
    )
    d = out["defense"]
    # 101 // 2 = 50, remainder 1 → 51 + 50
    assert d["man"]["effectiveness"] == 51
    assert d["2-3-zone"]["effectiveness"] == 50
    assert d["3-2-zone"]["effectiveness"] == 99


def test_custom_defense_dedupes_man_variants_to_one_bucket():
    scouting = {
        "defense": {
            "man": {"effectiveness": 10, "momentum": 0},
            "2-3-zone": {"effectiveness": 0, "momentum": 0},
        }
    }
    # man_normal + man_pressure both map to canonical "man" → one slot, all 40 points to man
    focus = {"offense": [], "defense": ["man_normal", "man_pressure"]}

    out = _apply_defense_training(
        copy.deepcopy(scouting),
        40,
        "custom",
        {},
        {},
        training_playbook_focus=focus,
    )
    assert out["defense"]["man"]["effectiveness"] == 50
    assert out["defense"]["2-3-zone"]["effectiveness"] == 0


def test_custom_offense_zero_points_noop():
    plays = _plays_three()
    focus = {"offense": ["aaaaaaaaaaaaaaaaaaaaaaaa"], "defense": []}
    inn = copy.deepcopy(plays)
    before = {k: inn[k]["effectiveness"] for k in inn}
    out = _apply_offense_play_training(inn, 0, "custom", {}, {}, training_playbook_focus=focus)
    for k in before:
        assert out[k]["effectiveness"] == before[k]
