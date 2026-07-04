"""Tests for FB shot logical coords used in overlay / rebound authoring."""

from types import SimpleNamespace

from BackEnd.engine.rim_runner_fast_break import _resolve_triangle_setup_payload
from BackEnd.utils.fb_shot_logical_coords import (
    attach_fb_shot_overlay_context,
    build_fb_shot_logical_coords,
    coords_for_fb_overlay_player,
)
from BackEnd.utils.shared import collect_near_bounce_rebound_attemptors


def _player(pid, x, y):
    return SimpleNamespace(player_id=pid, coords={"x": x, "y": y})


def _triangle_fixtures():
    off = {
        "PG": _player("bh", 45, 30),
        "SG": _player("lower-corner", 50, 10),
        "SF": _player("upper-corner", 52, 40),
        "PF": _player("rr", 35, 34),
        "C": _player("trailer", 25, 25),
    }
    deff = {
        "PG": _player("d1", 70, 25),
        "SG": _player("d2", 72, 20),
        "SF": _player("d3", 74, 30),
        "PF": _player("d4", 76, 12),
        "C": _player("d5", 78, 38),
    }
    payload = _resolve_triangle_setup_payload(
        off_lineup=off,
        def_lineup=deff,
        ball_handler=off["PG"],
        rim_runner=off["PF"],
        rebounder=off["C"],
        is_away_offense=False,
        fb_opp=0,
    )
    return off, deff, payload


def test_build_fb_shot_logical_coords_uses_triangle_setup_not_stale_runtime():
    off, deff, payload = _triangle_fixtures()
    roles = {"triangle_setup_phase": payload, "is_fast_break": True}

    logical = build_fb_shot_logical_coords(roles, off, deff)

    assert logical["rr"]["x"] == payload["rim_runner_to"]["x"]
    assert logical["rr"]["x"] >= 50.0
    assert logical["bh"]["x"] == payload["ball_handler_to"]["x"]
    assert logical["trailer"]["x"] == payload["trailer_to"]["x"]


def test_attach_fb_shot_overlay_context_merges_setup_before_resolve_shot():
    off, deff, payload = _triangle_fixtures()
    shot_roles = {
        "shooter": off["PG"],
        "is_fast_break": True,
        "shot_type": "outside",
    }
    fb_roles = {"triangle_setup_phase": payload, "rim_runner_burst_phase": {"rr_id": "rr"}}

    attach_fb_shot_overlay_context(shot_roles, fb_roles, off, deff)

    assert shot_roles["triangle_setup_phase"] is payload
    assert shot_roles["rim_runner_burst_phase"]["rr_id"] == "rr"
    assert shot_roles["fb_shot_logical_coords"]["rr"]["x"] >= 50.0


def test_coords_for_fb_overlay_player_prefers_logical_map():
    player = _player("rr", 35, 34)
    logical = {"rr": {"x": 86.0, "y": 32.0}}

    coords = coords_for_fb_overlay_player(player, logical)

    assert coords == {"x": 86.0, "y": 32.0}


def test_collect_near_bounce_rebound_attemptors_honors_logical_coords():
    off, deff, payload = _triangle_fixtures()
    logical = build_fb_shot_logical_coords(
        {"triangle_setup_phase": payload}, off, deff,
    )
    game = SimpleNamespace(
        game_state={},
        offense_team=SimpleNamespace(lineup=off, team_id="home"),
        defense_team=SimpleNamespace(lineup=deff, team_id="away"),
        away_team=SimpleNamespace(team_id="away"),
        home_team=SimpleNamespace(team_id="home"),
    )
    bounce = {"x": 88.0, "y": 25.0}

    without = collect_near_bounce_rebound_attemptors(
        game, bounce, rebounder_id="bh", max_distance=25,
        coords_already_display_oriented=True,
    )
    with_logical = collect_near_bounce_rebound_attemptors(
        game, bounce, rebounder_id="bh", max_distance=25,
        coords_already_display_oriented=True,
        logical_coords_by_id=logical,
    )

    assert "rr" not in without["offense_rebounders"]
    assert "rr" in with_logical["offense_rebounders"]
