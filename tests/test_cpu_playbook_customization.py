import random
from types import SimpleNamespace

from bson import ObjectId

from BackEnd.utils.cpu_playbook_customization import (
    build_cpu_playbook_for_team,
    build_user_schedule_cpu_playbook_groups,
    group_for_cpu_playbook_week,
    refresh_cpu_playbook_group_for_game_init,
)


def _player(pid, attrs, ratings):
    return SimpleNamespace(
        player_id=pid,
        attributes={**attrs, **{f"anchor_{k}": v for k, v in attrs.items()}},
        position_ratings=ratings,
    )


def _team():
    lineup = {
        "PG": _player("pg", {"SH": 90, "AG": 50, "SC": 45, "ST": 30}, {"PG": 80}),
        "SG": _player("sg", {"SH": 92, "AG": 55, "SC": 50, "ST": 30}, {"SG": 80}),
        "SF": _player("sf", {"SH": 88, "AG": 58, "SC": 52, "ST": 35}, {"SF": 80}),
        "PF": _player("pf", {"SH": 40, "AG": 45, "SC": 55, "ST": 60}, {"PF": 51}),
        "C": _player("c", {"SH": 25, "AG": 35, "SC": 50, "ST": 65}, {"C": 80}),
    }
    return SimpleNamespace(lineup=lineup, players={p.player_id: p for p in lineup.values()})


def _plays():
    rows = {
        "5-0 Motion": ("m50", "motion", None),
        "4-1 Motion": ("m41", "motion", None),
        "3-2 Motion": ("m32", "motion", None),
        "PF Post Motion": ("mpf", "motion", None),
        "Inside 1": ("i1", "set_play", "inside"),
        "Inside 2": ("i2", "set_play", "inside"),
        "Inside 3": ("i3", "set_play", "inside"),
        "Inside 4": ("i4", "set_play", "inside"),
        "Attack 1": ("a1", "set_play", "attack"),
        "Attack 2": ("a2", "set_play", "attack"),
        "Attack 3": ("a3", "set_play", "attack"),
        "Outside 1": ("o1", "set_play", "outside"),
        "Outside 2": ("o2", "set_play", "outside"),
        "Outside 3": ("o3", "set_play", "outside"),
        "Outside 4": ("o4", "set_play", "outside"),
    }
    return {
        name: {
            "play_id": pid,
            "name": name,
            "play_type": play_type,
            "play_focus": focus,
            "target_shooter": None,
            "motion_focus": None,
        }
        for name, (pid, play_type, focus) in rows.items()
    }


def test_build_user_schedule_cpu_playbook_groups_unique_ordered_opponents():
    schedule = [
        [("u", "a"), ("b", "c")],
        [("d", "u")],
        [("a", "u")],
        [("u", "e")],
        [("f", "u")],
    ]

    result = build_user_schedule_cpu_playbook_groups(schedule, "u")

    assert result["ordered_opponents"] == ["a", "d", "e", "f"]
    assert result["groups"] == {"1": ["a", "d", "e", "f"]}


def test_group_for_cpu_playbook_week_uses_defined_stagger():
    assert group_for_cpu_playbook_week(1) == 1
    assert group_for_cpu_playbook_week(5) == 5
    assert group_for_cpu_playbook_week(11) == 1
    assert group_for_cpu_playbook_week(25) == 5
    assert group_for_cpu_playbook_week(10) is None


def test_build_cpu_playbook_build_week_sets_constraints_and_play_fields():
    random.seed(7)

    result = build_cpu_playbook_for_team(
        _team(),
        {"position_filters": {"standard": []}, "pc_order": {"offense": [], "defense": []}},
        _plays(),
        update_week=False,
    )

    settings = result.playbook_settings
    # Man variants are randomized like zones (Base / Deny / Loose each 1..50, summing to 100)
    assert set(settings["man_defense"]) == {"man_normal", "man_tight", "man_loose"}
    assert sum(settings["man_defense"].values()) == 100
    assert max(settings["man_defense"].values()) <= 50
    assert min(settings["man_defense"].values()) >= 1
    assert sum(settings["zone_defense"].values()) == 100
    assert max(settings["zone_defense"].values()) <= 50
    assert sum(settings["fast_breaks"].values()) == 100
    assert max(settings["fast_breaks"].values()) <= 50
    assert sum(settings["motion"].values()) == 100
    assert "mpf" in settings["motion"]
    assert sum(settings["set_plays"].values()) == 100
    assert len(settings["set_plays"]) >= 6

    selected_set_ids = set(settings["set_plays"])
    for play in result.plays.values():
        if play["play_type"] == "set_play" and play["play_id"] in selected_set_ids:
            assert play["target_shooter"] in {"PG", "SG", "SF", "PF", "C"}
        if play["play_type"] == "motion" and play["play_id"] in settings["motion"]:
            assert play["motion_focus"] in {None, "inside", "attack", "outside"}


def test_build_cpu_playbook_update_week_preserves_and_appends_strong_focus():
    random.seed(11)
    base = {
        "set_plays": {"i1": 60, "a1": 40},
        "motion": {"m50": 34, "m41": 33, "m32": 33},
    }

    result = build_cpu_playbook_for_team(_team(), base, _plays(), update_week=True)

    selected = set(result.playbook_settings["set_plays"])
    assert {"i1", "a1"}.issubset(selected)
    assert len(selected) >= 3
    assert sum(result.playbook_settings["set_plays"].values()) == 100


class _FakeFtdCollection:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    def find_one(self, query):
        franchise_id = query["franchise_id"]
        team_id = query["team_id"]
        return self.docs.get((str(franchise_id), str(team_id)))

    def update_one(self, query, update):
        doc = self.find_one(query)
        assert doc is not None
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        self.updates.append((query, update))


def test_refresh_cpu_playbook_group_for_game_init_is_idempotent_by_week():
    random.seed(13)
    fid = ObjectId()
    user_id = ObjectId()
    team_ids = [ObjectId() for _ in range(4)]
    docs = {
        (str(fid), str(tid)): {
            "playbook_settings": {},
            "plays": _plays(),
        }
        for tid in team_ids
    }
    coll = _FakeFtdCollection(docs)
    franchise_doc = {
        "cpu_playbook_schedule": {"groups": {"1": [str(tid) for tid in team_ids]}},
        "schedule": [],
    }
    teams_by_id = {str(tid): _team() for tid in team_ids}

    refreshed = refresh_cpu_playbook_group_for_game_init(
        franchise_id=fid,
        franchise_doc=franchise_doc,
        week=1,
        user_team_id=str(user_id),
        teams_by_id=teams_by_id,
        franchise_team_data_collection=coll,
    )
    refreshed_again = refresh_cpu_playbook_group_for_game_init(
        franchise_id=fid,
        franchise_doc=franchise_doc,
        week=1,
        user_team_id=str(user_id),
        teams_by_id=teams_by_id,
        franchise_team_data_collection=coll,
    )

    assert set(refreshed) == {str(tid) for tid in team_ids}
    assert refreshed_again == []
    assert len(coll.updates) == 4
    for doc in docs.values():
        assert doc["cpu_playbook_last_refresh_week"] == 1
        assert doc["cpu_playbook_last_refresh_group"] == 1
        assert doc["playbook_settings"]["_meta"]["cpu_customized"] is True


def test_cpu_zone_selector_uses_cpu_playbook_settings():
    from BackEnd.models.turn_manager import TurnManager

    tm = object.__new__(TurnManager)
    offense = SimpleNamespace(team_id="off", name="Off", is_user_team=True, playbook_settings={})
    defense = SimpleNamespace(
        team_id="def",
        name="CPU Defense",
        is_user_team=False,
        playbook_settings={"zone_defense": {"zone_23": 0, "zone_32": 100, "zone_131": 0}},
    )
    tm.game = SimpleNamespace(offense_team=offense, defense_team=defense)

    assert tm._load_playbook_settings("def") == defense.playbook_settings
    assert tm._select_zone_defense_with_playbook_weights() == "3-2-zone"
