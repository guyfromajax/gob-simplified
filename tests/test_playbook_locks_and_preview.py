"""Locks normalization + shot-weights preview helpers for Playbooks redesign."""

from BackEnd.utils.playbook_settings_utils import (
    build_simplified_playbook_settings,
    empty_playbook_locks,
    normalize_playbook_locks,
)


def test_empty_playbook_locks_has_all_sections():
    locks = empty_playbook_locks()
    assert set(locks) == {
        "motion",
        "set_plays",
        "fast_breaks",
        "hc_traps",
        "man_defense",
        "zone_defense",
    }
    assert all(value == [] for value in locks.values())


def test_normalize_playbook_locks_list_and_dict_forms():
    plays_by_id = {
        "pid-motion": {"play_id": "pid-motion", "name": "Flex"},
        "pid-set": {"play_id": "pid-set", "name": "Horns"},
    }
    plays_by_name = {
        "Flex": plays_by_id["pid-motion"],
        "Horns": plays_by_id["pid-set"],
    }

    locks = normalize_playbook_locks(
        {
            "motion": ["Flex", "pid-motion", "Flex"],  # name + id + dup
            "set_plays": {"pid-set": True, "ghost": False},
            "man_defense": ["Base Man", "man_tight", "Base Man"],  # display name + id + dup
            "zone_defense": {"2-3 Zone": 1},
            "fast_breaks": ["Triangle"],
            "hc_traps": {"Straight Pressure": True},
        },
        plays_by_id,
        plays_by_name,
    )

    assert locks["motion"] == ["pid-motion"]
    assert locks["set_plays"] == ["pid-set"]
    assert locks["man_defense"] == ["man_normal", "man_tight"]
    assert locks["zone_defense"] == ["zone_23"]
    assert locks["fast_breaks"] == ["triangle"]
    assert locks["hc_traps"] == ["straight_pressure"]


def test_normalize_playbook_locks_missing_input():
    assert normalize_playbook_locks(None, {}, {}) == empty_playbook_locks()
    assert normalize_playbook_locks("nope", {}, {}) == empty_playbook_locks()


def test_build_simplified_includes_locks():
    plays_by_id = {"p1": {"play_id": "p1", "name": "Motion A"}}
    plays_by_name = {"Motion A": plays_by_id["p1"]}
    simplified = build_simplified_playbook_settings(
        {
            "motion": {"p1": 100},
            "set_plays": {},
            "fast_breaks": {"triangle": 100},
            "hc_traps": {"standard_trap": 100},
            "man_defense": {"man_normal": 100},
            "zone_defense": {"zone_23": 100},
            "pc_order": {"offense": ["p1"], "defense": []},
            "locks": {"motion": ["p1"], "man_defense": ["Man"]},
        },
        plays_by_id,
        plays_by_name,
    )
    assert simplified["locks"]["motion"] == ["p1"]
    assert simplified["locks"]["man_defense"] == ["man_normal"]
    assert simplified["locks"]["set_plays"] == []

