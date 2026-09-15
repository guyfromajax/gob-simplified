"""Last unswept empty-owner site: omit the key, do not write \"\"."""

from types import SimpleNamespace

from BackEnd.engine.covert_release_step_emitter import _build_step_back_step


def _player(pid, pos, x=80.0, y=25.0):
    return SimpleNamespace(
        player_id=pid, position=pos, coords={"x": x, "y": y}, attributes={}
    )


def test_step_back_omits_owner_key_when_fb_bh_id_missing():
    pg = _player(None, "PG")
    step = _build_step_back_step(
        turn_result={},
        fb_roles={"ball_handler": pg, "is_away_offense": False},
        off_lineup={"PG": pg},
        def_lineup={},
        step_start_coords={"ghost": {"x": 80.0, "y": 25.0}},
        clock_remaining_at_start=20.0,
        shot_clock_remaining_at_start=20.0,
    )
    assert step is not None
    assert "owner_player_id" not in (step["start"].get("ball") or {})
    assert "owner_player_id" not in (step["end"].get("ball") or {})


def test_step_back_keeps_owner_when_fb_bh_id_is_present():
    pg = _player("bh-1", "PG")
    step = _build_step_back_step(
        turn_result={},
        fb_roles={"ball_handler": pg, "is_away_offense": False},
        off_lineup={"PG": pg},
        def_lineup={},
        step_start_coords={"bh-1": {"x": 80.0, "y": 25.0}},
        clock_remaining_at_start=20.0,
        shot_clock_remaining_at_start=20.0,
    )
    assert step is not None
    assert (step["start"].get("ball") or {}).get("owner_player_id") == "bh-1"
