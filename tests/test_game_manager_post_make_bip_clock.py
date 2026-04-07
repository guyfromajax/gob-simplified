from BackEnd.models.game_manager import GameManager


def _make_minimal_gm(time_remaining: int) -> GameManager:
    gm = object.__new__(GameManager)
    gm.game_state = {
        "time_remaining": int(time_remaining),
        "clock": f"{int(time_remaining) // 60}:{int(time_remaining) % 60:02d}",
    }
    return gm


def test_post_make_bip_clock_runoff_applies_above_one_minute():
    gm = _make_minimal_gm(120)
    last_turn = {"result_type": "MAKE", "next_play_type": "BASELINE_INBOUND"}

    runoff = gm._resolve_post_make_bip_clock_runoff(last_turn)

    assert runoff == 2


def test_post_make_bip_clock_runoff_disabled_in_last_minute():
    gm = _make_minimal_gm(60)
    last_turn = {"result_type": "MAKE", "next_play_type": "BASELINE_INBOUND"}

    runoff = gm._resolve_post_make_bip_clock_runoff(last_turn)

    assert runoff == 0


def test_post_make_bip_clock_runoff_not_applied_for_free_throw_turn():
    gm = _make_minimal_gm(120)
    last_turn = {"result_type": "FREE_THROW", "next_play_type": "BASELINE_INBOUND"}

    runoff = gm._resolve_post_make_bip_clock_runoff(last_turn)

    assert runoff == 0
