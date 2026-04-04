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


def _event_types(result: dict) -> list[str]:
    return [str(row.get("event_type")) for row in result.get("clock_event_ledger", [])]


def test_timeout_clock_family_is_clock_dead_and_ledger_zero_elapsed():
    tm = _make_turn_manager(time_remaining=420, shot_clock_remaining=20, elapsed_authority="ledger")
    result = {"result_type": "TIMEOUT", "time_elapsed": 5}

    tm.update_clock_and_possession(result)

    assert result["time_elapsed"] == 0
    assert result["clock_start"] == 420
    assert result["clock_end"] == 420
    assert result["shot_clock_start"] == 20
    assert result["shot_clock_end"] == 20
    assert result["uess_clock_elapsed_authority"] == "ledger"
    assert result["uess_clock_elapsed_game_seconds"] == 0
    assert result["uess_clock_elapsed_delta_seconds"] == 0
    assert "game_clock_stop" in _event_types(result)


@pytest.mark.parametrize("result_type", ["SIDE_INBOUND", "BASELINE_INBOUND"])
def test_inbound_clock_family_resets_shot_clock_and_keeps_zero_elapsed(result_type: str):
    tm = _make_turn_manager(time_remaining=400, shot_clock_remaining=18, elapsed_authority="ledger")
    result = {"result_type": result_type, "time_elapsed": 4}

    tm.update_clock_and_possession(result)

    assert result["time_elapsed"] == 0
    assert result["clock_start"] == 400
    assert result["clock_end"] == 400
    assert result["shot_clock_start"] == 18
    assert result["shot_clock_end"] == 30
    assert result["shot_clock_reset"] is True
    assert result["shot_clock_reset_reason"] == "inbound_received"
    assert result["uess_clock_elapsed_game_seconds"] == 0
    assert result["uess_clock_elapsed_delta_seconds"] == 0
    reset_rows = [
        row for row in result.get("clock_event_ledger", [])
        if row.get("event_type") == "shot_clock_reset"
    ]
    assert reset_rows, "expected shot_clock_reset ledger event"
    assert reset_rows[-1].get("reason") == "inbound_received"


def test_free_throw_clock_family_is_clock_dead_for_elapsed_authority():
    tm = _make_turn_manager(time_remaining=360, shot_clock_remaining=12, elapsed_authority="ledger")
    result = {"result_type": "FREE_THROW", "time_elapsed": 3}

    tm.update_clock_and_possession(result)

    assert result["time_elapsed"] == 0
    assert result["clock_start"] == 360
    assert result["clock_end"] == 360
    assert result["shot_clock_start"] == 12
    assert result["shot_clock_end"] == 12
    assert result["uess_clock_elapsed_game_seconds"] == 0
    assert result["uess_clock_elapsed_delta_seconds"] == 0


def test_opening_tip_clock_family_consumes_elapsed_in_ledger_mode():
    tm = _make_turn_manager(time_remaining=480, shot_clock_remaining=30, elapsed_authority="ledger")
    result = {"result_type": "OPENING_TIP", "time_elapsed": 2}

    tm.update_clock_and_possession(result)

    assert result["clock_start"] == 480
    assert result["clock_end"] == 478
    assert result["time_elapsed"] == 2
    assert result["uess_clock_elapsed_game_seconds"] == 2
    assert result["uess_clock_elapsed_delta_seconds"] == 0
    assert "game_clock_start" in _event_types(result)
    assert "game_clock_stop" in _event_types(result)
