from types import SimpleNamespace

import pytest

from BackEnd.utils.simulation_diagnostics import calibration_diagnostics_enabled
from BackEnd.utils.shot_split_tracker import (
    format_master_eog_report,
    increment_block_funnel,
    record_altered_action,
    record_shot_split,
    record_subtle_movement,
    restore_shot_split_from_saved,
)


@pytest.mark.parametrize(
    ("game_state", "expected"),
    [
        ({}, True),
        ({"_is_full_simulation": False}, True),
        ({"_headless_simulation": False}, True),
        ({"_is_full_simulation": True}, False),
        ({"_headless_simulation": True}, False),
        (
            {
                "_is_full_simulation": True,
                "_headless_simulation": True,
            },
            False,
        ),
    ],
)
def test_calibration_diagnostics_enabled_flag_matrix(game_state, expected):
    assert calibration_diagnostics_enabled(game_state) is expected


def test_calibration_diagnostics_enabled_accepts_game_object():
    game = SimpleNamespace(game_state={"_headless_simulation": True})

    assert calibration_diagnostics_enabled(game) is False


@pytest.mark.parametrize("value", [None, object(), SimpleNamespace()])
def test_calibration_diagnostics_enabled_defaults_on_without_game_state(value):
    assert calibration_diagnostics_enabled(value) is True


@pytest.mark.parametrize(
    "bulk_flag",
    ["_is_full_simulation", "_headless_simulation"],
)
def test_bulk_modes_skip_all_hot_path_diagnostic_recording(bulk_flag):
    initial_split = {
        "3pt_def": {"make": 0, "miss": 0},
        "3pt_undef": {"make": 0, "miss": 0},
        "2pt_def": {"make": 0, "miss": 0},
        "2pt_undef": {"make": 0, "miss": 0},
    }
    state = {
        bulk_flag: True,
        "shot_split_tracking": initial_split,
        "block_funnel_tracking": {"eligible": 0},
    }
    game = SimpleNamespace(
        game_state=state,
        offense_team=SimpleNamespace(team_id="offense", name="Offense"),
    )

    record_shot_split(
        game,
        is_three=True,
        defended=True,
        made=True,
        turn_type="HCO",
        hco_shot_clock=20,
        defender_distance=4,
        contest_factor=0.5,
    )
    increment_block_funnel(state, "eligible")
    record_subtle_movement(game)
    record_altered_action(game, "backdoor")

    assert state["shot_split_tracking"] == initial_split
    assert state["block_funnel_tracking"] == {"eligible": 0}
    assert "shot_distance_bands" not in state
    assert "hco_shot_tier_counts" not in state
    assert "altered_action_tracking" not in state


def test_interactive_mode_retains_diagnostic_recording():
    game = SimpleNamespace(
        game_state={},
        offense_team=SimpleNamespace(team_id="offense", name="Offense"),
    )

    record_shot_split(
        game,
        is_three=False,
        defended=False,
        made=True,
        turn_type="HCO",
        hco_shot_clock=20,
        defender_distance=12,
        contest_factor=0,
    )
    increment_block_funnel(game.game_state, "eligible")
    record_subtle_movement(game)
    record_altered_action(game, "backdoor")

    assert game.game_state["shot_split_tracking"]["2pt_undef"]["make"] == 1
    assert game.game_state["hco_shot_tier_counts"]["mid"] == 1
    assert game.game_state["block_funnel_tracking"]["eligible"] == 1
    assert (
        game.game_state["altered_action_tracking"]["offense"]["subtle_movements"]
        == 1
    )


def test_bulk_mode_skips_restore_and_report_formatting():
    state = {"_headless_simulation": True}
    restore_shot_split_from_saved(
        state,
        {"shot_split_tracking": {"2pt_def": {"make": 4, "miss": 3}}},
    )

    assert "shot_split_tracking" not in state
    assert format_master_eog_report(SimpleNamespace(game_state=state)) == ""
