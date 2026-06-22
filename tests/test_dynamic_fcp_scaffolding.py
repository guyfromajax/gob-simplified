"""PR1 Step 1 — FCP press play scaffolding."""

from unittest.mock import MagicMock

from BackEnd.constants.fcp_press_play_types import (
    FCP_STRAIGHT_PRESSURE,
    play_key_for_fcp_press,
)
from BackEnd.engine.fcp_press_plays import (
    FCP_PRESS_PLAYS,
    StraightPressureFCP,
    get_fcp_press_play,
)


def test_play_key_defaults_to_fcp_straight_pressure():
    assert play_key_for_fcp_press(None) == FCP_STRAIGHT_PRESSURE
    assert play_key_for_fcp_press({}) == FCP_STRAIGHT_PRESSURE


def test_registry_contains_straight_pressure_only():
    assert set(FCP_PRESS_PLAYS.keys()) == {FCP_STRAIGHT_PRESSURE}
    play = get_fcp_press_play(None)
    assert isinstance(play, StraightPressureFCP)
    assert play.key == FCP_STRAIGHT_PRESSURE
    assert play.label == "Straight Pressure"


def test_determine_defensive_pressure_type_stashes_fcp_play():
    from BackEnd.models.turn_manager import TurnManager

    game = MagicMock()
    game.game_state = {}
    game.offense_team = MagicMock()
    game.offense_team.playbook_settings = {}

    tm = TurnManager(game)
    tm._select_defensive_pressure_type = MagicMock(return_value="FCP")

    assert tm.determine_defensive_pressure_type() == "FCP"
    assert game.game_state["fcp_press_play"] == FCP_STRAIGHT_PRESSURE
