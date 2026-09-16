"""Drive-contact O_FOUL charge: post-draw identity swap, not a pre-draw reweight.

select_foul_player already picked the 60% ball-handler slot. The slot is
correct; the identity is fabricated. Substitute the driver after the draw.
Do not rewrite ball_handler before select (that desyncs the stream).
"""

import pytest

from BackEnd.engine.phase_resolution import (
    _apply_drive_contact_o_foul_charge,
    assert_o_foul_charger_had_ball,
    get_ball_handler_from_skeleton,
    resolve_non_shooting_foul,
    select_foul_player,
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


def test_post_draw_sub_charges_driver_not_pg(caplog):
    off = _lineup()
    gs = {"_hco_drive_contact_driver_id": "sg", "stop_step_index": 1}
    with caplog.at_level("WARNING"):
        charged = _apply_drive_contact_o_foul_charge(
            off["PG"], off["PG"], gs, off, skeleton=_drive_skeleton())
    assert charged is off["SG"]
    assert "_hco_drive_contact_driver_id" not in gs
    assert "[DRIVE-CONTACT O_FOUL]" in caplog.text
    assert "pg" in caplog.text and "sg" in caplog.text


def test_forty_percent_slot_is_untouched():
    off = _lineup()
    gs = {"_hco_drive_contact_driver_id": "sg", "stop_step_index": 1}
    charged = _apply_drive_contact_o_foul_charge(
        off["SF"], off["PG"], gs, off, skeleton=_drive_skeleton())
    assert charged is off["SF"]
    assert "_hco_drive_contact_driver_id" not in gs


def test_does_not_rewrite_ball_handler():
    off = _lineup()
    bh = off["PG"]
    gs = {"_hco_drive_contact_driver_id": "sg", "stop_step_index": 1}
    _apply_drive_contact_o_foul_charge(
        off["PG"], bh, gs, off, skeleton=_drive_skeleton())
    assert bh is off["PG"]


def test_select_foul_player_still_weights_the_passed_handler():
    """The draw still sees the fabricated BH. We do not reweight first."""
    off = _lineup()
    def_lineup = _lineup()
    picked = select_foul_player("OFFENSE", off["PG"], off, def_lineup)
    assert picked in off.values()


def test_guard_accepts_the_driver():
    off = _lineup()
    assert_o_foul_charger_had_ball(_drive_skeleton(), 1, off["SG"], off)


def test_poison_stash_gate_leaves_fabricated_bh():
    off = _lineup()
    gs = {"stop_step_index": 1}
    charged = _apply_drive_contact_o_foul_charge(
        off["PG"], off["PG"], gs, off, skeleton=_drive_skeleton())
    assert charged is off["PG"]
    with pytest.raises(AssertionError, match="did not have the ball"):
        assert_o_foul_charger_had_ball(
            _drive_skeleton(), 1, charged, off)


def test_poison_skip_f_substitutes_without_incrementing():
    off = _lineup()
    gs = {"_hco_drive_contact_driver_id": "sg", "stop_step_index": 1}
    charged = _apply_drive_contact_o_foul_charge(
        off["PG"], off["PG"], gs, off, skeleton=_drive_skeleton())
    assert charged is off["SG"]
    assert off["SG"].get_stat("F") == 0
    assert off["PG"].get_stat("F") == 0


def test_poison_force_fo_fouls_out_the_driver():
    game = build_mock_game()
    game.game_state["foul_team"] = "OFFENSE"
    game.game_state["team_fouls"] = {}
    off = game.offense_team.lineup
    sg = off["SG"]
    pg = off["PG"]
    sg.player_id = sg.player_id or "sg-driver"
    pg.player_id = pg.player_id or "pg-fabricated"
    game.game_state["_hco_drive_contact_driver_id"] = sg.player_id
    game.game_state["stop_step_index"] = 1
    charged = _apply_drive_contact_o_foul_charge(
        pg, pg, game.game_state, off, skeleton=_drive_skeleton())
    assert charged is sg
    sg.stats.setdefault("game", {})["F"] = 4
    roles = {
        "ball_handler": pg,
        "defender": game.defense_team.lineup["SF"],
        "foul_player": charged,
        "shooter": pg,
        "screener": None,
        "passer": None,
        "steps": _drive_skeleton()["steps"],
    }
    result = resolve_non_shooting_foul(roles, game)
    assert result.get("fouled_out") is True
    assert sg.get_stat("F", "game") == 5
    assert pg.get_stat("F", "game") == 0


def test_poison_wrong_stash_id_fires_the_guard():
    off = _lineup()
    gs = {"_hco_drive_contact_driver_id": "pg", "stop_step_index": 1}
    with pytest.raises(AssertionError, match="did not have the ball"):
        _apply_drive_contact_o_foul_charge(
            off["PG"], off["PG"], gs, off, skeleton=_drive_skeleton())
