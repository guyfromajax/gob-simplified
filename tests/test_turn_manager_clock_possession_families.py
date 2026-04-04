import pytest

from BackEnd.models.turn_manager import TurnManager


class _DummyTeam:
    def __init__(self, name: str):
        self.name = name
        self.lineup = {}


class _DummyGame:
    def __init__(self, *, time_remaining: int, shot_clock_remaining: int, elapsed_authority: str = "ledger"):
        self.home_team = _DummyTeam("Home")
        self.away_team = _DummyTeam("Away")
        self.game_state = {
            "time_remaining": time_remaining,
            "shot_clock_remaining": shot_clock_remaining,
            "clock": "0:00",
            "uess_clock_authority_mode": "observe",
            "uess_clock_elapsed_authority": elapsed_authority,
        }


def _make_turn_manager(*, time_remaining: int = 480, shot_clock_remaining: int = 30, elapsed_authority: str = "ledger"):
    tm = object.__new__(TurnManager)
    tm.game = _DummyGame(
        time_remaining=time_remaining,
        shot_clock_remaining=shot_clock_remaining,
        elapsed_authority=elapsed_authority,
    )
    return tm


@pytest.mark.parametrize("result_type", ["DEAD BALL", "TURNOVER", "CHARGE", "STEAL"])
def test_possession_change_families_consume_elapsed_and_reset_next_shot_clock(result_type: str):
    tm = _make_turn_manager(time_remaining=300, shot_clock_remaining=14, elapsed_authority="ledger")
    result = {"result_type": result_type, "time_elapsed": 4, "possession_flips": True}

    tm.update_clock_and_possession(result)

    # Current turn contract values (before next-turn reset) should reflect live elapsed.
    assert result["clock_start"] == 300
    assert result["clock_end"] == 296
    assert result["shot_clock_start"] == 14
    assert result["shot_clock_end"] == 10
    assert result["time_elapsed"] == 4
    assert result["uess_clock_elapsed_authority"] == "ledger"
    assert result["uess_clock_elapsed_game_seconds"] == 4
    assert result["uess_clock_elapsed_legacy_game_seconds"] == 4
    assert result["uess_clock_elapsed_delta_seconds"] == 0
    assert result["uess_clock_reconciliation"]["within_tolerance"] is True

    # Next-turn game state shot clock should be reset on possession change families.
    assert tm.game.game_state["shot_clock_remaining"] == 30

    event_types = [str(row.get("event_type")) for row in result.get("clock_event_ledger", [])]
    assert "game_clock_start" in event_types
    assert "game_clock_stop" in event_types
    # Current contract records reset for the next turn in game_state, not as a same-turn ledger reset event.
    assert "shot_clock_reset" not in event_types


def test_possession_change_does_not_emit_same_turn_shot_clock_reset_row():
    tm = _make_turn_manager(time_remaining=260, shot_clock_remaining=11, elapsed_authority="ledger")
    result = {"result_type": "TURNOVER", "time_elapsed": 3, "possession_flips": True}

    tm.update_clock_and_possession(result)

    reset_rows = [
        row for row in result.get("clock_event_ledger", [])
        if row.get("event_type") == "shot_clock_reset"
    ]
    assert not reset_rows
    assert tm.game.game_state["shot_clock_remaining"] == 30
