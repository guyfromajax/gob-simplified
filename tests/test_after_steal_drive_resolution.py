"""Phase 2 after-steal E2E tests (drive resolution path)."""

from types import SimpleNamespace

import pytest

from BackEnd.engine.after_steal_fast_break import resolve_after_steal_fast_break
from BackEnd.engine.after_steal_fast_break_step_emitter import (
    build_after_steal_fast_break_animation_steps,
)
from tests.test_utils import build_mock_game


@pytest.fixture(autouse=True)
def _enable_drive_resolution(monkeypatch):
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_AFTER_STEAL", True)


def _seed_steal(game):
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    stealer = game.offense_team.lineup["PG"]
    stealer.player_id = "home-PG"
    game.game_state["last_stealer"] = stealer
    game.game_state["last_stealer_coords"] = {"x": 55.0, "y": 25.0}
    game.game_state["offensive_state"] = "FAST_BREAK"
    for team in (game.offense_team, game.defense_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_a, **_k: None
            player.add_momentum = lambda *_a, **_k: None
    return stealer


def test_neutral_hco_returns_defensive_stop(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NEUTRAL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "away-SF",
            "t_meet_game_seconds": 1.2,
            "t_drive_game_seconds": 1.2,
            "defender_end_coords": {"away-SF": meet},
            "defender_archetypes": {"away-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result["fb_drive_resolution"]["outcome"] == "NEUTRAL"
    assert result["next_play_type"] == "HCO"


def test_pos_o_stamps_path_knots_on_turn(monkeypatch):
    meet = {"x": 70, "y": 25}
    shimmy = {"x": 70, "y": 27}
    shot_spot = {"x": 88, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                shimmy,
                shot_spot,
            ],
            "shot_spot": shot_spot,
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": True,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 200,
            "shot_score_pre_defense": 180,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "home-PG",
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MAKE"
    assert len(result["fb_drive_resolution"]["bh_path_knots"]) == 4


def test_emitter_includes_path_knots_metadata_for_pos_o():
    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"home-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["home-PG"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"away-{pos}"] = {"x": 50.0, "y": 25.0}

    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                {"x": 70, "y": 27},
                shot_spot,
            ],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    meta = steps[0]["start"]["advance_trigger"]["metadata"]
    assert "path_knots" in meta
    assert len(meta["path_knots"]) == 4


def test_after_steal_no_meet_honors_resolver_offball_spots():
    """Phase 1: after-steal opts out of the blanket rim-crash
    (``crash_off_ball_to_basket=False``), so off-ball players keep the
    resolver-authored coordinated spread instead of all clustering on
    ``basketSpot``."""
    shot_spot = {"x": 88, "y": 25}
    # Distinct, spread destinations for the off-ball cast (nowhere near the rim).
    offball_spots = {
        "home-SG": {"x": 72.0, "y": 14.0},
        "home-SF": {"x": 72.0, "y": 36.0},
        "home-PF": {"x": 66.0, "y": 8.0},
        "home-C": {"x": 66.0, "y": 42.0},
        "away-SG": {"x": 70.0, "y": 16.0},
        "away-SF": {"x": 70.0, "y": 34.0},
        "away-PF": {"x": 62.0, "y": 20.0},
        "away-C": {"x": 62.0, "y": 30.0},
        "away-PG": {"x": 80.0, "y": 25.0},
    }
    end_coords = dict(offball_spots)
    end_coords["home-PG"] = dict(shot_spot)

    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "NO_MEET",
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 40.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    destinations = steps[0]["start"]["destination"]
    for pid, spot in offball_spots.items():
        assert destinations[pid] == spot, (
            f"{pid} should keep its resolver spot {spot}, got {destinations[pid]}"
        )


def _pos_o_payload():
    return {
        "outcome": "POS_O",
        "stopper_id": "away-SF",
        "meet_x": 70,
        "meet_y": 25,
        "shimmy": {"x": 70, "y": 27},
        "bh_start": {"x": 55, "y": 25},
        "shot_spot": {"x": 88, "y": 25},
        "path_segment_game_seconds": [1.0, 0.3, 0.5],
        "t_drive_game_seconds": 1.8,
    }


def test_cascade_collapses_to_pos_o_rim_finish(monkeypatch):
    """BH beats the first cutoff (POS_O) then finds a clear lane (NO_MEET): the
    cascade collapses into one curved POS_O drive and records the beaten
    stopper."""
    from BackEnd.engine import after_steal_drive_integration as asi

    calls = {"n": 0}

    def fake_resolve(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            assert not kw.get("excluded_stopper_ids")
            return _pos_o_payload()
        assert kw.get("excluded_stopper_ids") == {"away-SF"}
        assert kw["bh_start"] == {"x": 70, "y": 27}  # advanced to shimmy
        return {
            "outcome": "NO_MEET",
            "t_drive_game_seconds": 0.7,
            "contested": False,
            "shot_defender_id": None,
            "shot_spot": {"x": 88, "y": 25},
            "bh_start": {"x": 70, "y": 27},
        }

    monkeypatch.setattr(asi, "resolve_fb_drive_step", fake_resolve)
    drive = asi._resolve_drive_with_cascade(
        resolve_kwargs={"bh_start": {"x": 55, "y": 25}},
        shot_spot={"x": 88, "y": 25},
        max_attempts=2,
    )
    assert calls["n"] == 2
    assert drive["outcome"] == "POS_O"
    assert drive["cascade_beaten_stopper_ids"] == ["away-SF"]
    knots = drive["bh_path_knots"]
    assert knots[0] == {"x": 55.0, "y": 25.0}
    assert {"x": 70.0, "y": 25.0} in knots  # meet
    assert {"x": 70.0, "y": 27.0} in knots  # shimmy
    assert knots[-1] == {"x": 88.0, "y": 25.0}


def test_cascade_second_defender_stops_bh(monkeypatch):
    """BH beats the first cutoff but a later defender stops him: the cascade ends
    NEUTRAL with the second stopper credited and the first recorded as beaten."""
    from BackEnd.engine import after_steal_drive_integration as asi

    calls = {"n": 0}

    def fake_resolve(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _pos_o_payload()
        return {
            "outcome": "NEUTRAL",
            "stopper_id": "away-PF",
            "meet_x": 78,
            "meet_y": 25,
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "stop_decision": {"action": "HCO"},
            "bh_start": {"x": 70, "y": 27},
        }

    monkeypatch.setattr(asi, "resolve_fb_drive_step", fake_resolve)
    drive = asi._resolve_drive_with_cascade(
        resolve_kwargs={"bh_start": {"x": 55, "y": 25}},
        shot_spot={"x": 88, "y": 25},
        max_attempts=2,
    )
    assert drive["outcome"] == "NEUTRAL"
    assert drive["stopper_id"] == "away-PF"
    assert drive["cascade_beaten_stopper_ids"] == ["away-SF"]


def test_cascade_no_op_when_first_attempt_not_pos_o(monkeypatch):
    from BackEnd.engine import after_steal_drive_integration as asi

    calls = {"n": 0}

    def fake_resolve(**kw):
        calls["n"] += 1
        return {"outcome": "NO_MEET", "t_drive_game_seconds": 1.0, "shot_spot": {"x": 88, "y": 25}}

    monkeypatch.setattr(asi, "resolve_fb_drive_step", fake_resolve)
    drive = asi._resolve_drive_with_cascade(
        resolve_kwargs={"bh_start": {"x": 55, "y": 25}},
        shot_spot={"x": 88, "y": 25},
        max_attempts=2,
    )
    assert calls["n"] == 1
    assert "cascade_beaten_stopper_ids" not in drive


def test_cascade_respects_attempt_cap(monkeypatch):
    """POS_O on every attempt → stops at the cap and collapses to a rim finish."""
    from BackEnd.engine import after_steal_drive_integration as asi

    calls = {"n": 0}

    def fake_resolve(**kw):
        calls["n"] += 1
        payload = _pos_o_payload()
        payload["stopper_id"] = f"away-{calls['n']}"
        return payload

    monkeypatch.setattr(asi, "resolve_fb_drive_step", fake_resolve)
    drive = asi._resolve_drive_with_cascade(
        resolve_kwargs={"bh_start": {"x": 55, "y": 25}},
        shot_spot={"x": 88, "y": 25},
        max_attempts=2,
    )
    assert calls["n"] == 2
    assert drive["outcome"] == "POS_O"
    # Only the first stopper was beaten-and-excluded; the capped attempt finishes.
    assert drive["cascade_beaten_stopper_ids"] == ["away-1"]


def _pa_player(pid, x, y):
    return SimpleNamespace(
        player_id=pid, coords={"x": float(x), "y": float(y)},
        attributes={"AG": 50, "IQ": 50, "OD": 50, "CH": 50, "PS": 50},
    )


def test_find_open_pass_ahead_returns_ahead_teammate_when_lane_clear():
    from BackEnd.engine import after_steal_drive_integration as asi

    off = {
        "PG": _pa_player("home-PG", 55, 25),  # BH
        "SG": _pa_player("home-SG", 78, 25),  # ahead, in front
        "SF": _pa_player("home-SF", 45, 20),  # behind
        "PF": _pa_player("home-PF", 40, 30),
        "C": _pa_player("home-C", 38, 25),
    }
    # Defenders nowhere near the PG→SG lane (y≈25).
    dfn = {pos: _pa_player(f"away-{pos}", 30, 46) for pos in off}
    receiver, coord = asi._find_open_pass_ahead(
        off["PG"], {"x": 55, "y": 25}, off, dfn, is_away_offense=False
    )
    assert receiver is off["SG"]
    assert coord == {"x": 78.0, "y": 25.0}


def test_find_open_pass_ahead_blocked_by_lane_defender():
    from BackEnd.engine import after_steal_drive_integration as asi

    off = {
        "PG": _pa_player("home-PG", 55, 25),
        "SG": _pa_player("home-SG", 78, 25),
        "SF": _pa_player("home-SF", 45, 20),
        "PF": _pa_player("home-PF", 40, 30),
        "C": _pa_player("home-C", 38, 25),
    }
    dfn = {pos: _pa_player(f"away-{pos}", 30, 46) for pos in off}
    dfn["SF"] = _pa_player("away-SF", 66, 25)  # sitting in the PG→SG lane
    receiver, coord = asi._find_open_pass_ahead(
        off["PG"], {"x": 55, "y": 25}, off, dfn, is_away_offense=False
    )
    assert receiver is None
    assert coord is None


def test_pass_ahead_makes_receiver_the_shooter_and_credits_assist(monkeypatch):
    from BackEnd.engine import after_steal_drive_integration as asi

    monkeypatch.setattr(
        asi,
        "resolve_fb_drive_step",
        lambda **kw: {
            "outcome": "NO_MEET",
            "t_drive_game_seconds": 1.0,
            "contested": False,
            "shot_defender_id": None,
            "shot_spot": {"x": 88, "y": 25},
            "bh_start": dict(kw.get("bh_start") or {"x": 55, "y": 25}),
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )

    calls = {"n": 0}

    def fake_find(bh, bh_start, off_lineup, def_lineup, is_away):
        calls["n"] += 1
        if calls["n"] == 1:
            return off_lineup["SG"], {"x": 78.0, "y": 25.0}
        return None, None

    monkeypatch.setattr(asi, "_find_open_pass_ahead", fake_find)
    monkeypatch.setattr(asi.random, "random", lambda: 0.0)  # always take the pass
    monkeypatch.setattr(
        asi,
        "_resolve_shot_attempt",
        lambda **kw: {
            "made": True,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 200,
            "shot_score_pre_defense": 180,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": kw.get("shooter") and _safe_id_str(kw["shooter"]),
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    sg_id = game.offense_team.lineup["SG"].player_id
    pg_id = game.offense_team.lineup["PG"].player_id

    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MAKE"
    assert result["shooter_id"] == sg_id
    chain = result["after_steal_pass_ahead_chain"]
    assert len(chain) == 1
    assert chain[0]["passer_id"] == pg_id
    assert chain[0]["receiver_id"] == sg_id
    assert result["assist_player_id"] == pg_id


def _safe_id_str(obj):
    return getattr(obj, "player_id", None)


def test_meet_defensive_foul_non_bonus_routes_to_side_inbound(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "D_FOUL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "d8_credited_player_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "FOUL"
    assert result["next_play_type"] == "SIDE_INBOUND"
    assert game.game_state["free_throws_remaining"] == 0
    assert result["meet_coords"] == meet


def test_meet_defensive_foul_emits_meet_drive_step(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "D_FOUL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "d8_credited_player_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)
    end_coords = {
        f"home-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["home-PG"] = dict(meet)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"away-{pos}"] = {"x": 50.0, "y": 25.0}
    result["after_steal_end_coords"] = end_coords
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]

    steps = build_after_steal_fast_break_animation_steps(result, game)
    assert steps is not None
    assert len(steps) == 1
    assert steps[0]["end"]["next"] == {"kind": "end_of_turn"}


def test_miss_with_oreb_stamps_ball_bounce_coords(monkeypatch):
    """A drive-resolution MISS that yields an OREB must stamp ball_bounce_x/y so
    the follow-up OREB putback turn's rebound-capture step renders (regression:
    the drive-resolution rewrite dropped ball_bounce, only stamping ballSpot,
    which the OREB emitter doesn't read → OREB fell back to legacy, un-animated
    + un-announced)."""
    shot_spot = {"x": 88, "y": 25}
    bounce = {"x": 86.0, "y": 27.0}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": 70,
            "meet_y": 25,
            "shot_spot": shot_spot,
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": False,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 40,
            "shot_score_pre_defense": 60,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "home-PG",
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_rebound_on_miss",
        lambda **kwargs: (
            False,
            "OREB",
            dict(bounce),
            {"offense_rebounders": ["home-C"], "defense_rebounders": ["away-C"]},
            "home-C",
        ),
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MISS"
    assert result["next_play_type"] == "OREB"
    assert result["ballSpot"] == bounce
    assert result["ball_bounce_x"] == bounce["x"]
    assert result["ball_bounce_y"] == bounce["y"]


def test_fb_start_announcement_is_secondary_and_non_blocking():
    """The ``Fast Break!`` drive-start callout (shared by after-steal AND CR via
    ``_build_drive_step``) must be a secondary, non-blocking ribbon — otherwise
    the FE routes it to the center overlay and freezes the court ~1s."""
    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _fb_secondary_announcement,
    )

    ann = _fb_secondary_announcement("home")
    assert ann["text"] == "Fast Break!"
    assert ann["style"] == "secondary"
    assert ann["non_blocking"] is True


def test_suppress_fast_break_stinger_flags_only_fast_break_callouts():
    """Steal FBs keep the ``Fast Break!`` ribbon but must not play the court
    stinger — every FB callout gets ``meta.suppressCourtSfx`` while other
    announcements are left untouched."""
    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _suppress_fast_break_stinger,
    )

    steps = [
        {"start": {"announcement": {"text": "Fast Break!", "style": "secondary"}}},
        {"start": {"announcement": {"text": "Great Stop!", "style": "secondary"}}},
        {"start": {}},
    ]
    _suppress_fast_break_stinger(steps)
    assert steps[0]["start"]["announcement"]["meta"]["suppressCourtSfx"] is True
    assert "meta" not in steps[1]["start"]["announcement"]
    # No crash on steps without an announcement.
    assert "announcement" not in steps[2]["start"]


def test_steal_fb_drive_callout_suppresses_court_stinger():
    """End-to-end: a built steal-FB turn's ``Fast Break!`` schema callout carries
    ``meta.suppressCourtSfx`` so the FE skips ``fast-break-braddock.mp3``."""
    shot_spot = {"x": 88, "y": 25}
    meet = {"x": 70, "y": 25}
    end_coords = {f"home-{p}": {"x": 60.0, "y": 25.0} for p in ("PG", "SG", "SF", "PF", "C")}
    end_coords.update({f"away-{p}": {"x": 62.0, "y": 25.0} for p in ("PG", "SG", "SF", "PF", "C")})
    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [{"x": 55, "y": 25}, meet, {"x": 70, "y": 27}, shot_spot],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    fb_callouts = [
        s for s in steps
        if (s.get("start") or {}).get("announcement", {}).get("text") == "Fast Break!"
    ]
    assert fb_callouts, "expected a Fast Break! callout on the steal FB drive"
    for step in fb_callouts:
        assert step["start"]["announcement"]["meta"]["suppressCourtSfx"] is True
