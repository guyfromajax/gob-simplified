"""HCO shot-clock tier diagnostics — universal tracking via record_shot_split."""

from types import SimpleNamespace

from BackEnd.utils.shot_split_tracker import (
    hco_shot_clock_at_attempt,
    record_shot_split,
)


def _game_with_state(state):
    return SimpleNamespace(game_state=state)


def test_hco_shot_clock_prefers_dynamic_estimate():
    state = {"shot_clock_remaining": 24, "_hco_shot_clock_est": 8.5}
    assert hco_shot_clock_at_attempt(state) == 8.5
    assert "_hco_shot_clock_est" not in state
    assert state["shot_clock_remaining"] == 24


def test_hco_shot_clock_falls_back_to_game_state():
    state = {"shot_clock_remaining": 18}
    assert hco_shot_clock_at_attempt(state) == 18.0


def test_record_shot_split_tracks_hco_tier_for_all_hco_fga():
    state = {"shot_clock_remaining": 22}
    game = _game_with_state(state)
    record_shot_split(
        game, is_three=False, defended=True, made=True, turn_type="HCO",
    )
    assert state["hco_shot_tier_counts"]["mid"] == 1


def test_record_shot_split_skips_non_hco_turn_types():
    state = {"shot_clock_remaining": 10}
    game = _game_with_state(state)
    record_shot_split(
        game, is_three=False, defended=False, made=False, turn_type="Fast Break",
    )
    assert "hco_shot_tier_counts" not in state


def test_record_shot_split_uses_dynamic_estimate_when_stamped():
    state = {"shot_clock_remaining": 28, "_hco_shot_clock_est": 7.0}
    game = _game_with_state(state)
    record_shot_split(
        game, is_three=True, defended=True, made=False, turn_type="HCO",
    )
    assert state["hco_shot_tier_counts"]["late"] == 1
