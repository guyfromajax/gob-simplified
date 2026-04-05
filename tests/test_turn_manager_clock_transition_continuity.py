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


def _make_turn_manager(*, time_remaining: int, shot_clock_remaining: int, elapsed_authority: str = "ledger"):
    tm = object.__new__(TurnManager)
    tm.game = _DummyGame(
        time_remaining=time_remaining,
        shot_clock_remaining=shot_clock_remaining,
        elapsed_authority=elapsed_authority,
    )
    return tm


def _assert_recon_clean(result: dict):
    assert isinstance(result.get("clock_event_ledger"), list)
    assert result["uess_clock_elapsed_authority"] == "ledger"
    assert result["uess_clock_elapsed_delta_seconds"] == 0
    assert result["uess_clock_reconciliation"]["within_tolerance"] is True


def test_fast_break_make_then_baseline_inbound_continuity():
    tm = _make_turn_manager(time_remaining=300, shot_clock_remaining=30)

    make_turn = {
        "result_type": "MAKE",
        "current_turn": "FAST_BREAK",
        "time_elapsed": 5,
        "possession_flips": True,
    }
    tm.update_clock_and_possession(make_turn)
    _assert_recon_clean(make_turn)
    assert make_turn["clock_start"] == 300
    assert make_turn["clock_end"] == 295
    assert make_turn["shot_clock_start"] == 30
    assert make_turn["shot_clock_end"] == 25
    # Next-turn policy reset after made basket.
    assert tm.game.game_state["shot_clock_remaining"] == 30

    bip_turn = {
        "result_type": "BASELINE_INBOUND",
        "time_elapsed": 2,
    }
    tm.update_clock_and_possession(bip_turn)
    _assert_recon_clean(bip_turn)
    assert bip_turn["clock_start"] == 295
    assert bip_turn["clock_end"] == 295
    assert bip_turn["shot_clock_start"] == 30
    assert bip_turn["shot_clock_end"] == 30
    assert bip_turn.get("shot_clock_reset_reason") in (None, "")


def test_hco_miss_oreb_then_putback_make_continuity():
    tm = _make_turn_manager(time_remaining=420, shot_clock_remaining=18)

    miss_with_oreb = {
        "result_type": "MISS",
        "current_turn": "HCO",
        "rebound_type": "OREB",
        "time_elapsed": 4,
        "possession_flips": False,
    }
    tm.update_clock_and_possession(miss_with_oreb)
    _assert_recon_clean(miss_with_oreb)
    assert miss_with_oreb["clock_start"] == 420
    assert miss_with_oreb["clock_end"] == 416
    assert miss_with_oreb["shot_clock_start"] == 18
    assert miss_with_oreb["shot_clock_end"] == 14
    # OREB policy reset applies to next-turn state.
    assert tm.game.game_state["shot_clock_remaining"] == 30

    putback_make = {
        "result_type": "PUTBACK_MAKE",
        "current_turn": "OREB",
        "rebound_type": "OREB",
        "time_elapsed": 2,
        "possession_flips": True,
    }
    tm.update_clock_and_possession(putback_make)
    _assert_recon_clean(putback_make)
    assert putback_make["clock_start"] == 416
    assert putback_make["clock_end"] == 414
    assert putback_make["shot_clock_start"] == 30
    assert putback_make["shot_clock_end"] == 28
    assert tm.game.game_state["shot_clock_remaining"] == 30


def test_dead_ball_then_side_inbound_continuity():
    tm = _make_turn_manager(time_remaining=260, shot_clock_remaining=20)

    dead_ball = {
        "result_type": "DEAD BALL",
        "time_elapsed": 3,
        "possession_flips": True,
    }
    tm.update_clock_and_possession(dead_ball)
    _assert_recon_clean(dead_ball)
    assert dead_ball["clock_start"] == 260
    assert dead_ball["clock_end"] == 257
    assert dead_ball["shot_clock_start"] == 20
    assert dead_ball["shot_clock_end"] == 17
    assert tm.game.game_state["shot_clock_remaining"] == 30

    side_inbound = {
        "result_type": "SIDE_INBOUND",
        "time_elapsed": 1,
    }
    tm.update_clock_and_possession(side_inbound)
    _assert_recon_clean(side_inbound)
    assert side_inbound["clock_start"] == 257
    assert side_inbound["clock_end"] == 257
    assert side_inbound["shot_clock_start"] == 30
    assert side_inbound["shot_clock_end"] == 30
    assert side_inbound.get("shot_clock_reset_reason") in (None, "")
