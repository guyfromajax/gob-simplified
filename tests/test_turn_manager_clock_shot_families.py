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


def _ledger_rows(result: dict, event_type: str):
    return [row for row in result.get("clock_event_ledger", []) if row.get("event_type") == event_type]


def test_make_shot_family_burns_elapsed_and_resets_next_turn_shot_clock():
    tm = _make_turn_manager(time_remaining=500, shot_clock_remaining=30, elapsed_authority="ledger")
    result = {"result_type": "MAKE", "time_elapsed": 6}

    tm.update_clock_and_possession(result)

    assert result["clock_start"] == 500
    assert result["clock_end"] == 494
    assert result["shot_clock_start"] == 30
    assert result["shot_clock_end"] == 24
    assert result["time_elapsed"] == 6
    assert result["uess_clock_elapsed_game_seconds"] == 6
    assert result["uess_clock_elapsed_delta_seconds"] == 0

    stop_rows = _ledger_rows(result, "shot_clock_stop")
    assert stop_rows
    assert stop_rows[-1].get("reason") == "shot_detach"

    # Reset applies to next turn state after contract capture.
    assert tm.game.game_state["shot_clock_remaining"] == 30


def test_miss_shot_with_possession_flip_resets_next_turn_shot_clock_only():
    tm = _make_turn_manager(time_remaining=440, shot_clock_remaining=20, elapsed_authority="ledger")
    result = {
        "result_type": "MISS",
        "time_elapsed": 5,
        "possession_flips": True,
        "rebound_type": "DREB",
    }

    tm.update_clock_and_possession(result)

    assert result["clock_start"] == 440
    assert result["clock_end"] == 435
    assert result["shot_clock_start"] == 20
    assert result["shot_clock_end"] == 15
    assert result["time_elapsed"] == 5
    assert result["uess_clock_elapsed_game_seconds"] == 5
    assert result["uess_clock_elapsed_delta_seconds"] == 0

    # Same-turn ledger does not emit reset row for next-turn policy reset.
    assert not _ledger_rows(result, "shot_clock_reset")
    assert tm.game.game_state["shot_clock_remaining"] == 30


def test_shooting_foul_uses_resolution_step_for_shot_clock_burn():
    tm = _make_turn_manager(time_remaining=360, shot_clock_remaining=30, elapsed_authority="ledger")
    result = {
        "result_type": "FOUL",
        "free_throws_remaining": 2,
        "next_play_type": "FREE_THROW",
        "time_elapsed": 9,
        "step_clock_seconds": [2, 3, 4],
        "resolution_step_index": 1,  # burn only 2+3 for shot clock
    }

    tm.update_clock_and_possession(result)

    # Game clock burns full elapsed.
    assert result["clock_start"] == 360
    assert result["clock_end"] == 351
    # Shot clock burns only through shot resolution step.
    assert result["shot_clock_start"] == 30
    assert result["shot_clock_end"] == 25
    # Ledger authority keeps time_elapsed equal to ledger-derived elapsed.
    assert result["time_elapsed"] == 9
    assert result["uess_clock_elapsed_game_seconds"] == 9
    assert result["uess_clock_elapsed_legacy_game_seconds"] == 9
    assert result["uess_clock_elapsed_delta_seconds"] == 0

    stop_rows = _ledger_rows(result, "shot_clock_stop")
    assert stop_rows
    assert stop_rows[-1].get("reason") == "foul"
