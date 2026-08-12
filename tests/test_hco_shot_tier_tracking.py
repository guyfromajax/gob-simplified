"""HCO shot-clock tier diagnostics — at-attempt clock via skeleton detach math."""

from types import SimpleNamespace
from unittest.mock import patch

from BackEnd.utils.shot_split_tracker import (
    _elapsed_seconds_to_shot_step,
    record_shot_split,
    resolve_hco_shot_clock_at_attempt,
)


def _game_with_state(state):
    return SimpleNamespace(game_state=state)


def _minimal_steps(num_steps=3):
    """Steps with deterministic timing when calc_skeleton is patched."""
    return [{"pos_actions": {"PG": {"action": "handle"}}} for _ in range(num_steps)]


def test_elapsed_seconds_to_shot_step():
    assert _elapsed_seconds_to_shot_step([4, 5, 6], 1) == 9
    assert _elapsed_seconds_to_shot_step([4, 5, 6], 0) == 4


def test_resolve_prefers_dynamic_estimate():
    state = {"shot_clock_remaining": 24, "_hco_shot_clock_est": 8.5}
    roles = {"steps": _minimal_steps()}
    assert resolve_hco_shot_clock_at_attempt(state, roles) == 8.5
    assert "_hco_shot_clock_est" not in state


def test_resolve_shot_at_one_second():
    state = {"shot_clock_remaining": 18, "shot_at_one_second": True}
    roles = {"steps": _minimal_steps()}
    assert resolve_hco_shot_clock_at_attempt(state, roles) == 1.0


@patch("BackEnd.utils.shared.calc_skeleton_step_timing_contract")
def test_resolve_skeleton_detach_math(mock_timing):
    mock_timing.return_value = {
        "step_clock_seconds": [6, 4, 3],
        "resolution_step_index": 1,
    }
    state = {"shot_clock_remaining": 24, "offensive_state": "HCO"}
    roles = {"steps": _minimal_steps(3)}
    clock = resolve_hco_shot_clock_at_attempt(
        state, roles, shot_step_index=1, off_lineup={"PG": object()},
    )
    assert clock == 14.0  # 24 - (6 + 4)


def test_resolve_hco_skeleton_after_free_throw_state():
    """Block-recon path sets offensive_state FREE_THROW before diagnostics."""
    state = {"shot_clock_remaining": 30, "offensive_state": "FREE_THROW"}
    roles = {"steps": _minimal_steps(2)}

    with patch("BackEnd.utils.shared.calc_skeleton_step_timing_contract") as mock_timing:
        mock_timing.return_value = {
            "step_clock_seconds": [8, 5],
            "resolution_step_index": 1,
        }
        clock = resolve_hco_shot_clock_at_attempt(
            state, roles, shot_step_index=1, off_lineup={"PG": object()},
        )

    assert clock == 17.0  # 30 - 13
    mock_timing.assert_called_once()
    assert mock_timing.call_args.kwargs.get("phase_type") == "HCO"


def test_record_shot_split_tracks_hco_tier_from_passed_clock():
    state = {"shot_clock_remaining": 22}
    game = _game_with_state(state)
    record_shot_split(
        game,
        is_three=False,
        defended=True,
        made=True,
        turn_type="HCO",
        hco_shot_clock=16.0,
    )
    assert state["hco_shot_tier_counts"]["mid"] == 1


def test_record_shot_split_skips_non_hco_turn_types():
    state = {"shot_clock_remaining": 10}
    game = _game_with_state(state)
    record_shot_split(
        game,
        is_three=False,
        defended=False,
        made=False,
        turn_type="Fast Break",
    )
    assert "hco_shot_tier_counts" not in state


def test_record_shot_split_derives_clock_from_roles_when_not_passed():
    state = {"shot_clock_remaining": 30, "offensive_state": "HCO"}
    roles = {"steps": _minimal_steps(2)}
    game = _game_with_state(state)

    with patch("BackEnd.utils.shared.calc_skeleton_step_timing_contract") as mock_timing:
        mock_timing.return_value = {
            "step_clock_seconds": [10, 8],
            "resolution_step_index": 0,
        }
        record_shot_split(
            game,
            is_three=True,
            defended=True,
            made=False,
            turn_type="HCO",
            roles=roles,
            shot_step_index=0,
            off_lineup={"PG": object()},
        )

    # Shot detaches after 10 seconds: 30 - 10 = 20, the documented mid tier
    # (15-22 seconds), not early (23-30).
    assert state["hco_shot_tier_counts"]["mid"] == 1
