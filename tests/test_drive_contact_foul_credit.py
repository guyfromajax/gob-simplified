"""Drive-contact D_FOUL credit: the fouled man must have had the ball.

Twin of test_dead_ball_to_credit.py. get_ball_handler_from_skeleton still
omits drive (shot-clock IQ + zone RNG). The driver is stashed at the
drive-contact pin and consumed at the top of resolve_non_shooting_foul.
"""

import pathlib

import pytest

from BackEnd.engine.phase_resolution import (
    _apply_drive_contact_foul_credit,
    assert_fouled_handler_had_ball,
    get_ball_handler_from_skeleton,
    resolve_non_shooting_foul,
)
from tests.test_utils import build_mock_game


class _P:
    def __init__(self, pid):
        self.player_id = pid
        self.name = pid
        self.first_name = pid
        self.last_name = ""
        self.position = "PG"
        self.stats = {"game": {}}

    def get_name(self):
        return self.name

    def record_stat(self, stat, amount=1):
        self.stats["game"][stat] = self.stats["game"].get(stat, 0) + amount

    def get_stat(self, stat, scope="game"):
        return self.stats.get(scope, {}).get(stat, 0)


def _lineup():
    return {
        "PG": _P("pg"),
        "SG": _P("sg"),
        "SF": _P("sf"),
        "PF": _P("pf"),
        "C": _P("c"),
    }


def _drive_skeleton():
    return {
        "steps": [
            {"pos_actions": {
                "PG": {"action": "handle_ball", "location": "key"},
                "SG": {"action": "stationary", "location": "wing"},
            }},
            {"pos_actions": {
                "PG": {"action": "stationary", "location": "key"},
                "SG": {"action": "drive", "location": "elbow"},
            }},
        ]
    }


def test_shared_resolver_still_omits_drive():
    off = _lineup()
    bh = get_ball_handler_from_skeleton(_drive_skeleton(), off, step_index=1)
    assert bh is off["PG"]


def test_credit_names_the_driver_not_pg():
    off = _lineup()
    roles = {"ball_handler": off["PG"], "ball_handler_id": "pg",
             "steps": _drive_skeleton()["steps"]}
    gs = {"_hco_drive_contact_driver_id": "sg", "stop_step_index": 1}
    _apply_drive_contact_foul_credit(roles, gs, off, skeleton=_drive_skeleton())
    assert roles["ball_handler"] is off["SG"]
    assert roles["ball_handler_id"] == "sg"
    assert "_hco_drive_contact_driver_id" not in gs


def test_guard_accepts_the_driver():
    off = _lineup()
    assert_fouled_handler_had_ball(_drive_skeleton(), 1, off["SG"], off)


def test_poison_naming_pg_on_a_drive_step_fails_the_guard():
    off = _lineup()
    with pytest.raises(AssertionError, match="did not have the ball"):
        assert_fouled_handler_had_ball(_drive_skeleton(), 1, off["PG"], off)


def test_poison_suppress_stash_leaves_pg():
    off = _lineup()
    roles = {"ball_handler": off["PG"], "ball_handler_id": "pg",
             "steps": _drive_skeleton()["steps"]}
    gs = {"stop_step_index": 1}
    _apply_drive_contact_foul_credit(roles, gs, off, skeleton=_drive_skeleton())
    assert roles["ball_handler"] is off["PG"]
    with pytest.raises(AssertionError, match="did not have the ball"):
        assert_fouled_handler_had_ball(
            _drive_skeleton(), 1, roles["ball_handler"], off)


def test_poison_wrong_stash_id_fires_the_guard():
    off = _lineup()
    roles = {"ball_handler": off["PG"], "ball_handler_id": "pg",
             "steps": _drive_skeleton()["steps"]}
    gs = {"_hco_drive_contact_driver_id": "pg", "stop_step_index": 1}
    with pytest.raises(AssertionError, match="did not have the ball"):
        _apply_drive_contact_foul_credit(
            roles, gs, off, skeleton=_drive_skeleton())


def test_resolve_non_shooting_foul_without_stash_is_untouched():
    """DREB-OTB / FB meet / FCP / HCT / turn_manager call sites set no stash."""
    game = build_mock_game()
    game.game_state["foul_team"] = "DEFENSE"
    game.game_state["team_fouls"] = {}
    bh = game.offense_team.lineup["PG"]
    fouler = game.defense_team.lineup["SG"]
    roles = {
        "ball_handler": bh,
        "defender": fouler,
        "foul_player": fouler,
        "shooter": bh,
        "screener": None,
        "passer": None,
    }
    f_before = fouler.get_stat("F", "game")
    result = resolve_non_shooting_foul(roles, game)
    assert roles["ball_handler"] is bh
    assert bh.name in result["text"]
    assert fouler.get_stat("F", "game") == f_before + 1
    assert "_hco_drive_contact_driver_id" not in game.game_state


def test_non_drive_call_sites_do_not_write_the_stash():
    root = pathlib.Path(__file__).resolve().parents[1]
    writers = []
    for rel in (
        "BackEnd/models/game_manager.py",
        "BackEnd/models/turn_manager.py",
        "BackEnd/engine/after_steal_drive_integration.py",
        "BackEnd/engine/dynamic_hct.py",
        "BackEnd/engine/phase_resolution.py",
    ):
        lines = (root / rel).read_text().splitlines()
        for i, line in enumerate(lines):
            if (
                '["_hco_drive_contact_driver_id"]' in line
                and "=" in line
                and "pop" not in line
            ):
                window = " ".join(lines[max(0, i - 2): i + 1])
                writers.append("%s:%s:%s" % (rel, i + 1, window))
    assert len(writers) == 1, writers
    assert "phase_resolution.py" in writers[0]
    assert "DEAD_BALL_TURNOVER" in writers[0] and "D_FOUL" in writers[0]
    assert "O_FOUL" in writers[0]


def test_resolve_non_shooting_foul_with_stash_names_driver(caplog):
    game = build_mock_game()
    game.game_state["foul_team"] = "DEFENSE"
    off = game.offense_team.lineup
    sg = off["SG"]
    pg = off["PG"]
    sg.player_id = sg.player_id or "sg-driver"
    pg.player_id = pg.player_id or "pg-fabricated"
    fouler = game.defense_team.lineup["SF"]
    game.game_state["_hco_drive_contact_driver_id"] = sg.player_id
    game.game_state["stop_step_index"] = 1
    roles = {
        "ball_handler": pg,
        "defender": fouler,
        "foul_player": fouler,
        "shooter": pg,
        "screener": None,
        "passer": None,
        "steps": _drive_skeleton()["steps"],
    }
    # lineup ids from build_mock_game are not "sg" — rewrite the pin to
    # this game's SG and the skeleton's SG slot to that player.
    skel = _drive_skeleton()
    with caplog.at_level("WARNING"):
        result = resolve_non_shooting_foul(roles, game)
    assert roles["ball_handler"] is sg
    assert sg.name in result["text"]
    assert pg.name not in result["text"]
    assert game.game_state.get("shooter") is sg or game.game_state.get(
        "free_throws_remaining", 0) == 0
    assert "[DRIVE-CONTACT FOUL]" in caplog.text
    assert fouler.get_stat("F", "game") == 1
    assert pg.get_stat("F", "game") == 0
